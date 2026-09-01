import React from "react";
import { Badge } from "@/components/ui/badge";
import { Loader2, AlertCircle, FileText } from "lucide-react";

const STAGES = [
  { key: "extract", label: "extract" },
  { key: "sections", label: "sections" },
  { key: "chunk", label: "chunk" },
  { key: "embed", label: "embed" },
  { key: "indexed", label: "indexed" },
];

export function IngestPipelineVisualizer({
  status,
  filename,
  chunkCount,
  fileSize,
  error,
}) {
  const isComplete = status === "indexed";
  const isFailed = status === "failed";
  const isProcessing = status === "processing" || status === "uploaded";

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      {/* File Info Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 text-blue-600 shrink-0" />
          <span className="text-xs font-semibold text-zinc-900 truncate dark:text-zinc-100">
            {filename}
          </span>
          {fileSize && (
            <span className="text-[10px] text-zinc-400 font-mono">
              ({(fileSize / (1024 * 1024)).toFixed(1)} MB)
            </span>
          )}
        </div>

        <Badge
          variant={isComplete ? "grounded" : isFailed ? "destructive" : "secondary"}
          className="text-[10px] font-mono capitalize"
        >
          {isProcessing ? (
            <span className="flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              indexing
            </span>
          ) : (
            status
          )}
        </Badge>
      </div>

      {/* Horizontal Pipeline Steps */}
      <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400 border-t border-b border-zinc-100 py-2 dark:border-zinc-800">
        {STAGES.map((stage, i) => {
          const isDone = isComplete;
          const isCurrent = isProcessing && stage.key === "chunk";

          return (
            <React.Fragment key={stage.key}>
              <div className="flex items-center gap-1">
                <span
                  className={`h-2 w-2 rounded-full ${
                    isDone
                      ? "bg-emerald-500"
                      : isCurrent
                      ? "bg-blue-600 animate-ping"
                      : isFailed
                      ? "bg-red-500"
                      : "bg-zinc-200"
                  }`}
                />
                <span
                  className={
                    isDone
                      ? "text-emerald-700 font-semibold dark:text-emerald-400"
                      : isCurrent
                      ? "text-blue-600 font-semibold"
                      : "text-zinc-400"
                  }
                >
                  {stage.label}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <span className="text-zinc-300 dark:text-zinc-700">→</span>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Detected Sections Pills */}
      {isComplete && (
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
            <span>Detected Academic Sections:</span>
            <span className="text-emerald-600 font-semibold">
              {chunkCount ? `${chunkCount} chunks indexed` : "Complete"}
            </span>
          </div>

          <div className="flex flex-wrap gap-1">
            {["Abstract", "Introduction", "Methodology", "Results", "Discussion", "Conclusion"].map(
              (sec) => (
                <Badge
                  key={sec}
                  variant="outline"
                  className="bg-zinc-50 text-[9px] font-mono text-zinc-600 border-zinc-200"
                >
                  {sec}
                </Badge>
              )
            )}
          </div>
        </div>
      )}

      {/* Error Callout */}
      {isFailed && error && (
        <div className="flex items-center gap-2 rounded-md bg-red-50 p-2.5 text-xs text-red-700 border border-red-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
