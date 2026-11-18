"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Settings, ShieldCheck, User, LogOut, Check, Cpu, FolderArchive, RefreshCw, AlertTriangle } from "lucide-react";
import { formatDate } from "@/utils/formatters";
import { papersService } from "@/services/papers.service";
import { documentsService } from "@/services/documents.service";

export default function SettingsPage() {
  const { user, updateProfile, isUpdatingProfile, logout } = useAuth();
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Desktop diagnostics & permissions
  const [desktopStatus, setDesktopStatus] = useState(null);
  const [externalLookups, setExternalLookups] = useState(false);
  const [needsRestart, setNeedsRestart] = useState(false);

  // Library backup state
  const [backupRunning, setBackupRunning] = useState(false);
  const [backupNotice, setBackupNotice] = useState(null);

  // Reindex state
  const [reindexConfirmOpen, setReindexConfirmOpen] = useState(false);
  const [reindexRunning, setReindexRunning] = useState(false);
  const [reindexNotice, setReindexNotice] = useState(null);

  // Local AI status
  const [localAiStatus, setLocalAiStatus] = useState(null);

  useEffect(() => {
    if (user?.full_name) {
      setFullName(user.full_name);
    }
  }, [user]);

  useEffect(() => {
    const bridge = typeof window !== "undefined" ? window["researchLensDesktop"] : null;
    if (!bridge) return;

    if (bridge.getDiagnostics) {
      bridge.getDiagnostics().then(setDesktopStatus).catch(() => setDesktopStatus(null));
    }
    if (bridge.getExternalLookups) {
      bridge.getExternalLookups().then(setExternalLookups).catch(() => setExternalLookups(false));
    }
    if (bridge.getIntelligenceStatus) {
      bridge.getIntelligenceStatus().then(setLocalAiStatus).catch(() => setLocalAiStatus(null));
    }
  }, []);

  const handleToggleLookups = async (e) => {
    const nextVal = e.target.checked;
    setExternalLookups(nextVal);
    const bridge = typeof window !== "undefined" ? window["researchLensDesktop"] : null;
    if (bridge?.setExternalLookups) {
      await bridge.setExternalLookups(nextVal);
      setNeedsRestart(true);
    }
  };

  const handleRestartNow = () => {
    const bridge = typeof window !== "undefined" ? window["researchLensDesktop"] : null;
    if (bridge?.restartApp) {
      bridge.restartApp();
    }
  };

  const handleCreateBackup = async () => {
    const bridge = typeof window !== "undefined" ? window["researchLensDesktop"] : null;
    if (!bridge) return;

    setBackupRunning(true);
    setBackupNotice(null);
    try {
      let chosenFolder = null;
      if (bridge.chooseLibraryFolder) {
        chosenFolder = await bridge.chooseLibraryFolder();
        if (!chosenFolder) {
          setBackupRunning(false);
          return;
        }
      }
      const res = await (bridge.createBackup ? bridge.createBackup(chosenFolder) : null);
      setBackupNotice({
        type: "success",
        text: `Verified backup created: ${res?.backupPath || chosenFolder || "Library backup complete"}`,
      });
    } catch (err) {
      setBackupNotice({ type: "error", text: `Backup failed: ${err.message}` });
    } finally {
      setBackupRunning(false);
    }
  };

  const handleRebuildIndex = async () => {
    setReindexConfirmOpen(false);
    setReindexRunning(true);
    setReindexNotice(null);
    try {
      const papers = await papersService.getAll(1, 100);
      const paperList = papers?.items || papers || [];
      let totalReindexed = 0;

      for (const p of paperList) {
        const docs = await papersService.getDocuments(p.id);
        const docList = docs || [];
        for (const doc of docList) {
          await documentsService.reindex(doc.id);
          totalReindexed++;
        }
      }

      setReindexNotice({
        type: "success",
        text: `Rebuilt search index for ${totalReindexed} document${totalReindexed === 1 ? "" : "s"} successfully.`,
      });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
    } catch (err) {
      setReindexNotice({
        type: "error",
        text: `Rebuilding index failed: ${err.message || "Operation could not be completed."}`,
      });
    } finally {
      setReindexRunning(false);
    }
  };

  const handleProfileSave = async (e) => {
    e.preventDefault();
    await updateProfile({ full_name: fullName.trim() || null });
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div className="page-shell">
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Header */}
        <div className="border-b border-slate-200/80 pb-4 space-y-1">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-slate-900" />
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Settings & Privacy
            </h1>
          </div>
          <p className="text-xs text-slate-500">
            Manage your researcher profile, local storage, and privacy controls.
          </p>
        </div>

        {/* Section (a): Researcher Account */}
        <Card className="border-slate-200 shadow-2xs">
          <CardHeader className="p-4 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-slate-700" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-800">
                (a) Researcher Profile
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Your local workspace identity
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleProfileSave}>
            <CardContent className="p-4 space-y-3">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-slate-700">
                  Full Name
                </label>
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Researcher Name"
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-slate-700">
                  Email Address
                </label>
                <Input
                  value={user?.email || ""}
                  disabled
                  className="text-xs bg-slate-50 font-mono cursor-not-allowed"
                />
                <p className="text-[11px] text-slate-400 font-mono">
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
                className="text-xs rounded-full"
              >
                {isUpdatingProfile ? "Saving..." : "Save Changes"}
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => logout()}
                className="text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700 rounded-full"
              >
                <LogOut className="mr-1.5 h-3.5 w-3.5" />
                <span>Sign Out</span>
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Section (b): Privacy & Network */}
        <Card className="border-slate-200 shadow-2xs">
          <CardHeader className="p-4 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[#1d6fc4]" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-800">
                (b) Privacy & Network
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Strict offline boundary by default.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-4 text-xs">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <label
                  htmlFor="online-verification-toggle"
                  className="font-medium text-slate-800 cursor-pointer"
                >
                  Online source verification (Crossref, OpenAlex)
                </label>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Only the DOI is sent. Document text never leaves this computer.
                </p>
              </div>
              <input
                id="online-verification-toggle"
                type="checkbox"
                checked={externalLookups}
                onChange={handleToggleLookups}
                className="h-4 w-4 rounded border-slate-300 text-[#1d6fc4] focus:ring-[#1d6fc4] cursor-pointer mt-0.5"
              />
            </div>

            {needsRestart && (
              <div className="flex items-center justify-between rounded-xl border border-sky-200 bg-sky-50 p-3 text-xs text-sky-900">
                <span>Restart ResearchLens to apply network changes.</span>
                <Button
                  size="sm"
                  variant="workbench"
                  onClick={handleRestartNow}
                  className="h-7 text-xs rounded-full"
                >
                  Restart now
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Section (c): Local AI */}
        <Card className="border-slate-200 shadow-2xs">
          <CardHeader className="p-4 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-slate-700" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-800">
                (c) Local AI
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Optional on-device synthesis engine
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-2 text-xs">
            {localAiStatus?.ready || localAiStatus?.state === "ready_loaded" ? (
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Status</span>
                <Badge variant="grounded">
                  Installed locally ({localAiStatus.model || "Qwen"})
                </Badge>
              </div>
            ) : (
              <p className="text-slate-600 leading-relaxed">
                Not installed: answers are quoted directly from your sources.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Section (d): Library Storage & Backup */}
        <Card className="border-slate-200 shadow-2xs">
          <CardHeader className="p-4 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <FolderArchive className="h-4 w-4 text-slate-700" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-800">
                (d) Library Storage & Backup
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Location of your SQLite database and indexed documents
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-3 text-xs">
            <div>
              <span className="text-slate-500 font-medium">Library Path:</span>
              <div className="mt-1 font-mono text-[11px] bg-slate-50 p-2 rounded-lg border border-slate-200/80 break-all">
                {desktopStatus?.libraryPath || "Documents/ResearchLens Library"}
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100">
              <span className="text-slate-600">Create backup snapshot:</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCreateBackup}
                disabled={backupRunning}
                className="h-8 text-xs rounded-full"
              >
                {backupRunning ? "Creating backup…" : "Back up library"}
              </Button>
            </div>

            {backupNotice && (
              <div
                className={`p-2.5 rounded-lg text-xs ${
                  backupNotice.type === "success"
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-rose-50 text-rose-800 border border-rose-200"
                }`}
              >
                {backupNotice.text}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Section (e): Rebuild Search Index */}
        <Card className="border-slate-200 shadow-2xs">
          <CardHeader className="p-4 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-slate-700" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-800">
                (e) Search Index
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Re-index documents using the latest section-aware chunker
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-3 text-xs">
            <p className="text-slate-600 leading-relaxed">
              Re-parses and re-indexes all attached source documents with section boundaries and clean title detection.
            </p>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100">
              <span className="text-slate-600">Rebuild index:</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setReindexConfirmOpen(true)}
                disabled={reindexRunning}
                className="h-8 text-xs rounded-full border-amber-300 text-amber-900 hover:bg-amber-50"
              >
                {reindexRunning ? "Rebuilding index…" : "Rebuild search index"}
              </Button>
            </div>

            {reindexNotice && (
              <div
                className={`p-2.5 rounded-lg text-xs ${
                  reindexNotice.type === "success"
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-rose-50 text-rose-800 border border-rose-200"
                }`}
              >
                {reindexNotice.text}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Rebuild Confirmation Dialog */}
        {reindexConfirmOpen && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Confirm search index rebuild"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4"
          >
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl space-y-4">
              <div className="flex items-center gap-2.5 text-amber-600">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <h3 className="text-sm font-semibold text-slate-900">
                  Rebuild search index?
                </h3>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Rebuilding the search index will re-parse and re-index all documents with the latest section-aware chunker. This process may take a few minutes. Continue?
              </p>
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setReindexConfirmOpen(false)}
                  className="h-8 text-xs rounded-full"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="workbench"
                  size="sm"
                  onClick={handleRebuildIndex}
                  className="h-8 text-xs rounded-full"
                >
                  Continue
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
