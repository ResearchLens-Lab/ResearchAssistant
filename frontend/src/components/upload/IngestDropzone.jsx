"use client";

import React, { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { papersService } from "@/services/papers.service";
import { documentsService } from "@/services/documents.service";
import { Button } from "@/components/ui/button";
import { IngestPipelineVisualizer } from "./IngestPipelineVisualizer";
import { DocumentProcessingProgress } from "@/components/papers/DocumentProcessingProgress";
import { CreatePaperModal } from "@/components/papers/CreatePaperModal";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  ArrowRight,
  Plus,
  X,
  FolderPlus,
  CheckCircle2,
  FolderOpen,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import {
  batchIngestStatus,
  validateUploadFiles,
  mergeUploadFiles,
  formatUploadSize,
  MAX_UPLOAD_BATCH_SIZE_BYTES,
  MAX_UPLOAD_BATCH_FILES,
  isRetryableIngestionError,
} from "@/lib/researchWorkspace.mjs";

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
  const [dragActive, setDragActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [ingestStatus, setIngestStatus] = useState(null);
  const [chunkCount, setChunkCount] = useState(null);
  const [uploadResults, setUploadResults] = useState([]);
  const [uploadFailures, setUploadFailures] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const existingPapersQuery = useQuery({
    queryKey: ["papers", 1, 100],
    queryFn: () => papersService.list(1, 100),
    staleTime: 1000 * 30,
  });

  const selectedProject = existingPapersQuery.data?.items?.find((p) => p.id === targetPaperId) || null;

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
      const activePaperId = targetPaperId || cancelledDoc?.paper_id;
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

  const ingestMutation = useMutation({
    mutationFn: async (filesToUpload = files) => {
      if (!targetPaperId) {
        throw new Error("Please select or create a research project first.");
      }
      if (!filesToUpload.length) {
        throw new Error("Select at least one document to upload.");
      }

      setIngestStatus("processing");
      setUploadProgress({ loaded: 0, total: 0, percent: 0 });
      if (filesToUpload.length === files.length) {
        setUploadResults([]);
        setUploadFailures([]);
      }

      const abortController = new AbortController();
      uploadAbortControllerRef.current = abortController;

      // Upload Documents & Ingest to RAG
      const batch = await documentsService.uploadBatch(
        filesToUpload,
        targetPaperId,
        setUploadProgress,
        abortController.signal
      );
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
      if (failed.length) {
        setErrorMessage(`${failed.length} file(s) failed: ${failed.map((f) => f.filename).join(", ")}`);
      }

      return { paperId: targetPaperId, docs, failures: failed };
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      const paperId = result?.paperId || targetPaperId;
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
      setErrorMessage(err.message || "Failed to ingest documents into the research vectorstore.");
    },
  });

  const liveDocumentsQuery = useQuery({
    queryKey: ["paperDocuments", targetPaperId],
    queryFn: () => papersService.getDocuments(targetPaperId),
    enabled: !!targetPaperId,
    refetchInterval: (query) =>
      Boolean(
        ingestMutation?.isPending ||
        retryMutation?.isPending ||
        query.state.data?.some(
          (document) => document.processing_status === "processing" || document.processing_status === "uploaded"
        )
      )
        ? 2000
        : false,
  });

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
      setErrorMessage(`The selection exceeds the ${MAX_UPLOAD_BATCH_FILES} file limit. Please remove files before adding more.`);
    } else {
      setFiles(merged);
    }
  };

  const handleRemoveFile = (targetFile) => {
    setErrorMessage(null);
    setFiles((current) =>
      current.filter(
        (item) => !(item.name === targetFile.name && item.size === targetFile.size && item.lastModified === targetFile.lastModified)
      )
    );
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

  const retryableFailureNames = new Set([
    ...uploadFailures.filter((failure) => isRetryableIngestionError(failure.error)).map((failure) => failure.filename),
    ...uploadResults.filter((doc) => doc.processing_status === "failed" && isRetryableIngestionError(doc.processing_error)).map((doc) => doc.filename),
  ]);

  const totalQueueSize = files.reduce((sum, item) => sum + (item.size || 0), 0);

  return (
    <div className="page-shell mx-auto max-w-4xl space-y-6">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs font-medium text-zinc-500">
        <Link href="/papers" className="hover:text-[var(--rl-primary)] transition-colors">
          Library
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-zinc-400" />
        <span className="text-zinc-900 font-semibold dark:text-zinc-100">Add sources</span>
      </nav>

      {/* Main Page Heading */}
      <div className="space-y-1.5 border-b border-zinc-200/80 pb-5 dark:border-zinc-800">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          Add research sources
        </h1>
        <p className="text-xs text-zinc-600 leading-relaxed max-w-2xl dark:text-zinc-400">
          Upload the papers and documents you want to study. Choose an existing project or create a new one to keep everything organized.
        </p>
      </div>

      {/* Section A: Choose a Project */}
      <section className="rounded-xl border border-zinc-200/90 bg-white p-5 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.04)] space-y-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Choose a project
            </h2>
            <p className="text-xs text-zinc-500">
              Select where these documents should be saved.
            </p>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setIsCreateModalOpen(true)}
            className="h-8 gap-1.5 px-3 text-xs font-semibold text-zinc-700 hover:text-zinc-900 shadow-2xs dark:text-zinc-200"
          >
            <Plus className="h-3.5 w-3.5 text-[var(--rl-primary)]" />
            <span>Create a new project</span>
          </Button>
        </div>

        {/* Project Selector or Selected Project Context */}
        {selectedProject ? (
          <div className="rounded-lg border border-sky-200 bg-sky-50/60 p-4 space-y-2 dark:border-sky-900/60 dark:bg-sky-950/20">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4 text-[var(--rl-primary)] shrink-0" />
                <span className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                  {selectedProject.title}
                </span>
              </div>
              <button
                type="button"
                onClick={() => router.replace("/papers/upload")}
                className="text-xs font-semibold text-[var(--rl-primary)] hover:underline shrink-0"
              >
                Change project
              </button>
            </div>
            {selectedProject.description ? (
              <p className="text-xs text-zinc-600 line-clamp-2 dark:text-zinc-300">
                {selectedProject.description}
              </p>
            ) : selectedProject.abstract ? (
              <p className="text-xs text-zinc-600 line-clamp-2 dark:text-zinc-300">
                {selectedProject.abstract}
              </p>
            ) : (
              <p className="text-xs italic text-zinc-400">No description provided yet.</p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <select
              id="project-selector"
              value={targetPaperId || ""}
              onChange={(e) => {
                const val = e.target.value;
                if (val) {
                  router.replace(`/papers/upload?paper_id=${encodeURIComponent(val)}`);
                } else {
                  router.replace("/papers/upload");
                }
              }}
              className="w-full rounded-lg border border-zinc-200 bg-white p-2.5 text-xs font-medium text-zinc-900 shadow-2xs outline-none transition-colors hover:border-zinc-300 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 dark:border-zinc-800 dark:bg-zinc-850 dark:text-zinc-100"
            >
              <option value="">-- Select an existing research project --</option>
              {existingPapersQuery.data?.items?.map((proj) => (
                <option key={proj.id} value={proj.id}>
                  {proj.title}
                  {proj.description ? ` (${proj.description.slice(0, 50)}...)` : ""}
                </option>
              ))}
            </select>
            {!targetPaperId && (
              <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200/80 rounded-md p-2 dark:bg-amber-950/30 dark:border-amber-900/50 dark:text-amber-300">
                Please select an existing project from the dropdown or click <strong>Create a new project</strong> above.
              </p>
            )}
          </div>
        )}
      </section>

      {/* Hidden File Input */}
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

      {/* Section B: Document Upload Dropzone */}
      <section className="space-y-4">
        {files.length > 0 ? (
          /* Section C: Upload Queue */
          <div className="rounded-xl border border-zinc-200/90 bg-white p-5 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.04)] space-y-4 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 pb-3 dark:border-zinc-800">
              <div>
                <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                  Upload queue ({files.length} {files.length === 1 ? "file" : "files"} · {formatUploadSize(totalQueueSize)})
                </h2>
                <p className="text-xs text-zinc-500">
                  {ingestMutation.isPending
                    ? "Uploading and indexing your sources…"
                    : "Review your selected documents before indexing. Click × to remove a file."}
                </p>
              </div>

              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={ingestMutation.isPending}
                onClick={() => fileInputRef.current?.click()}
                className="h-8 gap-1.5 px-3 text-xs font-semibold"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Add more files</span>
              </Button>
            </div>

            {/* Live Upload Byte Progress Bar */}
            {ingestMutation.isPending && uploadProgress?.total > 0 && (
              <div className="rounded-lg bg-sky-50 border border-sky-100 p-3 space-y-1.5 dark:bg-sky-950/30 dark:border-sky-900">
                <div className="flex items-center justify-between text-xs text-sky-900 dark:text-sky-200">
                  <span className="font-semibold">Uploading document batch</span>
                  <span className="font-mono tabular-nums">
                    {uploadProgress.percent}% · {(uploadProgress.loaded / (1024 * 1024)).toFixed(1)} / {(uploadProgress.total / (1024 * 1024)).toFixed(1)} MB
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-sky-200 dark:bg-sky-900">
                  <div
                    className="h-full bg-[var(--rl-primary)] transition-all duration-300"
                    style={{ width: `${uploadProgress.percent}%` }}
                  />
                </div>
              </div>
            )}

            {/* Queue Item Rows */}
            <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200/80 overflow-hidden dark:divide-zinc-800 dark:border-zinc-800">
              {files.map((queuedFile) => {
                const backendDoc = liveDocumentsQuery.data?.find(
                  (doc) => doc.filename === queuedFile.name && (doc.file_size === queuedFile.size || !doc.file_size)
                );
                const isProcessing = backendDoc && ["processing", "uploaded"].includes(backendDoc.processing_status);
                const isCancelled = backendDoc?.processing_status === "cancelled";
                const isCancelling = cancelMutation.isPending && cancelMutation.variables === backendDoc?.id;

                return (
                  <li
                    key={`${queuedFile.name}:${queuedFile.size}:${queuedFile.lastModified}`}
                    className="flex items-center gap-3 p-3 bg-white text-xs hover:bg-zinc-50/50 transition-colors dark:bg-zinc-900 dark:hover:bg-zinc-850"
                  >
                    <FileText className="h-4 w-4 shrink-0 text-[var(--rl-primary)]" />
                    <span className="min-w-0 flex-1 truncate font-medium text-zinc-800 dark:text-zinc-200" title={queuedFile.name}>
                      {queuedFile.name}
                    </span>
                    <span className="shrink-0 text-[11px] font-mono text-zinc-400">
                      {formatUploadSize(queuedFile.size)} · {queuedFile.name.split(".").pop()?.toUpperCase()}
                    </span>

                    {(ingestMutation.isPending || isProcessing) && (
                      backendDoc ? (
                        <div className="w-48">
                          <DocumentProcessingProgress compact document={backendDoc} />
                        </div>
                      ) : (
                        <span className="shrink-0 text-[11px] font-semibold text-[var(--rl-primary)]">
                          {uploadProgress?.total ? `Uploading · ${uploadProgress.percent}%` : "Uploading"}
                        </span>
                      )
                    )}

                    {isCancelled ? (
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                        Cancelled
                      </span>
                    ) : isProcessing ? (
                      <button
                        type="button"
                        title="Cancel ingestion"
                        disabled={isCancelling}
                        onClick={() => cancelMutation.mutate(backendDoc.id)}
                        className="rounded p-1 text-zinc-400 hover:bg-rose-50 hover:text-rose-600 transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        title="Remove file"
                        disabled={ingestMutation.isPending}
                        onClick={() => handleRemoveFile(queuedFile)}
                        className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-rose-600 transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : (
          <div
            onDragEnter={() => setDragActive(true)}
            onDragLeave={() => setDragActive(false)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className={`flex min-h-52 flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all ${
              dragActive
                ? "border-sky-400 bg-sky-50/70 scale-[1.005]"
                : "border-zinc-200 bg-white hover:border-sky-300 hover:bg-sky-50/20 shadow-2xs dark:border-zinc-800 dark:bg-zinc-900"
            }`}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-50 text-[var(--rl-primary)] mb-3 shadow-2xs dark:bg-sky-950/40">
              <UploadCloud className="h-6 w-6" />
            </div>
            <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Add your documents
            </h2>
            <p className="mt-1 text-xs text-zinc-500 max-w-sm">
              Drag documents here or select files from your computer.
            </p>
            <p className="mt-1 text-[11px] text-zinc-400 font-mono">
              PDF, DOCX, TXT, Markdown, TeX, CSV, XLSX, PPTX, HTML, JSON, or ZIP · up to 100 MB per file
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="mt-4 h-9 px-4 text-xs font-semibold shadow-2xs"
            >
              Browse files
            </Button>
          </div>
        )}

        {/* File Format Validation Errors */}
        {fileErrors.length > 0 && (
          <ul role="alert" className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            {fileErrors.map(({ file: invalid, reason }) => (
              <li key={`${invalid.name}:${invalid.lastModified}`}>
                <strong>{invalid.name}:</strong> {reason}
              </li>
            ))}
          </ul>
        )}

        {/* Global Error Banner */}
        {errorMessage && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800"
          >
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Section E: Primary Action Button */}
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-zinc-500">
            {!targetPaperId
              ? "Select or create a project to enable upload."
              : !files.length
              ? "Add at least one document to proceed."
              : `${files.length} document(s) ready to index.`}
          </p>

          <Button
            type="button"
            onClick={() => ingestMutation.mutate()}
            disabled={
              !targetPaperId ||
              !files.length ||
              ingestMutation.isPending ||
              existingPapersQuery.isLoading
            }
            className="h-10 gap-2 px-5 text-xs font-semibold bg-[var(--rl-primary)] hover:bg-[#185ea8] text-white shadow-xs hover:shadow-sm hover:-translate-y-0.5 active:translate-y-0 transition-all focus-visible:ring-2 focus-visible:ring-sky-400 disabled:opacity-50"
          >
            {ingestMutation.isPending ? (
              <>
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Uploading & indexing sources…</span>
              </>
            ) : (
              <>
                <UploadCloud className="h-4 w-4" />
                <span>Add sources to project</span>
              </>
            )}
          </Button>
        </div>

        {/* Live Pipeline Visualizer & Success Card */}
        {ingestStatus && (
          <div className="space-y-4 pt-2">
            <IngestPipelineVisualizer
              status={ingestStatus}
              filename={file?.name || "paper.pdf"}
              chunkCount={chunkCount}
              fileSize={file?.size}
              error={errorMessage}
            />

            {ingestStatus === "indexed" && targetPaperId && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50/80 p-4 shadow-2xs">
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-900">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span>Sources successfully indexed and ready for research!</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" asChild className="h-8 text-xs font-semibold">
                    <Link href={`/papers/${targetPaperId}`}>
                      <span>View project sources</span>
                    </Link>
                  </Button>
                  <Button size="sm" asChild className="h-8 gap-1.5 text-xs font-semibold bg-[var(--rl-primary)] hover:bg-[#185ea8] text-white">
                    <Link href={`/chat?paper_id=${targetPaperId}`}>
                      <span>Open in Research Desk</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Project Creation Modal triggered from Add Sources */}
      <CreatePaperModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={async (payload) => {
          const created = await papersService.create(payload);
          return created;
        }}
        onSuccess={(createdProject) => {
          queryClient.invalidateQueries({ queryKey: ["papers"] });
          if (createdProject?.id) {
            router.replace(`/papers/upload?paper_id=${encodeURIComponent(createdProject.id)}`);
          }
        }}
      />
    </div>
  );
}
