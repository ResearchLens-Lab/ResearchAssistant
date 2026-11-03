"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { useCitationStore } from "@/store/citationStore";

export default function ComparePapersPage() {
  const { papers, isLoading: isLoadingPapers } = usePapers(1, 50);
  const { comparePapers, comparisonResult, isComparing, isError, error, reset } = useComparison();
  const searchParams = useSearchParams();
  const [mobilePanel, setMobilePanel] = useState(false);
  const { isDrawerOpen, closeDrawer, setSources } = useCitationStore();
  const initialIds = searchParams.get("paper_ids")?.split(",").filter(Boolean) || [];
  const [selectedIds, setSelectedIds] = useState(initialIds);
  const selectedPaperIds = useMemo(() => selectedIds.filter((id) => papers.some((paper) => paper.id === id)), [papers, selectedIds]);
  const selectedPaperIdsKey = useMemo(() => [...selectedPaperIds].sort(), [selectedPaperIds]);
  const documentsQuery = useQuery({
    queryKey: ["paperDocumentsByPapers", selectedPaperIdsKey],
    queryFn: () => papersService.getDocumentsByPapers(selectedPaperIdsKey),
    enabled: selectedPaperIdsKey.length > 0,
    staleTime: 10_000,
  });
  const documentsByPaper = documentsQuery.data || {};
  const checkedPaperIds = documentsQuery.isLoading ? [] : selectedPaperIds;
  const errorPaperIds = documentsQuery.isError ? selectedPaperIds : [];
  const isLoadingDocuments = documentsQuery.isLoading;
  const canCompare = selectedIds.length >= 2 && selectedIds.every((id) => documentsByPaper[id]?.some((doc) => doc.processing_status === "indexed"));
  const canInspectEvidence = Boolean(comparisonResult?.sources?.length);

  useEffect(() => {
    closeDrawer();
    setSources(comparisonResult?.sources || []);
  }, [comparisonResult, closeDrawer, setSources]);

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
    <div className="relative flex h-[calc(100dvh-4rem)] w-full overflow-hidden bg-[var(--rl-canvas)]">
      {/* Left & Center Comparison Studio */}
      <div className="flex-1 overflow-y-auto space-y-6 p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto">
        {/* Header */}
        <div className="border-b border-slate-200 pb-4 space-y-1">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><GitCompare className="h-5 w-5" /></span>
            <h1 className="text-2xl font-semibold tracking-tight text-[var(--rl-ink)] sm:text-3xl">
              Comparison Builder
            </h1>
          </div>
          <p className="text-sm leading-6 text-[var(--rl-muted)]">
            Compare indexed papers with a question grounded in the passages each source provides. Missing fields stay explicit.
          </p>
          <button type="button" disabled={!canInspectEvidence} title={!canInspectEvidence ? "Generate a comparison with returned evidence before inspecting citations" : undefined} onClick={() => { setSources(comparisonResult.sources); setMobilePanel(true); }} className="mt-2 inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[var(--rl-border)] bg-white px-3 text-xs font-medium text-[var(--rl-ink)] hover:bg-[var(--rl-tint)] disabled:cursor-not-allowed disabled:opacity-50"><PanelRight className="h-3.5 w-3.5" />Evidence Trail</button>
        </div>

        {/* Paper Selector & Focus Prompt */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {!isLoadingPapers && papers.length === 0 ? <div className="rounded-xl border border-dashed border-[var(--rl-border)] bg-white p-8 text-center md:col-span-2"><p className="text-base font-semibold text-[var(--rl-ink)]">No projects to compare yet</p><p className="mt-1 text-sm text-[var(--rl-muted)]">Add and index research sources before building a comparison.</p><Button asChild size="sm" variant="workbench" className="mt-3"><Link href="/papers/upload">Add sources</Link></Button></div> : <>
          <ComparePaperSelector
            papers={papers}
            documentsByPaper={documentsByPaper}
            checkedPaperIds={checkedPaperIds}
            loadingPaperIds={documentsQuery.isLoading ? selectedPaperIds : []}
            errorPaperIds={errorPaperIds}
            selectedIds={selectedIds}
            onToggle={handleToggle}
            onClear={() => setSelectedIds([])}
          />

          <div className="rounded-2xl border border-[var(--rl-border)] bg-white p-4 shadow-sm space-y-4">
            <div className="flex items-center gap-2 border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <Sparkles className="h-4 w-4 text-[var(--rl-primary)]" />
              <span className="text-sm font-semibold text-[var(--rl-ink)]">
                Comparison question
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-[var(--rl-ink)]">
                What would you like to compare?
              </label>
              <Input
                placeholder="Compare the reported evaluation methods and their conditions…"
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
                    className="w-full rounded-lg bg-[var(--rl-tint)] p-2.5 text-left text-xs leading-5 text-[var(--rl-muted)] hover:bg-[var(--rl-selected)] transition-colors"
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
              className="w-full mt-2 h-10 gap-1.5 text-sm"
            >
              {isComparing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Comparing selected evidence…</span>
                </>
              ) : (
                <>
                  <GitCompare className="h-3.5 w-3.5" />
                  <span>
                    Generate comparison ({selectedIds.length} selected)
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
      {(mobilePanel || isDrawerOpen) && <div role="dialog" aria-modal="true" aria-label="Evidence Trail" className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end bg-slate-950/35" onClick={() => { setMobilePanel(false); closeDrawer(); }} onKeyDown={(event) => { if (event.key === "Escape") { setMobilePanel(false); closeDrawer(); } }}><div className="h-full w-[min(26rem,94vw)] shadow-xl" onClick={(event) => event.stopPropagation()}><SourceInspectorRail onClose={() => { setMobilePanel(false); closeDrawer(); }} /></div></div>}
    </div>
  );
}


