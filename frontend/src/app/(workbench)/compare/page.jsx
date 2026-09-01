"use client";

import React, { useState } from "react";
import { usePapers } from "@/hooks/usePapers";
import { useComparison } from "@/hooks/useComparison";
import { ComparePaperSelector } from "@/components/compare/ComparePaperSelector";
import { ComparisonSynthesisCard } from "@/components/compare/ComparisonSynthesisCard";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GitCompare, Sparkles, AlertCircle, RefreshCw } from "lucide-react";

export default function ComparePapersPage() {
  const { papers, isLoading: isLoadingPapers } = usePapers(1, 50);
  const { comparePapers, comparisonResult, isComparing, isError, error, reset } = useComparison();

  const [selectedIds, setSelectedIds] = useState([]);
  const [focusArea, setFocusArea] = useState("");

  const handleToggle = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const handleRunCompare = async () => {
    if (selectedIds.length < 2) return;
    await comparePapers({
      paper_ids: selectedIds,
      focus_area: focusArea.trim() || undefined,
    });
  };

  const presets = [
    "Compare retriever, dataset benchmarks, and reported top-20 accuracy",
    "Compare core methodology, loss functions, and architectural differences",
    "Compare computational efficiency, latency, and hardware constraints",
  ];

  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-white dark:bg-zinc-950">
      {/* Left & Center Comparison Studio */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
          <div className="flex items-center gap-2">
            <GitCompare className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Multi-Paper Comparison Studio
            </h1>
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            Extract side-by-side matrices and synthesize cross-paper methodologies grounded in ChromaDB.
          </p>
        </div>

        {/* Paper Selector & Focus Prompt */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ComparePaperSelector
            papers={papers}
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
              disabled={selectedIds.length < 2 || isComparing}
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
              <p className="text-[10px] text-amber-600 text-center font-mono">
                Select at least 2 papers to compare.
              </p>
            )}
          </div>
        </div>

        {/* Error Alert */}
        {isError && (
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700 border border-red-200">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>
              {error?.message || "Failed to compare papers via RAG."}
            </span>
          </div>
        )}

        {/* Results Canvas */}
        {comparisonResult && (
          <div className="space-y-4">
            <ComparisonSynthesisCard result={comparisonResult} />
          </div>
        )}
      </div>

      {/* Right Source Inspector */}
      <SourceInspectorRail />
    </div>
  );
}
