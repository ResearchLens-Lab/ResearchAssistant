"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { usePapers } from "@/hooks/usePapers";
import { useComparison } from "@/hooks/useComparison";
import { papersService } from "@/services/papers.service";
import { ComparePaperSelector } from "@/components/compare/ComparePaperSelector";
import { ComparisonSynthesisCard } from "@/components/compare/ComparisonSynthesisCard";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { AlertCircle, Check, FileText, GitCompare, LoaderCircle, PanelRight, Plus, Sparkles, X } from "lucide-react";
import { useCitationStore } from "@/store/citationStore";

const FOCUS_SUGGESTIONS = [
  ["Objectives and research questions", "Compare the objectives and research questions reported in each selected document."],
  ["Definitions and concepts", "Compare how each selected document defines the key concepts and terms."],
  ["Methods and algorithms", "Compare the methods and algorithms described in the selected documents."],
  ["Datasets and experimental setup", "Compare the datasets and experimental setups, preserving their original conditions."],
  ["Findings and results", "Compare the findings and results explicitly reported in each document."],
  ["Strengths and limitations", "Compare the strengths and limitations reported in the selected documents."],
  ["Agreements and evidence gaps", "Identify reported agreements, disagreements, and information missing from the retrieved evidence."],
];

export default function ComparePapersPage() {
  const { papers = [], isLoading: isLoadingPapers } = usePapers(1, 50);
  const { comparePapers, comparisonResult, isComparing, isError, error, reset } = useComparison();
  const searchParams = useSearchParams();
  const preselectionApplied = useRef(false);
  const [mobilePanel, setMobilePanel] = useState(false);
  const { isDrawerOpen, closeDrawer, setSources, setResearchTrace } = useCitationStore();
  const [focusArea, setFocusArea] = useState("");
  const [outputFormat, setOutputFormat] = useState("table");
  const initialDocumentIds = useMemo(() => searchParams.get("document_ids")?.split(",").filter(Boolean) || [], [searchParams]);
  const projectContext = useMemo(() => (searchParams.get("paper_ids") || searchParams.get("paper_id") || "").split(",").filter(Boolean), [searchParams]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState(initialDocumentIds);
  const allPaperIds = useMemo(() => papers.map((paper) => paper.id).sort(), [papers]);
  const documentsQuery = useQuery({
    queryKey: ["comparisonDocuments", allPaperIds],
    queryFn: () => papersService.getDocumentsByPapers(allPaperIds),
    enabled: allPaperIds.length > 0,
    staleTime: 10_000,
    refetchInterval: (query) => Object.values(query.state.data || {}).flat().some((document) => ["uploaded", "queued", "processing", "parsing", "chunking", "embedding", "indexing"].includes(document.processing_status)) ? 3000 : false,
  });
  const documentsByPaper = documentsQuery.data || {};
  const allDocuments = useMemo(() => Object.values(documentsByPaper).flat(), [documentsByPaper]);
  const documentsById = useMemo(() => new Map(allDocuments.map((document) => [document.id, document])), [allDocuments]);
  const selectedDocuments = useMemo(() => selectedDocumentIds.map((id) => documentsById.get(id)).filter(Boolean), [selectedDocumentIds, documentsById]);
  const selectedPapers = useMemo(() => [...new Set(selectedDocuments.map((document) => document.paper_id))].map((id) => papers.find((paper) => paper.id === id)).filter(Boolean), [selectedDocuments, papers]);
  const readyDocumentIds = useMemo(() => allDocuments.filter((document) => document.processing_status === "indexed").map((document) => document.id), [allDocuments]);
  const canCompare = selectedDocuments.length >= 2 && selectedDocuments.length === selectedDocumentIds.length && selectedDocuments.every((document) => document.processing_status === "indexed");
  const minimumMessage = selectedDocumentIds.length < 2 ? "Select at least two distinct indexed documents. You can select multiple documents from the same project." : !canCompare ? "Only indexed documents can be compared. Documents that are still processing or failed indexing are excluded." : "";

  useEffect(() => {
    if (!documentsQuery.isSuccess || preselectionApplied.current) return;
    preselectionApplied.current = true;
    if (initialDocumentIds.length) {
      setSelectedDocumentIds(initialDocumentIds.filter((id) => documentsById.has(id) && documentsById.get(id)?.processing_status === "indexed"));
    } else if (projectContext.length) {
      const ready = projectContext.flatMap((paperId) => (documentsByPaper[paperId] || []).filter((document) => document.processing_status === "indexed").map((document) => document.id));
      setSelectedDocumentIds(ready);
    }
  }, [documentsQuery.isSuccess, initialDocumentIds, projectContext, documentsById, documentsByPaper]);

  useEffect(() => {
    closeDrawer();
    setSources(comparisonResult?.sources || []);
    setResearchTrace(comparisonResult?.metadata?.research || null);
  }, [comparisonResult, closeDrawer, setSources, setResearchTrace]);

  const handleToggleDocument = (id) => {
    reset();
    setSelectedDocumentIds((current) => current.includes(id) ? current.filter((selected) => selected !== id) : [...current, id]);
  };
  const handleToggleProject = (_paperId, readyIds) => {
    reset();
    setSelectedDocumentIds((current) => readyIds.every((id) => current.includes(id)) ? current.filter((id) => !readyIds.includes(id)) : [...new Set([...current, ...readyIds])]);
  };
  const handleFocusChange = (value) => { if (comparisonResult) reset(); setFocusArea(value); };
  const handleFormatChange = (value) => { if (comparisonResult) reset(); setOutputFormat(value); };
  const handleRunCompare = async () => {
    if (!canCompare) return;
    reset();
    try {
      await comparePapers({ document_ids: selectedDocumentIds, focus_area: focusArea.trim() || undefined, output_format: outputFormat });
    } catch { /* Mutation error is rendered in the setup view. */ }
  };

  const formatOptions = [
    { id: "table", title: "Comparison table", description: "Compare each document in a structured matrix." },
    { id: "side_by_side", title: "Side-by-side", description: "Review cited excerpts under each document." },
    { id: "detailed_report", title: "Detailed report", description: "Organize evidence and state its limits." },
  ];

  return (
    <div className="min-h-full w-full bg-[var(--rl-canvas)]">
      <main className="min-h-full px-4 py-3 sm:px-6 lg:px-8">
        <div className="mx-auto flex min-h-full max-w-[1600px] flex-col gap-3">
          <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
            <div><div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><GitCompare className="h-5 w-5" /></span><div><p className="eyebrow text-[var(--rl-primary)]">Research workspace</p><h1 className="text-2xl font-semibold tracking-tight text-[var(--rl-ink)]">Compare &amp; Reports</h1></div></div><p className="mt-2 max-w-3xl text-sm text-[var(--rl-muted)]">Select individual indexed documents, compare sources within or across projects, and review every finding against its cited passages.</p></div>
            {comparisonResult && <Button variant="outline" onClick={() => { reset(); setMobilePanel(false); }} className="h-9 gap-2 text-xs"><Plus className="h-4 w-4" />New comparison</Button>}
          </header>

          <div className="grid items-stretch gap-3 lg:h-[calc(100dvh-14rem)] lg:min-h-[480px] lg:max-h-[720px] lg:grid-cols-[minmax(290px,0.8fr)_minmax(0,1.2fr)]">
            <ComparePaperSelector papers={papers} documentsByPaper={documentsByPaper} selectedDocumentIds={selectedDocumentIds} onToggleDocument={handleToggleDocument} onToggleProject={handleToggleProject} onClear={() => { reset(); setSelectedDocumentIds([]); }} onSelectAll={() => { reset(); setSelectedDocumentIds(readyDocumentIds); }} isLoading={isLoadingPapers || documentsQuery.isLoading} error={documentsQuery.isError ? documentsQuery.error : null} />

            <section className="flex min-h-0 min-w-0 flex-col overflow-y-auto rounded-2xl border border-[var(--rl-border)] bg-white p-3 shadow-sm sm:p-4" aria-label="Comparison setup">
              <div className="flex shrink-0 items-center gap-2 border-b border-slate-100 pb-2.5"><Sparkles className="h-4 w-4 text-[var(--rl-primary)]" /><h2 className="text-sm font-semibold text-[var(--rl-ink)]">Comparison question</h2><span className="ml-auto text-[10px] text-[var(--rl-muted)]">Evidence-only · no generative model</span></div>
              <div className="mt-3 shrink-0 space-y-1.5">
                <label htmlFor="comparison-focus" className="text-sm font-medium text-[var(--rl-ink)]">What do you want to compare?</label>
                <textarea id="comparison-focus" maxLength={500} rows={2} placeholder="Compare how these documents define an algorithm, including its purpose, characteristics and examples." value={focusArea} onChange={(event) => handleFocusChange(event.target.value)} className="min-h-[76px] w-full resize-y rounded-xl border border-[var(--rl-border)] bg-white px-3.5 py-2.5 text-sm leading-5 text-[var(--rl-ink)] placeholder:text-[var(--rl-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)]" />
                <div className="flex items-start justify-between gap-3"><p className="text-[11px] leading-4 text-[var(--rl-muted)]">One shared question across selected documents. Unsupported details stay marked as missing.</p><span className="shrink-0 text-[10px] tabular-nums text-[var(--rl-muted)]">{focusArea.length}/500</span></div>
              </div>

              <div className="mt-3 shrink-0"><p className="mb-1.5 text-[10px] font-medium text-[var(--rl-muted)]">Suggested comparison focus</p><div className="flex flex-wrap gap-1.5">{FOCUS_SUGGESTIONS.map(([label, prompt]) => <button key={label} type="button" onClick={() => handleFocusChange(prompt)} className={`rounded-full border px-2.5 py-1 text-[10px] transition-colors ${focusArea === prompt ? "border-[var(--rl-primary)] bg-[var(--rl-selected)] text-[var(--rl-primary)]" : "border-[var(--rl-border)] bg-white text-[var(--rl-muted)] hover:bg-[var(--rl-tint)]"}`}>{label}</button>)}</div></div>

              <fieldset className="mt-3 shrink-0"><legend className="mb-1.5 text-xs font-semibold text-[var(--rl-ink)]">Report format</legend><div className="grid gap-1.5 sm:grid-cols-3">{formatOptions.map((option) => <label key={option.id} className={`cursor-pointer rounded-xl border p-2.5 transition-colors ${outputFormat === option.id ? "border-[var(--rl-primary)] bg-[var(--rl-selected)]/50" : "border-[var(--rl-border)] hover:bg-slate-50"}`}><input type="radio" name="comparison-format" value={option.id} checked={outputFormat === option.id} onChange={() => handleFormatChange(option.id)} className="sr-only" /><span className="flex items-center justify-between gap-2 text-[11px] font-semibold text-[var(--rl-ink)]">{option.title}{outputFormat === option.id && <Check className="h-3.5 w-3.5 text-[var(--rl-primary)]" />}</span><span className="mt-0.5 block text-[9px] leading-3 text-[var(--rl-muted)]">{option.description}</span></label>)}</div></fieldset>

              <div className="mt-3 min-h-0 flex-1 rounded-xl border border-[var(--rl-border)] bg-[var(--rl-canvas)] p-2.5">
                <div className="flex items-center justify-between gap-2"><p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--rl-muted)]">Selected documents</p><span className="text-xs font-semibold text-[var(--rl-primary)]">{selectedDocuments.length} selected</span></div>
                {selectedDocuments.length ? <div className="mt-2 flex flex-wrap gap-2">{selectedDocuments.map((document) => { const paper = papers.find((item) => item.id === document.paper_id); return <span key={document.id} className="inline-flex max-w-full items-center gap-2 rounded-lg border border-[var(--rl-border)] bg-white py-1.5 pl-2.5 pr-1.5 text-[11px] text-[var(--rl-ink)]" title={`${paper?.title || "Project"} · ${document.filename}`}><FileText className="h-3.5 w-3.5 shrink-0 text-[var(--rl-primary)]" /><span className="max-w-64 truncate">{document.filename}</span><button type="button" onClick={() => handleToggleDocument(document.id)} aria-label={`Remove ${document.filename}`} className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="h-3.5 w-3.5" /></button></span>; })}</div> : <p className="mt-2 text-xs text-[var(--rl-muted)]">Choose two or more indexed documents on the left. They may come from the same project.</p>}
              </div>

              <div className="sticky bottom-0 z-10 -mx-3 mt-2 shrink-0 border-t border-slate-100 bg-white px-3 pt-2.5 sm:-mx-4 sm:px-4">
                <Button variant="workbench" onClick={handleRunCompare} disabled={!canCompare || isComparing || documentsQuery.isLoading} className="h-10 w-full gap-2 text-sm">
                  {isComparing ? <><LoaderCircle className="h-4 w-4 animate-spin" />Retrieving evidence from each selected document…</> : <><GitCompare className="h-4 w-4" />Generate comparison · {selectedDocuments.length} {selectedDocuments.length === 1 ? "source" : "sources"}</>}
                </Button>
                {minimumMessage && <p className="mt-1.5 text-center text-[10px] leading-4 text-amber-800">{minimumMessage}</p>}
              </div>
            </section>
          </div>

          {isError && <div role="alert" className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"><AlertCircle className="h-4 w-4 shrink-0" /><span className="min-w-0 flex-1">{error?.message || "The comparison could not be generated."}</span><Button variant="outline" size="sm" onClick={handleRunCompare} disabled={!canCompare || isComparing} className="h-8 border-rose-300 text-xs">Retry</Button></div>}

          {comparisonResult && <div className="space-y-3">
            <div className="flex justify-end"><button type="button" disabled={!comparisonResult.sources?.length} onClick={() => { setSources(comparisonResult.sources || []); setResearchTrace(comparisonResult.metadata?.research || null); setMobilePanel(true); }} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[var(--rl-border)] bg-white px-3 text-xs font-medium text-[var(--rl-ink)] hover:bg-[var(--rl-tint)] disabled:opacity-50"><PanelRight className="h-3.5 w-3.5" />Open evidence trail</button></div>
            <ComparisonSynthesisCard result={comparisonResult} question={comparisonResult.metadata?.focus_area || focusArea} paperTitles={selectedDocuments.map((document) => document.filename)} outputFormat={outputFormat} documentScope={comparisonResult.metadata?.comparison_scope || []} projectTitles={selectedPapers.map((paper) => paper.title)} />
          </div>}
        </div>
      </main>

      {(mobilePanel || isDrawerOpen) && <div role="dialog" aria-modal="true" aria-label="Evidence Trail" className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end bg-slate-950/35" onClick={() => { setMobilePanel(false); closeDrawer(); }} onKeyDown={(event) => { if (event.key === "Escape") { setMobilePanel(false); closeDrawer(); } }}><div className="h-full w-[min(26rem,94vw)] shadow-xl" onClick={(event) => event.stopPropagation()}><SourceInspectorRail onClose={() => { setMobilePanel(false); closeDrawer(); }} /></div></div>}
    </div>
  );
}
