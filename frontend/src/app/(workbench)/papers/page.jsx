"use client";

import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePapers } from "@/hooks/usePapers";
import { papersService } from "@/services/papers.service";
import { PaperGrid } from "@/components/papers/PaperGrid";
import { PaperTableView } from "@/components/papers/PaperTableView";
import { CreatePaperModal } from "@/components/papers/CreatePaperModal";
import { EditPaperModal } from "@/components/papers/EditPaperModal";
import { AddSourcesModal } from "@/components/upload/AddSourcesModal";
import { DeletePaperDialog } from "@/components/papers/DeletePaperDialog";
import { Button } from "@/components/ui/button";
import {
  BookOpen,
  Plus,
  LayoutGrid,
  List,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  X,
} from "lucide-react";

export default function PaperLibraryPage() {
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState("grid");
  const [searchFilter, setSearchFilter] = useState("");
  const [sortBy, setSortBy] = useState("recent");

  // Dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [paperToEdit, setPaperToEdit] = useState(null);
  const [paperToDelete, setPaperToDelete] = useState(null);
  const [isAddSourcesOpen, setIsAddSourcesOpen] = useState(false);
  const [addSourcesPaperId, setAddSourcesPaperId] = useState(null);

  const {
    papers,
    pagination,
    isLoading,
    isError,
    error,
    createPaper,
    isCreating,
    updatePaper,
    isUpdating,
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
      return groups.some((documents) =>
        documents.some(
          (doc) => doc.processing_status === "processing" || doc.processing_status === "uploaded"
        )
      )
        ? 3000
        : false;
    },
  });

  const sourceCounts = useMemo(() => {
    if (documentsQuery.data) {
      return Object.fromEntries(
        paperIds.map((id) => {
          const documents = documentsQuery.data[id] || [];
          return [
            id,
            {
              total: documents.length,
              indexed: documents.filter(
                (doc) => doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0)
              ).length,
              processing: documents.filter(
                (doc) => doc.processing_status === "processing" || doc.processing_status === "uploaded"
              ).length,
              failed: documents.filter((doc) => doc.processing_status === "failed").length,
              documents,
            },
          ];
        })
      );
    }
    if (documentsQuery.isError) return Object.fromEntries(paperIds.map((id) => [id, -1]));
    return {};
  }, [documentsQuery.data, documentsQuery.isError, paperIds]);

  // Instant local filtering across project title, description, and source names
  const filteredAndSortedPapers = useMemo(() => {
    let result = papers.filter((p) => {
      if (!searchFilter.trim()) return true;
      const term = searchFilter.toLowerCase().trim();
      const inTitle = p.title?.toLowerCase().includes(term);
      const inDesc = (p.description || p.abstract)?.toLowerCase().includes(term);
      const inAuthors = p.authors?.some((a) => a.toLowerCase().includes(term));
      const inSources = sourceCounts[p.id]?.documents?.some((doc) =>
        doc.filename?.toLowerCase().includes(term)
      );
      return inTitle || inDesc || inAuthors || inSources;
    });

    if (sortBy === "name") {
      result.sort((a, b) => a.title.localeCompare(b.title));
    } else if (sortBy === "sources") {
      result.sort((a, b) => {
        const countA = sourceCounts[a.id]?.total || 0;
        const countB = sourceCounts[b.id]?.total || 0;
        return countB - countA;
      });
    } else {
      // Default: recent
      result.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }

    return result;
  }, [papers, searchFilter, sortBy, sourceCounts]);

  const handleDeleteConfirm = async () => {
    if (paperToDelete) {
      await deletePaper(paperToDelete);
      setPaperToDelete(null);
    }
  };

  const handleOpenAddSources = (paperId = null) => {
    setAddSourcesPaperId(paperId);
    setIsAddSourcesOpen(true);
  };

  return (
    <div className="page-shell space-y-7">
      {/* Top Header Section Arranged to Maximize Space and Place Search in Middle */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2">
          {/* Left: Compact, Unique "Your Project Library" Branding */}
          <div className="shrink-0 max-w-sm">
            <div className="flex items-baseline gap-2">
              <h1 className="text-2xl sm:text-[26px] font-bold text-slate-900 tracking-tight leading-tight">
                Your Project <span className="text-[var(--rl-primary)]">Library</span>
              </h1>
              {!isLoading && (
                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-sky-100/70 border border-sky-200/60 text-[11px] font-semibold text-[#1d6fc4]">
                  {pagination.total || papers.length}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-slate-400 leading-snug">
              One space for each study. Keep every paper and cited passage organized.
            </p>
          </div>

          {/* Middle: Centered Search Pill Utilizing the Space */}
          <div className="flex-1 w-full max-w-lg mx-auto lg:px-3">
            <div className="relative w-full">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by title, description or source"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="w-full h-10 pl-11 pr-10 rounded-full bg-white border border-slate-200/90 text-xs sm:text-sm text-slate-800 placeholder:text-slate-400 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.04)] focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all"
              />
              {searchFilter && (
                <button
                  type="button"
                  onClick={() => setSearchFilter("")}
                  aria-label="Clear search"
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Top Right: View Mode Icons, Sort Dropdown & Add Sources Button */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0 justify-end">
            <div className="relative">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="appearance-none rounded-full bg-white border border-slate-200/90 pl-3.5 pr-7 py-1.5 text-xs font-medium text-slate-700 shadow-[0_2px_6px_-2px_rgba(0,0,0,0.04)] outline-none hover:border-slate-300 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 cursor-pointer transition-all"
              >
                <option value="recent">Recently created</option>
                <option value="name">Project title (A–Z)</option>
                <option value="sources">Most sources</option>
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 pointer-events-none text-slate-400" />
            </div>

            <div className="flex items-center gap-1 rounded-full border border-slate-200/80 bg-white p-0.5 shadow-2xs">
              <button
                type="button"
                onClick={() => setViewMode("grid")}
                className={`p-1.5 rounded-full transition-all ${
                  viewMode === "grid"
                    ? "bg-[#1d6fc4] text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-600 hover:bg-slate-50"
                }`}
                title="Grid view"
                aria-label="Grid view"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded-full transition-all ${
                  viewMode === "table"
                    ? "bg-[#1d6fc4] text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-600 hover:bg-slate-50"
                }`}
                title="Table view"
                aria-label="Table view"
              >
                <List className="h-3.5 w-3.5" />
              </button>
            </div>

          </div>
        </div>

        {/* Main Content Area */}
        {isError ? (
          <div
            role="alert"
            className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800"
          >
            {error?.message || "Research projects could not be loaded. Please try again."}
          </div>
        ) : isLoading ? (
          <PaperGrid papers={[]} isLoading />
        ) : filteredAndSortedPapers.length === 0 && !isLoading ? (
          <div className="rounded-3xl border border-dashed border-slate-200 bg-white/70 p-12 text-center space-y-4">
            <BookOpen className="mx-auto h-10 w-10 text-slate-300 stroke-[1.5]" />
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-800">
                {pagination.total === 0 ? "Start your first research project" : "No projects match this search"}
              </h3>
              {pagination.total > 0 && (
                <p className="text-xs text-slate-500">
                  No projects matched &ldquo;{searchFilter}&rdquo;. Try another keyword or clear the search.
                </p>
              )}
            </div>
            {pagination.total === 0 ? (
              <>
                <p className="mx-auto max-w-md text-xs text-slate-500 leading-relaxed">
                  Create a project to organize your papers, ask evidence-grounded questions, and inspect supporting citations.
                </p>
                <Button
                  onClick={() => setIsCreateOpen(true)}
                  className="rounded-full bg-[#1d6fc4] hover:bg-[#185ea8] text-white text-xs font-semibold px-5 shadow-sm"
                >
                  <Plus className="h-4 w-4 mr-1.5" />
                  <span>Create a project</span>
                </Button>
              </>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSearchFilter("")}
                className="rounded-full text-xs"
              >
                Clear search filter
              </Button>
            )}
          </div>
        ) : viewMode === "grid" ? (
          <PaperGrid
            papers={filteredAndSortedPapers}
            isLoading={isLoading}
            sourceCounts={sourceCounts}
            onDelete={(id) => setPaperToDelete(id)}
            onEdit={(paper) => setPaperToEdit(paper)}
            onOpenAddSource={handleOpenAddSources}
            onOpenCreate={() => setIsCreateOpen(true)}
            showNewProjectCard={!searchFilter && page === 1}
          />
        ) : (
          <PaperTableView
            papers={filteredAndSortedPapers}
            sourceCounts={sourceCounts}
            onDelete={(id) => setPaperToDelete(id)}
            onEdit={(paper) => setPaperToEdit(paper)}
          />
        )}

        {/* Pagination Controls */}
        {pagination.totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200/80 pt-5 text-xs text-slate-500">
            <span>
              Page {pagination.page} of {pagination.totalPages} ({pagination.total} total items)
            </span>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={pagination.page <= 1}
                className="h-8 rounded-full text-xs gap-1 border-slate-200"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                <span>Previous</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
                disabled={pagination.page >= pagination.totalPages}
                className="h-8 rounded-full text-xs gap-1 border-slate-200"
              >
                <span>Next</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}

        {/* Create Project Modal Pop-up */}
        <CreatePaperModal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          onSubmit={createPaper}
          isLoading={isCreating}
        />

        {/* Edit Project Modal Pop-up */}
        {paperToEdit && (
          <EditPaperModal
            isOpen={!!paperToEdit}
            paper={paperToEdit}
            onClose={() => setPaperToEdit(null)}
            onSubmit={updatePaper}
            isLoading={isUpdating}
          />
        )}

        {/* Add Sources Pop-up Modal matching Create Project modal size */}
        <AddSourcesModal
          isOpen={isAddSourcesOpen}
          onClose={() => {
            setIsAddSourcesOpen(false);
            setAddSourcesPaperId(null);
          }}
          preselectedPaperId={addSourcesPaperId}
          papers={papers}
        />

        {/* Delete Confirmation Dialog */}
        <DeletePaperDialog
          isOpen={!!paperToDelete}
          onClose={() => setPaperToDelete(null)}
          onConfirm={handleDeleteConfirm}
          isLoading={isDeleting}
        />
      </div>
  );
}
