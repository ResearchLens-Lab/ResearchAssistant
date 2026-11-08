"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ArrowUpRight, Trash2 } from "lucide-react";
import { formatDate } from "@/utils/formatters";

export function PaperTableView({ papers, sourceCounts = {}, onDelete }) {
  const router = useRouter();
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-2xs dark:border-zinc-800 dark:bg-zinc-900">
      <Table>
        <TableHeader><TableRow><TableHead className="w-[55%]">Research Project</TableHead><TableHead>Sources</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
        <TableBody>{papers.map((paper) => <TableRow key={paper.id} tabIndex={0} className="cursor-pointer focus-within:bg-sky-50 hover:bg-sky-50" onClick={() => router.push(`/papers/${paper.id}`)} onKeyDown={(event) => { if (event.key === "Enter") router.push(`/papers/${paper.id}`); }}>
          <TableCell className="font-semibold text-zinc-900 dark:text-zinc-100">{paper.title}</TableCell>
          <TableCell className="text-xs text-zinc-600">{sourceCounts[paper.id] == null ? "Checking…" : sourceCounts[paper.id] < 0 ? "Unavailable" : <>
            <span>{sourceCounts[paper.id].indexed} / {sourceCounts[paper.id].total} ready</span>
            {sourceCounts[paper.id].processing > 0 && <span className="ml-2 text-sky-700">{sourceCounts[paper.id].processing} processing</span>}
            {sourceCounts[paper.id].failed > 0 && <span className="ml-2 text-rose-700">{sourceCounts[paper.id].failed} failed</span>}
          </>}</TableCell>
          <TableCell className="text-xs text-zinc-500">{formatDate(paper.created_at)}</TableCell>
          <TableCell className="text-right"><div className="flex justify-end gap-1">
            <Button variant="ghost" size="icon" aria-label={`Open ${paper.title}`} onClick={(event) => { event.stopPropagation(); router.push(`/papers/${paper.id}`); }} className="h-7 w-7"><ArrowUpRight className="h-3.5 w-3.5" /></Button>
            {onDelete && <Button variant="ghost" size="icon" aria-label={`Delete ${paper.title}`} onClick={(event) => { event.stopPropagation(); onDelete(paper.id); }} className="h-7 w-7 text-zinc-400 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></Button>}
          </div></TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>
  );
}
