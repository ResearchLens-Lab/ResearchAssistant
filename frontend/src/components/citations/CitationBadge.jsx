"use client";

import React, { useRef, useEffect } from "react";
import { cn } from "@/utils/cn";
import { useCitationStore } from "@/store/citationStore";
import { getSourceIdentity } from "@/utils/sourceIdentity";
import { formatPages, plausibleHeading } from "@/utils/citationNumbering.mjs";
import { HoverCard, HoverCardTrigger, HoverCardContent } from "@/components/ui/hover-card";

export function CitationBadge({
  sourceId,
  source,
  highlight = null,
  autoSelect = false,
  question = "",
  researchPlan = null,
  number,
  messageId = null,
}) {
  const { activeSourceKey, activeHighlight, openSource, sources } = useCitationStore();
  const matchedSource = source || sources.find((s) => s.source_id === sourceId);
  const sourceKey = getSourceIdentity(matchedSource) || `source:${sourceId}`;
  const isActive =
    activeSourceKey === sourceKey &&
    (!activeHighlight?.claimText || activeHighlight.claimText === highlight?.claimText);
  const missing = !matchedSource;

  const highlightRef = useRef(highlight);
  highlightRef.current = highlight;
  const contextRef = useRef({ question, researchPlan, messageId });
  contextRef.current = { question, researchPlan, messageId };

  useEffect(() => {
    if (autoSelect) {
      openSource(
        sourceId,
        highlightRef.current,
        sourceKey,
        contextRef.current.question,
        contextRef.current.researchPlan,
        contextRef.current.messageId
      );
    }
  }, [autoSelect, openSource, sourceId, sourceKey]);

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    openSource(sourceId, highlight, sourceKey, question, researchPlan, messageId);

    setTimeout(() => {
      const el = document.getElementById(`source-${encodeURIComponent(sourceKey)}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  const n = number ?? sourceId.replace(/\D/g, "");
  const filename = matchedSource?.filename || matchedSource?.title || "Document";
  const pagesText = formatPages(matchedSource);
  const sectionHeading = plausibleHeading(matchedSource?.section);

  return (
    <HoverCard openDelay={150} closeDelay={100}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          onClick={handleClick}
          title={missing ? "Citation not found in retrieved sources" : undefined}
          aria-label={`Citation ${n}: ${missing ? "Citation not found in retrieved sources" : filename}`}
          className={cn(
            "mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-md px-1 align-baseline text-[11px] font-semibold leading-none tabular-nums transition-colors cursor-pointer",
            missing
              ? "bg-amber-100 text-amber-800"
              : isActive
              ? "bg-[var(--rl-primary)] text-white"
              : "bg-[var(--rl-selected)] text-[var(--rl-primary)] hover:bg-[#d4e8f8]"
          )}
        >
          [{n}]
        </button>
      </HoverCardTrigger>
      <HoverCardContent
        side="top"
        align="start"
        className="w-80 rounded-lg border border-zinc-200 bg-white p-3 shadow-lg outline-none text-left"
      >
        <div className="space-y-1.5 text-left">
          <div className="flex items-start justify-between gap-2">
            <span className="block text-xs font-semibold text-zinc-900 leading-tight truncate">
              {filename}
            </span>
            {pagesText && (
              <span className="shrink-0 text-[11px] font-mono text-zinc-500">
                {pagesText}
              </span>
            )}
          </div>

          {sectionHeading && (
            <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-700">
              {sectionHeading}
            </span>
          )}

          {matchedSource?.text ? (
            <span className="block text-[11px] text-zinc-600 line-clamp-3 italic border-l-2 border-indigo-200 pl-2">
              &ldquo;{matchedSource.text}&rdquo;
            </span>
          ) : missing ? (
            <span className="block text-[11px] text-amber-800 italic">
              Citation not found in retrieved sources.
            </span>
          ) : null}

          <span className="block pt-1 text-[11px] text-[var(--rl-primary)] font-medium">
            Click to open in the evidence panel →
          </span>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
