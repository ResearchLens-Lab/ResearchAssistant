"use client";

import React, { useState, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { useCitationStore } from "@/store/citationStore";
import { openAuthenticatedPdfSource } from "@/services/documents.service";

export function CitationBadge({ sourceId, source }) {
  const { activeSourceId, openSource, sources } = useCitationStore();
  const matchedSource = source || sources.find((s) => s.source_id === sourceId);
  const isActive = activeSourceId === sourceId;
  const [isHovered, setIsHovered] = useState(false);
  const timeoutRef = useRef(null);

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => setIsHovered(true), 150);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setIsHovered(false);
  };

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    openSource(sourceId);
    if (matchedSource?.document_id && /\.pdf$/i.test(matchedSource.filename || "")) {
      openAuthenticatedPdfSource(matchedSource).catch(() => {});
    }

    const el = document.getElementById(`source-${sourceId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  return (
    <span
      className="relative inline-flex items-baseline mx-0.5 align-baseline"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        type="button"
        onClick={handleClick}
        className="inline-flex items-baseline cursor-pointer"
        aria-label={`Source citation ${sourceId}`}
      >
        <Badge
          variant="citation"
          className={`px-1.5 py-0 text-[10px] font-mono transition-transform hover:scale-105 ${
            isActive
              ? "bg-[#2678b8] text-white border-[#2678b8] ring-2 ring-sky-400/30"
              : "bg-[#e8f3fc] text-[#2678b8] border-sky-200"
          }`}
        >
          {sourceId}
        </Badge>
      </button>

      {isHovered && (
        <div
          role="tooltip"
          className="absolute bottom-full left-0 mb-2 z-50 w-80 rounded-md border border-zinc-200 bg-white p-3 shadow-lg outline-none pointer-events-none"
        >
          <div className="space-y-1.5 text-left">
            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
              <span className="font-bold text-[#2678b8]">[{sourceId}] Source passage</span>
              <span>
                {matchedSource?.page ? `p. ${matchedSource.page}` : matchedSource?.page_start ? `p. ${matchedSource.page_start}` : ""}
              </span>
            </div>

            <div className="text-xs font-semibold text-zinc-900 leading-tight">
              {matchedSource?.title || (matchedSource?.paper_id ? `Paper ID: ${matchedSource.paper_id.slice(0, 10)}...` : `Source [${sourceId}]`)}
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
        </div>
      )}
    </span>
  );
}
