"use client";

import React from "react";
import { usePapers } from "@/hooks/usePapers";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, Layers, Plus } from "lucide-react";
import Link from "next/link";

export function PaperScopeRail() {
  const { papers, isLoading } = usePapers(1, 50);
  const { selectedPaperIds, togglePaper, selectPapers, clearSelection } = useChatScopeStore();

  const handleSelectAll = () => {
    selectPapers(papers.map((p) => p.id));
  };

  // Auto-select if user has only 1 paper in library and nothing selected
  React.useEffect(() => {
    if (!isLoading && papers.length === 1 && selectedPaperIds.length === 0) {
      selectPapers([papers[0].id]);
    }
  }, [papers, isLoading, selectedPaperIds.length, selectPapers]);

  return (
    <div className="flex h-full w-64 md:w-72 flex-col border-r border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-950/50 shrink-0 select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-3.5 py-3 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
          <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
            Paper Scope ({selectedPaperIds.length})
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          asChild
          className="h-6 px-2 text-[10px] gap-1"
        >
          <Link href="/papers/upload">
            <Plus className="h-3 w-3" />
            <span>Add</span>
          </Link>
        </Button>
      </div>

      {/* Scope Controls */}
      <div className="flex items-center justify-between border-b border-zinc-200/60 bg-zinc-100/60 px-3 py-1.5 text-[10px] font-mono text-zinc-500">
        <span>Target Papers</span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSelectAll}
            className="hover:text-zinc-900 hover:underline"
          >
            All
          </button>
          <span>•</span>
          <button
            onClick={clearSelection}
            className="hover:text-zinc-900 hover:underline"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Papers List */}
      <ScrollArea className="flex-1 p-2">
        {isLoading ? (
          <div className="space-y-2 p-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 rounded-md bg-zinc-200/60 animate-pulse" />
            ))}
          </div>
        ) : papers.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-6 text-center text-zinc-400 space-y-2">
            <BookOpen className="h-6 w-6 text-zinc-300" />
            <p className="text-xs font-medium text-zinc-600">No papers in library</p>
            <p className="text-[11px] text-zinc-400">
              Upload research papers to start grounded RAG querying.
            </p>
            <Button variant="workbench" size="sm" asChild className="mt-2">
              <Link href="/papers/upload">Upload PDF</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-1.5">
            {papers.map((paper) => {
              const isSelected = selectedPaperIds.includes(paper.id);
              const authorStr = paper.authors?.length
                ? paper.authors.join(", ")
                : "Unknown author";

              return (
                <div
                  key={paper.id}
                  onClick={() => togglePaper(paper.id)}
                  className={`group flex items-start gap-2.5 rounded-lg border p-2.5 transition-all cursor-pointer ${
                    isSelected
                      ? "border-zinc-900 bg-white shadow-2xs dark:border-zinc-100 dark:bg-zinc-900"
                      : "border-zinc-200/80 bg-zinc-50/70 hover:border-zinc-300 hover:bg-white dark:border-zinc-800 dark:bg-zinc-950"
                  }`}
                >
                  <div className="pt-0.5" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => togglePaper(paper.id)}
                    />
                  </div>

                  <div className="flex-1 min-w-0 space-y-1">
                    <p className="text-xs font-medium text-zinc-900 line-clamp-2 leading-tight dark:text-zinc-100">
                      {paper.title}
                    </p>

                    <p className="text-[10px] text-zinc-500 font-mono truncate">
                      {authorStr} {paper.publication_year ? `· ${paper.publication_year}` : ""} {paper.venue ? `· ${paper.venue}` : ""}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
