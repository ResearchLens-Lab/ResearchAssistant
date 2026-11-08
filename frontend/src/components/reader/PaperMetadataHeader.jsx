import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink } from "lucide-react";
import Link from "next/link";

export function PaperMetadataHeader({ paper, onOpenChat }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      {/* Badges & Meta */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 flex-wrap">
          {paper.publication_year && (
            <Badge variant="secondary" className="font-mono text-xs">
              Year: {paper.publication_year}
            </Badge>
          )}
          {paper.venue && (
            <Badge variant="outline" className="text-xs">
              {paper.venue}
            </Badge>
          )}
          {paper.doi && (
            <span className="text-[11px] font-mono text-zinc-500">
              DOI: {paper.doi}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {paper.source_url && (
            <Button variant="outline" size="sm" asChild className="h-7 text-xs gap-1">
              <a href={paper.source_url} target="_blank" rel="noreferrer">
                <span>Source URL</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            </Button>
          )}

        </div>
      </div>

      {/* Paper Title */}
      <h1 className="text-lg font-bold text-zinc-900 tracking-tight dark:text-zinc-100">
        {paper.title}
      </h1>

      {/* Authors */}
      {paper.authors && paper.authors.length > 0 && (
        <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
          <span className="text-zinc-400">Authors: </span>
          {paper.authors.join(", ")}
        </div>
      )}

      {/* Abstract */}
      {paper.abstract && (
        <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800 space-y-1">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
            Abstract
          </h4>
          <p className="text-xs text-zinc-700 leading-relaxed dark:text-zinc-300">
            {paper.abstract}
          </p>
        </div>
      )}
    </div>
  );
}
