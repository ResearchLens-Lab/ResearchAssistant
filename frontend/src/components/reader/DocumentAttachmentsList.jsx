"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { FileText } from "lucide-react";
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
    <div className="rounded-lg border border-zinc-200 bg-white p-5 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
            Project sources {isLoading ? "(loading)" : isError ? "(unavailable)" : `(${documents.length})`}
          </h3>
        </div>

      </div>

      {isLoading ? (
        <div className="h-16 rounded-md bg-zinc-100 animate-pulse" />
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p>{error?.message || "Project sources could not be loaded."}</p>
          <button type="button" onClick={onRetry} className="mt-2 font-medium underline underline-offset-2">Retry</button>
        </div>
      ) : documents.length === 0 ? (
        <div className="py-6 text-center text-zinc-400 space-y-1">
            <p className="text-sm font-medium text-zinc-700">No sources added yet</p>
          <p className="text-[11px] text-zinc-400">
              Add a source and wait for indexing before asking source-grounded questions or generating a summary.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {retryMutation.isError && <p role="alert" className="text-xs text-rose-700">{retryMutation.error?.message || "Could not retry the source."}</p>}
          {documents.map((doc) => {
            const isIndexed = doc.processing_status === "indexed";
            const isFailed = doc.processing_status === "failed";
            const isProcessing = doc.processing_status === "processing" || doc.processing_status === "uploaded";

            return (
              <div
                key={doc.id}
                className="space-y-2 rounded-lg border border-zinc-100 bg-zinc-50/50 p-3 dark:border-zinc-800 dark:bg-zinc-950/40"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-zinc-200 bg-white text-blue-600">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 space-y-0.5">
                      <p className="truncate text-xs font-semibold text-zinc-900 dark:text-zinc-100">{doc.filename}</p>
                      <p className="font-mono text-[10px] text-zinc-500">{formatBytes(doc.file_size)} · Uploaded {formatDate(doc.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {doc.chunk_count && <span className="font-mono text-[11px] text-zinc-500">{doc.chunk_count} chunks</span>}
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
