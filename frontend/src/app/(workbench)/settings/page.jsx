"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@tanstack/react-query";
import { researchService } from "@/services/research.service";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Settings, ShieldCheck, User, LogOut, Check, Cpu, RefreshCw } from "lucide-react";
import { formatDate } from "@/utils/formatters";

export default function SettingsPage() {
  const { user, updateProfile, isUpdatingProfile, logout } = useAuth();
  const [fullName, setFullName] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [desktopStatus, setDesktopStatus] = useState(null);
  const [backupRunning, setBackupRunning] = useState(false);
  const [backupNotice, setBackupNotice] = useState(null);

  const handleCreateBackup = async () => {
    const bridge = typeof window !== "undefined" ? window["researchLensDesktop"] : null;
    if (!bridge || !bridge.createBackup) return;
    setBackupRunning(true);
    setBackupNotice(null);
    try {
      const res = await bridge.createBackup();
      setBackupNotice({ type: "success", text: `Verified backup created: ${res.backupPath}` });
    } catch (err) {
      setBackupNotice({ type: "error", text: `Backup failed: ${err.message}` });
    } finally {
      setBackupRunning(false);
    }
  };

  useEffect(() => {
    if (user?.full_name) {
      setFullName(user.full_name);
    }
  }, [user]);

  useEffect(() => {
    const bridge = typeof window !== "undefined" ? window["researchLensDesktop"] : null;
    if (!bridge) return;
    bridge.getDiagnostics().then(setDesktopStatus).catch(() => setDesktopStatus(null));
  }, []);

  const { data: healthData } = useQuery({
    queryKey: ["healthCheck"],
    queryFn: () => researchService.getHealth(),
  });

  const { data: readyData } = useQuery({
    queryKey: ["readinessCheck"],
    queryFn: () => researchService.getReadiness(),
  });

  const { data: modelData, isFetching: modelRefreshing, refetch: refreshModel } = useQuery({
    queryKey: ["localModelStatus"],
    queryFn: () => researchService.getLocalModelStatus(),
    refetchInterval: 15000,
    retry: 1,
  });

  const modelState = modelData?.state;
  const modelBadge = modelState === "ready_loaded" ? ["Loaded and ready", "grounded"]
    : modelState === "inference_active" ? ["Generating locally", "grounded"]
    : modelState === "ready_not_loaded" ? ["Installed · not loaded", "secondary"]
    : modelState === "model_missing" ? ["Model not installed", "warning"]
    : ["Ollama unavailable", "destructive"];

  const handleProfileSave = async (e) => {
    e.preventDefault();
    await updateProfile({ full_name: fullName.trim() || null });
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-4xl mx-auto">
      <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Account & System Settings
          </h1>
        </div>
        <p className="text-xs text-zinc-500 font-mono">
          Manage your researcher profile and monitor backend architecture integration health.
        </p>
      </div>

      {desktopStatus && (
        <Card className="border-sky-200 bg-sky-50/50 shadow-2xs dark:border-sky-900 dark:bg-sky-950/20">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-sky-700 dark:text-sky-300" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider">Privacy &amp; Permissions Centre</CardTitle>
              <Badge variant="secondary" className="ml-auto">Local Only</Badge>
            </div>
            <CardDescription className="text-xs">
              ResearchLens operates strictly on this Windows computer. Your research library, documents, and indexes are never transmitted externally.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-4 pt-2 text-xs">
            <div className="grid gap-3 sm:grid-cols-2">
              <div><span className="text-muted-foreground">Active Library:</span><div className="mt-1 break-all font-mono font-medium">{desktopStatus.libraryPath}</div></div>
              <div><span className="text-muted-foreground">Local Engine:</span><div className="mt-1 font-medium">FastAPI Sidecar ({desktopStatus.backendReady ? "Ready" : "Offline"}) · SQLite + FTS5 ({desktopStatus.databaseReady ? "Active" : "Pending"})</div></div>
              <div><span className="text-muted-foreground">Available Disk Space:</span><div className="mt-1 font-medium">{Number.isFinite(desktopStatus.diskFreeBytes) ? `${(desktopStatus.diskFreeBytes / (1024 ** 3)).toFixed(1)} GB free` : "Checking…"}</div></div>
              <div><span className="text-muted-foreground">Network Boundary:</span><div className="mt-1 font-medium text-emerald-700 dark:text-emerald-400">Strict Loopback (127.0.0.1 only)</div></div>
            </div>

            <div className="border-t border-sky-200/60 pt-3 dark:border-sky-800">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-sky-950 dark:text-sky-100 mb-2">Active Permission Matrix</h4>
              <div className="divide-y divide-sky-100 dark:divide-sky-900/40 text-[11px]">
                <div className="flex justify-between py-1"><span>Selected local document access</span><span className="font-semibold text-emerald-700">Allowed after selection</span></div>
                <div className="flex justify-between py-1"><span>Managed library storage</span><span className="font-semibold text-emerald-700">Copy mode active</span></div>
                <div className="flex justify-between py-1"><span>Linked file access</span><span className="font-semibold text-zinc-600">Explicit choice</span></div>
                <div className="flex justify-between py-1"><span>External generative AI</span><span className="font-semibold text-zinc-500">Disabled / absent</span></div>
                <div className="flex justify-between py-1"><span>Cloud synchronization</span><span className="font-semibold text-zinc-500">Disabled</span></div>
                <div className="flex justify-between py-1"><span>Telemetry &amp; Analytics</span><span className="font-semibold text-zinc-500">Disabled</span></div>
                <div className="flex justify-between py-1"><span>Crash report uploads</span><span className="font-semibold text-zinc-500">Disabled</span></div>
                <div className="flex justify-between py-1"><span>External scholarly lookup</span><span className="font-semibold text-zinc-500">Disabled (blocked)</span></div>
                <div className="flex justify-between py-1"><span>Background tasks when closed</span><span className="font-semibold text-zinc-500">Disabled</span></div>
              </div>
            </div>

            <div className="border-t border-sky-200/60 pt-3 dark:border-sky-800 flex items-center justify-between">
              <div>
                <span className="font-semibold text-sky-950 dark:text-sky-100">Library Backup</span>
                <p className="text-[10px] text-muted-foreground">Create a consistent verified SQLite snapshot and document bundle.</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCreateBackup}
                disabled={backupRunning}
                className="text-xs bg-white hover:bg-sky-50 dark:bg-zinc-900"
              >
                {backupRunning ? "Creating Snapshot…" : "Create Backup Now"}
              </Button>
            </div>
            {backupNotice && (
              <div className={`p-2 rounded text-[11px] ${backupNotice.type === "success" ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-800 border border-red-200"}`}>
                {backupNotice.text}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Profile Settings */}
        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                Researcher Profile
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Update your workspace identity
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleProfileSave}>
            <CardContent className="p-4 space-y-3">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-zinc-700">
                  Full Name
                </label>
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Dr. Jane Doe"
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-zinc-700">
                  Email Address
                </label>
                <Input
                  value={user?.email || ""}
                  disabled
                  className="text-xs bg-zinc-100 font-mono cursor-not-allowed dark:bg-zinc-800"
                />
                <p className="text-[10px] text-zinc-400 font-mono">
                  Registered: {user?.created_at ? formatDate(user.created_at) : "--"}
                </p>
              </div>

              {saveSuccess && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                  <Check className="h-3.5 w-3.5" />
                  <span>Profile updated successfully</span>
                </div>
              )}
            </CardContent>

            <CardFooter className="p-4 pt-0 flex justify-between">
              <Button
                type="submit"
                variant="workbench"
                size="sm"
                disabled={isUpdatingProfile}
                className="text-sm"
              >
                {isUpdatingProfile ? "Saving..." : "Save Changes"}
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => logout()}
                className="text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
              >
                <LogOut className="mr-1.5 h-3.5 w-3.5" />
                <span>Sign Out</span>
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Backend & Architecture Status */}
        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                System Integration Status
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Live status from FastAPI and storage backends
            </CardDescription>
          </CardHeader>

          <CardContent className="p-4 space-y-3 text-xs font-mono">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <span className="text-zinc-500">FastAPI Gateway:</span>
              <Badge
                variant={healthData?.status === "ok" ? "grounded" : "destructive"}
                className="text-[10px]"
              >
                {healthData?.status === "ok" ? "200 Healthy" : "Offline"}
              </Badge>
            </div>

            <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <span className="text-zinc-500">PostgreSQL DB:</span>
              <Badge
                variant={readyData?.status === "ready" ? "grounded" : "warning"}
                className="text-[10px]"
              >
                {readyData?.status === "ready" ? "Ready" : "Degraded"}
              </Badge>
            </div>

            <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <span className="text-zinc-500">ChromaDB Vector Store:</span>
              <Badge variant="secondary" className="text-[10px]">
                In-Process / Docker
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Upload Size Limit:</span>
              <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                1 GiB per file · 1 GiB per batch
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-blue-600" />
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                  Local AI Model
                </CardTitle>
              </div>
              <Button type="button" variant="ghost" size="icon" aria-label="Refresh model status"
                onClick={() => refreshModel()} disabled={modelRefreshing} className="h-7 w-7">
                <RefreshCw className={`h-3.5 w-3.5 ${modelRefreshing ? "animate-spin" : ""}`} />
              </Button>
            </div>
            <CardDescription className="text-xs">
              Read-only Ollama status. ResearchLens will not download or load a model from this screen.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-3 text-xs">
            <div className="flex items-center justify-between gap-3">
              <span className="text-zinc-500">Configured model</span>
              <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">{modelData?.model || "qwen3.5:0.8b"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-zinc-500">Runtime and model</span>
              <Badge variant={modelBadge[1]} className="text-[10px]">{modelBadge[0]}</Badge>
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-zinc-100 pt-2 dark:border-zinc-800">
              <span className="text-zinc-500">Generation limits</span>
              <span className="text-right font-mono text-zinc-700 dark:text-zinc-300">
                {modelData?.generation_limits
                  ? `${modelData.generation_limits.max_output_tokens} output · ${modelData.generation_limits.context_tokens} context tokens`
                  : "Status unavailable"}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed text-zinc-500">
              {modelState === "ready_not_loaded"
                ? "The model loads on its first research request and unloads according to Ollama's keep-alive setting."
                : modelState === "model_missing"
                  ? "Install the configured model manually in Ollama. No model download has been started."
                  : modelState === "runtime_unavailable"
                    ? "Start Ollama to enable local synthesis. Evidence retrieval remains available."
                    : "Only the final response content is used; private model thinking is not displayed."}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
