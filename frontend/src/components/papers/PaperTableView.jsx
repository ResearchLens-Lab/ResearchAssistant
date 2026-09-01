import React from "react";
import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowUpRight, Trash2 } from "lucide-react";

export function PaperTableView({ papers, onDelete }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white overflow-hidden shadow-2xs dark:border-zinc-800 dark:bg-zinc-900">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[45%]">Title</TableHead>
            <TableHead className="w-[25%]">Authors</TableHead>
            <TableHead className="w-[10%]">Year</TableHead>
            <TableHead className="w-[10%]">Venue</TableHead>
            <TableHead className="w-[10%] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {papers.map((paper) => (
            <TableRow key={paper.id} className="group">
              <TableCell className="font-medium text-zinc-900 dark:text-zinc-100">
                <Link
                  href={`/papers/${paper.id}`}
                  className="hover:text-blue-600 font-semibold line-clamp-1 transition-colors"
                >
                  {paper.title}
                </Link>
                {paper.doi && (
                  <span className="text-[10px] font-mono text-zinc-400">
                    DOI: {paper.doi}
                  </span>
                )}
              </TableCell>

              <TableCell className="text-xs text-zinc-600 dark:text-zinc-400">
                <span className="line-clamp-1">
                  {paper.authors?.join(", ") || "--"}
                </span>
              </TableCell>

              <TableCell className="font-mono text-xs text-zinc-500">
                {paper.publication_year || "--"}
              </TableCell>

              <TableCell>
                {paper.venue ? (
                  <Badge variant="outline" className="text-[10px]">
                    {paper.venue}
                  </Badge>
                ) : (
                  <span className="text-xs text-zinc-400">--</span>
                )}
              </TableCell>

              <TableCell className="text-right">
                <div className="flex items-center justify-end gap-1">
                  <Button variant="ghost" size="icon" asChild className="h-7 w-7">
                    <Link href={`/papers/${paper.id}`}>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                  {onDelete && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onDelete(paper.id)}
                      className="h-7 w-7 text-zinc-400 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
