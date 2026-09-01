"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePapers } from "@/hooks/usePapers";
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
    createPaper,
    isCreating,
    deletePaper,
    isDeleting,
  } = usePapers(page, 18);

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
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200/80 pb-5 dark:border-zinc-800">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Paper Library
            </h1>
            <Badge variant="secondary" className="font-mono text-xs">
              {pagination.total} papers
            </Badge>
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            Browse, manage, and inspect all ingested academic publications.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="h-8 gap-1.5 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Metadata</span>
          </Button>

          <Button
            variant="workbench"
            size="sm"
            asChild
            className="h-8 gap-1.5 text-xs bg-zinc-900 text-white"
          >
            <Link href="/papers/upload">
              <UploadCloud className="h-3.5 w-3.5" />
              <span>Ingest PDF</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Filter & View Switcher Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-400" />
          <Input
            placeholder="Filter library by title or author..."
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
                  ? "bg-zinc-900 text-white shadow-2xs dark:bg-zinc-100 dark:text-zinc-900"
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
                  ? "bg-zinc-900 text-white shadow-2xs dark:bg-zinc-100 dark:text-zinc-900"
                  : "text-zinc-500 hover:text-zinc-900"
              }`}
              title="Table view"
            >
              <List className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Paper List Content */}
      {filteredPapers.length === 0 && !isLoading ? (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900 space-y-3">
          <BookOpen className="mx-auto h-8 w-8 text-zinc-300 stroke-[1.5]" />
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              No research papers found
            </h3>
            <p className="text-xs text-zinc-400">
              {searchFilter
                ? "No papers match your filter term."
                : "Upload PDF documents to index academic sections and start querying."}
            </p>
          </div>
          <Button variant="workbench" size="sm" asChild className="mt-2">
            <Link href="/papers/upload">Upload Paper PDF</Link>
          </Button>
        </div>
      ) : viewMode === "grid" ? (
        <PaperGrid
          papers={filteredPapers}
          isLoading={isLoading}
          onDelete={(id) => setPaperToDelete(id)}
        />
      ) : (
        <PaperTableView
          papers={filteredPapers}
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
