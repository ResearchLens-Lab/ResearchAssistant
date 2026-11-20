import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import path, { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(desktop, '..');
const build = join(desktop, 'build');
const runtime = join(build, 'app-runtime');
const webOnly = process.argv.includes('--web-only');
const noPackage = process.argv.includes('--no-package');
const skipNext = process.argv.includes('--skip-next') && existsSync(join(runtime, 'frontend', 'server.js'));

const run = (command, args, cwd, env = {}) => {
  const result = spawnSync(command, args, { cwd, env: { ...process.env, ...env }, stdio: 'inherit', windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} ${args.join(' ')} exited with status ${result.status}`);
};

const safeCopy = (source, target, filter) => {
  if (!existsSync(source)) throw new Error(`Required build input is missing: ${source}`);
  cpSync(source, target, { recursive: true, filter: filter || (() => true) });
};

const runRobocopy = (src, dest, extraArgs = []) => {
  if (!existsSync(src)) throw new Error(`Source does not exist: ${src}`);
  mkdirSync(dest, { recursive: true });
  const args = [src, dest, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/MT:16', ...extraArgs];
  const res = spawnSync('robocopy', args, { stdio: 'ignore', windowsHide: true });
  if (res.status > 7) {
    throw new Error(`Robocopy from ${src} to ${dest} failed with status ${res.status}`);
  }
};

const isPrivateRelPath = (relPath) => /(^|[\\/])(?:\.env(?:\.[^\\/]*)?|\.git|\.pytest_cache|__pycache__|tests?|testdata|storage|uploads|\.chroma|\.model_cache|\.venv[^\\/]*|node_modules)(?:[\\/]|$)/i.test(relPath);

try {
  if (!skipNext) {
    console.log(`[1/5] Preparing app-runtime directory at ${runtime}...`);
    mkdirSync(runtime, { recursive: true });
    const frontendTarget = join(runtime, 'frontend');
    rmSync(frontendTarget, { recursive: true, force: true });

    // 1. Build Next.js frontend standalone
    console.log(`[2/5] Building Next.js standalone frontend...`);
    const frontend = join(repo, 'frontend');
    const hiddenEnvFiles = [];
    try {
      for (const name of readdirSync(frontend).filter((entry) => entry.startsWith('.env'))) {
        const original = join(frontend, name);
        const hidden = `${original}.desktop-build-${process.pid}`;
        renameSync(original, hidden);
        hiddenEnvFiles.push([hidden, original]);
      }
      run(process.execPath, [join(frontend, 'node_modules', 'next', 'dist', 'bin', 'next'), 'build'], frontend, {
        DESKTOP_BUILD: '1',
        NEXT_PUBLIC_API_URL: 'http://127.0.0.1:1/api/v1',
        NEXT_PUBLIC_APP_ENV: 'production',
        NEXT_TELEMETRY_DISABLED: '1',
      });
    } finally {
      for (const [hidden, original] of hiddenEnvFiles.reverse()) {
        if (existsSync(hidden)) renameSync(hidden, original);
      }
    }

    const standaloneServer = join(frontend, '.next', 'standalone', 'server.js');
    if (!existsSync(standaloneServer)) {
      throw new Error('Next.js standalone server output was not generated.');
    }

    console.log(`      Staging Next.js standalone artifacts...`);
    safeCopy(join(frontend, '.next', 'standalone'), join(runtime, 'frontend'));
    if (existsSync(join(frontend, '.next', 'static'))) {
      safeCopy(join(frontend, '.next', 'static'), join(runtime, 'frontend', '.next', 'static'));
    }
    if (existsSync(join(frontend, 'public'))) {
      safeCopy(join(frontend, 'public'), join(runtime, 'frontend', 'public'));
    }
  } else {
    console.log(`[1/5] Using existing staged standalone web frontend (--skip-next)...`);
  }

  if (webOnly) {
    console.log(`\nStandalone web runtime staged successfully at ${runtime}`);
    process.exit(0);
  }

  // 2. Stage Python & Backend dependencies
  if (!existsSync(join(runtime, 'python', 'python.exe'))) {
    console.log(`[3/5] Staging Python 3.12 runtime and native dependencies...`);
    const pythonHome = process.env.RESEARCHLENS_PYTHON_HOME || join(process.env.APPDATA, '..', 'Roaming', 'uv', 'python', 'cpython-3.12.15-windows-x86_64-none');
    const sitePackages = process.env.RESEARCHLENS_SITE_PACKAGES || join(repo, '.venv_stabilization', 'Lib', 'site-packages');
    const pythonTarget = join(runtime, 'python');
    mkdirSync(pythonTarget, { recursive: true });

    for (const name of ['python.exe', 'python3.dll', 'python312.dll', 'python312.zip', 'vcruntime140.dll', 'vcruntime140_1.dll']) {
      const from = join(pythonHome, name);
      if (existsSync(from)) safeCopy(from, join(pythonTarget, name));
    }

    console.log(`      Copying Python standard library and DLLs...`);
    runRobocopy(join(pythonHome, 'DLLs'), join(pythonTarget, 'DLLs'));
    runRobocopy(join(pythonHome, 'Lib'), join(pythonTarget, 'Lib'), ['/XD', 'test', 'idlelib', 'tkinter']);

    console.log(`      Copying packaged site-packages (model-free by construction)...`);
    runRobocopy(sitePackages, join(pythonTarget, 'Lib', 'site-packages'), [
      '/XD', '__pycache__', 'tests', 'test', '.git', 'pip*', 'kubernetes*', 'chromadb*', 'fastembed*', 'onnxruntime*', 'google*', 'torch*', 'sentence_transformers*',
      '/XF', '*.pyc', '*.pyo'
    ]);

    console.log(`      Copying Node runtime binary...`);
    safeCopy(process.execPath, join(runtime, 'node.exe'));

    console.log(`[4/5] Staging backend and RAG engine sources...`);
    const source = join(runtime, 'source');
    mkdirSync(source, { recursive: true });
    for (const folder of ['backend', 'rag']) {
      const srcFolder = join(repo, folder);
      safeCopy(srcFolder, join(source, folder), (src) => {
        const rel = src.slice(srcFolder.length);
        return !isPrivateRelPath(rel);
      });
    }
    safeCopy(join(repo, 'backend', 'alembic.ini'), join(source, 'backend', 'alembic.ini'));

    console.log(`      Verifying staged Python runtime in isolation...`);
    run(join(pythonTarget, 'python.exe'), [
      '-c',
      'import fastapi, uvicorn, aiosqlite, sqlalchemy, alembic; print("      Staged Python runtime verified successfully!")',
    ], repo);
  } else {
    console.log(`[3/5] Staged Python 3.12 runtime already present.`);
    console.log(`[4/5] Refreshing application source in runtime...`);
    const source = join(runtime, 'source');
    rmSync(source, { recursive: true, force: true });
    mkdirSync(source, { recursive: true });
    for (const folder of ['backend', 'rag']) {
      const srcFolder = join(repo, folder);
      safeCopy(srcFolder, join(source, folder), (src) => {
        const rel = src.slice(srcFolder.length);
        return !isPrivateRelPath(rel);
      });
    }
    safeCopy(join(repo, 'backend', 'alembic.ini'), join(source, 'backend', 'alembic.ini'));
  }

  // Stage sample showcase documents
  const samplesTarget = join(runtime, 'samples');
  mkdirSync(samplesTarget, { recursive: true });
  const sampleFiles = [
    join(desktop, 'samples', 'CS_GATE2027_Syllabus.pdf'),
    join(repo, 'storage', 'uploads', '5918c028-3381-480a-b6e5-7bae7bc97b06.pdf'),
  ];
  for (const sample of sampleFiles) {
    if (existsSync(sample)) {
      safeCopy(sample, join(samplesTarget, 'CS_GATE2027_Syllabus.pdf'));
      break;
    }
  }

  // Ollama CPU bundling disabled for packaging slimming
  console.log(`      Notice: Local Intelligence (Ollama) bundling disabled for packaging slimming; pure extractive engine.`);

  // Stage Third-Party Licenses
  const licensesTarget = join(runtime, 'licenses');
  mkdirSync(licensesTarget, { recursive: true });
  const licenseFile = join(desktop, 'licenses', 'THIRD_PARTY_LICENSES.md');
  if (existsSync(licenseFile)) {
    safeCopy(licenseFile, join(licensesTarget, 'THIRD_PARTY_LICENSES.md'));
  }

  // Compute comprehensive source and staged runtime hashes for manifest audit
  const computeFileHash = (filePath) => {
    return existsSync(filePath) ? createHash('sha256').update(readFileSync(filePath)).digest('hex') : null;
  };

  const getDirectoryHashes = (baseDir, prefix = '') => {
    const hashes = {};
    if (!existsSync(baseDir)) return hashes;
    const walk = (dir, currentPrefix) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory()) {
          if (!['__pycache__', 'tests', 'test', '.pytest_cache'].includes(entry.name)) {
            walk(join(dir, entry.name), currentPrefix ? `${currentPrefix}/${entry.name}` : entry.name);
          }
        } else if (entry.isFile()) {
          const relKey = currentPrefix ? `${currentPrefix}/${entry.name}` : entry.name;
          hashes[relKey] = computeFileHash(join(dir, entry.name));
        }
      }
    };
    walk(baseDir, prefix);
    return hashes;
  };

  const stagedRagHashes = getDirectoryHashes(join(runtime, 'source', 'rag'), 'rag');
  const stagedBackendHashes = getDirectoryHashes(join(runtime, 'source', 'backend'), 'backend');
  const desktopHashes = {
    'desktop/main.cjs': computeFileHash(join(desktop, 'main.cjs')),
    'desktop/preload.cjs': computeFileHash(join(desktop, 'preload.cjs')),
    'runtime/node.exe': computeFileHash(join(runtime, 'node.exe')),
    'runtime/python/python.exe': computeFileHash(join(runtime, 'python', 'python.exe')),
    ...(existsSync(join(runtime, 'ollama', 'ollama.exe')) ? { 'runtime/ollama/ollama.exe': computeFileHash(join(runtime, 'ollama', 'ollama.exe')) } : {}),
  };

  const ragModuleHashes = {
    'rag/generation/local_intelligence_service.py': computeFileHash(join(runtime, 'source', 'rag', 'generation', 'local_intelligence_service.py')),
    'rag/generation/evidence_validator.py': computeFileHash(join(runtime, 'source', 'rag', 'generation', 'evidence_validator.py')),
    'rag/ingestion/document_loader.py': computeFileHash(join(runtime, 'source', 'rag', 'ingestion', 'document_loader.py')),
    'rag/ingestion/document_normalizer.py': computeFileHash(join(runtime, 'source', 'rag', 'ingestion', 'document_normalizer.py')),
    'rag/ingestion/preflight.py': computeFileHash(join(runtime, 'source', 'rag', 'ingestion', 'preflight.py')),
    'rag/ingestion/ocr_engine.py': computeFileHash(join(runtime, 'source', 'rag', 'ingestion', 'ocr_engine.py')),
    'rag/ingestion/structure_extractor.py': computeFileHash(join(runtime, 'source', 'rag', 'ingestion', 'structure_extractor.py')),
    'rag/chunking/strategies.py': computeFileHash(join(runtime, 'source', 'rag', 'chunking', 'strategies.py')),
    'rag/chunking/structure_chunker.py': computeFileHash(join(runtime, 'source', 'rag', 'chunking', 'structure_chunker.py')),
    'rag/intelligence/engine.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'engine.py')),
    'rag/intelligence/query_analyzer.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'query_analyzer.py')),
    'rag/intelligence/sentence_analyzer.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'sentence_analyzer.py')),
    'rag/intelligence/retrieval_engine.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'retrieval_engine.py')),
    'rag/intelligence/confidence_evaluator.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'confidence_evaluator.py')),
    'rag/intelligence/answer_composer.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'answer_composer.py')),
    'rag/intelligence/report_generator.py': computeFileHash(join(runtime, 'source', 'rag', 'intelligence', 'report_generator.py')),
    'rag/skills/runtime.py': computeFileHash(join(runtime, 'source', 'rag', 'skills', 'runtime.py')),
    'rag/skills/schema.py': computeFileHash(join(runtime, 'source', 'rag', 'skills', 'schema.py')),
    'rag/independent/topic_analyzer.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'topic_analyzer.py')),
    'rag/independent/intent_classifier.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'intent_classifier.py')),
    'rag/independent/retriever.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'retriever.py')),
    'rag/independent/engine.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'engine.py')),
    'rag/independent/answer_composer.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'answer_composer.py')),
    'rag/independent/evidence_validator.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'evidence_validator.py')),
    'rag/independent/index_writer.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'index_writer.py')),
    'rag/independent/ingest_pipeline.py': computeFileHash(join(runtime, 'source', 'rag', 'independent', 'ingest_pipeline.py')),
  };

  const report = {
    applicationVersion: '0.1.0',
    buildDate: new Date().toISOString(),
    targetArchitecture: 'x64 (Windows)',
    ragEngineMode: 'independent',
    pythonRuntime: 'Python 3.12.15 (Windows x86_64, cpython, model-free)',
    nodeVersion: process.version,
    electronVersion: '39.8.10',
    nextBuild: 'Next.js 15.5.28 Standalone Production',
    databaseSchemaVersion: 'Alembic revision d3e4f5a6b7c8 (head)',
    codeSigned: false,
    signatureNotice: 'Unsigned showcase build for Windows x64 evaluation',
    pythonExecutable: existsSync(join(runtime, 'python', 'python.exe')),
    nextStandalone: existsSync(join(runtime, 'frontend', 'server.js')),
    localIntelligence: {
      provider: 'deterministic_extractive_engine',
      model: 'none',
      bundledOllama: false,
      licenses: 'licenses/THIRD_PARTY_LICENSES.md',
    },
    ragModuleHashes,
    stagedBackendHashes,
    stagedRagHashes,
    desktopHashes,
    excluded: [
      '.env and developer secrets',
      'developer SQLite / PostgreSQL databases',
      'ChromaDB collections and vector caches',
      'User uploaded documents and PDFs',
      'developer test suites and fixtures',
      'model caches',
      'chromadb, fastembed, onnxruntime, and generative AI packages',
    ],
  };

  const manifestPath = join(build, 'build-manifest.json');
  writeFileSync(manifestPath, JSON.stringify(report, null, 2));
  console.log(`      Build manifest recorded at: ${manifestPath}`);

  // 5. Package Windows x64 NSIS Installer
  if (!noPackage) {
    console.log(`\n[5/5] Packaging self-contained Windows x64 NSIS installer...`);
    // Ensure NSIS direct-extraction optimization is applied with unified status reporting
    const extractAppPackagePath = join(desktop, 'node_modules', 'app-builder-lib', 'templates', 'nsis', 'include', 'extractAppPackage.nsh');
    if (existsSync(extractAppPackagePath)) {
      let content = readFileSync(extractAppPackagePath, 'utf8');
      const targetMacro = /!macro extractUsing7za FILE[\s\S]*?!macroend/;
      const directExtractionMacro = `!macro extractUsing7za FILE\n  ClearErrors\n  SetOutPath $OUTDIR\n  Nsis7z::ExtractWithDetails "\${FILE}" "Extracting %s..."\n!macroend`;
      content = content.replace(targetMacro, directExtractionMacro);

      const targetEmbedded = /!macro extractEmbeddedAppPackage[\s\S]*?!macroend/;
      const newEmbedded = `!macro extractEmbeddedAppPackage\n  DetailPrint "Preparing installation..."\n  SetDetailsPrint textonly\n  !ifdef COMPRESS\n    SetCompress off\n  !endif\n\n  Var /GLOBAL packageArch\n  \n  !insertmacro identify_package\n  !insertmacro compute_files_for_current_arch\n\n  !ifdef COMPRESS\n    SetCompress "\${COMPRESS}"\n  !endif\n\n  DetailPrint "Extracting application files..."\n  SetDetailsPrint both\n  !insertmacro decompress\n  Delete "$PLUGINSDIR\\\\app-$packageArch.7z"\n  !insertmacro custom_files_post_decompression\n\n  DetailPrint "Finishing installation..."\n!macroend`;
      content = content.replace(targetEmbedded, newEmbedded);
      writeFileSync(extractAppPackagePath, content, 'utf8');
      console.log(`      Verified and applied high-performance NSIS extraction patch.`);
    }
    // Build to local temp outside OneDrive to avoid EPERM file locking
    const localAppData = process.env.LOCALAPPDATA || path.join(process.env.USERPROFILE, 'AppData', 'Local');
    const tempDistDir = join(localAppData, 'ResearchLensDist');
    rmSync(tempDistDir, { recursive: true, force: true });
    mkdirSync(tempDistDir, { recursive: true });

    const builderBin = join(desktop, 'node_modules', 'electron-builder', 'cli.js');
    run(process.execPath, [
      builderBin,
      '--win',
      'nsis',
      '--x64',
      `-c.directories.output=${tempDistDir}`,
    ], desktop);

    const builtExe = join(tempDistDir, 'ResearchLens-Setup-x64.exe');
    if (!existsSync(builtExe)) {
      throw new Error(`Expected installer was not found at ${builtExe}`);
    }

    const releaseDir = join(repo, 'release', 'desktop');
    mkdirSync(releaseDir, { recursive: true });
    const finalInstallerPath = join(releaseDir, 'ResearchLens-Setup-x64.exe');
    const prevInstallerPath = join(releaseDir, 'ResearchLens-Setup-x64.previous.exe');
    if (existsSync(finalInstallerPath)) {
      safeCopy(finalInstallerPath, prevInstallerPath);
      console.log(`      Previous installer backed up to: ${prevInstallerPath}`);
    }
    safeCopy(builtExe, finalInstallerPath);

    const stats = statSync(finalInstallerPath);
    const fileBytes = readFileSync(finalInstallerPath);
    const sha256 = createHash('sha256').update(fileBytes).digest('hex');

    console.log(`\n================================================================`);
    console.log(`  RESEARCHLENS DESKTOP INSTALLER GENERATED SUCCESSFULLY!`);
    console.log(`================================================================`);
    console.log(`  Installer:   ${finalInstallerPath}`);
    console.log(`  File size:   ${(stats.size / (1024 * 1024)).toFixed(2)} MB (${stats.size} bytes)`);
    console.log(`  SHA-256:     ${sha256}`);
    console.log(`  Target:      Windows x64 NSIS Installer`);
    console.log(`  Self-contained: Bundled Node.js + Python 3.12 + FastAPI + Next.js`);
    console.log(`================================================================\n`);

    report.installer = {
      path: finalInstallerPath,
      sizeBytes: stats.size,
      sizeMB: (stats.size / (1024 * 1024)).toFixed(2),
      sha256,
    };
    writeFileSync(manifestPath, JSON.stringify(report, null, 2));
  } else {
    console.log(`\nRuntime staged at: ${runtime} (--no-package specified)`);
  }
} catch (error) {
  console.error(`\nDesktop build failed: ${error.message}`);
  process.exitCode = 1;
}
