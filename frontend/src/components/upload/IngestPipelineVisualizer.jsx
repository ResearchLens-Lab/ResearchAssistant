import React from "react";
import { Badge } from "@/components/ui/badge";
import { Loader2, AlertCircle, FileText, CheckCircle2 } from "lucide-react";

export function IngestPipelineVisualizer({ status, filename, chunkCount, fileSize, error }) {
  const isComplete = status === "indexed";
  const isPartial = status === "partial";
  const isFailed = status === "failed";
  const isProcessing = status === "processing" || status === "uploaded";
  return (
    <section aria-live="polite" className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          {isProcessing ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--rl-primary)]" /> : isComplete ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-700" /> : isFailed ? <AlertCircle className="h-4 w-4 shrink-0 text-rose-700" /> : <FileText className="h-4 w-4 shrink-0 text-amber-700" />}
          <div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-900" title={filename}>{filename}</p><p className="mt-0.5 text-[10px] text-slate-500">{fileSize ? `${(fileSize / (1024 * 1024)).toFixed(1)} MB · ` : ""}{isProcessing ? "Processing source" : isComplete ? `${chunkCount || 0} chunks reported indexed` : isPartial ? "Some files indexed; see individual results" : "No files were indexed"}</p></div>
        </div>
        <Badge variant={isComplete ? "grounded" : isFailed ? "destructive" : "secondary"} className="text-[10px] capitalize">{isProcessing ? "processing" : status}</Badge>
      </div>
      {isFailed && error && <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 p-2.5 text-xs leading-relaxed text-rose-800">{error}</p>}
      {isPartial && <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-xs leading-relaxed text-amber-900">The batch completed with mixed results. The per-file status below identifies which documents need attention.</p>}
    </section>
  );
}
