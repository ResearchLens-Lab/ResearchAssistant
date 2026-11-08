"use client";

import React from "react";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sparkles, ShieldCheck, AlertCircle, RefreshCw } from "lucide-react";
import { useCitationStore } from "@/store/citationStore";

export function GroundedSummaryCard({
  summary,
  isLoading,
  onGenerate,
  error,
  hasIndexedSources = true,
  isCheckingSources = false,
  isSourceError = false,
}) {
  const { setSources } = useCitationStore();

  const handleGenerate = async () => {
    const res = await onGenerate();
    if (res?.sources) {
      setSources(res.sources);
    }
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 space-y-4 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="flex items-center justify-between border-b border-zinc-100 pb-3 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[var(--rl-primary)]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
            RAG Grounded Summary
          </h3>
          {summary && (
            <Badge variant="grounded" className="text-[10px] gap-1">
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
          className="h-7 text-xs gap-1.5"
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
              <Sparkles className="h-3 w-3" />
              <span>Generate Grounded Summary</span>
            </>
          )}
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700 border border-red-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message || "Failed to generate summary from RAG."}</span>
        </div>
      )}

      {isSourceError ? (
        <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">Project source status is unavailable. Retry the source list before generating a summary.</p>
      ) : isCheckingSources ? (
        <div aria-label="Loading project sources" aria-busy="true" className="space-y-2 py-4">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" />
        </div>
      ) : summary ? (
        <div className="pt-1">
          <GroundedAnswer content={summary.answer} sources={summary.sources} />
        </div>
      ) : !isLoading ? (
        <div className="py-6 text-center text-zinc-400 space-y-1">
          <p className="text-xs font-medium text-zinc-600">
            {hasIndexedSources ? "No summary generated yet" : "No indexed sources yet"}
          </p>
          <p className="text-[11px] text-zinc-400">
            {hasIndexedSources ? "Generate a structured synthesis with citations linked to the source passages." : "Add and index a source before generating a grounded summary."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
