"use client";

import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePapers } from "@/hooks/usePapers";
import { papersService } from "@/services/papers.service";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, FileText, Layers, Plus, Search, AlertCircle, X, CheckCircle2, ChevronLeft } from "lucide-react";
import { documentType, indexedPaperIds } from "@/lib/researchWorkspace.mjs";
import Link from "next/link";

const statusStyles = {
  indexed: "bg-emerald-50 text-emerald-700 border border-emerald-200/60",
  processing: "bg-amber-50 text-amber-700 border border-amber-200/60",
  uploaded: "bg-sky-50 text-sky-700 border border-sky-200/60",
  failed: "bg-rose-50 text-rose-700 border border-rose-200/60",
  cancelled: "bg-slate-100 text-slate-600 border border-slate-200/60",
};

function formatDocumentDisplayName(filename, paperTitle) {
  if (!filename) return "Document";
  const ext = filename.lastIndexOf(".") > 0 ? filename.slice(filename.lastIndexOf(".")) : "";
  const base = filename.slice(0, filename.length - ext.length);
  const isHashOrUuid = /^[0-9a-f]{16,}$/i.test(base) || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(base);
  const isRawTimestamp = /^\d{10,13}(_|\-)?([0-9a-f]+)?$/i.test(base);
  if ((isHashOrUuid || isRawTimestamp) && paperTitle) {
    return `${paperTitle}${ext}`;
  }
  return filename;
}

export function PaperScopeRail({ className = "", onClose }) {
  const { papers, isLoading, isError, error } = usePapers(1, 50);
  const {
    selectedPaperIds,
    selectedDocumentIds,
    togglePaper,
    toggleDocument,
    selectPapers,
    clearSelection,
  } = useChatScopeStore();

  const [filter, setFilter] = useState("");
  const paperIds = useMemo(() => papers.map((paper) => paper.id), [papers]);
  const documentsQuery = useQuery({
    queryKey: ["paperDocumentsByPapers", paperIds],
    queryFn: () => papersService.getDocumentsByPapers(paperIds),
    enabled: paperIds.length > 0,
    staleTime: 10_000,
  });
  const documentsByPaper = documentsQuery.data || {};
  const entries = useMemo(() => papers.map((paper) => ({
    paper,
    documents: documentsByPaper[paper.id] || [],
    loading: documentsQuery.isLoading,
    error: documentsQuery.isError,
  })), [papers, documentsByPaper, documentsQuery.isLoading, documentsQuery.isError]);

  const filteredEntries = entries.filter(({ paper, documents }) =>
    `${paper.title} ${(paper.authors || []).join(" ")} ${documents.map((doc) => doc.filename).join(" ")}`.toLowerCase().includes(filter.toLowerCase()));

  const selectableIds = indexedPaperIds(entries);

  const allIndexedDocIds = useMemo(() => {
    const ids = [];
    for (const e of entries) {
      for (const doc of e.documents) {
        if (doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0)) {
          ids.push(doc.id);
        }
      }
    }
    return ids;
  }, [entries]);

  const handleSelectAllIndexed = () => {
    selectPapers(selectableIds, allIndexedDocIds);
  };

  const totalSelectedDocs = selectedDocumentIds.length;

  return (
    <aside aria-label="Research sources" className={`flex h-full w-full min-w-0 flex-col border-r border-[var(--rl-border)] bg-[var(--rl-canvas)] ${className}`}>
      <div className="border-b border-slate-200 bg-white px-3.5 py-3 space-y-2.5 shrink-0 min-w-0">
        {/* Prominent Back Button to return to Chat / Sessions */}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-2 text-xs font-semibold text-sky-700 bg-sky-50/80 hover:bg-sky-100 hover:text-sky-900 px-3 py-2 rounded-lg border border-sky-200/80 transition-all w-full group mb-1 cursor-pointer shadow-2xs"
            title="Return to research sessions"
          >
            <ChevronLeft className="h-4 w-4 text-sky-600 group-hover:-translate-x-0.5 transition-transform shrink-0" />
            <span className="font-medium">Back to Research Sessions</span>
          </button>
        )}

        <div className="flex items-center justify-between gap-2 min-w-0">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--rl-primary)]">RESEARCH LIBRARY</p>
            <h2 className="mt-0.5 flex items-center gap-1.5 text-base font-semibold text-[var(--rl-ink)]">
              <Layers className="h-4 w-4 shrink-0 text-[var(--rl-primary)]" />
              <span className="truncate">Sources &amp; projects</span>
            </h2>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button asChild variant="soft" size="sm" className="h-7 gap-1 px-2 text-[11px]">
              <Link href={selectedPaperIds.length === 1 ? `/papers/upload?paper_id=${selectedPaperIds[0]}` : "/papers/upload"} aria-label="Add source documents">
                <Plus className="h-3 w-3" />
                <span>Add sources</span>
              </Link>
            </Button>
            {onClose && (
              <button
                type="button"
                aria-label="Close sources"
                onClick={onClose}
                className="rounded-md p-1.5 text-slate-500 hover:bg-[var(--rl-tint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)]"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs text-slate-600 min-w-0">
          <span className="font-medium text-slate-700 truncate">
            {totalSelectedDocs > 0
              ? `${totalSelectedDocs} source${totalSelectedDocs === 1 ? "" : "s"} (${selectedPaperIds.length} project${selectedPaperIds.length === 1 ? "" : "s"})`
              : `${selectedPaperIds.length} project${selectedPaperIds.length === 1 ? "" : "s"} selected`}
          </span>
          <span className="flex gap-1 shrink-0">
            <button
              type="button"
              onClick={handleSelectAllIndexed}
              disabled={!selectableIds.length}
              className="rounded px-1.5 py-0.5 text-xs font-medium text-[var(--rl-primary)] hover:bg-slate-100 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)]"
            >
              Select indexed
            </button>
            <button
              type="button"
              onClick={clearSelection}
              disabled={!selectedPaperIds.length && !totalSelectedDocs}
              className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-500 hover:bg-slate-100 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
            >
              Clear
            </button>
          </span>
        </div>

        {/* Informative scope badge banners */}
        {selectableIds.length > 0 && selectedPaperIds.length === 0 && totalSelectedDocs === 0 && (
          <div className="rounded-md bg-amber-50 p-2 text-[11px] text-amber-800 border border-amber-200">
            No sources selected. Check one or more projects or sources below to ground your question.
          </div>
        )}

        {selectableIds.length === 0 && !isLoading && papers.length > 0 && (
          <div className="rounded-md bg-slate-100 p-2 text-[11px] text-slate-700 border border-slate-200">
            No indexed sources available. Upload and wait for documents to finish indexing.
          </div>
        )}

        <label className="relative block">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            aria-label="Filter papers and files"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter papers or files..."
            className="h-8 w-full min-w-0 rounded-md border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)]"
          />
        </label>
      </div>

      <ScrollArea className="min-h-0 flex-1 p-3">
        {isLoading ? (
          <div className="space-y-2.5" aria-label="Loading source library">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-24 animate-pulse rounded-lg bg-slate-200/70" />
            ))}
          </div>
        ) : isError ? (
          <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
            <AlertCircle className="mb-1 h-4 w-4" />
            {error?.message || "Could not load your source library."}
          </div>
        ) : papers.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-center">
            <BookOpen className="mx-auto h-6 w-6 text-slate-400" />
            <p className="mt-2 text-sm font-medium text-slate-800">Your library is empty</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">Upload research papers and supporting files to begin.</p>
            <Button asChild size="sm" variant="workbench" className="mt-3">
              <Link href="/papers/upload">Add sources</Link>
            </Button>
          </div>
        ) : filteredEntries.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-slate-500">No sources match “{filter}”.</p>
        ) : (
          <div className="space-y-3 min-w-0">
            {filteredEntries.map(({ paper, documents, loading, error: docsError }) => {
              const isPaperSelected = selectedPaperIds.includes(paper.id);
              const indexedDocs = documents.filter((doc) => doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0));
              const indexedCount = indexedDocs.length;
              const totalChunks = indexedDocs.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);

              const allIndexedSelected = indexedCount > 0 && indexedDocs.every((doc) => selectedDocumentIds.includes(doc.id));
              const someIndexedSelected = indexedDocs.some((doc) => selectedDocumentIds.includes(doc.id));
              const isChecked = allIndexedSelected || (isPaperSelected && (indexedCount === 0 || someIndexedSelected));
              const disabled = !loading && !indexedCount && !isPaperSelected;

              const handleToggleProject = () => {
                const docIds = indexedDocs.map((d) => d.id);
                togglePaper(paper.id, docIds);
              };

              return (
                <section
                  key={paper.id}
                  className={`rounded-lg border bg-white transition-colors overflow-hidden min-w-0 max-w-full ${
                    isChecked
                      ? "border-[var(--rl-primary)] ring-1 ring-[var(--rl-primary)]/20 shadow-2xs"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  {/* Project Header Row */}
                  <div className="flex items-start gap-2.5 p-3 min-w-0 bg-slate-50/40">
                    <Checkbox
                      aria-label={`Select ${paper.title}`}
                      checked={isChecked}
                      disabled={disabled}
                      onCheckedChange={handleToggleProject}
                      className="mt-0.5 shrink-0 data-[state=checked]:bg-[#1d6fc4] data-[state=checked]:border-[#1d6fc4] data-[state=checked]:text-white"
                    />
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={handleToggleProject}
                      className="min-w-0 flex-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)]"
                    >
                      <span
                        className="block text-xs font-semibold leading-snug text-slate-900 break-words"
                        title={paper.title}
                      >
                        {paper.title}
                      </span>
                      <span className="mt-0.5 block truncate text-[11px] text-slate-500">
                        {paper.authors?.join(", ") || "Author not listed"}
                        {paper.publication_year ? ` · ${paper.publication_year}` : ""}
                      </span>
                    </button>
                  </div>

                  {/* Attached Documents Container with Per-Document Selection */}
                  <div className="border-t border-slate-100 p-2.5 bg-white min-w-0 space-y-1.5">
                    {loading ? (
                      <p className="text-[11px] text-slate-400">Loading document status…</p>
                    ) : docsError ? (
                      <p role="alert" className="text-[11px] text-rose-700">Document status unavailable</p>
                    ) : documents.length ? (
                      <ul className="space-y-1.5 min-w-0">
                        {documents.map((doc) => {
                          const isIndexed = doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0);
                          const isDocSelected = selectedDocumentIds.includes(doc.id);

                          return (
                            <li
                              key={doc.id}
                              className={`rounded-md border p-2 text-xs transition-colors min-w-0 ${
                                isDocSelected
                                  ? "border-sky-300 bg-sky-50/30 shadow-2xs"
                                  : "border-slate-200/80 bg-white hover:border-slate-300"
                              }`}
                            >
                              {/* Row 1: Checkbox + Document Icon + Filename */}
                              <div className="flex items-center gap-2 min-w-0">
                                <Checkbox
                                  id={`doc-select-${doc.id}`}
                                  aria-label={`Select ${doc.filename}`}
                                  checked={isDocSelected}
                                  disabled={!isIndexed}
                                  onCheckedChange={() => toggleDocument(doc.id, paper.id)}
                                  className="shrink-0"
                                />
                                <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                                {(() => {
                                  const displayName = formatDocumentDisplayName(doc.filename, paper.title);
                                  const truncatedDisplay = displayName.length > 28 ? displayName.slice(0, 25) + "..." : displayName;
                                  return (
                                    <label
                                      htmlFor={`doc-select-${doc.id}`}
                                      className={`min-w-0 flex-1 truncate text-xs font-medium cursor-pointer ${
                                        isIndexed ? "text-slate-800" : "text-slate-400 cursor-not-allowed"
                                      }`}
                                      title={doc.filename}
                                    >
                                      {truncatedDisplay}
                                    </label>
                                  );
                                })()}
                              </div>

                              {/* Row 2: Format Badge, Chunk Count, Status Badge, Quick Focus Button */}
                              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1.5 pl-6">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                                    {documentType(doc.filename)}
                                  </span>
                                  {doc.chunk_count ? (
                                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 font-mono">
                                      {doc.chunk_count.toLocaleString()} chunks
                                    </span>
                                  ) : null}
                                  <span
                                    className={`rounded px-1.5 py-0.5 text-[11px] font-medium capitalize ${
                                      statusStyles[doc.processing_status] || "bg-slate-100 text-slate-600"
                                    }`}
                                  >
                                    {doc.processing_status}
                                  </span>
                                </div>
                                {isIndexed && (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      selectPapers([paper.id], [doc.id]);
                                    }}
                                    className="text-[11px] font-medium text-sky-600 hover:text-sky-800 hover:underline px-1 py-0.5 rounded cursor-pointer"
                                    title={`Ask questions specifically from ${doc.filename}`}
                                  >
                                    Only this source
                                  </button>
                                )}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p className="text-[11px] text-slate-500">No files attached · paper scope unavailable</p>
                    )}

                    {/* Project Status Summary Footer */}
                    {indexedCount > 0 && (
                      <div className="mt-2 flex min-w-0 flex-wrap items-center justify-between gap-1 border-t border-slate-100 pt-1.5 text-[11px] text-slate-500">
                        <span className="flex min-w-0 items-center gap-1 text-emerald-700 font-medium truncate">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{indexedCount} indexed file{indexedCount === 1 ? "" : "s"}</span>
                          {totalChunks > 0 && (
                            <span className="shrink-0 text-slate-400 font-normal">({totalChunks.toLocaleString()} chunks)</span>
                          )}
                        </span>
                        <Link
                          href={`/papers/${paper.id}`}
                          onClick={(event) => event.stopPropagation()}
                          className="font-medium text-[var(--rl-primary)] hover:underline shrink-0"
                        >
                          Details
                        </Link>
                      </div>
                    )}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        <p className="mt-3 px-1 text-[11px] leading-relaxed text-slate-400 break-words">
          Select entire projects or choose individual sources above to precisely control the research boundary for your inquiry.
        </p>
      </ScrollArea>
    </aside>
  );
}
