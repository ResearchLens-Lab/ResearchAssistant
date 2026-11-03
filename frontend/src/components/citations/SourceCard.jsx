import React from "react";
import { ScoreProgressBar } from "./ScoreProgressBar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/cn";

export function SourceCard({ source, isActive = false, onSelect, claimStatuses = [] }) {
  const pageDisplay = source.locator && source.page_start == null
      ? source.locator
      :
    source.page !== undefined && source.page !== null
      ? `p. ${source.page}`
      : source.page_start && source.page_end
      ? source.page_start === source.page_end
        ? `p. ${source.page_start}`
        : `p. ${source.page_start}–${source.page_end}`
      : "p. --";

  return (
    <div
      id={`source-${source.source_id}`}
      role="button"
      tabIndex={0}
      aria-pressed={isActive}
      onClick={onSelect}
      onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect?.(); } }}
      className={cn(
        "group relative block w-full rounded-xl border p-3 transition-all duration-200 cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)]",
        isActive
          ? "border-sky-400 bg-[var(--rl-selected)] ring-2 ring-sky-500/20 shadow-xs"
          : "border-zinc-200 bg-white hover:border-zinc-300 hover:shadow-2xs dark:border-zinc-800 dark:bg-zinc-900"
      )}
    >
      {/* Header: Source ID & Paper / Page */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          {source.source_id && (
            <Badge
              variant="citation"
              className="px-1.5 py-0.5 text-[10px] font-bold"
            >
              {source.source_id}
            </Badge>
          )}
          <span className="text-xs font-semibold text-zinc-900 truncate max-w-[180px] dark:text-zinc-100">
            {source.filename || source.title || `Paper ${source.paper_id?.slice(0, 8)}`}
          </span>
        </div>
        <span className="text-[11px] font-mono text-zinc-500 shrink-0">
          {pageDisplay}
        </span>
      </div>

      {/* Section Tag */}
      {source.section && (
        <div className="mt-1.5">
          <Badge variant="section" className="text-[9px] px-1.5 py-0">
            {source.section}
          </Badge>
        </div>
      )}
      {claimStatuses.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1" aria-label="Claim support statuses">
          {claimStatuses.map((status) => <Badge key={status} variant="outline" className="text-[9px] capitalize">{status.replaceAll("_", " ")}</Badge>)}
        </div>
      )}

      {/* Verbatim Snippet */}
      {source.text && (
        <div className="mt-2 rounded-r-md border-l-2 border-[var(--rl-sky)] bg-[var(--rl-tint)] px-2.5 py-2 text-sm leading-relaxed text-[var(--rl-ink)] line-clamp-4">
          &ldquo;{source.text.trim()}&rdquo;
        </div>
      )}

      {/* Footer: Chunk ID & Relevance Score Bar */}
      <div className="mt-3 pt-2 border-t border-zinc-100 dark:border-zinc-800/80 space-y-1.5">
        {source.score !== undefined && source.score !== null && (
          <ScoreProgressBar score={source.score} />
        )}
        {source.chunk_id && (
          <div className="text-[10px] font-mono text-zinc-400 truncate">
            {source.chunk_id}
          </div>
        )}
      </div>
    </div>
  );
}
