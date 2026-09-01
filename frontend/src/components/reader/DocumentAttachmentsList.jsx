"use client";

import React, { useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FileText, UploadCloud, Loader2 } from "lucide-react";
import { formatBytes, formatDate } from "@/utils/formatters";

export function DocumentAttachmentsList({
  documents,
  isLoading,
  onUpload,
  isUploading,
}) {
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (file) {
      await onUpload(file);
    }
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
            Attached PDF Documents ({documents.length})
          </h3>
        </div>

        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="h-7 text-xs gap-1"
          >
            {isUploading ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <UploadCloud className="h-3.5 w-3.5" />
                <span>Upload PDF</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="h-16 rounded-md bg-zinc-100 animate-pulse" />
      ) : documents.length === 0 ? (
        <div className="py-6 text-center text-zinc-400 space-y-1">
          <p className="text-xs font-medium text-zinc-600">No PDF attached yet</p>
          <p className="text-[11px] text-zinc-400">
            Upload the PDF file to extract chunks and enable grounded RAG answering.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => {
            const isIndexed = doc.processing_status === "indexed";
            const isFailed = doc.processing_status === "failed";
            const isProcessing = doc.processing_status === "processing" || doc.processing_status === "uploaded";

            return (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-lg border border-zinc-100 bg-zinc-50/50 p-3 dark:border-zinc-800 dark:bg-zinc-950/40"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white text-blue-600 border border-zinc-200 shrink-0">
                    <FileText className="h-4 w-4" />
                  </div>

                  <div className="space-y-0.5 min-w-0">
                    <p className="text-xs font-semibold text-zinc-900 truncate dark:text-zinc-100">
                      {doc.filename}
                    </p>
                    <p className="text-[10px] text-zinc-500 font-mono">
                      {formatBytes(doc.file_size)} • Uploaded {formatDate(doc.created_at)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {doc.chunk_count && (
                    <span className="text-[11px] font-mono text-zinc-500">
                      {doc.chunk_count} chunks
                    </span>
                  )}

                  <Badge
                    variant={isIndexed ? "grounded" : isFailed ? "destructive" : "secondary"}
                    className="text-[10px] capitalize"
                  >
                    {isProcessing ? "Indexing..." : doc.processing_status}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
