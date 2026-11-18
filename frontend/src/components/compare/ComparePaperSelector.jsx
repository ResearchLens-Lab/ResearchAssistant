"use client";

import React, { useMemo, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { ChevronDown, ChevronRight, FileText, GitCompare, Search } from "lucide-react";

const isReady = (document) => document.processing_status === "indexed";

export function ComparePaperSelector({
  papers = [], documentsByPaper = {}, selectedDocumentIds = [], onToggleDocument,
  onToggleProject, onClear, onSelectAll, isLoading = false, error = null,
}) {
  const [search, setSearch] = useState("");
  const [collapsedProjects, setCollapsedProjects] = useState({});
  const filteredProjects = useMemo(() => papers.map((paper) => {
    const documents = documentsByPaper[paper.id] || [];
    const query = search.trim().toLowerCase();
    return { paper, documents: query ? documents.filter((document) => `${document.filename} ${paper.title} ${(paper.authors || []).join(" ")}`.toLowerCase().includes(query)) : documents };
  }).filter(({ paper, documents }) => !search.trim() || paper.title.toLowerCase().includes(search.trim().toLowerCase()) || documents.length > 0), [papers, documentsByPaper, search]);

  return (
    <section className="flex min-h-[390px] min-w-0 flex-col overflow-hidden rounded-2xl border border-[var(--rl-border)] bg-white shadow-sm" aria-label="Select research sources">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--rl-border)] px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2"><GitCompare className="h-4 w-4 shrink-0 text-[var(--rl-primary)]" /><div><h2 className="text-sm font-semibold text-[var(--rl-ink)]">Select research sources</h2><p className="text-[11px] text-[var(--rl-muted)]">Projects organize your documents</p></div></div>
        <div className="flex shrink-0 items-center gap-2"><button type="button" onClick={onSelectAll} disabled={!papers.some((paper) => (documentsByPaper[paper.id] || []).some(isReady))} className="text-[11px] font-medium text-[var(--rl-primary)] hover:underline disabled:opacity-40">Select all ready</button><span className="text-slate-300">·</span><button type="button" onClick={onClear} disabled={!selectedDocumentIds.length} className="text-[11px] text-[var(--rl-muted)] hover:text-[var(--rl-primary)] disabled:opacity-40">Clear</button></div>
      </header>
      <div className="shrink-0 border-b border-[var(--rl-border)] p-2.5">
        <label className="relative block"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[var(--rl-muted)]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents or projects" aria-label="Search documents" className="h-9 w-full rounded-lg border border-[var(--rl-border)] bg-[var(--rl-canvas)] pl-9 pr-3 text-xs text-[var(--rl-ink)] outline-none focus:ring-2 focus:ring-[var(--rl-sky)]" /></label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
        {isLoading ? <div className="space-y-2" aria-label="Loading indexed sources">{[0, 1, 2].map((item) => <div key={item} className="h-12 animate-pulse rounded-xl bg-slate-100" />)}</div> : error ? <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-800">Could not load project documents. Refresh the list and try again.</div> : filteredProjects.length ? <div className="space-y-2">
          {filteredProjects.map(({ paper, documents }) => {
            const readyDocuments = (documentsByPaper[paper.id] || []).filter(isReady);
            const selectedCount = readyDocuments.filter((document) => selectedDocumentIds.includes(document.id)).length;
            const projectChecked = readyDocuments.length > 0 && selectedCount === readyDocuments.length;
            const projectIndeterminate = selectedCount > 0 && selectedCount < readyDocuments.length;
            const isCollapsed = search.trim() ? false : collapsedProjects[paper.id] ?? true;
            return <section key={paper.id} className="overflow-hidden rounded-xl border border-[var(--rl-border)]" aria-label={`Project ${paper.title}`}>
              <div className="flex min-h-11 items-center gap-2 bg-[var(--rl-canvas)]/80 px-2.5 py-1.5">
                <Checkbox aria-label={`Select all indexed sources in ${paper.title}`} checked={projectIndeterminate ? "indeterminate" : projectChecked} disabled={!readyDocuments.length} onCheckedChange={() => onToggleProject(paper.id, readyDocuments.map((document) => document.id))} />
                <button type="button" onClick={() => setCollapsedProjects((current) => ({ ...current, [paper.id]: !(current[paper.id] ?? true) }))} aria-label={`${isCollapsed ? "Expand" : "Collapse"} ${paper.title}`} className="text-[var(--rl-muted)]">{isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</button>
                <div className="min-w-0 flex-1"><h3 className="truncate text-xs font-semibold text-[var(--rl-ink)]" title={paper.title}>{paper.title}</h3><p className="text-[11px] text-[var(--rl-muted)]">{readyDocuments.length} ready {readyDocuments.length === 1 ? "source" : "sources"}{selectedCount ? ` · ${selectedCount} selected` : ""}</p></div>
              </div>
              {!isCollapsed && <div className="divide-y divide-slate-100">
                {documents.length ? documents.map((document) => {
                  const ready = isReady(document);
                  const selected = selectedDocumentIds.includes(document.id);
                  const statusLabel = ready ? `${document.chunk_count ?? 0} chunks` : document.processing_status === "failed" ? "Indexing failed" : document.processing_status || "Not ready";
                  const authorYear = [paper.authors?.length ? paper.authors.join(", ") : "", paper.publication_year || ""].filter(Boolean).join(" · ");
                  return <label key={document.id} className={`flex min-h-12 cursor-pointer items-center gap-2.5 px-2.5 py-1.5 ${selected ? "bg-[var(--rl-selected)]/50" : "hover:bg-slate-50"} ${!ready ? "cursor-not-allowed opacity-65" : ""}`}>
                    <Checkbox aria-label={`Select document ${document.filename}`} checked={selected} disabled={!ready} onCheckedChange={() => onToggleDocument(document.id)} />
                    <FileText className={`h-4 w-4 shrink-0 ${ready ? "text-[var(--rl-primary)]" : "text-slate-400"}`} />
                    <span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium leading-4 text-[var(--rl-ink)]" title={document.filename}>{document.filename}</span><span className="block truncate text-[11px] leading-4 text-[var(--rl-muted)]">{statusLabel}{authorYear ? ` · ${authorYear}` : ""}</span></span>
                  </label>;
                }) : <p className="px-3 py-3 text-xs text-[var(--rl-muted)]">{search ? "No matching documents in this project." : "No documents have been added to this project."}</p>}
              </div>}
            </section>;
          })}
        </div> : <p className="py-8 text-center text-xs text-[var(--rl-muted)]">No projects or documents match that search.</p>}
      </div>
      <footer className="flex shrink-0 items-center justify-between border-t border-[var(--rl-border)] bg-white px-3 py-2 text-xs"><span className="font-medium text-[var(--rl-ink)]">{selectedDocumentIds.length} {selectedDocumentIds.length === 1 ? "source" : "sources"} selected</span><span className="text-[11px] text-[var(--rl-muted)]">2 ready documents minimum</span></footer>
    </section>
  );
}
