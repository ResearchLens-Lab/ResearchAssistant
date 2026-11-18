"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/cn";
import { FileText, ExternalLink, BookOpen, Quote, Copy, Check, Sparkles } from "lucide-react";
import { useCitationStore } from "@/store/citationStore";
import { getSourceIdentity } from "@/utils/sourceIdentity";
import { formatPages, plausibleHeading } from "@/utils/citationNumbering.mjs";

export function reflowText(text) {
  if (!text) return "";
  return text
    .replace(/\r\n/g, "\n")
    .replace(/([^\n])\n([^\n])/g, "$1 $2")
    .replace(/[ \t]+/g, " ")
    .trim()
    .replace(/^[“”"'`]+|[“”"'`]+$/g, "");
}

export function truncateSentenceBoundary(text, maxLength = 500) {
  if (!text || text.length <= maxLength) return text;
  const sub = text.slice(0, maxLength);
  const lastPeriod = Math.max(sub.lastIndexOf(". "), sub.lastIndexOf("! "), sub.lastIndexOf("? "));
  if (lastPeriod > maxLength * 0.4) {
    return sub.slice(0, lastPeriod + 1);
  }
  return sub.trim();
}

function normalizeText(s) {
  return (s || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function matchCandidate(text, cand) {
  if (!cand || cand.length < 3) return null;
  const idx = text.indexOf(cand);
  if (idx !== -1) {
    return {
      start: idx,
      end: idx + cand.length,
      matchedText: text.slice(idx, idx + cand.length),
    };
  }

  const normalizedSource = [];
  let normalized = "";
  let previousWasSpace = true;
  for (let i = 0; i < text.length; i += 1) {
    const normalizedChar = text[i].normalize("NFKC").toLowerCase();
    if (!/[\p{L}\p{N}]/u.test(normalizedChar)) {
      if (!previousWasSpace) {
        normalized += " ";
        normalizedSource.push(i);
      }
      previousWasSpace = true;
      continue;
    }
    for (const char of normalizedChar) {
      normalized += char;
      normalizedSource.push(i);
    }
    previousWasSpace = false;
  }
  if (normalized.endsWith(" ")) {
    normalized = normalized.slice(0, -1);
    normalizedSource.pop();
  }
  const normalizedCandidate = normalizeText(cand);
  const normalizedIndex = normalized.indexOf(normalizedCandidate);
  if (normalizedIndex < 0 || !normalizedCandidate) return null;
  const start = normalizedSource[normalizedIndex];
  const end = normalizedSource[normalizedIndex + normalizedCandidate.length - 1] + 1;
  const matchedText = text.slice(start, end);
  if (normalizeText(matchedText) !== normalizedCandidate) return null;
  return { start, end, matchedText };
}

function findMatchSpan(text, source, highlight) {
  if (!text || !highlight) return null;
  const rawStart = source?.text_offset_start;
  const rawEnd = source?.text_offset_end;
  const evidenceExcerpt = (source?.evidence_excerpt || "").trim();
  if (Number.isInteger(rawStart) && Number.isInteger(rawEnd) && rawStart >= 0 && rawEnd > rawStart && rawEnd <= text.length) {
    const offsetText = text.slice(rawStart, rawEnd);
    const coversWholeChunk = rawStart === 0 && rawEnd >= text.length;
    const excerptMatches = !evidenceExcerpt || normalizeText(offsetText) === normalizeText(evidenceExcerpt);
    const excerptIsSpecific = evidenceExcerpt && normalizeText(evidenceExcerpt) !== normalizeText(text);
    if (!coversWholeChunk && excerptMatches && (!evidenceExcerpt || excerptIsSpecific)) {
      return { start: rawStart, end: rawEnd, matchedText: offsetText.trim() };
    }
  }

  if (evidenceExcerpt && normalizeText(evidenceExcerpt) !== normalizeText(text)) {
    const excerptMatch = matchCandidate(text, evidenceExcerpt);
    if (excerptMatch) return excerptMatch;
  }

  const claim = (highlight.claimText || "")
    .replace(/^[-*+]\s+/, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .trim();
  const claimMatch = matchCandidate(text, claim);
  return claimMatch;
}

export function SourceCard({
  source,
  isActive = false,
  onSelect,
  onOpenDocument,
  claimStatuses = [],
  hideDocumentTitle = false,
}) {
  const { activeHighlight } = useCitationStore();
  const [copied, setCopied] = useState(false);
  const [copiedFocused, setCopiedFocused] = useState(false);
  const [copiedPassage, setCopiedPassage] = useState(false);
  const [passageExpanded, setPassageExpanded] = useState(false);

  const highlightRef = useRef(null);
  const quoteRef = useRef(null);

  const primaryName = source.filename || "Source document";
  const rawCitationLabel = source.citation_label?.trim();
  const citationName = rawCitationLabel && !/^\[?S\d+\]?$/i.test(rawCitationLabel) && (source.author_metadata?.length || source.publication_year) ? rawCitationLabel : primaryName;

  const pageDisplay = formatPages(source) || source.locator || "Document source";
  const sectionLabel = plausibleHeading(source.section);

  const cleanText = useMemo(() => reflowText(source.text), [source.text]);

  const passageIsLong = cleanText.length > 700;

  // Match the active clicked highlight in this source
  const matches = useMemo(() => {
    if (!isActive || !activeHighlight) return [];
    const claims = activeHighlight.relatedClaimTexts?.length
      ? [...new Set(activeHighlight.relatedClaimTexts)]
      : [activeHighlight.claimText];
    const found = claims
      .map((claimText) => findMatchSpan(cleanText, source, { ...activeHighlight, claimText }))
      .filter(Boolean)
      .sort((a, b) => a.start - b.start);
    return found.reduce((merged, span) => {
      const previous = merged[merged.length - 1];
      if (previous && span.start <= previous.end) {
        previous.end = Math.max(previous.end, span.end);
        previous.matchedText = cleanText.slice(previous.start, previous.end);
      } else {
        merged.push({ ...span });
      }
      return merged;
    }, []);
  }, [isActive, activeHighlight, cleanText]);
  const match = matches[0] || null;

  // Smoothly scroll the excerpt to the highlighted mark
  useEffect(() => {
    if (isActive && highlightRef.current && quoteRef.current) {
      const timer = setTimeout(() => {
        const markEl = highlightRef.current;
        const container = quoteRef.current;
        if (markEl && container) {
          const markTop = markEl.offsetTop - container.offsetTop;
          const targetScroll = markTop - container.clientHeight / 2 + markEl.clientHeight / 2;
          container.scrollTo({
            top: Math.max(0, targetScroll),
            behavior: "smooth",
          });
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [isActive, match?.start]);

  const handleCopy = (e) => {
    e.stopPropagation();
    const formattedCitation = `${citationName}, ${pageDisplay}:\n"${cleanText}"`;
    navigator.clipboard.writeText(formattedCitation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyFocused = (e) => {
    e.stopPropagation();
    const sectionTitle = activeHighlight?.headingText ? `${activeHighlight.headingText}: ` : "";
    const focusedText = match?.matchedText || cleanText;
    const formattedCitation = `${citationName}, ${pageDisplay} — ${sectionTitle}\n"${focusedText}"`;
    navigator.clipboard.writeText(formattedCitation);
    setCopiedFocused(true);
    setTimeout(() => setCopiedFocused(false), 2000);
  };

  const displayStart = match && matches.length === 1 && !passageExpanded ? Math.max(0, match.start - 140) : 0;
  const truncatedSentenceLen = useMemo(() => truncateSentenceBoundary(cleanText, 500).length, [cleanText]);
  const displayEnd = match && matches.length === 1 && !passageExpanded
    ? Math.min(cleanText.length, match.end + 160)
    : !match && passageIsLong && !passageExpanded ? truncatedSentenceLen : cleanText.length;
  const visibleText = cleanText.slice(displayStart, displayEnd);
  const visibleMatches = matches
    .map((span) => ({ ...span, start: span.start - displayStart, end: span.end - displayStart }))
    .filter((span) => span.start >= 0 && span.end <= visibleText.length);
  const highlightedPassage = [];
  let textCursor = 0;
  visibleMatches.forEach((span, index) => {
    if (span.start > textCursor) highlightedPassage.push(visibleText.slice(textCursor, span.start));
    highlightedPassage.push(
      <mark
        key={"match-" + index}
        id={index === 0 ? "active-evidence-highlight" : undefined}
        ref={index === 0 ? highlightRef : undefined}
        className="bg-sky-100 text-slate-900 font-semibold px-1 py-0.5 rounded border border-sky-300 ring-1 ring-sky-200 inline transition-colors duration-150"
      >
        {visibleText.slice(span.start, span.end)}
      </mark>
    );
    textCursor = span.end;
  });
  highlightedPassage.push(visibleText.slice(textCursor));
  const canExpandPassage = matches.length < 2 && (passageIsLong || (match && (displayStart > 0 || displayEnd < cleanText.length)));

  return (
    <div
      id={`source-${encodeURIComponent(getSourceIdentity(source))}`}
      role="button"
      tabIndex={0}
      aria-pressed={isActive}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect?.();
        }
      }}
      className={cn(
        "group relative block min-w-0 max-w-full w-full rounded-xl border p-3 transition-colors duration-150 text-left font-sans cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
        isActive
          ? "border-[#1d6fc4] bg-sky-50/70 ring-2 ring-sky-500/30 shadow-md scale-[1.01]"
          : "border-slate-200/90 bg-white hover:border-sky-300 hover:shadow-2xs"
      )}
    >
      {/* Top Header: Citation Badge & Document Name */}
      <div className="flex items-start justify-between gap-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <div className="min-w-0">
            <h4
              title={hideDocumentTitle ? pageDisplay : primaryName}
              className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900"
            >
              {hideDocumentTitle ? pageDisplay : primaryName}
            </h4>
            {source.author_metadata?.length > 0 && (
              <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">
                {source.author_metadata.join(", ")}
                {source.publication_year ? ` · ${source.publication_year}` : ""}
              </p>
            )}
          </div>
        </div>

        {!hideDocumentTitle && (
          <span className="shrink-0 rounded-full bg-sky-100/70 border border-sky-200/60 px-2 py-0.5 text-[11px] font-semibold text-[#1d6fc4]">
            {pageDisplay}
          </span>
        )}
      </div>

      {/* Section Subheading if present */}
      {sectionLabel && sectionLabel !== "Main Content" && (
        <div className="mt-2 min-w-0">
          <span className="inline-flex max-w-full min-w-0 items-center gap-1 rounded-md bg-slate-50 border border-slate-200/60 px-2 py-0.5 text-[11px] text-slate-600">
            <BookOpen className="h-3 w-3 text-[#1d6fc4] shrink-0" />
            <span className="truncate">{sectionLabel}</span>
          </span>
        </div>
      )}

      {/* Excerpt Header with Actions */}
      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1">
            <Quote className="h-3 w-3 text-[#1d6fc4]" />
            <span>Retrieved passage</span>
          </p>

          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1d6fc4] hover:text-[#185ea8] bg-sky-50 hover:bg-sky-100 px-2 py-0.5 rounded-full border border-sky-200/60 transition-all cursor-pointer"
            title="Copy citation and excerpt"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-emerald-600" />
                <span className="text-emerald-700">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>Copy full citation</span>
              </>
            )}
          </button>
        </div>

        {/* Focused Section / Claim Indicator Banner */}
        {match && (
          <div className="mb-2 flex items-center justify-between rounded-lg bg-amber-50/95 border border-amber-200/80 px-2.5 py-1.5 text-xs text-amber-950 shadow-2xs">
            <div className="flex items-center gap-1.5 min-w-0 pr-2">
              <Sparkles className="h-3.5 w-3.5 text-amber-600 shrink-0" />
              <span className="truncate font-semibold text-[11px] text-amber-900">
                {matches.length > 1
                  ? "Highlighted " + matches.length + " cited sections"
                  : "Focused: " + (activeHighlight?.headingText || "Clicked claim")}
              </span>
            </div>

            <button
              type="button"
              onClick={handleCopyFocused}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-900 hover:text-amber-950 bg-white hover:bg-amber-100/70 border border-amber-300 px-2 py-0.5 rounded-lg shadow-2xs transition-all cursor-pointer shrink-0"
              title="Copy citation for this specific focused section"
            >
              {copiedFocused ? (
                <>
                  <Check className="h-3 w-3 text-emerald-600" />
                  <span className="text-emerald-700 font-bold">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 text-amber-800" />
                  <span>Copy focused citation</span>
                </>
              )}
            </button>
          </div>
        )}

        {cleanText ? (
          <blockquote
            ref={quoteRef}
            className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border-l-2 border-[#1d6fc4] bg-slate-50 p-3 text-xs leading-relaxed text-slate-700"
          >
            {displayStart > 0 ? "…" : ""}
            {match ? highlightedPassage : visibleText}
            {displayEnd < cleanText.length ? " …" : ""}
          </blockquote>
        ) : (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500 italic">
            No text excerpt saved for this citation.
          </p>
        )}
        {canExpandPassage && cleanText && (
          <button type="button" onClick={(event) => { event.stopPropagation(); setPassageExpanded((expanded) => !expanded); }} className="mt-1 text-xs font-medium text-[var(--rl-primary)] hover:underline">
            {passageExpanded ? "Show less" : "Show full passage"}
          </button>
        )}
      </div>

      {/* Bottom Actions */}
      <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-100">
        <button type="button" onClick={(event) => { event.stopPropagation(); navigator.clipboard.writeText(cleanText); setCopiedPassage(true); setTimeout(() => setCopiedPassage(false), 2000); }} className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-[var(--rl-primary)]">
          {copiedPassage ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copiedPassage ? "Copied passage" : "Copy passage"}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpenDocument?.(match?.matchedText || source.evidence_excerpt || source.text || activeHighlight?.claimText || "");
          }}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#1d6fc4] hover:text-[#185ea8] transition-colors"
        >
          <FileText className="h-3.5 w-3.5" />
          <span>Open PDF at page</span>
          <ExternalLink className="h-3 w-3" />
        </button>

      </div>
    </div>
  );
}
