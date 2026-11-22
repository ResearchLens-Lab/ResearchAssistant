"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ArrowRight, Trash2, Pencil, FileText } from "lucide-react";
import { formatDate } from "@/utils/formatters";
import { projectHref } from "@/lib/researchWorkspace.mjs";

export function PaperTableView({ papers, sourceCounts = {}, onDelete, onEdit }) {
  const router = useRouter();

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xs dark:border-zinc-800 dark:bg-zinc-900">
      <Table>
        <TableHeader className="bg-zinc-50/70 dark:bg-zinc-800/50">
          <TableRow>
            <TableHead className="w-[50%] text-xs font-semibold text-zinc-600">Project details</TableHead>
            <TableHead className="text-xs font-semibold text-zinc-600">Sources status</TableHead>
            <TableHead className="text-xs font-semibold text-zinc-600">Created</TableHead>
            <TableHead className="text-right text-xs font-semibold text-zinc-600">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {papers.map((paper) => {
            const count = sourceCounts[paper.id];
            const desc = paper.description || paper.abstract;

            return (
              <TableRow
                key={paper.id}
                tabIndex={0}
                className="cursor-pointer transition-colors hover:bg-sky-50/60 focus-within:bg-sky-50/60"
                onClick={() => router.push(projectHref(paper.id))}
                onMouseEnter={() => router.prefetch(projectHref(paper.id))}
                onKeyDown={(event) => {
                  if (event.key === "Enter") router.push(projectHref(paper.id));
                }}
              >
                <TableCell className="py-3">
                  <div className="space-y-0.5">
                    <span className="font-semibold text-zinc-900 text-sm hover:text-[var(--rl-primary)] dark:text-zinc-100">
                      {paper.title}
                    </span>
                    <p className="text-xs text-zinc-500 line-clamp-1 max-w-md">
                      {desc || <span className="italic text-zinc-400">No description added yet</span>}
                    </p>
                  </div>
                </TableCell>
                <TableCell className="text-xs text-zinc-600 py-3">
                  {count == null ? (
                    <span className="text-zinc-400 font-mono text-[11px]">Checking…</span>
                  ) : count < 0 ? (
                    <span className="text-rose-600 text-[11px]">Unavailable</span>
                  ) : (
                    <div className="flex items-center gap-1.5 text-xs">
                      <FileText className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                      <span>{count.indexed} / {count.total} ready</span>
                      {count.processing > 0 && <span className="text-sky-700 font-medium font-mono text-[11px]">({count.processing} proc)</span>}
                      {count.failed > 0 && <span className="text-rose-700 font-medium font-mono text-[11px]">({count.failed} fail)</span>}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-xs text-zinc-500 py-3">
                  {formatDate(paper.created_at)}
                </TableCell>
                <TableCell className="text-right py-3">
                  <div className="flex justify-end items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Open ${paper.title}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        router.push(`/papers/${paper.id}`);
                      }}
                      className="h-8 w-8 text-zinc-500 hover:text-[var(--rl-primary)] hover:bg-sky-50"
                    >
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                    {onEdit && (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Edit ${paper.title}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onEdit(paper);
                        }}
                        className="h-8 w-8 text-zinc-400 hover:text-sky-600 hover:bg-sky-50"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    )}
                    {onDelete && (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${paper.title}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDelete(paper.id);
                        }}
                        className="h-8 w-8 text-zinc-400 hover:text-rose-600 hover:bg-rose-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
