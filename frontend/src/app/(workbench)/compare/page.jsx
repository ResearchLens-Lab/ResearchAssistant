"use client";

import React, { useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { usePapers } from "@/hooks/usePapers";
import { useComparison } from "@/hooks/useComparison";
import { papersService } from "@/services/papers.service";
import { ComparePaperSelector } from "@/components/compare/ComparePaperSelector";
import { ComparisonSynthesisCard } from "@/components/compare/ComparisonSynthesisCard";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GitCompare, Sparkles, AlertCircle, RefreshCw, PanelRight } from "lucide-react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

export default function ComparePapersPage() {
  const { papers, isLoading: isLoadingPapers } = usePapers(1, 50);
  const { comparePapers, comparisonResult, isComparing, isError, error, reset } = useComparison();
  const searchParams = useSearchParams();
  const [mobilePanel, setMobilePanel] = useState(false);
  const initialIds = searchParams.get("paper_ids")?.split(",").filter(Boolean) || [];
  const [selectedIds, setSelectedIds] = useState(initialIds);
  const documentQueries = useQueries({ queries: papers.map((paper) => ({ queryKey: ["paperDocuments", paper.id], queryFn: () => papersService.getDocuments(paper.id), staleTime: 10_000 })) });
  const documentsByPaper = useMemo(() => Object.fromEntries(papers.map((paper, index) => [paper.id, documentQueries[index]?.data || []])), [papers, documentQueries]);
  const isLoadingDocuments = documentQueries.some((query) => query.isLoading);
  const canCompare = selectedIds.length >= 2 && selectedIds.every((id) => documentsByPaper[id]?.some((doc) => doc.processing_status === "indexed"));

  const [focusArea, setFocusArea] = useState("");

  const handleToggle = (id) => {
    reset();
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const handleRunCompare = async () => {
    if (!canCompare) return;
    reset();
    try {
      await comparePapers({ paper_ids: selectedIds, focus_area: focusArea.trim() || undefined });
    } catch {
      // The mutation state renders the API error and retry action below.
    }
  };

  const presets = [
    "Compare objectives, methods, results, and limitations where the selected sources report them.",
    "Compare the evaluation settings and explain whether the reported metrics are directly comparable.",
    "Identify disagreements, assumptions, and evidence gaps across the selected papers.",
  ];

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-[#f8faf9]">
      {/* Left & Center Comparison Studio */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="border-b border-slate-200 pb-4 space-y-1">
          <div className="flex items-center gap-2">
            <GitCompare className="h-5 w-5 text-teal-800" />
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Cross-paper research matrix
            </h1>
          </div>
          <p className="text-xs text-slate-600">
            Compare the indexed evidence in your selected papers. Dimensions follow your question and the available passages.
          </p>
          <button type="button" onClick={() => setMobilePanel(true)} className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 xl:hidden"><PanelRight className="h-3.5 w-3.5" />Evidence inspector</button>
        </div>

        {/* Paper Selector & Focus Prompt */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {!isLoadingPapers && papers.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center md:col-span-2"><p className="text-sm font-semibold text-slate-900">No papers to compare yet</p><p className="mt-1 text-xs text-slate-600">Upload and index research documents before building a comparison.</p><Button asChild size="sm" className="mt-3 bg-teal-800 text-white hover:bg-teal-900"><Link href="/papers/upload">Add sources</Link></Button></div> : <>
          <ComparePaperSelector
            papers={papers}
            documentsByPaper={documentsByPaper}
            selectedIds={selectedIds}
            onToggle={handleToggle}
            onClear={() => setSelectedIds([])}
          />

          <div className="rounded-lg border border-zinc-200 bg-white p-4 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
            <div className="flex items-center gap-2 border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <Sparkles className="h-4 w-4 text-indigo-600" />
              <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                Focus Dimensions
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-zinc-600">
                Comparison Focus Prompt
              </label>
              <Input
                placeholder="e.g. Compare loss function and BLEU scores..."
                value={focusArea}
                onChange={(e) => setFocusArea(e.target.value)}
                className="text-xs"
              />
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono text-zinc-400">Quick presets:</span>
              <div className="space-y-1">
                {presets.map((preset) => (
                  <button
                    key={preset}
                    onClick={() => setFocusArea(preset)}
                    className="w-full text-left rounded-md bg-zinc-50 p-1.5 text-[11px] text-zinc-600 hover:bg-zinc-100 transition-colors truncate block dark:bg-zinc-800 dark:text-zinc-300"
                  >
                    &ldquo;{preset}&rdquo;
                  </button>
                ))}
              </div>
            </div>
            <Button
              variant="workbench"
              onClick={handleRunCompare}
              disabled={!canCompare || isComparing}
              className="w-full mt-2 h-8 text-xs gap-1.5 bg-zinc-900 text-white"
            >
              {isComparing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Synthesizing cross-paper analysis...</span>
                </>
              ) : (
                <>
                  <GitCompare className="h-3.5 w-3.5" />
                  <span>
                    Run Comparative RAG ({selectedIds.length} papers selected)
                  </span>
                </>
              )}
            </Button>
            {selectedIds.length < 2 && (
              <p className="text-[10px] text-amber-700 text-center">
                Select at least two papers with indexed files.
              </p>
            )}
            {selectedIds.length >= 2 && !canCompare && <p className="text-center text-[10px] text-amber-700">{isLoadingDocuments ? "Checking document processing status…" : "Each selected paper needs at least one indexed document."}</p>}
          </div>
          </>}
        </div>

        {/* Error Alert */}
        {isError && (
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700 border border-red-200">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>
              {error?.message || "Failed to compare papers via RAG."}
            </span>
            <Button variant="outline" size="sm" onClick={handleRunCompare} disabled={!canCompare || isComparing} className="ml-auto h-7 border-red-300 text-xs">Retry</Button>
          </div>
        )}

        {/* Results Canvas */}
        {comparisonResult && (
          <div className="space-y-4">
          <ComparisonSynthesisCard result={comparisonResult} question={focusArea} />
          </div>
        )}
      </div>

      {/* Right Source Inspector */}
      <SourceInspectorRail className="hidden xl:flex" />
      {mobilePanel && <div className="absolute inset-0 z-40 flex justify-end bg-slate-950/35 xl:hidden" onClick={() => setMobilePanel(false)}><div className="h-full max-w-[90vw] shadow-xl" onClick={(event) => event.stopPropagation()}><SourceInspectorRail onClose={() => setMobilePanel(false)} /></div></div>}
    </div>
  );
}
