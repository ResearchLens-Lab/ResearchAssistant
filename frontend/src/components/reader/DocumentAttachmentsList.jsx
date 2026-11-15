"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { FileText, Plus, RefreshCw } from "lucide-react";
import { formatBytes, formatDate } from "@/utils/formatters";
import { DocumentProcessingProgress } from "@/components/papers/DocumentProcessingProgress";
import { documentsService } from "@/services/documents.service";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";

export function DocumentAttachmentsList({
  documents,
  isLoading,
  isError = false,
  error,
  onRetry,
  onAddSource,
}) {
  const queryClient = useQueryClient();
  const retryMutation = useMutation({
    mutationFn: documentsService.retry,
    onSuccess: (document) => {
      queryClient.invalidateQueries({ queryKey: ["paperDocuments", document.paper_id] });
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
    },
  });
  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-5 space-y-3 font-serif shadow-2xs">
      <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-[#1d6fc4]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 font-serif">
            Project sources {isLoading ? "(loading)" : isError ? "(unavailable)" : `(${documents.length})`}
          </h3>
        </div>

        {onAddSource && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onAddSource}
            className="h-7 text-xs font-serif text-[#1d6fc4] hover:bg-sky-50 px-2.5 gap-1 rounded-full"
          >
            <Plus className="h-3 w-3 stroke-[2.2]" />
            <span>Add source</span>
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="h-16 rounded-xl bg-slate-100 animate-pulse" />
      ) : isError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-800">
          <p>{error?.message || "Project sources could not be loaded."}</p>
          <button type="button" onClick={onRetry} className="mt-2 font-medium underline underline-offset-2">Retry</button>
        </div>
      ) : documents.length === 0 ? (
        <div className="py-6 text-center text-slate-400 space-y-2">
          <p className="text-sm font-medium text-slate-700 font-serif">No sources added yet</p>
          <p className="text-[11px] text-slate-400 font-serif max-w-xs mx-auto">
            Upload PDF, DOCX, or text files to index citations and ground your research synthesis.
          </p>
          {onAddSource && (
            <Button
              size="sm"
              variant="outline"
              onClick={onAddSource}
              className="mt-2 h-7 text-xs font-serif rounded-full border-sky-200 text-[#1d6fc4] hover:bg-sky-50"
            >
              <Plus className="h-3 w-3 mr-1" />
              <span>Add your first source</span>
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
          {retryMutation.isError && <p role="alert" className="text-xs text-rose-700">{retryMutation.error?.message || "Could not retry the source."}</p>}
          {documents.map((doc) => {
            const isIndexed = doc.processing_status === "indexed";
            const isFailed = doc.processing_status === "failed";
            const isProcessing = doc.processing_status === "processing" || doc.processing_status === "uploaded";

            return (
              <div
                key={doc.id}
                className="space-y-2 rounded-xl border border-slate-100 bg-slate-50/60 p-3 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-sky-100 bg-white text-[#1d6fc4] shadow-2xs">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 space-y-0.5">
                      <p className="truncate text-xs font-semibold text-slate-900 font-serif" title={doc.filename}>{doc.filename}</p>
                      <p className="font-mono text-[10px] text-slate-400">{formatBytes(doc.file_size)} · Uploaded {formatDate(doc.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {doc.chunk_count && <span className="font-mono text-[11px] text-slate-500">{doc.chunk_count} chunks</span>}
                    <Badge variant={isIndexed ? "grounded" : isFailed ? "destructive" : "secondary"} className="text-[10px] capitalize">{isIndexed ? "Ready" : isProcessing ? "Processing" : doc.processing_status}</Badge>
                    {isFailed && <Button size="sm" variant="soft" disabled={retryMutation.isPending} onClick={() => retryMutation.mutate(doc.id)} className="h-7 text-[10px]">{retryMutation.isPending && retryMutation.variables === doc.id ? "Retrying…" : "Retry"}</Button>}
                  </div>
                </div>
                {isProcessing && <DocumentProcessingProgress document={doc} />}
                {isFailed && <p role="alert" className="text-xs text-rose-700">{doc.processing_error || "Indexing failed. Retry the source or add a corrected file."}</p>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
