"use client";

import React from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { GitCompare } from "lucide-react";

export function ComparePaperSelector({
  papers,
  selectedIds,
  onToggle,
  onClear,
  documentsByPaper = {},
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
          <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
            Select Papers to Compare ({selectedIds.length} selected)
          </span>
        </div>

        {selectedIds.length > 0 && (
          <button
            onClick={onClear}
            className="text-[11px] text-zinc-500 hover:text-zinc-900 hover:underline"
          >
            Clear all
          </button>
        )}
      </div>

      <ScrollArea className="max-h-48">
        <div className="space-y-1.5 pr-2">
          {papers.map((paper) => {
            const isSelected = selectedIds.includes(paper.id);
            const documents = documentsByPaper[paper.id] || [];
            const indexed = documents.filter((document) => document.processing_status === "indexed").length;
            const disabled = indexed === 0 && !isSelected;
            return (
              <div
                key={paper.id}
                className={`flex items-center justify-between p-2 rounded-md border text-xs transition-colors ${
                  isSelected
                    ? "border-zinc-900 bg-zinc-50 dark:border-zinc-100 dark:bg-zinc-800"
                    : disabled ? "border-zinc-100 opacity-55 dark:border-zinc-800" : "border-zinc-100 hover:bg-zinc-50/75 dark:border-zinc-800"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Checkbox
                    aria-label={`Select ${paper.title} for comparison`}
                    checked={isSelected}
                    disabled={disabled}
                    onCheckedChange={() => onToggle(paper.id)}
                  />
                  <button type="button" disabled={disabled} onClick={() => onToggle(paper.id)} className="min-w-0 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">
                    <span className="block truncate font-medium text-zinc-800 dark:text-zinc-200">{paper.title}</span>
                    <span className="mt-0.5 block text-[10px] text-zinc-500">{indexed} indexed file{indexed === 1 ? "" : "s"}</span>
                  </button>
                </div>

                {paper.publication_year && (
                  <span className="font-mono text-[10px] text-zinc-400 shrink-0 ml-2">
                    {paper.publication_year}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
