"use client";

import React from "react";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BookOpen, ShieldCheck, AlertCircle, RefreshCw, Sparkles, ArrowRight } from "lucide-react";
import { useCitationStore } from "@/store/citationStore";

export function GroundedSummaryCard({
  summary,
  isLoading,
  onGenerate,
  error,
  hasIndexedSources = true,
  isCheckingSources = false,
  isSourceError = false,
  onAskInDesk,
}) {
  const { setSources } = useCitationStore();

  const handleGenerate = async () => {
    const res = await onGenerate();
    if (res?.sources) {
      setSources(res.sources);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-5 space-y-4 shadow-2xs min-h-[340px]">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-[#1d6fc4]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
            Grounded summary
          </h3>
          {summary && (
            <Badge variant="grounded" className="text-[11px] gap-1">
              <ShieldCheck className="h-3 w-3" />
              {summary.sources?.length || 0} citations
            </Badge>
          )}
        </div>

        <Button
          variant={summary ? "outline" : "workbench"}
          size="sm"
          onClick={handleGenerate}
          disabled={isLoading || !hasIndexedSources}
          title={!hasIndexedSources ? "Add and index a source before generating a grounded summary" : undefined}
          className="h-7 text-xs gap-1.5 rounded-full"
        >
          {isLoading ? (
            <>
              <RefreshCw className="h-3 w-3 animate-spin" />
              <span>Synthesizing from ChromaDB...</span>
            </>
          ) : summary ? (
            <>
              <RefreshCw className="h-3 w-3" />
              <span>Regenerate</span>
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              <span>Generate grounded summary</span>
            </>
          )}
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 p-3 text-xs text-red-700 border border-red-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message || "Failed to generate summary from RAG."}</span>
        </div>
      )}

      {isSourceError ? (
        <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          Project source status is unavailable. Retry the source list before generating a summary.
        </p>
      ) : isCheckingSources ? (
        <div aria-label="Loading project sources" aria-busy="true" className="space-y-2 py-4">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" />
        </div>
      ) : summary ? (
        <div className="pt-1 space-y-4">
          <GroundedAnswer content={summary.answer} sources={summary.sources} />
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 flex-wrap gap-2">
            <span className="text-[11px] text-slate-400">
              Click any citation badge to view source excerpt
            </span>
            {onAskInDesk && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onAskInDesk}
                className="h-7 text-xs text-[#1d6fc4] hover:bg-sky-50 gap-1 rounded-full"
              >
                <span>Ask questions in Research Desk</span>
                <ArrowRight className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>
      ) : !isLoading ? (
        <div className="py-12 text-center text-slate-400 space-y-2">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-[#1d6fc4]">
            <BookOpen className="h-5 w-5" />
          </div>
          <p className="text-sm font-medium text-slate-700">
            {hasIndexedSources ? "No grounded summary generated yet" : "No indexed sources yet"}
          </p>
          <p className="text-[11px] text-slate-400 max-w-sm mx-auto leading-relaxed">
            {hasIndexedSources
              ? "Synthesize key arguments and research evidence across your project sources with precise citation links."
              : "Upload and index at least one source document in the left pane to generate a cited synthesis."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
