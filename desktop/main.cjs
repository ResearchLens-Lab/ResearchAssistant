const { app, BrowserWindow, dialog, ipcMain, shell, safeStorage, clipboard, screen, Menu } = require("electron");
const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { fileURLToPath } = require("node:url");

const LOCAL_APP_DATA = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
const isPackaged = app.isPackaged;
const defaultRuntimeHome = isPackaged
  ? path.join(LOCAL_APP_DATA, "ResearchLens")
  : path.join(LOCAL_APP_DATA, "ResearchLens-Dev");
const RUNTIME_HOME = process.env.RESEARCHLENS_RUNTIME_HOME || defaultRuntimeHome;
app.setPath("userData", RUNTIME_HOME);
const isDevMode = !isPackaged || RUNTIME_HOME.toLowerCase().includes("researchlens-dev");

const settingsFile = path.join(RUNTIME_HOME, "desktop-settings.json");
const jwtKeyFile = path.join(RUNTIME_HOME, "secrets", "jwt-signing.key");
const profileFile = path.join(RUNTIME_HOME, "profile.json");
function readJsonSafe(file, fallback) { try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return fallback; } }
function writeJsonSafe(file, data) { try { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, JSON.stringify(data, null, 2), { mode: 0o600 }); } catch (e) { appendPrivateLog(`profile write failed: ${e.message}`); } }
const selectedLibraries = new Set();
let mainWindow = null;
let appSettings = null;
let backendProcess = null;
let frontendProcess = null;
let ollamaProcess = null;
let localIntelligenceActive = false;
let localModelInstalled = false;
let localIntelligenceUrl = "http://127.0.0.1:11434";
let requestKey = "";
let apiBaseUrl = "";
let uiOrigin = "";
let shuttingDown = false;
let currentJobs = 0;

const runtimeRoot = isPackaged
  ? path.join(process.resourcesPath, "app-runtime")
  : path.join(__dirname, "build", "app-runtime");
const sourceRoot = path.join(runtimeRoot, "source");
const frontendRoot = path.join(runtimeRoot, "frontend");
const pythonRoot = path.join(runtimeRoot, "python");
const onboardingFile = path.join(__dirname, "onboarding", "index.html");
const startupFile = path.join(__dirname, "startup", "index.html");

const userDocuments = path.join(os.homedir(), "Documents");
const isOneDrive = Boolean(
  (process.env.OneDrive && userDocuments.toLowerCase().startsWith(process.env.OneDrive.toLowerCase())) ||
  userDocuments.toLowerCase().includes("onedrive") ||
  fs.existsSync(path.join(os.homedir(), "OneDrive", "Documents"))
);
const defaultSuggestedLibrary = isOneDrive
  ? path.join(LOCAL_APP_DATA, "ResearchLens", "Library")
  : path.join(os.homedir(), "Documents", "ResearchLens Library");
selectedLibraries.add(defaultSuggestedLibrary.toLowerCase());

const trackedProcesses = new Map();

function sanitizeDiagnostics(text) {
  if (!text) return "";
  let clean = String(text);
  if (appSettings?.jwtSigningKey) {
    clean = clean.split(appSettings.jwtSigningKey).join("[REDACTED_SECRET]");
  }
  if (requestKey) {
    clean = clean.split(requestKey).join("[REDACTED_KEY]");
  }
  clean = clean.replace(/X-ResearchLens-Desktop-Key:\s*[\w-]+/gi, "X-ResearchLens-Desktop-Key: [REDACTED]");
  clean = clean.replace(/Authorization:\s*Bearer\s+[\w.-]+/gi, "Authorization: Bearer [REDACTED]");
  return clean;
}

class ProcessTracker {
  constructor(role, executable, args, cwd) {
    this.role = role;
    this.executable = executable;
    this.args = args;
    this.cwd = cwd;
    this.pid = null;
    this.startTime = Date.now();
    this.endTime = null;
    this.exitCode = null;
    this.exitSignal = null;
    this.stdoutRing = [];
    this.stderrRing = [];
    this.maxRingLines = 60;
  }

  appendOutput(ring, chunk) {
    const lines = chunk.toString("utf8").split(/\r?\n/);
    for (const line of lines) {
      if (!line && ring.length > 0 && !ring[ring.length - 1]) continue;
      ring.push(line);
      if (ring.length > this.maxRingLines) {
        ring.shift();
      }
    }
  }

  getLastStderr(linesCount = 20) {
    const lines = this.stderrRing.filter((l) => l.trim().length > 0);
    return lines.slice(-linesCount).join("\n");
  }

  getLastStdout(linesCount = 10) {
    const lines = this.stdoutRing.filter((l) => l.trim().length > 0);
    return lines.slice(-linesCount).join("\n");
  }

  getTracebackOrError() {
    const stderrText = this.getLastStderr(30);
    if (stderrText) return sanitizeDiagnostics(stderrText);
    const stdoutText = this.getLastStdout(15);
    if (stdoutText) return sanitizeDiagnostics(stdoutText);
    return `Process terminated with exit code ${this.exitCode ?? "none"}`;
  }
}

function childEnvironment(extra) {
  const systemRoot = process.env.SystemRoot || "C:\\Windows";
  const safeEnv = {
    SystemRoot: systemRoot,
    WINDIR: systemRoot,
    SystemDrive: process.env.SystemDrive || "C:",
    PATHEXT: process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD",
    COMSPEC: process.env.COMSPEC || path.join(systemRoot, "System32", "cmd.exe"),
    PROCESSOR_ARCHITECTURE: process.env.PROCESSOR_ARCHITECTURE || "AMD64",
    NUMBER_OF_PROCESSORS: process.env.NUMBER_OF_PROCESSORS || "4",
    TEMP: process.env.TEMP || path.join(LOCAL_APP_DATA, "Temp"),
    TMP: process.env.TMP || path.join(LOCAL_APP_DATA, "Temp"),
    USERPROFILE: os.homedir(),
    LOCALAPPDATA: LOCAL_APP_DATA,
    APPDATA: process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
    PATH: [
      pythonRoot,
      path.join(pythonRoot, "DLLs"),
      path.join(pythonRoot, "Scripts"),
      path.join(systemRoot, "System32"),
      systemRoot,
    ].join(path.delimiter),
    PYTHONHOME: pythonRoot,
    PYTHONPATH: sourceRoot,
    PYTHONNOUSERSITE: "1",
    PYTHONUTF8: "1",
    PYTHONUNBUFFERED: "1",
    PYTHONDONTWRITEBYTECODE: "1",
    ...extra,
  };
  return safeEnv;
}

function appendPrivateLog(message) {
  const logDir = path.join(RUNTIME_HOME, "logs");
  try {
    fs.mkdirSync(logDir, { recursive: true });
    const target = path.join(logDir, "desktop.log");
    if (fs.existsSync(target) && fs.statSync(target).size > 1024 * 1024) {
      const rotated = path.join(logDir, "desktop.previous.log");
      try { fs.rmSync(rotated, { force: true }); } catch { }
      fs.renameSync(target, rotated);
    }
    fs.appendFileSync(target, `${new Date().toISOString()} ${message.replace(/[\r\n\t]/g, " ").slice(0, 500)}\n`, { mode: 0o600 });
  } catch { }
}

function listenForPort(preferred = 0) {
  const tryPort = (port) => new Promise((resolve, reject) => {
    const server = http.createServer();
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      const boundPort = server.address().port;
      server.close((error) => (error ? reject(error) : resolve(boundPort)));
    });
  });
  if (preferred && Number.isInteger(preferred) && preferred > 0 && preferred <= 65535) {
    return tryPort(preferred).catch(() => tryPort(0));
  }
  return tryPort(0);
}

function waitForHttp(url, headers = {}, timeoutMs = 45000, childProc = null) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    let finished = false;
    let timer = null;

    const cleanup = () => {
      finished = true;
      if (timer) clearTimeout(timer);
    };

    if (childProc) {
      const onChildExit = (code, signal) => {
        if (finished) return;
        cleanup();
        const tracker = childProc._tracker;
        const errDetails = tracker ? tracker.getTracebackOrError() : `Service exited with code ${code ?? "none"}`;
        const role = childProc._role || "Child service";
        reject(new Error(`${role} terminated unexpectedly (exit code ${code ?? "none"}).\n${errDetails}`));
      };
      childProc.once("exit", onChildExit);
    }

    const attempt = () => {
      if (finished) return;
      const request = http.get(url, { headers, timeout: 1500 }, (response) => {
        response.resume();
        if (response.statusCode >= 200 && response.statusCode < 300) {
          cleanup();
          return resolve();
        }
        retry(new Error(`Service returned HTTP ${response.statusCode}`));
      });
      request.on("error", retry);
      request.on("timeout", () => {
        request.destroy();
        retry(new Error("Service health check timed out"));
      });
      function retry(error) {
        if (finished) return;
        if (Date.now() - started >= timeoutMs) {
          cleanup();
          return reject(error);
        }
        timer = setTimeout(attempt, 200);
      }
    };
    attempt();
  });
}

function spawnTracked(role, executable, args, options = {}) {
  const safeEnv = childEnvironment(options.env || {});
  const proc = spawn(executable, args, {
    cwd: options.cwd || sourceRoot,
    env: safeEnv,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    detached: false,
  });

  const tracker = new ProcessTracker(role, executable, args, options.cwd || sourceRoot);
  tracker.pid = proc.pid;
  proc._tracker = tracker;
  proc._role = role;
  trackedProcesses.set(proc.pid, tracker);

  const sanitizedCmd = sanitizeDiagnostics([path.basename(executable), ...args].join(" "));
  appendPrivateLog(`[PROCESS-START] Role: ${role} | PID: ${proc.pid} | Command: ${sanitizedCmd} | Cwd: ${options.cwd || sourceRoot}`);

  proc.stdout?.on("data", (chunk) => {
    tracker.appendOutput(tracker.stdoutRing, chunk);
  });

  proc.stderr?.on("data", (chunk) => {
    tracker.appendOutput(tracker.stderrRing, chunk);
  });

  proc.once("error", (error) => {
    appendPrivateLog(`[PROCESS-ERROR] Role: ${role} | PID: ${proc.pid} | Error: ${error.code || error.message}`);
  });

  proc.once("exit", (code, signal) => {
    tracker.endTime = Date.now();
    tracker.exitCode = code;
    tracker.exitSignal = signal;
    const runtimeMs = tracker.endTime - tracker.startTime;

    if (code !== 0 && !shuttingDown) {
      const errDetails = tracker.getTracebackOrError();
      appendPrivateLog(`[PROCESS-EXIT] Role: ${role} | PID: ${proc.pid} | ExitCode: ${code ?? "none"} | Signal: ${signal || "none"} | Duration: ${runtimeMs}ms`);
      appendPrivateLog(`[PROCESS-CRASH-DIAGNOSTICS] Role: ${role} | Captured output:\n${errDetails}`);
    } else {
      appendPrivateLog(`[PROCESS-EXIT] Role: ${role} | PID: ${proc.pid} | ExitCode: ${code ?? 0} | Signal: ${signal || "none"} | Duration: ${runtimeMs}ms`);
    }
  });

  return proc;
}

function spawnOwned(executable, args, options = {}) {
  return spawnTracked("generic-service", executable, args, options);
}

function resolveOllamaExecutable() {
  const candidates = [
    path.join(runtimeRoot, "ollama", "ollama.exe"),
    path.join(process.resourcesPath || "", "app-runtime", "ollama", "ollama.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Programs", "Ollama", "ollama.exe"),
  ];
  for (const c of candidates) {
    if (c && fs.existsSync(c)) return c;
  }
  return null;
}

function checkOllamaAlive(url = "http://127.0.0.1:11434") {
  return new Promise((resolve) => {
    const req = http.get(`${url}/api/tags`, { timeout: 1500 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

function checkModelAvailable(url = "http://127.0.0.1:11434", targetModel = "qwen3.5:0.8b") {
  return new Promise((resolve) => {
    const req = http.get(`${url}/api/tags`, { timeout: 2500 }, (res) => {
      let body = "";
      res.on("data", (chunk) => body += chunk);
      res.on("end", () => {
        try {
          const data = JSON.parse(body);
          const models = data.models || [];
          const found = models.some((m) => {
            const name = (m.name || m.model || "").toLowerCase();
            return name === targetModel.toLowerCase() || name.startsWith(targetModel.toLowerCase());
          });
          resolve(found);
        } catch {
          resolve(false);
        }
      });
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function ensureLocalIntelligence() {
  localIntelligenceActive = false;
  localModelInstalled = false;
  appendPrivateLog("Local Intelligence engine disabled; running in pure deterministic extractive mode.");
}

function appApiEnvironment() {
  const library = appSettings.libraryPath;
  const documents = path.join(library, "documents");
  const indexes = path.join(library, "indexes");
  const databasePath = path.join(library, "library.sqlite3").replace(/\\/g, "/");
  const origin = uiOrigin;
  const useLocalIntelligence = (process.env.LLM_ENABLED === "false")
    ? false
    : (localIntelligenceActive && localModelInstalled);
  return {
    APP_ENV: "production",
    APP_NAME: "ResearchLens",
    DATABASE_URL: `sqlite+aiosqlite:///${databasePath}`,
    JWT_SECRET_KEY: appSettings.jwtSigningKey,
    CORS_ORIGINS: origin,
    DESKTOP_RUNTIME: "true",
    DESKTOP_REQUEST_KEY: requestKey,
    DESKTOP_UI_ORIGIN: origin,
    REFRESH_TOKEN_EXPIRE_DAYS: "30",
    UPLOAD_DIR: documents,
    RAG_ENGINE_MODE: "independent",
    RAG_ANSWER_MODE: "INDEPENDENT",
    RAG_MODE: "local",
    LLM_ENABLED: useLocalIntelligence ? "true" : "false",
    LLM_PROVIDER: useLocalIntelligence ? "local_intelligence" : "none",
    LLM_API_KEY: "",
    GEMINI_API_KEY: "",
    EMBEDDING_PROVIDER: "local",
    CHROMA_USE_HTTP: "false",
    CHROMA_PERSIST_DIR: indexes,
    CHROMA_COLLECTION_NAME: "researchlens_local",
    EMBEDDING_CACHE_PATH: path.join(library, "cache", "embeddings.sqlite3"),
    FASTEMBED_CACHE_DIR: path.join(library, "cache", "models"),
    OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || localIntelligenceUrl,
    OLLAMA_MODEL: process.env.OLLAMA_MODEL || "qwen3.5:0.8b",
    EXTERNAL_LOOKUPS_ENABLED: (readJsonSafe(profileFile, {}).allowExternalLookups === true) ? "true" : "false",
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONPYCACHEPREFIX: path.join(library, "cache", "pycache"),
    NODE_OPTIONS: "",
  };
}

async function runMigrations() {
  const python = path.join(pythonRoot, "python.exe");
  const env = { ...appApiEnvironment(), DESKTOP_RUNTIME: "false" };
  const databasePath = path.join(appSettings?.libraryPath || "", "library.sqlite3");
  const migrationsDir = path.join(sourceRoot, "backend", "migrations", "versions");

  // Check alembic_version in SQLite before spawning alembic subprocess; skip if already at head
  const isAtHead = await new Promise((resolve) => {
    if (!fs.existsSync(databasePath)) return resolve(false);
    const checkScript = `
import sqlite3, os, re, sys
try:
    db = sys.argv[1]
    mig_dir = sys.argv[2]
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
    row = cur.fetchone()
    if not row: sys.exit(1)
    cur_rev = row[0]
    re_rev = re.compile(r"^revision\\s*(?::\\s*str)?\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]", re.M)
    re_down = re.compile(r"^down_revision\\s*(?::\\s*[^=]+)?\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]", re.M)
    all_revs, down_revs = set(), set()
    for f in os.listdir(mig_dir):
        if f.endswith('.py') and not f.startswith('__'):
            c = open(os.path.join(mig_dir, f), encoding='utf-8', errors='ignore').read()
            m1, m2 = re_rev.search(c), re_down.search(c)
            if m1: all_revs.add(m1.group(1))
            if m2 and m2.group(1): down_revs.add(m2.group(1))
    heads = all_revs - down_revs
    if cur_rev in heads:
        sys.exit(0)
    sys.exit(1)
except Exception:
    sys.exit(1)
`;
    const proc = spawn(python, ["-c", checkScript, databasePath, migrationsDir], { stdio: "ignore" });
    proc.once("error", () => resolve(false));
    proc.once("exit", (code) => resolve(code === 0));
  });

  if (isAtHead) {
    appendPrivateLog("Database schema is already at Alembic head revision; skipping migration subprocess.");
    return;
  }

  return new Promise((resolve, reject) => {
    const proc = spawnTracked("db-migration", python, ["-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], {
      cwd: sourceRoot,
      env,
    });
    proc.once("error", reject);
    proc.once("exit", (code) => {
      if (code === 0) return resolve();
      const tracker = proc._tracker;
      const errDetails = tracker ? tracker.getTracebackOrError() : `Migration exited with code ${code}`;
      appendPrivateLog(`Database migration failed (exit ${code}): ${errDetails}`);
      reject(new Error(`Database migration failed (exit code ${code}).\n${errDetails.slice(0, 500)}`));
    });
  });
}

function emitStartupProgress(payload) {
  try {
    if (mainWindow && !mainWindow.isDestroyed() && mainWindow.webContents) {
      mainWindow.webContents.send("startup:progress", payload);
    }
  } catch { }
}

async function startLocalServices() {
  const isWindows = process.platform === "win32";
  const overallStart = Date.now();
  requestKey = crypto.randomBytes(32).toString("base64url");
  let activeStageId = "runtime";

  // Startup stages copy:
  // 1: Getting ready / Checking your library folder
  // 2: Opening your library / Making sure your projects are up to date
  // 3: Starting search / Preparing your search tools
  // 4: Opening your workspace / Almost ready
  const stagesState = [
    { id: "runtime", title: "Getting ready", status: "pending", label: "Checking your library folder" },
    { id: "database", title: "Opening your library", status: "pending", label: "Making sure your projects are up to date" },
    { id: "engine", title: "Starting search", status: "pending", label: "Preparing your search tools" },
    { id: "workbench", title: "Opening your workspace", status: "pending", label: "Almost ready" },
  ];

  const emitStage = (stageId, status, label, percent, detail = "") => {
    activeStageId = stageId;
    const stage = stagesState.find((s) => s.id === stageId);
    if (stage) {
      stage.status = status;
      if (label) stage.label = label;
    }
    const idx = stagesState.findIndex((s) => s.id === stageId) + 1;
    emitStartupProgress({
      step: idx,
      stageId,
      stageIndex: idx,
      stageTitle: stage ? stage.title : "",
      stageDetail: detail || label,
      percent,
      stages: stagesState.map((s) => ({ ...s })),
    });
  };

  try {
    // STAGE 1: Runtime
    const t0 = Date.now();
    emitStage("runtime", "in-progress", "Verifying application runtime…", 12, "Resolving local runtime binaries and ports…");

    const pythonExe = path.join(pythonRoot, "python.exe");
    if (!fs.existsSync(pythonExe)) {
      throw new Error(`Bundled Python executable not found at: ${pythonExe}`);
    }
    const nodeBinary = [
      path.join(runtimeRoot, "node.exe"),
      path.join(process.resourcesPath, "node.exe"),
      process.execPath,
    ].find((candidate) => fs.existsSync(candidate)) || "node";

    const saved = readJsonSafe(profileFile, {});
    const apiPort = await listenForPort(saved.apiPort);
    let uiPort = await listenForPort(saved.uiPort);
    if (uiPort === apiPort) uiPort = await listenForPort(0);
    writeJsonSafe(profileFile, { ...readJsonSafe(profileFile, {}), apiPort, uiPort });
    apiBaseUrl = `http://127.0.0.1:${apiPort}/api/v1`;
    uiOrigin = `http://127.0.0.1:${uiPort}`;
    const runtimeMs = Date.now() - t0;
    emitStage("runtime", "completed", `Verified (${runtimeMs}ms)`, 25, "Application runtime and local ports ready.");

    // STAGE 2: Database / Library Check
    const t1 = Date.now();
    emitStage("database", "in-progress", "Checking library…", 35, "Checking SQLite database and migrations…");
    await runMigrations();
    const dbMs = Date.now() - t1;
    emitStage("database", "completed", `Checking library (${dbMs}ms)`, 50, "SQLite database and migrations verified.");

    // STAGE 3: Research Engine & Local Intelligence
    const t2 = Date.now();
    emitStage("engine", "in-progress", "Starting local services…", 60, "Verifying local intelligence engine…");
    await ensureLocalIntelligence();
    emitStage("engine", "in-progress", "Starting local services…", 70, "Spawning FastAPI sidecar…");
    const apiEnv = appApiEnvironment();
    backendProcess = spawnTracked("fastapi-backend", pythonExe, [
      "-m", "uvicorn", "backend.app.main:app",
      "--host", "127.0.0.1",
      "--port", String(apiPort),
      "--no-access-log",
    ], { cwd: sourceRoot, env: apiEnv });

    await waitForHttp(`http://127.0.0.1:${apiPort}/health`, {
      Origin: uiOrigin,
      Host: `127.0.0.1:${apiPort}`,
      "X-ResearchLens-Desktop-Key": requestKey,
    }, 90000, backendProcess);
    const engineMs = Date.now() - t2;
    emitStage("engine", "completed", `Starting local services (${engineMs}ms)`, 80, "Research intelligence engine healthy and ready.");

    // STAGE 4: Workbench
    const t3 = Date.now();
    emitStage("workbench", "in-progress", "Starting workbench application server…", 88, "Spawning Next.js application server…");
    frontendProcess = spawnTracked("nextjs-workbench", nodeBinary, [path.join(frontendRoot, "server.js")], {
      cwd: frontendRoot,
      env: { NODE_ENV: "production", HOSTNAME: "127.0.0.1", PORT: String(uiPort), NEXT_TELEMETRY_DISABLED: "1" },
    });

    await waitForHttp(uiOrigin, {}, 60000, frontendProcess);
    const workbenchMs = Date.now() - t3;
    emitStage("workbench", "completed", "Ready", 100, "Ready");

    const totalDuration = Date.now() - overallStart;
    appendPrivateLog(`Local services started successfully in ${totalDuration}ms (runtime=${runtimeMs}ms, db=${dbMs}ms, engine=${engineMs}ms, workbench=${workbenchMs}ms, apiPort=${apiPort}, uiPort=${uiPort}).`);
  } catch (error) {
    const failedStage = stagesState.find((s) => s.id === activeStageId);
    if (failedStage) {
      failedStage.status = "failed";
      failedStage.label = "Failed";
    }
    const errObj = {
      stageId: activeStageId,
      stageTitle: failedStage ? failedStage.title : "Initialization",
      summary: `${failedStage ? failedStage.title : "Startup"} could not complete`,
      message: error.message ? error.message.split("\n")[0] : "Service startup failed.",
      diagnostics: sanitizeDiagnostics(error.message || String(error)),
      logPath: path.join(RUNTIME_HOME, "logs", "desktop.log"),
      canChangeLibrary: activeStageId === "database",
      stages: stagesState.map((s) => ({ ...s })),
    };
    appendPrivateLog(`Startup failed at stage [${activeStageId}]: ${error.message}`);
    throw errObj;
  }
}

function isTrustedSender(event) {
  const senderUrl = event.senderFrame?.url || event.sender.getURL();
  if (senderUrl.startsWith("file://")) {
    try {
      const resolved = path.resolve(fileURLToPath(senderUrl)).toLowerCase();
      return (
        resolved === path.resolve(onboardingFile).toLowerCase() ||
        resolved === path.resolve(startupFile).toLowerCase()
      );
    } catch {
      return false;
    }
  }
  try {
    const parsed = new URL(senderUrl);
    return parsed.origin === uiOrigin && parsed.hostname === "127.0.0.1";
  } catch {
    return false;
  }
}

function registerIpc() {
  const guarded = (name, handler) => ipcMain.handle(name, async (event, ...args) => {
    if (!isTrustedSender(event)) throw new Error("Untrusted desktop UI sender.");
    return handler(...args);
  });

  guarded("onboarding:state", async () => ({
    configured: Boolean(appSettings?.libraryPath),
    suggestedLibrary: defaultSuggestedLibrary,
    isOneDriveSynced: isOneDrive,
  }));

  guarded("onboarding:choose-library", async () => {
    const result = await dialog.showOpenDialog(mainWindow, { properties: ["openDirectory", "createDirectory"] });
    if (result.canceled || !result.filePaths[0]) return null;
    const selected = path.resolve(result.filePaths[0]);
    selectedLibraries.add(selected.toLowerCase());
    return { path: selected, selectionId: crypto.randomUUID() };
  });

  guarded("onboarding:initialize", async (selection, options = {}) => {
    const chosenPath = path.resolve(String(selection?.path || ""));
    const isDefault = selection?.selectionId === "default-suggested" || chosenPath.toLowerCase() === defaultSuggestedLibrary.toLowerCase();
    if (!isDefault && !selectedLibraries.has(chosenPath.toLowerCase())) {
      throw new Error("Choose a library folder with the folder picker first.");
    }
    if (!["low", "standard"].includes(options.profile || "low")) throw new Error("Invalid library setup options.");
    const root = chosenPath;
    await fsp.mkdir(root, { recursive: true });

    const dbFile = path.join(root, "library.sqlite3");
    const isExistingLibrary = fs.existsSync(dbFile);

    if (!isExistingLibrary) {
      const entries = await fsp.readdir(root);
      if (entries.length > 0) {
        throw new Error("The selected folder contains existing files. Please select an empty folder for a new library or choose your existing ResearchLens Library.");
      }
    }

    const requiredDirs = ["documents", "attachments", "indexes", "annotations", "notebooks", "feedback", "exports", "backups", "cache"];
    for (const directory of requiredDirs) await fsp.mkdir(path.join(root, directory), { recursive: true });

    appSettings = {
      version: 1,
      libraryPath: root,
      storageMode: options.storageMode || "copy",
      profile: options.profile || "low",
      createdAt: new Date().toISOString(),
    };
    await fsp.mkdir(path.dirname(settingsFile), { recursive: true });
    await fsp.mkdir(path.dirname(jwtKeyFile), { recursive: true });
    if (!fs.existsSync(jwtKeyFile)) await fsp.writeFile(jwtKeyFile, crypto.randomBytes(48).toString("base64url"), { flag: "wx", mode: 0o600 });
    appSettings.jwtSigningKey = await fsp.readFile(jwtKeyFile, "utf8");
    await fsp.writeFile(settingsFile, JSON.stringify({ ...appSettings, jwtSigningKey: undefined }, null, 2), { mode: 0o600 });

    try {
      const whoami = await new Promise((resolve, reject) => {
        const proc = spawn(path.join(process.env.SystemRoot || "C:\\Windows", "System32", "whoami.exe"), [], { windowsHide: true, stdio: ["ignore", "pipe", "ignore"] });
        let output = "";
        proc.stdout.on("data", (chunk) => output += chunk.toString("utf8"));
        proc.once("error", reject);
        proc.once("exit", (code) => code === 0 ? resolve(output.trim()) : reject(new Error("Current Windows user could not be resolved.")));
      });
      await new Promise((resolve, reject) => {
        const acl = spawn(path.join(process.env.SystemRoot || "C:\\Windows", "System32", "icacls.exe"), [root, "/inheritance:r", "/grant:r", `${whoami}:(OI)(CI)F`, "SYSTEM:(OI)(CI)F"], { windowsHide: true, stdio: "ignore" });
        acl.once("error", reject);
        acl.once("exit", (code) => code === 0 ? resolve() : reject(new Error("Private library permissions could not be applied.")));
      });
    } catch (error) {
      appendPrivateLog(`Library permissions notice (non-fatal): ${error.message}`);
    }

    appendPrivateLog("Local library verified and configured.");
    try {
      await startLocalServices();
      await mainWindow.loadURL(`${uiOrigin}/papers`);
    } catch (error) {
      appendPrivateLog(`First-run service initialization failed: ${error.message}`);
      throw new Error(`The local library was prepared, but ResearchLens could not start. Your data was preserved. ${error.message}`);
    }
    return { ok: true };
  });

  guarded("desktop:runtime-config", async () => ({ apiBaseUrl, requestKey }));
  guarded("desktop:save-session", async (sessionData) => {
    if (!sessionData || typeof sessionData !== "object") return { ok: false };
    if (!safeStorage || !safeStorage.isEncryptionAvailable()) {
      appendPrivateLog("Session save rejected: DPAPI safeStorage encryption unavailable.");
      return { ok: false };
    }
    try {
      const raw = JSON.stringify(sessionData);
      const payload = safeStorage.encryptString(raw).toString("base64");
      const sessionFile = path.join(RUNTIME_HOME, "session.dat");
      const tempFile = path.join(RUNTIME_HOME, "session.dat.tmp");
      await fsp.writeFile(tempFile, JSON.stringify({ encrypted: true, payload }), { encoding: "utf8", mode: 0o600 });
      await fsp.rename(tempFile, sessionFile);
      return { ok: true };
    } catch (err) {
      appendPrivateLog(`Session encryption save notice: ${err.message}`);
      return { ok: false };
    }
  });

  guarded("desktop:get-session", async () => {
    const sessionFile = path.join(RUNTIME_HOME, "session.dat");
    try {
      const content = await fsp.readFile(sessionFile, "utf8");
      const data = JSON.parse(content);
      if (!data.encrypted) {
        return null;
      }
      if (safeStorage && safeStorage.isEncryptionAvailable()) {
        const buf = Buffer.from(data.payload, "base64");
        const decrypted = safeStorage.decryptString(buf);
        return JSON.parse(decrypted);
      }
      return null;
    } catch {
      return null;
    }
  });

  guarded("desktop:get-profile", async () => {
    const p = readJsonSafe(profileFile, {});
    return { lastUsername: p.lastUsername || "", rememberMe: p.rememberMe !== false };
  });

  guarded("desktop:save-profile", async (data) => {
    if (!data || typeof data !== "object") return { ok: false };
    const current = readJsonSafe(profileFile, {});
    const update = {};
    if (typeof data.lastUsername === "string") {
      update.lastUsername = data.lastUsername.slice(0, 64);
    }
    if (typeof data.rememberMe === "boolean") {
      update.rememberMe = data.rememberMe;
    }
    writeJsonSafe(profileFile, { ...current, ...update });
    return { ok: true };
  });

  guarded("desktop:clear-session", async () => {
    const sessionFile = path.join(RUNTIME_HOME, "session.dat");
    try { await fsp.unlink(sessionFile); } catch { }
    return { ok: true };
  });

  guarded("desktop:get-external-lookups", async () => {
    const p = readJsonSafe(profileFile, {});
    return Boolean(p.allowExternalLookups);
  });

  guarded("desktop:set-external-lookups", async (enabled) => {
    const current = readJsonSafe(profileFile, {});
    current.allowExternalLookups = Boolean(enabled);
    writeJsonSafe(profileFile, current);
    return { ok: true };
  });

  guarded("desktop:restart-app", async () => {
    try {
      app.releaseSingleInstanceLock();
    } catch { }
    app.relaunch();
    app.quit();
    return { ok: true };
  });

  let failedPinAttempts = 0;
  let lockoutUntil = 0;
  let currentLockoutSeconds = 30;

  function hashPin(pin, salt) {
    return crypto.scryptSync(String(pin), salt, 64).toString("hex");
  }

  guarded("desktop:pin-status", async () => {
    const p = readJsonSafe(profileFile, {});
    const now = Date.now();
    const isLocked = now < lockoutUntil;
    return {
      enabled: Boolean(p.pin && p.pin.enabled && p.pin.hash),
      locked: isLocked,
      remainingSeconds: isLocked ? Math.ceil((lockoutUntil - now) / 1000) : 0,
    };
  });

  guarded("desktop:set-pin", async (pin) => {
    const pinStr = String(pin || "").trim();
    if (!/^\d{4,6}$/.test(pinStr)) {
      return { ok: false, error: "PIN must be between 4 and 6 digits." };
    }
    const salt = crypto.randomBytes(16).toString("hex");
    const hash = hashPin(pinStr, salt);
    const p = readJsonSafe(profileFile, {});
    p.pin = { hash, salt, enabled: true };
    writeJsonSafe(profileFile, p);
    failedPinAttempts = 0;
    lockoutUntil = 0;
    currentLockoutSeconds = 30;
    return { ok: true };
  });

  guarded("desktop:verify-pin", async (pin) => {
    const p = readJsonSafe(profileFile, {});
    if (!p.pin || !p.pin.enabled) {
      return { ok: true, notConfigured: true };
    }
    const now = Date.now();
    if (now < lockoutUntil) {
      return {
        ok: false,
        locked: true,
        remainingSeconds: Math.ceil((lockoutUntil - now) / 1000),
      };
    }
    const pinStr = String(pin || "").trim();
    const computed = hashPin(pinStr, p.pin.salt);
    if (computed === p.pin.hash) {
      failedPinAttempts = 0;
      lockoutUntil = 0;
      currentLockoutSeconds = 30;
      return { ok: true };
    }
    failedPinAttempts++;
    if (failedPinAttempts >= 5) {
      lockoutUntil = now + currentLockoutSeconds * 1000;
      const duration = currentLockoutSeconds;
      currentLockoutSeconds = Math.min(15 * 60, currentLockoutSeconds * 2);
      return {
        ok: false,
        locked: true,
        remainingSeconds: duration,
        error: `Too many failed attempts. Locked for ${duration}s.`,
      };
    }
    return {
      ok: false,
      locked: false,
      attemptsRemaining: 5 - failedPinAttempts,
      error: "Incorrect PIN.",
    };
  });

  guarded("desktop:remove-pin", async (currentPin) => {
    const p = readJsonSafe(profileFile, {});
    if (!p.pin || !p.pin.enabled) {
      return { ok: true };
    }
    const pinStr = String(currentPin || "").trim();
    const computed = hashPin(pinStr, p.pin.salt);
    if (computed !== p.pin.hash) {
      return { ok: false, error: "Incorrect PIN." };
    }
    delete p.pin;
    writeJsonSafe(profileFile, p);
    failedPinAttempts = 0;
    lockoutUntil = 0;
    currentLockoutSeconds = 30;
    return { ok: true };
  });

  guarded("startup:retry", async () => {
    await stopOwnedServicesAsync();
    backendProcess = null;
    frontendProcess = null;
    openApplication();
    return { ok: true };
  });

  guarded("startup:open-logs", async () => {
    const logDir = path.join(RUNTIME_HOME, "logs");
    try { await shell.openPath(logDir); } catch { }
    return { ok: true };
  });

  guarded("startup:copy-details", async (details) => {
    try {
      clipboard.writeText(String(details || ""));
      return { ok: true };
    } catch {
      return { ok: false };
    }
  });

  guarded("startup:select-library", async () => {
    await stopOwnedServicesAsync();
    backendProcess = null;
    frontendProcess = null;
    appSettings = null;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadFile(onboardingFile);
    }
    return { ok: true };
  });
  guarded("desktop:diagnostics", async () => ({
    appVersion: app.getVersion(),
    backendReady: Boolean(backendProcess && !backendProcess.killed),
    databaseReady: Boolean(appSettings?.libraryPath && fs.existsSync(path.join(appSettings.libraryPath, "library.sqlite3"))),
    libraryPath: appSettings?.libraryPath || "",
    diskFreeBytes: appSettings?.libraryPath ? await getFreeBytes(appSettings.libraryPath) : null,
    activeJobs: currentJobs,
    networkFeatures: (readJsonSafe(profileFile, {}).allowExternalLookups === true) ? "online-verification-enabled" : "disabled",
    localIntelligence: {
      available: localIntelligenceActive,
      modelInstalled: localModelInstalled,
      model: "qwen3.5:0.8b",
      engine: (localIntelligenceActive && localModelInstalled) ? "synthesized_local_llm" : "extractive_deterministic",
    },
  }));

  guarded("intelligence:status", async () => ({
    available: localIntelligenceActive,
    modelInstalled: localModelInstalled,
    modelName: "qwen3.5:0.8b",
    displayName: "Local Intelligence Engine",
    approximateDownloadSizeMB: 574,
    provider: "application_managed_ollama",
    mode: (localIntelligenceActive && localModelInstalled) ? "synthesized_local_llm" : "extractive_deterministic",
  }));

  guarded("intelligence:pull-model", async () => {
    if (!localIntelligenceActive) {
      throw new Error("Local Intelligence engine service is not active.");
    }
    return new Promise((resolve, reject) => {
      const postData = JSON.stringify({ name: "qwen3.5:0.8b", stream: true });
      const options = {
        hostname: "127.0.0.1",
        port: 11434,
        path: "/api/pull",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(postData),
        },
      };
      const req = http.request(options, (res) => {
        let buffer = "";
        res.on("data", (chunk) => {
          buffer += chunk.toString("utf8");
          const lines = buffer.split("\n");
          buffer = lines.pop();
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const statusObj = JSON.parse(line);
              if (mainWindow && !mainWindow.isDestroyed() && mainWindow.webContents) {
                mainWindow.webContents.send("intelligence:progress", statusObj);
              }
            } catch { }
          }
        });
        res.on("end", async () => {
          localModelInstalled = await checkModelAvailable(localIntelligenceUrl, "qwen3.5:0.8b");
          resolve({ success: localModelInstalled });
        });
      });
      req.on("error", reject);
      req.write(postData);
      req.end();
    });
  });

  guarded("desktop:create-backup", async (destinationFolder) => {
    if (!appSettings?.libraryPath) throw new Error("No active library found.");
    const library = appSettings.libraryPath;
    const backupDir = destinationFolder || path.join(library, "backups");
    await fsp.mkdir(backupDir, { recursive: true });
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const backupTarget = path.join(backupDir, `ResearchLens-Backup-${timestamp}.zip`);

    const python = path.join(pythonRoot, "python.exe");
    const script = `
import sqlite3, os, zipfile, hashlib, json

lib = r'''${library}'''
out = r'''${backupTarget}'''
db_path = os.path.join(lib, 'library.sqlite3')
doc_dir = os.path.join(lib, 'documents')

# 1. Snapshot SQLite DB using online backup API
snap_db = os.path.join(lib, 'cache', 'snapshot.sqlite3')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    bck = sqlite3.connect(snap_db)
    conn.backup(bck)
    bck.close()
    conn.close()

# 2. Bundle into ZIP with checksums and manifest
manifest = {'created_at': '${new Date().toISOString()}', 'files': {}}
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
    if os.path.exists(snap_db):
        with open(snap_db, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        zf.write(snap_db, 'library.sqlite3')
        manifest['files']['library.sqlite3'] = h
        try: os.remove(snap_db)
        except: pass
    if os.path.exists(doc_dir):
        for root, _, files in os.walk(doc_dir):
            for file in files:
                fp = os.path.join(root, file)
                rel = os.path.relpath(fp, lib)
                with open(fp, 'rb') as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                zf.write(fp, rel)
                manifest['files'][rel] = h
    zf.writestr('manifest.json', json.dumps(manifest, indent=2))
print('BACKUP_OK:' + out)
`;
    return new Promise((resolve, reject) => {
      const proc = spawn(python, ["-c", script], {
        cwd: sourceRoot,
        env: childEnvironment({ ...appApiEnvironment(), DESKTOP_RUNTIME: "false" }),
        windowsHide: true,
      });
      let out = "";
      proc.stdout?.on("data", (c) => out += c.toString());
      proc.once("exit", (code) => {
        if (code === 0 && out.includes("BACKUP_OK:")) {
          resolve({ ok: true, backupPath: backupTarget });
        } else {
          reject(new Error("Backup creation failed."));
        }
      });
    });
  });
}

async function getFreeBytes(target) {
  try {
    const stat = await fsp.statfs(target);
    return stat.bavail * stat.bsize;
  } catch { return null; }
}

async function readSettings() {
  try {
    const stored = JSON.parse(await fsp.readFile(settingsFile, "utf8"));
    if (!stored.libraryPath || !path.isAbsolute(stored.libraryPath)) return null;
    const library = path.resolve(stored.libraryPath);
    const rootStat = await fsp.stat(library);
    if (!rootStat.isDirectory()) throw new Error("The saved library path is not a directory.");
    const key = await fsp.readFile(jwtKeyFile, "utf8");
    return { ...stored, libraryPath: library, jwtSigningKey: key };
  } catch (error) {
    if (error.code !== "ENOENT") appendPrivateLog("Saved library validation failed; no reset was performed.");
    return null;
  }
}

async function openApplication() {
  if (!appSettings) appSettings = await readSettings();
  if (appSettings) {
    try {
      await startLocalServices();
      // Provide a brief pause so user sees 100% completion before UI transition
      setTimeout(async () => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.once("did-finish-load", () => {
            appendPrivateLog("workspace:ready");
          });
          mainWindow.loadURL(`${uiOrigin}/papers`);
        }
      }, 450);
      return;
    } catch (errPayload) {
      const isCustomError = errPayload && typeof errPayload === "object" && errPayload.stageId;
      const errorObj = isCustomError ? errPayload : {
        stageId: "unknown",
        stageTitle: "Startup",
        summary: "Startup Interrupted",
        message: errPayload?.message || String(errPayload),
        diagnostics: sanitizeDiagnostics(errPayload?.message || String(errPayload)),
        logPath: path.join(RUNTIME_HOME, "logs", "desktop.log"),
        canChangeLibrary: false,
      };
      appendPrivateLog(`Startup failed safely: ${errorObj.summary} — ${errorObj.message}`);
      if (mainWindow && !mainWindow.isDestroyed() && mainWindow.webContents) {
        mainWindow.webContents.send("startup:error", errorObj);
      }
      return;
    }
  }
  mainWindow.loadFile(onboardingFile);
}

function createWindow() {
  const appIcon = fs.existsSync(path.join(__dirname, "build", "icon.ico"))
    ? path.join(__dirname, "build", "icon.ico")
    : (fs.existsSync(path.join(__dirname, "build", "icon.png"))
      ? path.join(__dirname, "build", "icon.png")
      : undefined);

  const profileData = readJsonSafe(profileFile, {});
  const winConfig = profileData.window || {};
  let winBounds = {
    width: Number.isInteger(winConfig.width) && winConfig.width >= 1040 ? winConfig.width : 1500,
    height: Number.isInteger(winConfig.height) && winConfig.height >= 720 ? winConfig.height : 960,
  };
  if (Number.isInteger(winConfig.x) && Number.isInteger(winConfig.y)) {
    const rect = { x: winConfig.x, y: winConfig.y, width: winBounds.width, height: winBounds.height };
    const displays = screen.getAllDisplays();
    const visible = displays.some((d) => {
      const wa = d.workArea;
      return (
        rect.x < wa.x + wa.width &&
        rect.x + rect.width > wa.x &&
        rect.y < wa.y + wa.height &&
        rect.y + rect.height > wa.y
      );
    });
    if (visible) {
      winBounds.x = winConfig.x;
      winBounds.y = winConfig.y;
    }
  }

  const isWindows = process.platform === "win32";
  const windowChromeOptions = isWindows
    ? {
      titleBarStyle: "hidden",
      titleBarOverlay: {
        color: "#ffffff",
        symbolColor: "#203449",
        height: 40,
      },
    }
    : {};

  const appTitle = isDevMode
    ? "[DEV] ResearchLens"
    : (process.env.RESEARCHLENS_RUNTIME_HOME ? "[ISOLATED TEST ENVIRONMENT] ResearchLens" : "ResearchLens");

  mainWindow = new BrowserWindow({
    title: appTitle,
    ...winBounds,
    minWidth: 1040,
    minHeight: 720,
    show: false,
    autoHideMenuBar: true,
    ...windowChromeOptions,
    icon: appIcon,
    backgroundColor: "#F3F9FE",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      devTools: !app.isPackaged,
    },
  });

  mainWindow.webContents.on("did-finish-load", () => {
    const pData = readJsonSafe(profileFile, {});
    const zLevel = Number(pData.zoomLevel) || 0;
    mainWindow.webContents.setZoomLevel(Math.max(-2, Math.min(3, zLevel)));
  });

  mainWindow.webContents.on("before-input-event", (event, input) => {
    if (input.control && !input.alt && input.type === "keyDown") {
      let currentZoom = mainWindow.webContents.getZoomLevel();
      let changed = false;
      if (input.key === "=" || input.key === "+") {
        currentZoom = Math.min(3, currentZoom + 0.5);
        changed = true;
      } else if (input.key === "-") {
        currentZoom = Math.max(-2, currentZoom - 0.5);
        changed = true;
      } else if (input.key === "0") {
        currentZoom = 0;
        changed = true;
      }
      if (changed) {
        event.preventDefault();
        mainWindow.webContents.setZoomLevel(currentZoom);
        const curProf = readJsonSafe(profileFile, {});
        curProf.zoomLevel = currentZoom;
        writeJsonSafe(profileFile, curProf);
      }
    }
  });

  if (app.isPackaged) {
    Menu.setApplicationMenu(null);
  }

  if (winConfig.maximized) {
    mainWindow.maximize();
  }

  mainWindow.on("close", () => {
    try {
      const normal = mainWindow.getNormalBounds ? mainWindow.getNormalBounds() : mainWindow.getBounds();
      const maximized = mainWindow.isMaximized();
      const current = readJsonSafe(profileFile, {});
      writeJsonSafe(profileFile, {
        ...current,
        window: {
          x: normal.x,
          y: normal.y,
          width: normal.width,
          height: normal.height,
          maximized,
        },
      });
    } catch (e) {
      appendPrivateLog(`Window bounds save notice: ${e.message}`);
    }
  });
  if (isDevMode || process.env.RESEARCHLENS_RUNTIME_HOME) {
    mainWindow.on("page-title-updated", (event) => {
      event.preventDefault();
      mainWindow.setTitle(appTitle);
    });
  }
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url) return { action: "deny" };
    if (
      (uiOrigin && url.startsWith(uiOrigin)) ||
      url.startsWith("http://127.0.0.1:") ||
      url.startsWith("http://localhost:") ||
      url.includes("/pdf-viewer")
    ) {
      mainWindow.loadURL(url);
      return { action: "deny" };
    }
    if (/^https?:\/\//i.test(url)) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, target) => {
    if (target.startsWith("file://")) {
      try {
        const resolved = path.resolve(new URL(target).pathname).toLowerCase();
        if (
          resolved === path.resolve(onboardingFile).toLowerCase() ||
          resolved === path.resolve(startupFile).toLowerCase()
        ) {
          return;
        }
      } catch { }
    }
    if (uiOrigin && (target === uiOrigin || target.startsWith(`${uiOrigin}/`))) return;
    event.preventDefault();
  });
  mainWindow.webContents.on("will-attach-webview", (event) => event.preventDefault());

  // Show the branded startup screen immediately so user never sees a blank screen
  mainWindow.loadFile(startupFile);
  openApplication();
}

function killProcessTreeAsync(pid) {
  if (!pid) return Promise.resolve();
  return new Promise((resolve) => {
    try {
      const isWindows = process.platform === "win32";
      if (isWindows) {
        const taskkill = path.join(process.env.SystemRoot || "C:\\Windows", "System32", "taskkill.exe");
        const k = spawn(taskkill, ["/pid", String(pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
        k.on("close", () => resolve());
        k.on("error", () => resolve());
        setTimeout(resolve, 1500);
      } else {
        try { process.kill(-pid, "SIGKILL"); } catch { }
        resolve();
      }
    } catch {
      resolve();
    }
  });
}

function killProcessTree(pid) {
  if (!pid) return;
  killProcessTreeAsync(pid).catch(() => {});
}

async function stopOwnedServicesAsync() {
  shuttingDown = true;
  const procs = [frontendProcess, backendProcess, ollamaProcess].filter((p) => p && !p.killed && p.pid);
  for (const proc of procs) {
    try {
      proc.kill("SIGTERM");
    } catch { }
  }
  await new Promise((r) => setTimeout(r, 800));
  for (const proc of procs) {
    if (proc.pid) {
      await killProcessTreeAsync(proc.pid);
    }
  }
  // Brief pause to allow OS file handles and sockets in TIME_WAIT to cleanly release
  await new Promise((r) => setTimeout(r, 600));
  shuttingDown = false;
}

function stopOwnedServices() {
  shuttingDown = true;
  for (const proc of [frontendProcess, backendProcess, ollamaProcess]) {
    if (!proc || proc.killed) continue;
    try {
      proc.kill("SIGTERM");
    } catch { }
  }
  // Allow graceful exit for database transactions before force kill
  setTimeout(() => {
    for (const proc of [frontendProcess, backendProcess, ollamaProcess]) {
      if (proc && !proc.killed && proc.pid) {
        killProcessTree(proc.pid);
      }
    }
  }, 2000).unref();
}

app.on("before-quit", () => {
  if (readJsonSafe(profileFile, {}).rememberMe === false) {
    try {
      fs.unlinkSync(path.join(RUNTIME_HOME, "session.dat"));
    } catch { }
  }
  stopOwnedServices();
});
app.on("window-all-closed", () => app.quit());
app.whenReady().then(() => {
  appendPrivateLog("app:ready");
  registerIpc();
  createWindow();
}).catch((error) => {
  appendPrivateLog(`Desktop startup failed: ${error.message}`);
  app.quit();
});
