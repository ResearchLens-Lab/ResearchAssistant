"use client";

import React from "react";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { Badge } from "@/components/ui/badge";
import { useCitationStore } from "@/store/citationStore";

export function CitationBadge({ sourceId, source }) {
  const { activeSourceId, openSource, sources } = useCitationStore();
  const matchedSource = source || sources.find((s) => s.source_id === sourceId);
  const isActive = activeSourceId === sourceId;

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    openSource(sourceId);

    const el = document.getElementById(`source-${sourceId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  return (
    <HoverCard openDelay={150} closeDelay={100}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          onClick={handleClick}
          className="inline-flex items-baseline mx-0.5 align-baseline"
        >
          <Badge
            variant="citation"
            className={`px-1.5 py-0 text-[10px] font-mono transition-transform hover:scale-105 ${
              isActive
                ? "bg-blue-600 text-white border-blue-600 ring-2 ring-blue-400/30"
                : "bg-indigo-50 text-indigo-700 border-indigo-200"
            }`}
          >
            {sourceId}
          </Badge>
        </button>
      </HoverCardTrigger>

      <HoverCardContent align="start" className="w-80 p-3 shadow-md border-zinc-200">
        <div className="space-y-1.5 text-left">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
            <span className="font-bold text-indigo-600">[{sourceId}] Grounding Source</span>
            <span>
              {matchedSource?.page ? `p. ${matchedSource.page}` : matchedSource?.page_start ? `p. ${matchedSource.page_start}` : ""}
            </span>
          </div>

          <div className="text-xs font-semibold text-zinc-900 leading-tight">
            {matchedSource?.title || `Paper ID: ${matchedSource?.paper_id?.slice(0, 10)}...`}
          </div>

          {matchedSource?.section && (
            <Badge variant="section" className="text-[9px] px-1 py-0">
              {matchedSource.section}
            </Badge>
          )}

          {matchedSource?.text && (
            <p className="text-[11px] text-zinc-600 line-clamp-3 italic border-l-2 border-indigo-200 pl-2">
              &ldquo;{matchedSource.text}&rdquo;
            </p>
          )}

          <div className="pt-1 text-[10px] text-blue-600 font-medium">
            Click badge to inspect full passage →
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
