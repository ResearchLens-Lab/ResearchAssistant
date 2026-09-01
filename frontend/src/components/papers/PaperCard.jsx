"use client";

import React from "react";
import Link from "next/link";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Trash2, ArrowUpRight } from "lucide-react";
import { formatDate } from "@/utils/formatters";

export function PaperCard({ paper, onDelete }) {
  const authorStr = paper.authors?.length
    ? paper.authors.slice(0, 3).join(", ") + (paper.authors.length > 3 ? " et al." : "")
    : "Author not specified";

  return (
    <Card className="group flex flex-col justify-between border-zinc-200 bg-white hover:border-zinc-300 hover:shadow-xs transition-all dark:border-zinc-800 dark:bg-zinc-900">
      <CardHeader className="space-y-2 p-4 pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            {paper.publication_year && (
              <Badge variant="secondary" className="font-mono text-[10px] px-1.5 py-0">
                {paper.publication_year}
              </Badge>
            )}
            {paper.venue && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 truncate max-w-[120px]">
                {paper.venue}
              </Badge>
            )}
          </div>

          {onDelete && (
            <button
              onClick={() => onDelete(paper.id)}
              className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-600 transition-opacity p-1 rounded"
              title="Delete paper"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <CardTitle className="text-sm font-semibold leading-snug line-clamp-2 text-zinc-900 dark:text-zinc-100">
          <Link
            href={`/papers/${paper.id}`}
            className="hover:text-blue-600 transition-colors"
          >
            {paper.title}
          </Link>
        </CardTitle>

        <p className="text-xs text-zinc-500 font-medium truncate">
          {authorStr}
        </p>
      </CardHeader>

      <CardContent className="p-4 pt-1 pb-2">
        {paper.abstract ? (
          <p className="text-xs text-zinc-600 line-clamp-3 leading-relaxed dark:text-zinc-400">
            {paper.abstract}
          </p>
        ) : (
          <p className="text-xs text-zinc-400 italic">
            No abstract available for this paper.
          </p>
        )}
      </CardContent>

      <CardFooter className="flex items-center justify-between border-t border-zinc-100 px-4 py-2.5 dark:border-zinc-800 text-[11px] text-zinc-400 font-mono">
        <span>Added {formatDate(paper.created_at)}</span>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" asChild className="h-6 px-2 text-xs">
            <Link href={`/papers/${paper.id}`}>
              <span>Inspect</span>
              <ArrowUpRight className="ml-1 h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
