"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, ArrowUpRight } from "lucide-react";
import { formatDate } from "@/utils/formatters";
import { projectHref } from "@/lib/researchWorkspace.mjs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { documentsService } from "@/services/documents.service";
import { DocumentProcessingProgress } from "./DocumentProcessingProgress";
import { Button } from "@/components/ui/button";

export function PaperCard({ paper, sourceCount, onDelete }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const retryMutation = useMutation({
    mutationFn: documentsService.retry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      queryClient.invalidateQueries({ queryKey: ["paperDocuments", paper.id] });
    },
  });
  const openProject = () => router.push(projectHref(paper.id));

  return (
    <Card
      role="link"
      tabIndex={0}
      aria-label={`Open Research Project: ${paper.title}`}
      onClick={openProject}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openProject();
        }
      }}
      className="group flex cursor-pointer flex-col justify-between border-zinc-200 bg-white transition-all hover:border-sky-300 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <CardHeader className="space-y-2 p-4 pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="text-[10px] font-medium uppercase tracking-wide text-sky-700">Research Project</div>
          {onDelete && <button type="button" aria-label={`Delete ${paper.title}`} onClick={(event) => { event.stopPropagation(); onDelete(paper.id); }} className="rounded p-1 text-zinc-400 hover:bg-rose-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"><Trash2 className="h-3.5 w-3.5" /></button>}
        </div>
        <CardTitle className="text-sm font-semibold leading-snug line-clamp-2 text-zinc-900 dark:text-zinc-100">{paper.title}</CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2 pb-3">
        {paper.abstract ? <p className="text-xs text-zinc-600 line-clamp-3 leading-relaxed dark:text-zinc-400">{paper.abstract}</p> : <p className="text-xs text-zinc-500">Open this project to add sources and continue your research.</p>}
        {sourceCount == null ? <p className="mt-3 text-xs text-zinc-500">Checking source status…</p> : sourceCount < 0 ? <p className="mt-3 text-xs text-rose-700">Source status unavailable</p> : <>
          <p className="mt-3 text-xs text-zinc-600">
            {sourceCount.total} source{sourceCount.total === 1 ? "" : "s"} · {sourceCount.indexed} ready
            {sourceCount.processing ? ` · ${sourceCount.processing} processing` : ""}
            {sourceCount.failed ? ` · ${sourceCount.failed} failed` : ""}
          </p>
          {!!sourceCount.documents?.length && <div className="mt-3 space-y-2" onClick={(event) => event.stopPropagation()}>
            {sourceCount.documents.slice(0, 3).map((document) => <div key={document.id} className="rounded-md border border-slate-100 p-2">
              <div className="flex items-center justify-between gap-2 text-[10px]">
                <span className="min-w-0 flex-1 truncate font-medium text-slate-700" title={document.filename}>{document.filename}</span>
                <span className={`shrink-0 capitalize ${document.processing_status === "indexed" ? "text-emerald-700" : document.processing_status === "failed" ? "text-rose-700" : "text-sky-700"}`}>{document.processing_status === "indexed" ? "Ready" : document.processing_status}</span>
              </div>
              {(document.processing_status === "processing" || document.processing_status === "uploaded") && <div className="mt-2"><DocumentProcessingProgress compact document={document} /></div>}
              {document.processing_status === "failed" && <>
                <p className="mt-1 line-clamp-2 text-[10px] text-rose-700">{document.processing_error || "Indexing failed."}</p>
                <Button size="sm" variant="soft" disabled={retryMutation.isPending} onClick={() => retryMutation.mutate(document.id)} className="mt-1 h-7 text-[10px]">{retryMutation.isPending && retryMutation.variables === document.id ? "Retrying…" : "Retry source"}</Button>
              </>}
            </div>)}
            {sourceCount.total > 3 && <p className="text-[10px] text-slate-500">Open project to see {sourceCount.total - 3} more source{sourceCount.total === 4 ? "" : "s"}.</p>}
            {retryMutation.isError && <p role="alert" className="text-[10px] text-rose-700">{retryMutation.error?.message || "Could not retry this source."}</p>}
          </div>}
        </>}
      </CardContent>
      <CardFooter className="flex items-center justify-between border-t border-zinc-100 px-4 py-2.5 text-[11px] text-zinc-400 dark:border-zinc-800">
        <span>Created {formatDate(paper.created_at)}</span>
        <span className="inline-flex items-center gap-1 font-medium text-sky-700">Open project <ArrowUpRight className="h-3 w-3" /></span>
      </CardFooter>
    </Card>
  );
}
