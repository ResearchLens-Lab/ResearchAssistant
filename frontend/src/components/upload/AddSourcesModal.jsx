"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { UploadCloud, FileText, X, AlertCircle, Loader2, CheckCircle2 } from "lucide-react";
import { documentsService } from "@/services/documents.service";
import {
  validateUploadFiles,
  mergeUploadFiles,
  MAX_UPLOAD_BATCH_FILES,
  MAX_UPLOAD_BATCH_SIZE_BYTES,
  formatUploadSize,
} from "@/lib/researchWorkspace.mjs";
import { formatBytes } from "@/utils/formatters";
import { useQueryClient } from "@tanstack/react-query";

export function AddSourcesModal({
  isOpen,
  onClose,
  preselectedPaperId = null,
  papers = [],
  onSuccess,
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef(null);

  const [targetPaperId, setTargetPaperId] = useState(preselectedPaperId || "");
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState("idle"); // "idle" | "uploading" | "preparing"
  const [uploadProgress, setUploadProgress] = useState(null);
  const [formError, setFormError] = useState("");
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTargetPaperId(preselectedPaperId || (papers.length > 0 ? papers[0].id : ""));
      setFiles([]);
      setIsUploading(false);
      setUploadStage("idle");
      setUploadProgress(null);
      setFormError("");
    }
  }, [isOpen, preselectedPaperId, papers]);

  const handleClose = () => {
    setFiles([]);
    setFormError("");
    setIsUploading(false);
    setUploadStage("idle");
    onClose();
  };

  const handleFileSelect = (selectedFiles) => {
    setFormError("");
    const incoming = Array.from(selectedFiles || []);
    const acceptable = [];
    const rejected = [];

    incoming.forEach((candidate) => {
      const reason = validateUploadFiles([candidate]);
      if (reason) rejected.push({ file: candidate, reason });
      else acceptable.push(candidate);
    });

    if (rejected.length > 0) {
      setFormError(`${rejected.length} file(s) unsupported: ${rejected.map((r) => r.file.name).join(", ")}`);
    }

    const merged = mergeUploadFiles(files, acceptable);
    const totalSize = merged.reduce((sum, item) => sum + item.size, 0);

    if (merged.length > MAX_UPLOAD_BATCH_FILES || totalSize > MAX_UPLOAD_BATCH_SIZE_BYTES) {
      setFormError(`Selection exceeds batch limit (${MAX_UPLOAD_BATCH_FILES} files or 100 MB).`);
    } else {
      setFiles(merged);
    }
  };

  const handleRemoveFile = (targetFile) => {
    setFormError("");
    setFiles((current) =>
      current.filter(
        (f) => !(f.name === targetFile.name && f.size === targetFile.size && f.lastModified === targetFile.lastModified)
      )
    );
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) handleFileSelect(e.dataTransfer.files);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError("");

    if (!targetPaperId) {
      setFormError("Please select a target research project.");
      return;
    }
    if (files.length === 0) {
      setFormError("Please select at least one document to upload.");
      return;
    }

    setIsUploading(true);
    setUploadStage("uploading");
    setUploadProgress({ percent: 5 });

    try {
      const batch = await documentsService.uploadBatch(
        files,
        targetPaperId,
        (progress) => {
          setUploadProgress(progress);
          if (progress?.percent >= 100) {
            setUploadStage("preparing");
          } else {
            setUploadStage("uploading");
          }
        }
      );

      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      queryClient.invalidateQueries({ queryKey: ["paperDocuments", targetPaperId] });

      if (onSuccess) onSuccess(batch);
      handleClose();
    } catch (err) {
      setIsUploading(false);
      setUploadStage("idle");
      setFormError(err.message || "Failed to upload documents. Please try again.");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
      <DialogContent className="max-w-lg rounded-2xl border-zinc-200/90 bg-white p-6 shadow-[0_24px_64px_-16px_rgba(0,0,0,0.22)] font-serif dark:border-zinc-800 dark:bg-zinc-900">
        <DialogHeader className="space-y-1.5 pb-2 text-left">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-[#1d6fc4] shadow-2xs dark:bg-sky-950/50">
              <UploadCloud className="h-4.5 w-4.5" />
            </span>
            <DialogTitle className="text-xl font-bold tracking-tight text-zinc-900 font-serif dark:text-zinc-100">
              Add research sources
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-zinc-500 leading-relaxed font-serif dark:text-zinc-400">
            Select files to upload into your research vectorstore and index for citations.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="space-y-4 py-1 font-serif">
          {formError && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
              <span className="leading-snug">{formError}</span>
            </div>
          )}

          {/* Project Selection */}
          <div className="space-y-1.5">
            <label htmlFor="sources-target-project" className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
              Target research project <span className="text-rose-500">*</span>
            </label>
            <select
              id="sources-target-project"
              value={targetPaperId}
              onChange={(e) => {
                setTargetPaperId(e.target.value);
                if (formError) setFormError("");
              }}
              disabled={isUploading || papers.length === 0}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-800 shadow-2xs outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 font-serif dark:border-zinc-800 dark:bg-zinc-850 dark:text-zinc-200"
            >
              {papers.length === 0 ? (
                <option value="">No projects available</option>
              ) : (
                papers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Compact Dropzone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-all ${
              dragActive
                ? "border-sky-500 bg-sky-50/70"
                : "border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-300"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) handleFileSelect(e.target.files);
              }}
              accept=".pdf,.docx,.txt,.md,.tex,.csv,.xlsx,.pptx,.html,.json,.zip"
            />
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white border border-slate-200/90 text-sky-600 mb-2 shadow-2xs">
              <UploadCloud className="h-5 w-5" />
            </div>
            <p className="text-xs font-semibold text-slate-700">
              Drop documents here, or <span className="text-[#1d6fc4] underline">browse</span>
            </p>
            <p className="mt-1 text-[10px] text-slate-400">
              PDF, DOCX, TXT, Markdown, CSV, TeX · up to 100 MB per file
            </p>
          </div>

          {/* Selected Files Queue */}
          {files.length > 0 && (
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 px-0.5">
                <span>Selected documents ({files.length})</span>
                <span>{formatBytes(files.reduce((acc, f) => acc + f.size, 0))}</span>
              </div>
              {files.map((file, idx) => (
                <div
                  key={`${file.name}-${idx}`}
                  className="flex items-center justify-between gap-2 rounded-lg bg-white border border-slate-200/90 px-2.5 py-1.5 text-xs shadow-2xs"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <span className="truncate text-[11px] font-medium text-slate-700 max-w-[260px]" title={file.name}>
                      {file.name}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">({formatBytes(file.size)})</span>
                  </div>
                  {!isUploading && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveFile(file);
                      }}
                      className="text-slate-400 hover:text-rose-500 p-0.5"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs text-slate-600 font-medium">
                <span className="flex items-center gap-1.5">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#1d6fc4]" />
                  {uploadStage === "preparing" ? (
                    <span>Upload complete. Preparing document…</span>
                  ) : (
                    <span>Uploading document — {uploadProgress?.percent || 0}%</span>
                  )}
                </span>
                <span className="font-mono text-[11px]">{uploadProgress?.percent || 0}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full bg-[#1d6fc4] transition-all duration-300"
                  style={{ width: `${Math.min(100, uploadProgress?.percent || 10)}%` }}
                />
              </div>
              <p className="text-[10px] text-slate-500 italic">
                Your document will continue processing in the background. You can close this dialog at any time.
              </p>
            </div>
          )}

          <DialogFooter className="gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              className="h-9 px-4 text-xs font-semibold font-serif"
            >
              {isUploading ? "Continue in background" : "Cancel"}
            </Button>
            <Button
              type="submit"
              disabled={isUploading || files.length === 0}
              className="h-9 gap-1.5 px-5 text-xs font-semibold bg-[#1d6fc4] hover:bg-[#185ea8] text-white shadow-xs font-serif disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Processing…</span>
                </>
              ) : (
                <span>Add sources</span>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
