import React from "react";
import { ScoreProgressBar } from "./ScoreProgressBar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/cn";

export function SourceCard({ source, isActive = false, onSelect, claimStatuses = [] }) {
  const primaryName = source.title || source.filename || `Paper ${source.paper_id?.slice(0, 8) || "unknown"}`;
  const showFilename = source.filename && source.title && source.filename !== source.title;
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
        "group relative block min-w-0 max-w-full w-full rounded-xl border p-3 transition-all duration-200 cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)]",
        isActive
          ? "border-sky-400 bg-[var(--rl-selected)] ring-2 ring-sky-500/20 shadow-xs"
          : "border-zinc-200 bg-white hover:border-zinc-300 hover:shadow-2xs dark:border-zinc-800 dark:bg-zinc-900"
      )}
    >
      {/* Header: Source ID & Paper / Page */}
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          {source.source_id && (
            <Badge
              variant="citation"
              className="px-1.5 py-0.5 text-[10px] font-bold"
            >
              {source.source_id}
            </Badge>
          )}
          <span title={primaryName} className="min-w-0 break-words text-xs font-semibold leading-5 text-zinc-900 [overflow-wrap:anywhere] dark:text-zinc-100">
            {primaryName}
          </span>
        </div>
        <span className="max-w-[42%] shrink-0 break-words text-right text-[11px] font-mono text-zinc-500 [overflow-wrap:anywhere]">
          {pageDisplay}
        </span>
      </div>

      {showFilename && <p className="mt-1 break-words text-[10px] leading-4 text-zinc-500 [overflow-wrap:anywhere]">File: {source.filename}</p>}

      {/* Section Tag */}
      {source.section && (
        <div className="mt-1.5">
          <Badge variant="section" className="max-w-full whitespace-normal break-words text-[9px] px-1.5 py-0 [overflow-wrap:anywhere]">
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
      <div className="mt-3 min-w-0 max-w-full">
        <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-zinc-500">Retrieved passage · full excerpt</p>
        {source.text ? <blockquote className="min-w-0 max-w-full whitespace-pre-wrap break-words rounded-r-md border-l-2 border-[var(--rl-sky)] bg-[var(--rl-tint)] px-2.5 py-2 text-sm leading-relaxed text-[var(--rl-ink)] [overflow-wrap:anywhere]">{source.text.trim()}</blockquote> : <p className="rounded-lg bg-[var(--rl-tint)] px-2.5 py-2 text-xs leading-5 text-zinc-500">No text excerpt was saved for this citation.</p>}
      </div>

      {/* Footer: Chunk ID & Relevance Score Bar */}
      <div className="mt-3 min-w-0 space-y-2 border-t border-zinc-100 pt-2 dark:border-zinc-800/80">
        {source.score !== undefined && source.score !== null && (
          <div>
            <p className="mb-1 text-[9px] text-zinc-500">Retrieval score · not a confidence rating</p>
            <ScoreProgressBar score={source.score} />
          </div>
        )}
        <dl className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-[9px] leading-4 text-zinc-500">
          {source.paper_id && <><dt>Paper ID</dt><dd className="min-w-0 break-all font-mono">{source.paper_id}</dd></>}
          {source.document_id && <><dt>Document ID</dt><dd className="min-w-0 break-all font-mono">{source.document_id}</dd></>}
          {source.chunk_id && <><dt>Chunk ID</dt><dd className="min-w-0 break-all font-mono">{source.chunk_id}</dd></>}
          {source.locator && source.locator !== pageDisplay && <><dt>Location</dt><dd className="min-w-0 break-words [overflow-wrap:anywhere]">{source.locator}</dd></>}
        </dl>
        {onSelect && <p className="pt-1 text-[9px] text-[var(--rl-primary)]">Select to open this source document</p>}
      </div>
    </div>
  );
}
