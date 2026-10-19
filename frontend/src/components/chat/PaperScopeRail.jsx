"use client";

import React, { useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { usePapers } from "@/hooks/usePapers";
import { papersService } from "@/services/papers.service";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, FileText, Layers, Plus, Search, AlertCircle, X } from "lucide-react";
import { documentType, indexedPaperIds } from "@/lib/researchWorkspace.mjs";
import Link from "next/link";

const statusStyles = {
  indexed: "bg-emerald-50 text-emerald-700",
  processing: "bg-amber-50 text-amber-700",
  uploaded: "bg-sky-50 text-sky-700",
  failed: "bg-rose-50 text-rose-700",
};

export function PaperScopeRail({ className = "", onClose }) {
  const { papers, isLoading, isError, error } = usePapers(1, 50);
  const { selectedPaperIds, togglePaper, selectPapers, clearSelection } = useChatScopeStore();
  const [filter, setFilter] = useState("");
  const documentQueries = useQueries({
    queries: papers.map((paper) => ({
      queryKey: ["paperDocuments", paper.id],
      queryFn: () => papersService.getDocuments(paper.id),
      staleTime: 10_000,
    })),
  });
  const entries = useMemo(() => papers.map((paper, index) => ({
    paper,
    documents: documentQueries[index]?.data || [],
    loading: documentQueries[index]?.isLoading,
    error: documentQueries[index]?.isError,
  })), [papers, documentQueries]);
  const filteredEntries = entries.filter(({ paper, documents }) =>
    `${paper.title} ${(paper.authors || []).join(" ")} ${documents.map((doc) => doc.filename).join(" ")}`.toLowerCase().includes(filter.toLowerCase()));
  const selectableIds = indexedPaperIds(entries);

  return (
    <aside aria-label="Research sources" className={`flex h-full w-72 shrink-0 flex-col border-r border-slate-200 bg-[#f8faf9] ${className}`}>
      <div className="border-b border-slate-200 bg-white px-4 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-teal-700">Research library</p>
            <h2 className="mt-1 flex items-center gap-2 text-sm font-semibold text-slate-900"><Layers className="h-4 w-4 text-teal-700" />Source scope</h2>
          </div>
          {onClose && <button autoFocus type="button" aria-label="Close sources" onClick={onClose} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"><X className="h-4 w-4" /></button>}
          <Button asChild variant="outline" size="sm" className="h-8 gap-1.5 border-slate-300 px-2.5 text-xs">
            <Link href="/papers/upload" aria-label="Upload source documents"><Plus className="h-3.5 w-3.5" /> Add</Link>
          </Button>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-slate-600">
          <span>{selectedPaperIds.length} paper{selectedPaperIds.length === 1 ? "" : "s"} selected</span>
          <span className="flex gap-2">
            <button type="button" onClick={() => selectPapers(selectableIds)} className="rounded px-1 py-1 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Select indexed</button>
            <button type="button" onClick={clearSelection} className="rounded px-1 py-1 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Clear</button>
          </span>
        </div>
        <label className="relative mt-3 block">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input aria-label="Filter papers and files" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter papers or files" className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700" />
        </label>
      </div>

      <ScrollArea className="min-h-0 flex-1 p-3">
        {isLoading ? (
          <div className="space-y-2" aria-label="Loading source library">{[0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-lg bg-slate-200/70" />)}</div>
        ) : isError ? (
          <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800"><AlertCircle className="mb-1 h-4 w-4" />{error?.message || "Could not load your source library."}</div>
        ) : papers.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-center">
            <BookOpen className="mx-auto h-6 w-6 text-slate-400" />
            <p className="mt-2 text-sm font-medium text-slate-800">Your library is ready</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">Upload research papers and supporting files to begin.</p>
            <Button asChild size="sm" className="mt-3 bg-teal-800 text-white hover:bg-teal-900"><Link href="/papers/upload">Upload sources</Link></Button>
          </div>
        ) : filteredEntries.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-slate-500">No sources match “{filter}”.</p>
        ) : (
          <div className="space-y-2">
            {filteredEntries.map(({ paper, documents, loading, error: docsError }) => {
              const selected = selectedPaperIds.includes(paper.id);
              const indexedCount = documents.filter((doc) => doc.processing_status === "indexed").length;
              const disabled = !loading && !indexedCount && !selected;
              return (
                <section key={paper.id} className={`rounded-lg border bg-white transition-colors ${selected ? "border-teal-700 ring-1 ring-teal-700/15" : "border-slate-200 hover:border-slate-300"}`}>
                  <div className="flex gap-2.5 p-3">
                    <Checkbox aria-label={`Select ${paper.title}`} checked={selected} disabled={disabled} onCheckedChange={() => togglePaper(paper.id)} className="mt-0.5" />
                    <button type="button" disabled={disabled} onClick={() => togglePaper(paper.id)} className="min-w-0 flex-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">
                      <span className="block truncate text-xs font-semibold leading-5 text-slate-900" title={paper.title}>{paper.title}</span>
                      <span className="mt-0.5 block truncate text-[10px] text-slate-500">{paper.authors?.join(", ") || "Author not listed"}{paper.publication_year ? ` · ${paper.publication_year}` : ""}</span>
                    </button>
                  </div>
                  <div className="border-t border-slate-100 px-3 py-2">
                    {loading ? <p className="text-[10px] text-slate-400">Loading document status…</p> : docsError ? <p role="alert" className="text-[10px] text-rose-700">Document status unavailable</p> : documents.length ? (
                      <ul className="space-y-1.5">
                        {documents.map((doc) => <li key={doc.id} title={doc.filename} className="flex min-w-0 items-center gap-1.5 text-[10px]">
                          <FileText className="h-3 w-3 shrink-0 text-slate-400" />
                          <span className="min-w-0 flex-1 truncate text-slate-600">{doc.filename}</span>
                          <span className="rounded bg-slate-100 px-1 py-0.5 font-medium text-slate-500">{documentType(doc.filename)}</span>
                          <span className={`rounded px-1.5 py-0.5 font-medium capitalize ${statusStyles[doc.processing_status] || "bg-slate-100 text-slate-600"}`}>{doc.processing_status}</span>
                        </li>)}
                      </ul>
                    ) : <p className="text-[10px] text-slate-500">No files attached · paper scope unavailable</p>}
                    {indexedCount > 0 && <p className="mt-1.5 text-[10px] text-slate-400">{indexedCount} indexed file{indexedCount === 1 ? "" : "s"} included in this paper scope</p>}
                    <Link href={`/papers/${paper.id}`} onClick={(event) => event.stopPropagation()} className="mt-1.5 inline-flex rounded text-[10px] font-medium text-teal-800 underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Open paper details</Link>
                  </div>
                </section>
              );
            })}
          </div>
        )}
        <p className="mt-3 px-1 text-[10px] leading-relaxed text-slate-400">Research scope is paper-level. Selecting a paper includes its indexed attached files, matching the current API.</p>
      </ScrollArea>
    </aside>
  );
}
