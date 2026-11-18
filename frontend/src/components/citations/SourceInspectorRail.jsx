"use client";

import React, { useState } from "react";
import { useCitationStore } from "@/store/citationStore";
import { SourceCard } from "./SourceCard";
import { BookOpen, FileText, X } from "lucide-react";
import { openAuthenticatedPdfSource } from "@/services/documents.service";
import { getSourceIdentity } from "@/utils/sourceIdentity";
import { filterSourcesByScopedAnswer } from "@/utils/citationNumbering.mjs";

export function SourceInspectorRail({ className = "", onClose }) {
  const {
    sources,
    activeSourceKey,
    setActiveSource,
    evidenceScope = "answer",
    setEvidenceScope,
    scopedMessageId,
    conversationMessages = [],
  } = useCitationStore();
  const [documentError, setDocumentError] = useState("");

  const openSource = async (source, highlightedText = "") => {
    setActiveSource(source);
    setDocumentError("");
    try {
      const opened = await openAuthenticatedPdfSource(source, highlightedText);
      if (/\.pdf$/i.test(source.filename || "") && !opened) {
        setDocumentError("The PDF could not be opened. Allow popups for this site and try again.");
      }
    } catch (error) {
      if (error?.message?.includes("404") || error?.statusCode === 404) {
        setDocumentError("This source document is no longer available in your library. You can still inspect the preserved evidence excerpt below.");
      } else {
        setDocumentError(error.message || "The source document could not be opened. You can still inspect the excerpt below.");
      }
    }
  };

  const targetMessage = scopedMessageId
    ? conversationMessages.find((m) => m.id === scopedMessageId)
    : conversationMessages.slice().reverse().find((m) => m.role === "assistant" && (m.sources?.length || m.content?.includes("[S")));

  const displaySources =
    evidenceScope === "answer" && targetMessage
      ? filterSourcesByScopedAnswer(targetMessage, sources)
      : sources;

  const citedSources = displaySources.filter((s) => s.source_id);
  const sourceGroups = citedSources.reduce((groups, source) => {
    const key = source.document_id || source.paper_id || source.filename || source.paper_title || source.title || source.source_id;
    const group = groups.get(key) || { key, title: source.filename || "Source document", sources: [] };
    group.sources.push(source);
    groups.set(key, group);
    return groups;
  }, new Map());

  const scopeLabel = evidenceScope === "answer" ? "this answer" : "whole conversation";

  return (
    <aside
      aria-label="Evidence and citation inspector"
      className={`flex h-full w-full min-w-0 max-w-full flex-col overflow-hidden border-l border-slate-200/90 bg-white font-sans ${className}`}
    >
      {/* Human-Readable Header */}
      <div className="flex flex-col gap-2 border-b border-slate-200/80 bg-white px-4 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-50 text-[#1d6fc4]">
              <BookOpen className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-slate-800">
                Evidence & sources
              </h2>
              <p className="text-[11px] text-slate-500">
                {citedSources.length} passages · {sourceGroups.size} documents · {scopeLabel}
              </p>
            </div>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              title="Close evidence panel"
              aria-label="Close evidence panel"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* C3: Scope Toggle */}
        <div className="flex items-center rounded-lg bg-slate-100 p-0.5 text-[11px] font-medium text-slate-600 self-start">
          <button
            type="button"
            onClick={() => setEvidenceScope?.("answer")}
            className={`rounded-md px-2.5 py-0.5 transition-colors ${
              evidenceScope === "answer"
                ? "bg-white text-slate-900 shadow-2xs font-semibold"
                : "hover:text-slate-900"
            }`}
          >
            This answer
          </button>
          <button
            type="button"
            onClick={() => setEvidenceScope?.("conversation")}
            className={`rounded-md px-2.5 py-0.5 transition-colors ${
              evidenceScope === "conversation"
                ? "bg-white text-slate-900 shadow-2xs font-semibold"
                : "hover:text-slate-900"
            }`}
          >
            Whole conversation
          </button>
        </div>
      </div>

      {/* Main Evidence Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="min-h-0 w-full flex-1 overflow-y-auto p-3.5">
          {documentError && (
            <div
              role="alert"
              className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-relaxed text-rose-800"
            >
              {documentError}
            </div>
          )}

          {citedSources.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center text-slate-400 space-y-2">
              <FileText className="h-8 w-8 text-slate-300 stroke-[1.5]" />
              <p className="text-sm font-semibold text-slate-700">
                No cited passages yet
              </p>
              <p className="text-[11px] text-slate-500 max-w-[220px] leading-relaxed">
                Source passages cited in an answer will appear here for review.
              </p>
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {[...sourceGroups.values()].map((group) => (
                <section key={group.key} aria-label={group.title} className="space-y-2">
                  {sourceGroups.size > 1 && <div className="flex items-baseline justify-between gap-2 px-1"><h3 className="min-w-0 truncate text-xs font-semibold text-slate-700" title={group.title}>{group.title}</h3><span className="shrink-0 text-[11px] text-slate-400">{group.sources.length} passage{group.sources.length === 1 ? "" : "s"}</span></div>}
                  {group.sources.map((source, index) => (
                    <SourceCard
                      key={source.source_id || source.chunk_id || `${group.key}-${index}`}
                      source={source}
                      isActive={activeSourceKey === getSourceIdentity(source)}
                      onSelect={() => setActiveSource(source)}
                      onOpenDocument={(highlightedText) => openSource(source, highlightedText)}
                      hideDocumentTitle={sourceGroups.size > 1}
                    />
                  ))}
                </section>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
