"use client";

import React, { useState, useRef, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { useCitationStore } from "@/store/citationStore";
import { getSourceIdentity } from "@/utils/sourceIdentity";

export function CitationBadge({ sourceId, source, highlight = null, autoSelect = false, question = "", researchPlan = null }) {
  const { activeSourceKey, activeHighlight, openSource, sources } = useCitationStore();
  const matchedSource = source || sources.find((s) => s.source_id === sourceId);
  const sourceKey = getSourceIdentity(matchedSource) || `source:${sourceId}`;
  const isActive = activeSourceKey === sourceKey && (!activeHighlight?.claimText || activeHighlight.claimText === highlight?.claimText);
  const [isHovered, setIsHovered] = useState(false);
  const timeoutRef = useRef(null);
  const highlightRef = useRef(highlight);
  highlightRef.current = highlight;
  const contextRef = useRef({ question, researchPlan });
  contextRef.current = { question, researchPlan };

  useEffect(() => {
    if (autoSelect) openSource(sourceId, highlightRef.current, sourceKey, contextRef.current.question, contextRef.current.researchPlan);
  }, [autoSelect, openSource, sourceId, sourceKey]);

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
    openSource(sourceId, highlight, sourceKey, question, researchPlan);

    setTimeout(() => {
      const el = document.getElementById(`source-${encodeURIComponent(sourceKey)}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  const authors = Array.isArray(matchedSource?.author_metadata)
    ? matchedSource.author_metadata
    : [];
  const authorLabel = authors.length > 0
    ? `${authors[0]}${authors.length > 1 ? " et al." : ""}${matchedSource?.publication_year ? `, ${matchedSource.publication_year}` : ""}`
    : null;
  const rawLabel = matchedSource?.citation_label;
  const hasCitationMetadata = authors.length > 0 || matchedSource?.publication_year;
  const fallbackTitle = matchedSource?.filename || "Source passage";
  const displayLabel = rawLabel && !/^\[?S\d+\]?$/i.test(rawLabel.trim()) && hasCitationMetadata
    ? rawLabel
    : authorLabel || fallbackTitle || `Source${matchedSource?.page_start || matchedSource?.page ? ` · PDF p. ${matchedSource.page_start || matchedSource.page}` : ""}`;

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
        aria-label={`Source citation ${displayLabel}`}
      >
        <Badge
          variant="citation"
          className={`px-1.5 py-0 text-[10px] font-sans font-medium transition-transform hover:scale-105 ${
            isActive
              ? "bg-[#2678b8] text-white border-[#2678b8] ring-2 ring-sky-400/30"
              : "bg-[#e8f3fc] text-[#2678b8] border-sky-200"
          }`}
        >
          {displayLabel}
        </Badge>
      </button>

      {isHovered && (
        <span
          role="tooltip"
          className="absolute bottom-full left-0 mb-2 z-50 block w-84 rounded-md border border-zinc-200 bg-white p-3 shadow-lg outline-none pointer-events-none"
        >
          <span className="block space-y-1.5 text-left">
            <span className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
              <span className="font-bold text-[#2678b8]">{displayLabel}</span>
              <span>
                {matchedSource?.page ? `p. ${matchedSource.page}` : matchedSource?.page_start ? `p. ${matchedSource.page_start}` : ""}
              </span>
            </span>

            <span className="block text-xs font-semibold text-zinc-900 leading-tight">
              {matchedSource?.filename || "Source passage"}
            </span>

            {matchedSource?.author_metadata && matchedSource.author_metadata.length > 0 && (
              <span className="block text-[10px] text-zinc-600 font-medium">
                {matchedSource.author_metadata.join(", ")}
              </span>
            )}

            {matchedSource?.section && (
              <Badge variant="section" className="text-[9px] px-1 py-0">
                {matchedSource.section}
              </Badge>
            )}

            {matchedSource?.text && (
              <span className="block text-[11px] text-zinc-600 line-clamp-3 italic border-l-2 border-indigo-200 pl-2">
                &ldquo;{matchedSource.text}&rdquo;
              </span>
            )}

            <span className="block pt-1 text-[10px] text-blue-600 font-medium">
              Click badge to inspect full passage →
            </span>
          </span>
        </span>
      )}
    </span>
  );
}
