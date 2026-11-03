"use client";

import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePapers } from "@/hooks/usePapers";
import { papersService } from "@/services/papers.service";
import { PaperGrid } from "@/components/papers/PaperGrid";
import { PaperTableView } from "@/components/papers/PaperTableView";
import { CreatePaperModal } from "@/components/papers/CreatePaperModal";
import { DeletePaperDialog } from "@/components/papers/DeletePaperDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  BookOpen,
  Plus,
  LayoutGrid,
  List,
  Search,
  UploadCloud,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export default function PaperLibraryPage() {
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState("grid");
  const [searchFilter, setSearchFilter] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [paperToDelete, setPaperToDelete] = useState(null);

  const {
    papers,
    pagination,
    isLoading,
    isError,
    error,
    createPaper,
    isCreating,
    deletePaper,
    isDeleting,
  } = usePapers(page, 18);
  const paperIds = useMemo(() => papers.map((paper) => paper.id), [papers]);
  const documentsQuery = useQuery({
    queryKey: ["paperDocumentsByPapers", paperIds],
    queryFn: () => papersService.getDocumentsByPapers(paperIds),
    enabled: paperIds.length > 0,
    staleTime: 10_000,
    refetchInterval: (query) => {
      const groups = Object.values(query.state.data || {});
      return groups.some((documents) => documents.some((document) =>
        document.processing_status === "processing" || document.processing_status === "uploaded"
      )) ? 3000 : false;
    },
  });
  const sourceCounts = useMemo(() => {
    if (documentsQuery.data) return Object.fromEntries(paperIds.map((id) => {
      const documents = documentsQuery.data[id] || [];
      return [id, {
        total: documents.length,
        indexed: documents.filter((document) => document.processing_status === "indexed").length,
        processing: documents.filter((document) => document.processing_status === "processing" || document.processing_status === "uploaded").length,
        failed: documents.filter((document) => document.processing_status === "failed").length,
        documents,
      }];
    }));
    if (documentsQuery.isError) return Object.fromEntries(paperIds.map((id) => [id, -1]));
    return {};
  }, [documentsQuery.data, documentsQuery.isError, paperIds]);

  const filteredPapers = papers.filter((p) => {
    if (!searchFilter.trim()) return true;
    const term = searchFilter.toLowerCase();
    return (
      p.title.toLowerCase().includes(term) ||
      p.authors?.some((a) => a.toLowerCase().includes(term)) ||
      p.venue?.toLowerCase().includes(term)
    );
  });

  const handleDeleteConfirm = async () => {
    if (paperToDelete) {
      await deletePaper(paperToDelete);
      setPaperToDelete(null);
    }
  };

  return (
    <div className="page-shell space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200/80 pb-5 dark:border-zinc-800">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Research Library
            </h1>
            {isLoading ? <Badge variant="secondary" className="font-mono text-xs">Loading projects</Badge> : !isError && <Badge variant="secondary" className="font-mono text-xs">{pagination.total} {pagination.total === 1 ? "project" : "projects"}</Badge>}
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            Organize research sources into projects, then open a project to inspect evidence or continue your research.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!isLoading && <Button
            variant="outline"
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="h-8 gap-1.5 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Create project</span>
          </Button>}

          {!isLoading && pagination.total > 0 && <Button
            variant="workbench"
            size="sm"
            asChild
            className="h-9 gap-1.5 text-sm"
          >
            <Link href="/papers/upload">
              <UploadCloud className="h-3.5 w-3.5" />
              <span>Add sources</span>
            </Link>
          </Button>}
        </div>
      </div>

      {/* Filter & View Switcher Bar */}
      {(!isLoading && pagination.total > 0) && <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-400" />
          <Input
            placeholder="Filter this page by title or author…"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="pl-8 h-8 text-xs bg-white dark:bg-zinc-900"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <div className="flex items-center rounded-lg border border-zinc-200 bg-white p-0.5 dark:border-zinc-800 dark:bg-zinc-900">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === "grid"
                  ? "bg-[var(--rl-primary)] text-white shadow-sm"
                  : "text-zinc-500 hover:text-zinc-900"
              }`}
              title="Grid view"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === "table"
                  ? "bg-[var(--rl-primary)] text-white shadow-sm"
                  : "text-zinc-500 hover:text-zinc-900"
              }`}
              title="Table view"
            >
              <List className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>}

      {/* Paper List Content */}
      {isError ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">{error?.message || "Research projects could not be loaded. Please try again."}</div> : isLoading ? <PaperGrid papers={[]} isLoading /> : filteredPapers.length === 0 && !isLoading ? (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900 space-y-3">
          <BookOpen className="mx-auto h-8 w-8 text-zinc-300 stroke-[1.5]" />
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              {pagination.total === 0 ? "Start with a Research Project" : "No projects match this filter"}
            </h3>
            {pagination.total > 0 && <p className="text-xs text-zinc-400">No projects on this page match your filter.</p>}
          </div>
          {pagination.total === 0 ? <>
            <p className="mx-auto max-w-lg text-sm text-zinc-500">Create a Research Project to organize your sources, ask questions, and inspect supporting evidence.</p>
            <Button variant="workbench" size="sm" onClick={() => setIsCreateOpen(true)} className="mt-1"><Plus className="mr-1.5 h-3.5 w-3.5" />Create project</Button>
            <ol className="mx-auto grid max-w-2xl gap-3 border-t border-zinc-100 pt-4 text-left sm:grid-cols-3">{["Create a Research Project", "Add supported documents and wait for indexing", "Ask a question and inspect its evidence"].map((step, index) => <li key={step} className="flex gap-2 text-xs text-zinc-500"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-50 font-semibold text-sky-700">{index + 1}</span><span>{step}</span></li>)}</ol>
          </> : <p className="text-xs text-zinc-500">No projects on this page match your filter.</p>}
        </div>
      ) : viewMode === "grid" ? (
        <PaperGrid
          papers={filteredPapers}
          isLoading={isLoading}
          sourceCounts={sourceCounts}
          onDelete={(id) => setPaperToDelete(id)}
        />
      ) : (
        <PaperTableView
          papers={filteredPapers}
          sourceCounts={sourceCounts}
          onDelete={(id) => setPaperToDelete(id)}
        />
      )}

      {/* Pagination Controls */}
      {pagination.totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-zinc-200 pt-4 dark:border-zinc-800 text-xs font-mono text-zinc-500">
          <span>
            Page {pagination.page} of {pagination.totalPages} ({pagination.total} total items)
          </span>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={pagination.page <= 1}
              className="h-7 text-xs gap-1"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
              disabled={pagination.page >= pagination.totalPages}
              className="h-7 text-xs gap-1"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Create Paper Modal */}
      <CreatePaperModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={createPaper}
        isLoading={isCreating}
      />

      {/* Delete Paper Dialog */}
      <DeletePaperDialog
        isOpen={!!paperToDelete}
        onClose={() => setPaperToDelete(null)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
      />
    </div>
  );
}
