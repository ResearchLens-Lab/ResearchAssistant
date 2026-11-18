"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Copy, Check, Clock, FileSearch, AlertCircle, RotateCcw, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatResearchTimestamp } from "@/utils/researchTime.mjs";
import { buildCitationIndex } from "@/utils/citationNumbering.mjs";
import { useCitationStore } from "@/store/citationStore";

const GroundedAnswer = dynamic(
  () => import("./GroundedAnswer").then((mod) => mod.GroundedAnswer),
  {
    ssr: false,
    loading: () => (
      <div className="space-y-2 py-2">
        <div className="h-4 w-3/4 animate-pulse rounded bg-zinc-100" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-zinc-100" />
      </div>
    ),
  }
);

function formatTimestamp(timestamp) {
  return formatResearchTimestamp(timestamp);
}

function ResearchActivityCard({ summary, meta, content, sources, isPending, progress }) {
  if (!summary && !meta?.research_intelligence && !meta?.research && !isPending) {
    return null;
  }

  const { citedCount, documentCount } = buildCitationIndex(content, sources);
  const confTier = summary?.confidence_tier || meta?.confidence_tier || meta?.research_intelligence?.confidence?.tier || "";
  const provider = meta?.generation_provider;
  const queryPlan = summary?.query_plan || meta?.research_intelligence?.intent || {};
  const concept = summary?.concept || queryPlan?.primary_concept || "";

  const tierStyle =
    confTier === "STRONG"
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : confTier === "PARTIAL"
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-rose-100 text-rose-800 border-rose-200";

  const citedText =
    isPending && citedCount === 0
      ? "Gathering evidence…"
      : `${citedCount} passage${citedCount === 1 ? "" : "s"} · ${documentCount} document${documentCount === 1 ? "" : "s"}`;

  return (
    <div className="mb-3 rounded-xl border border-sky-100 bg-sky-50/50 p-2.5 text-xs text-slate-700 shadow-2xs">
      <div className="flex items-center justify-between gap-2 border-b border-sky-100/70 pb-1.5 mb-1.5">
        <div className="flex items-center gap-1.5 font-medium text-sky-900">
          <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-200/80 text-[11px] text-sky-700">
            <FileSearch className="h-3 w-3" />
          </span>
          <span>Research Activity & Scoping</span>
          {isPending && (
            <span className="flex items-center gap-1 text-[11px] font-normal text-sky-600 animate-pulse">
              • {progress || "Analyzing…"}
            </span>
          )}
        </div>
        {confTier ? (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase border ${tierStyle}`}
          >
            {confTier}
          </span>
        ) : null}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
        <div>
          <span className="font-semibold text-slate-500 block">Question Scope:</span>
          <span className="text-slate-800 font-medium truncate block" title={concept || "Target Concepts"}>
            {concept ? concept.charAt(0).toUpperCase() + concept.slice(1) : "Document Evidence"}
          </span>
        </div>
        <div>
          <span className="font-semibold text-slate-500 block">Cited:</span>
          <span className="text-slate-800">{citedText}</span>
        </div>
        {typeof provider === "string" && provider.trim() !== "" && (
          <div>
            <span className="font-semibold text-slate-500 block">Answer style:</span>
            <span className="text-slate-800">
              {provider === "local_intelligence"
                ? "Local AI summary, checked against sources"
                : "Quoted directly from sources"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MessageItem({
  message,
  onFollowUp,
  autoSelectFirstCitation = false,
  researchQuestion = "",
  scopeLine = "",
}) {
  const isAssistant = message.role === "assistant";
  const [copied, setCopied] = useState(false);

  const { openInspector, openSource } = useCitationStore();

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleOpenAddSources = () => {
    window.dispatchEvent(new CustomEvent("researchlens:open-add-sources"));
  };

  const handleRephrase = () => {
    window.dispatchEvent(
      new CustomEvent("researchlens:rephrase", {
        detail: { question: researchQuestion || "" },
      })
    );
  };

  const formattedTime = formatTimestamp(message.created_at);
  const { citedCount } = buildCitationIndex(message.content, message.sources);

  const meta = message.meta || message.metadata || {};
  const isNotLocated = meta.confidence_tier === "NOT LOCATED";
  const isIndexUnavailable = meta.error_kind === "index_unavailable";

  return (
    <div className="group w-full px-4 py-3 sm:px-6">
      <div className={`mx-auto flex w-full max-w-3xl ${isAssistant ? "items-start gap-3" : "justify-end"}`}>
        {isAssistant && (
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[var(--rl-primary)]">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
        )}

        <div className={`min-w-0 ${isAssistant ? "flex-1" : "max-w-[88%] sm:max-w-[78%]"}`}>
          {isAssistant ? (
            <div className="mb-2 flex min-h-7 flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-xs font-semibold text-slate-800">
                ResearchLens
              </span>
              {formattedTime && <span className="text-[11px] text-slate-400">{formattedTime}</span>}
              {citedCount > 0 && (
                <Badge variant="grounded" className="text-[11px] px-1.5 py-0 gap-1">
                  {citedCount} passage{citedCount === 1 ? "" : "s"} cited
                </Badge>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto h-6 w-6 text-slate-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-slate-700"
                onClick={handleCopy}
                title="Copy answer"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          ) : (
            <>
              <div className="rounded-2xl rounded-br-md bg-[var(--rl-primary)] px-4 py-3 text-sm leading-relaxed text-white shadow-sm whitespace-pre-wrap">
                {message.content}
              </div>
              <div className="mt-1 flex items-center justify-end gap-1 text-[11px] text-slate-400">
                {formattedTime && <><Clock className="h-3 w-3" /><span>{formattedTime}</span></>}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5 text-slate-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-slate-700"
                  onClick={handleCopy}
                  title="Copy question"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
                </Button>
              </div>
            </>
          )}

          {isAssistant ? (
            <div className="min-w-0">
              {isIndexUnavailable ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 text-xs text-amber-900 shadow-2xs space-y-2.5">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
                    <span>Search index unavailable</span>
                  </div>
                  <p className="leading-relaxed text-amber-800">
                    {message.content || "The lexical search index could not be reached or is currently rebuilding. Please retry in a moment."}
                  </p>
                  {onFollowUp && Boolean(researchQuestion && researchQuestion.trim()) && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onFollowUp(researchQuestion)}
                      className="h-7 text-xs border-amber-300 hover:bg-amber-100 rounded-full"
                    >
                      <RotateCcw className="h-3 w-3 mr-1" />
                      <span>Retry</span>
                    </Button>
                  )}
                </div>
              ) : isNotLocated ? (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-5 text-xs text-slate-700 shadow-2xs space-y-3.5">
                  <div>
                    <h3 className="text-sm font-semibold tracking-tight text-slate-800">
                      Not found in your selected sources
                    </h3>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {scopeLine}
                    </p>
                  </div>

                  {Array.isArray(meta.weak_matches) && meta.weak_matches.length > 0 && (
                    <div className="space-y-2 pt-1 border-t border-slate-100">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 block">
                        Closest passages (not a match)
                      </span>
                      <div className="space-y-1.5">
                        {meta.weak_matches.map((item, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              openSource(
                                item.source_id || `weak-${idx}`,
                                { claimText: item.excerpt, fullText: item.excerpt },
                                null,
                                researchQuestion
                              );
                              openInspector();
                            }}
                            className="w-full text-left rounded-xl border border-slate-100 bg-slate-50/70 p-2.5 hover:bg-sky-50/50 hover:border-sky-200 transition-colors"
                          >
                            <div className="flex items-center justify-between text-[11px] font-medium text-slate-700">
                              <span className="truncate">{item.title || "Source"}</span>
                              {item.page && <span className="text-slate-400 shrink-0 ml-2">p. {item.page}</span>}
                            </div>
                            {item.excerpt && (
                              <p className="mt-1 text-[11px] text-slate-600 line-clamp-2 leading-relaxed italic">
                                &ldquo;{item.excerpt}&rdquo;
                              </p>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="workbench"
                      onClick={handleOpenAddSources}
                      className="h-8 text-xs rounded-full gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>Add a source</span>
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={handleRephrase}
                      className="h-8 text-xs rounded-full gap-1.5"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      <span>Rephrase</span>
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <ResearchActivityCard
                    summary={message.activity_summary || message.meta?.activity_summary}
                    meta={message.meta}
                    content={message.content}
                    sources={message.sources}
                    isPending={message.pending}
                    progress={message.progress}
                  />
                  <GroundedAnswer
                    rawContent={message.content}
                    sources={message.sources}
                    autoSelectFirstCitation={autoSelectFirstCitation}
                    question={researchQuestion}
                    researchPlan={message.meta?.research || message.metadata?.research || null}
                    messageId={message.id}
                  />
                  {(message.meta?.follow_up_suggestions || message.metadata?.follow_up_suggestions)?.length > 0 && (
                    <div className="mt-4 flex flex-wrap items-center gap-1.5">
                      <span className="mr-0.5 text-[11px] font-medium text-slate-400">Explore further:</span>
                      {(message.meta?.follow_up_suggestions || message.metadata?.follow_up_suggestions).map((chip, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => onFollowUp?.(chip)}
                          className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white px-2.5 py-1 text-[11px] font-medium text-sky-800 transition-colors hover:border-sky-300 hover:bg-sky-50"
                        >
                          <span>{chip}</span><span className="text-sky-500">&rarr;</span>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
