"use client";

import React, { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { papersService } from "@/services/papers.service";
import { documentsService } from "@/services/documents.service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { IngestPipelineVisualizer } from "./IngestPipelineVisualizer";
import { DocumentProcessingProgress } from "@/components/papers/DocumentProcessingProgress";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  Sparkles,
  ArrowRight,
  Plus,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  batchIngestStatus,
  validateUploadFiles,
  mergeUploadFiles,
  formatUploadSize,
  MAX_UPLOAD_BATCH_SIZE_BYTES,
  MAX_UPLOAD_BATCH_FILES,
  buildProjectCreatePayload,
  isRetryableIngestionError,
} from "@/lib/researchWorkspace.mjs";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

export function IngestDropzone() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetPaperId = searchParams.get("paper_id");
  const queryClient = useQueryClient();
  const fileInputRef = useRef(null);
  const uploadAbortControllerRef = useRef(null);

  const [files, setFiles] = useState([]);
  const file = files[0] || null;
  const [fileErrors, setFileErrors] = useState([]);
  const [title, setTitle] = useState("");

  const [dragActive, setDragActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [ingestStatus, setIngestStatus] = useState(null);
  const [createdPaperId, setCreatedPaperId] = useState(null);
  const [chunkCount, setChunkCount] = useState(null);
  const [uploadResults, setUploadResults] = useState([]);
  const [uploadFailures, setUploadFailures] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(null);

  const retryMutation = useMutation({
    mutationFn: documentsService.retry,
    onMutate: async (docId) => {
      setErrorMessage(null);
      setUploadResults((current) =>
        current.map((doc) =>
          doc.id === docId
            ? {
                ...doc,
                processing_status: "processing",
                processing_stage: "extracting_text",
                processing_progress: 0,
                processing_error: null,
                processing_started_at: new Date().toISOString(),
              }
            : doc
        )
      );
    },
    onSuccess: (document) => {
      setUploadResults((current) =>
        current.map((doc) => (doc.id === document.id ? { ...doc, ...document } : doc))
      );
      queryClient.invalidateQueries({ queryKey: ["paperDocuments", document.paper_id] });
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      queryClient.invalidateQueries({ queryKey: ["paper", document.paper_id] });
    },
    onError: (error) => {
      queryClient.invalidateQueries({ queryKey: ["paperDocuments"] });
      setErrorMessage(error.message || "Could not retry this source.");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async (docId) => {
      return await documentsService.cancel(docId);
    },
    onSuccess: (cancelledDoc) => {
      const activePaperId = createdPaperId || targetPaperId || cancelledDoc?.paper_id;
      if (activePaperId) {
        queryClient.invalidateQueries({ queryKey: ["paperDocuments", activePaperId] });
        queryClient.invalidateQueries({ queryKey: ["paper", activePaperId] });
      }
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      setUploadResults((current) =>
        current.map((doc) => (doc.id === cancelledDoc.id ? { ...doc, ...cancelledDoc } : doc))
      );
    },
    onError: (error) => setErrorMessage(error.message || "Could not cancel processing."),
  });

  const targetPaperQuery = useQuery({
    queryKey: ["paper", targetPaperId],
    queryFn: () => papersService.getById(targetPaperId),
    enabled: !!targetPaperId,
  });

  const existingPapersQuery = useQuery({
    queryKey: ["papers", 1, 50],
    queryFn: () => papersService.list(1, 50),
    enabled: !targetPaperId,
    staleTime: 1000 * 60 * 2,
  });

  useEffect(() => {
    if (targetPaperQuery.data && !title) setTitle(targetPaperQuery.data.title || "");
  }, [targetPaperQuery.data, title]);

  const handleFile = (selectedFiles) => {
    setErrorMessage(null);
    const incoming = Array.from(selectedFiles || []);
    const acceptable = [];
    const rejected = [];
    incoming.forEach((candidate) => {
      const reason = validateUploadFiles([candidate]);
      if (reason) rejected.push({ file: candidate, reason });
      else acceptable.push(candidate);
    });
    setFileErrors(rejected);
    const merged = mergeUploadFiles(files, acceptable);
    const total = merged.reduce((sum, candidate) => sum + candidate.size, 0);
    if (merged.length > MAX_UPLOAD_BATCH_FILES || total > MAX_UPLOAD_BATCH_SIZE_BYTES) {
      setErrorMessage(`The selection exceeds the ${MAX_UPLOAD_BATCH_FILES} file or batch limit. Remove files before adding more.`);
    } else {
      setFiles(merged);
    }
    if (!title && acceptable.length && !targetPaperId) {
      const cleanTitle = (acceptable[0]?.name || "").replace(/\.[^.]+$/, "").replace(/[_-]/g, " ");
      setTitle(cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1));
    }
  };

  const handleRemoveFile = (targetFile) => {
    setErrorMessage(null);
    setFiles((current) => {
      const remaining = current.filter(
        (item) => !(item.name === targetFile.name && item.size === targetFile.size && item.lastModified === targetFile.lastModified)
      );
      if (remaining.length === 0 && !targetPaperId) {
        setTitle("");
      }
      return remaining;
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) handleFile(e.dataTransfer.files);
  };

  const ingestMutation = useMutation({
    mutationFn: async (filesToUpload = files) => {
      if (!filesToUpload.length || (!targetPaperId && !title.trim())) {
        throw new Error("Select at least one document and provide a project title.");
      }

      setIngestStatus("processing");
      setUploadProgress({ loaded: 0, total: 0, percent: 0 });
      if (filesToUpload.length === files.length) {
        setUploadResults([]);
        setUploadFailures([]);
      }

      // Create only the project container fields. Source metadata belongs to each document.
      const paper = targetPaperId
        ? targetPaperQuery.data || await papersService.getById(targetPaperId)
        : createdPaperId ? await papersService.getById(createdPaperId) : await papersService.create(buildProjectCreatePayload(title));

      setCreatedPaperId(paper.id);
      if (!targetPaperId) router.replace(`/papers/upload?paper_id=${encodeURIComponent(paper.id)}`);

      const abortController = new AbortController();
      uploadAbortControllerRef.current = abortController;

      // 2. Upload Document & Ingest to RAG
      const batch = await documentsService.uploadBatch(filesToUpload, paper.id, setUploadProgress, abortController.signal);
      setUploadProgress(null);
      const docs = batch.documents || [];
      const failed = batch.failures || [];
      setUploadResults((current) => [
        ...current.filter((document) => !filesToUpload.some((uploadFile) => uploadFile.name === document.filename)),
        ...docs,
      ]);
      setUploadFailures(failed);
      setChunkCount(docs.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0) || null);
      setIngestStatus(batchIngestStatus(docs, failed));
      if (failed.length) setErrorMessage(`${failed.length} file(s) failed: ${failed.map((f) => f.filename).join(", ")}`);

      return { paper, docs, failures: failed };
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      const paperId = result?.paper?.id || createdPaperId || targetPaperId;
      const failedNames = new Set([
        ...(result?.failures || []).map((failure) => failure.filename),
        ...(result?.docs || []).filter((doc) => doc.processing_status === "failed").map((doc) => doc.filename),
      ]);
      const completedNames = new Set((result?.docs || []).map((doc) => doc.filename));
      setFiles((current) => current.filter((candidate) => failedNames.has(candidate.name) || !completedNames.has(candidate.name)));
      if (paperId) {
        queryClient.invalidateQueries({ queryKey: ["paperDocuments", paperId] });
        queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
      }
    },
    onError: (err) => {
      setIngestStatus("failed");
      setUploadProgress(null);
      setErrorMessage(err.message || "Failed to ingest paper into RAG vectorstore.");
    },
  });

  const liveDocumentsQuery = useQuery({
    queryKey: ["paperDocuments", createdPaperId || targetPaperId],
    queryFn: () => papersService.getDocuments(createdPaperId || targetPaperId),
    enabled: !!(createdPaperId || targetPaperId),
    refetchInterval: (query) =>
      ingestMutation.isPending ||
      retryMutation.isPending ||
      query.state.data?.some(
        (document) => document.processing_status === "processing" || document.processing_status === "uploaded"
      )
        ? 1500
        : false,
  });

  const retryableFailureNames = new Set([
    ...uploadFailures.filter((failure) => isRetryableIngestionError(failure.error)).map((failure) => failure.filename),
    ...uploadResults.filter((doc) => doc.processing_status === "failed" && isRetryableIngestionError(doc.processing_error)).map((doc) => doc.filename),
  ]);

  const totalQueueSize = files.reduce((sum, item) => sum + (item.size || 0), 0);

  return (
    <div className="page-shell mx-auto grid max-w-5xl grid-cols-1 gap-6">
      {/* Left 2 Columns: Dropzone & Metadata */}
      <div className="lg:col-span-2 space-y-6">
        <div className="space-y-1">
          <p className="eyebrow text-[var(--rl-primary)]">Research Library</p>
          <h1 className="page-heading">{targetPaperId ? "Add sources to project" : "Create a research project"}</h1>
          <p className="page-description">
            {targetPaperId
              ? "Add files to the selected project. Each source keeps its own processing status and citations."
              : "Choose a project title and add the documents you want to research. Each source keeps its own processing status and citations."}
          </p>
        </div>

        {targetPaperId && targetPaperQuery.isError && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {targetPaperQuery.error?.message || "This project could not be loaded."}
          </div>
        )}

        {targetPaperId && targetPaperQuery.data && (
          <div className="flex items-center gap-2 rounded-xl border border-[var(--rl-border)] bg-white px-4 py-3 text-sm">
            <span className="text-[var(--rl-muted)]">Adding sources to</span>
            <span className="min-w-0 flex-1 truncate font-medium text-[var(--rl-ink)]">{targetPaperQuery.data.title}</span>
            <Button type="button" variant="ghost" size="sm" onClick={() => router.replace("/papers/upload")}>
              Change project
            </Button>
          </div>
        )}

        {!targetPaperId && existingPapersQuery.data?.items?.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--rl-border)] bg-white px-4 py-3">
            <label htmlFor="upload-project" className="text-sm font-medium text-[var(--rl-ink)]">
              Add to an existing project
            </label>
            <select
              id="upload-project"
              defaultValue=""
              onChange={(event) =>
                router.replace(event.target.value ? `/papers/upload?paper_id=${encodeURIComponent(event.target.value)}` : "/papers/upload")
              }
              className="min-h-10 min-w-0 flex-1 rounded-lg border border-[var(--rl-border)] bg-white px-3 text-sm text-[var(--rl-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)]"
            >
              <option value="">Create a new project instead</option>
              {existingPapersQuery.data.items.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.title}
                </option>
              ))}
            </select>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          aria-label="Choose source documents"
          accept=".pdf,.docx,.txt,.md,.markdown,.tex,.csv,.xlsx,.pptx,.html,.htm,.json,.zip"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) handleFile(e.target.files);
            e.target.value = "";
          }}
        />

        {files.length ? (
          <section aria-label="Selected source files" className="rounded-xl border border-[var(--rl-border)] bg-white p-4 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-[var(--rl-ink)]">
                  Upload queue{" "}
                  <span className="text-[var(--rl-muted)]">
                    ({files.length} {files.length === 1 ? "file" : "files"} · {formatUploadSize(totalQueueSize)})
                  </span>
                </h2>
                <p className="text-xs text-[var(--rl-muted)]">
                  {ingestMutation.isPending
                    ? "Uploading and indexing your sources…"
                    : "Files stay here until they upload successfully. Click × on any file to remove it."}
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={ingestMutation.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Add files
              </Button>
            </div>

            {ingestMutation.isPending && uploadProgress?.total > 0 && (
              <div className="mb-3 rounded-lg bg-sky-50 p-3" aria-live="polite">
                <div className="mb-1.5 flex items-center justify-between gap-2 text-xs text-sky-900">
                  <span className="font-medium">Uploading files</span>
                  <span className="tabular-nums">
                    {uploadProgress.percent}% · {(uploadProgress.loaded / (1024 * 1024)).toFixed(1)} / {(uploadProgress.total / (1024 * 1024)).toFixed(1)} MB
                  </span>
                </div>
                <div
                  role="progressbar"
                  aria-label="Batch upload progress"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={uploadProgress.percent}
                  className="h-2 overflow-hidden rounded-full bg-sky-100"
                >
                  <div
                    className="h-full rounded-full bg-sky-500 transition-[width] duration-300"
                    style={{ width: `${uploadProgress.percent}%` }}
                  />
                </div>
                <p className="mt-1 text-[10px] text-sky-800">
                  Upload percentage is measured from bytes sent. Processing progress appears per source after upload.
                </p>
              </div>
            )}

            <ul className="divide-y divide-[var(--rl-border)] rounded-lg border border-[var(--rl-border)]">
              {files.map((queuedFile) => {
                const backendDoc = liveDocumentsQuery.data?.find(
                  (doc) => doc.filename === queuedFile.name && (doc.file_size === queuedFile.size || !doc.file_size)
                );
                const isProcessing = backendDoc && ["processing", "uploaded"].includes(backendDoc.processing_status);
                const isCancelling = cancelMutation.isPending && cancelMutation.variables === backendDoc?.id;
                const isCancelled = backendDoc?.processing_status === "cancelled";

                return (
                  <li
                    key={`${queuedFile.name}:${queuedFile.size}:${queuedFile.lastModified}`}
                    className="flex items-center gap-3 px-3 py-2.5"
                  >
                    <FileText className="h-4 w-4 shrink-0 text-[var(--rl-primary)]" />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--rl-ink)]" title={queuedFile.name}>
                      {queuedFile.name}
                    </span>
                    <span className="shrink-0 text-xs text-[var(--rl-muted)]">
                      {formatUploadSize(queuedFile.size)} - {queuedFile.name.split(".").pop()?.toUpperCase()}
                    </span>

                    {(ingestMutation.isPending || isProcessing) && (
                      backendDoc ? (
                        <div className="w-48">
                          <DocumentProcessingProgress compact document={backendDoc} />
                        </div>
                      ) : (
                        <span className="shrink-0 text-[11px] font-medium text-[var(--rl-primary)]" role="status">
                          {uploadProgress?.total ? `Uploading · ${uploadProgress.percent}%` : "Uploading"}
                        </span>
                      )
                    )}

                    {isCancelled ? (
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800">Cancelled</span>
                        <button
                          type="button"
                          title="Dismiss"
                          aria-label={`Dismiss ${queuedFile.name}`}
                          onClick={() => handleRemoveFile(queuedFile)}
                          className="rounded p-1 text-[var(--rl-muted)] hover:bg-slate-100 hover:text-rose-700 transition-colors"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ) : isProcessing ? (
                      <button
                        type="button"
                        title="Cancel ingestion"
                        aria-label={`Cancel ingestion for ${queuedFile.name}`}
                        disabled={isCancelling}
                        onClick={() => cancelMutation.mutate(backendDoc.id)}
                        className="rounded p-1 text-[var(--rl-muted)] hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40 transition-colors"
                      >
                        {isCancelling ? (
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-rose-500 border-t-transparent" />
                        ) : (
                          <X className="h-4 w-4" />
                        )}
                      </button>
                    ) : ingestMutation.isPending ? (
                      <button
                        type="button"
                        title="Cancel upload"
                        aria-label={`Cancel upload for ${queuedFile.name}`}
                        onClick={() => {
                          if (uploadAbortControllerRef.current) {
                            uploadAbortControllerRef.current.abort();
                          }
                          handleRemoveFile(queuedFile);
                        }}
                        className="rounded p-1 text-[var(--rl-muted)] hover:bg-rose-50 hover:text-rose-600 transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        title="Remove file"
                        aria-label={`Remove ${queuedFile.name}`}
                        onClick={() => handleRemoveFile(queuedFile)}
                        className="rounded p-1 text-[var(--rl-muted)] hover:bg-slate-100 hover:text-rose-700 transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : (
          <div
            onDragEnter={() => setDragActive(true)}
            onDragLeave={() => setDragActive(false)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className={`flex min-h-48 flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
              dragActive ? "border-[var(--rl-sky)] bg-[var(--rl-selected)]" : "border-[var(--rl-border)] bg-white hover:border-[var(--rl-sky)] hover:bg-[var(--rl-tint)]"
            }`}
          >
            <UploadCloud className="mb-2 h-9 w-9 text-[var(--rl-primary)]" />
            <p className="text-sm font-semibold text-[var(--rl-ink)]">Drop research documents here, or browse</p>
            <p className="mt-1 text-xs text-[var(--rl-muted)]">
              PDF, DOCX, TXT, Markdown, TeX, CSV, XLSX, PPTX, HTML, JSON, ZIP - up to 1 GiB per file
            </p>
            <Button type="button" variant="soft" size="sm" onClick={() => fileInputRef.current?.click()} className="mt-3">
              Browse files
            </Button>
          </div>
        )}

        {fileErrors.length > 0 && (
          <ul role="alert" className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            {fileErrors.map(({ file: invalid, reason }) => (
              <li key={`${invalid.name}:${invalid.lastModified}`}>
                <strong>{invalid.name}:</strong> {reason}
              </li>
            ))}
          </ul>
        )}

        {/* Paper Metadata Form */}
        {!targetPaperId && (
          <div className="surface-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-[var(--rl-ink)]">Project details</h3>

            <div className="space-y-1">
              <label className="text-sm font-medium text-[var(--rl-ink)]">
                Project title <span className="text-red-500">*</span>
              </label>
              <Input
                placeholder="Algorithms"
                maxLength={500}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
          </div>
        )}

        {errorMessage && (
          <div role="alert" className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2.5 text-xs text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2">
          {!targetPaperId && <span className="text-[11px] text-zinc-400">Creates a project and adds its sources</span>}

          <Button
            type="button"
            variant="workbench"
            onClick={() => ingestMutation.mutate()}
            disabled={!files.length || (!targetPaperId && !title.trim()) || (targetPaperId && targetPaperQuery.isLoading) || targetPaperQuery.isError || ingestMutation.isPending}
            className="gap-1.5 px-4"
          >
            {ingestMutation.isPending ? (
              <>
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Ingesting to RAG...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                <span>{targetPaperId ? "Add and index sources" : "Create project and add sources"}</span>
              </>
            )}
          </Button>
        </div>

        {/* Live Ingestion Pipeline Result */}
        {ingestStatus && (
          <div className="space-y-3">
            <IngestPipelineVisualizer
              status={ingestStatus}
              filename={file?.name || "paper.pdf"}
              chunkCount={chunkCount}
              fileSize={file?.size}
              error={errorMessage}
            />

            {(uploadResults.length > 0 || uploadFailures.length > 0) && (
              <section aria-label="Per-file processing results" className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <h3 className="border-b border-slate-100 px-3 py-2 text-xs font-semibold text-slate-800">File processing results</h3>
                <ul className="divide-y divide-slate-100">
                  {uploadResults.map((rawDoc) => {
                    const doc = liveDocumentsQuery.data?.find((d) => d.id === rawDoc.id) || rawDoc;
                    const isRetrying = retryMutation.isPending && retryMutation.variables === doc.id;
                    const isProcessing = ["processing", "uploaded"].includes(doc.processing_status) || isRetrying;

                    return (
                      <li key={doc.id} className="space-y-1.5 p-3 text-xs">
                        <div className="flex flex-wrap items-center gap-2">
                          <FileText className="h-3.5 w-3.5 text-slate-400" />
                          <span className="min-w-0 flex-1 truncate font-medium text-slate-800" title={doc.filename}>
                            {doc.filename}
                          </span>
                          <span
                            className={`rounded px-1.5 py-0.5 font-medium capitalize ${
                              doc.processing_status === "indexed"
                                ? "bg-emerald-50 text-emerald-800"
                                : doc.processing_status === "failed" && !isRetrying
                                ? "bg-rose-50 text-rose-800"
                                : doc.processing_status === "cancelled"
                                ? "bg-amber-50 text-amber-800"
                                : "bg-sky-50 text-sky-800"
                            }`}
                          >
                            {isRetrying ? "Retrying…" : doc.processing_status}
                          </span>
                          {doc.chunk_count != null && doc.chunk_count > 0 && (
                            <span className="text-[10px] text-slate-500">{doc.chunk_count} chunks</span>
                          )}
                          {doc.processing_status === "failed" && !isRetrying && (
                            <Button
                              type="button"
                              variant="soft"
                              size="sm"
                              disabled={retryMutation.isPending}
                              onClick={() => retryMutation.mutate(doc.id)}
                              className="h-7 text-[10px]"
                            >
                              Retry source
                            </Button>
                          )}
                          {isRetrying && (
                            <div className="flex items-center gap-1.5 text-xs text-[var(--rl-primary)]">
                              <div className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--rl-primary)] border-t-transparent" />
                              <span className="font-medium">Retrying source…</span>
                            </div>
                          )}
                          {["processing", "uploaded"].includes(doc.processing_status) && !isRetrying && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={cancelMutation.isPending && cancelMutation.variables === doc.id}
                              onClick={() => cancelMutation.mutate(doc.id)}
                              className="h-7 text-[10px] text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                            >
                              {cancelMutation.isPending && cancelMutation.variables === doc.id ? "Cancelling…" : "Cancel ingestion"}
                            </Button>
                          )}
                        </div>

                        {/* If actively processing or retrying, render live progress bar with countdown */}
                        {isProcessing && (
                          <div className="pt-1">
                            <DocumentProcessingProgress compact document={doc} />
                          </div>
                        )}

                        {/* Error message only displayed when not retrying or actively processing */}
                        {doc.processing_error && !isProcessing && (
                          <p className="pl-5 text-[11px] text-rose-700">{doc.processing_error}</p>
                        )}
                      </li>
                    );
                  })}
                  {uploadFailures.map((failure, index) => (
                    <li key={`${failure.filename}-${index}`} className="flex flex-wrap gap-2 px-3 py-2 text-xs text-rose-800">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      <span className="font-medium">{failure.filename}</span>
                      <span className="basis-full pl-5 text-[11px]">{failure.error}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {retryableFailureNames.size > 0 && (
              <Button
                type="button"
                variant="soft"
                size="sm"
                disabled={ingestMutation.isPending}
                onClick={() => {
                  ingestMutation.mutate(files.filter((candidate) => retryableFailureNames.has(candidate.name)));
                }}
              >
                Retry failed files
              </Button>
            )}

            {ingestStatus === "indexed" && createdPaperId && (
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" asChild className="gap-1">
                  <Link href={`/papers/${createdPaperId}`}>
                    <span>Open project</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </Button>

                <Button variant="workbench" size="sm" asChild className="gap-1">
                  <Link href={`/chat?paper_id=${createdPaperId}`}>
                    <span>Ask in Research Desk</span>
                  </Link>
                </Button>
              </div>
            )}
          </div>
        )}

        {targetPaperId && !ingestStatus && !liveDocumentsQuery.isError && liveDocumentsQuery.data?.length > 0 && (
          <section aria-label="Saved project sources" className="space-y-3 rounded-xl border border-[var(--rl-border)] bg-white p-4 shadow-sm">
            <div>
              <h2 className="text-sm font-semibold text-[var(--rl-ink)]">Saved sources</h2>
              <p className="text-xs text-[var(--rl-muted)]">Processing state and elapsed time are saved with the project.</p>
            </div>
            <ul className="divide-y divide-[var(--rl-border)] rounded-lg border border-[var(--rl-border)]">
              {liveDocumentsQuery.data.map((document) => {
                const isRetrying = retryMutation.isPending && retryMutation.variables === document.id;
                const isProcessing = ["processing", "uploaded"].includes(document.processing_status) || isRetrying;

                return (
                  <li key={document.id} className="space-y-2 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <FileText className="h-4 w-4 text-[var(--rl-primary)]" />
                      <span className="min-w-0 flex-1 truncate text-xs font-medium text-[var(--rl-ink)]">{document.filename}</span>
                      <span className="text-xs capitalize text-[var(--rl-muted)]">
                        {document.processing_status === "indexed" ? "Ready" : isRetrying ? "Retrying…" : document.processing_status}
                      </span>
                      {document.processing_status === "failed" && !isRetrying && (
                        <Button
                          type="button"
                          variant="soft"
                          size="sm"
                          disabled={retryMutation.isPending}
                          onClick={() => retryMutation.mutate(document.id)}
                        >
                          Retry source
                        </Button>
                      )}
                      {isRetrying && (
                        <div className="flex items-center gap-1.5 text-xs text-[var(--rl-primary)]">
                          <div className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--rl-primary)] border-t-transparent" />
                          <span className="font-medium">Retrying…</span>
                        </div>
                      )}
                      {["processing", "uploaded"].includes(document.processing_status) && !isRetrying && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={cancelMutation.isPending && cancelMutation.variables === document.id}
                          onClick={() => cancelMutation.mutate(document.id)}
                          className="text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                        >
                          {cancelMutation.isPending && cancelMutation.variables === document.id ? "Cancelling…" : "Cancel"}
                        </Button>
                      )}
                    </div>
                    {isProcessing ? (
                      <DocumentProcessingProgress document={document} />
                    ) : (
                      document.processing_error && <p role="alert" className="text-xs text-rose-700">{document.processing_error}</p>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>

      {/* Right 1 Column: RAG Configuration Inspector */}
    </div>
  );
}
