import React from "react";
import { PaperCard } from "./PaperCard";
import { Skeleton } from "@/components/ui/skeleton";

export function PaperGrid({ papers, isLoading, onDelete, sourceCounts = {} }) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="h-48 rounded-lg border border-zinc-200 bg-white p-4 space-y-3">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-16 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (papers.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {papers.map((paper) => (
        <PaperCard key={paper.id} paper={paper} sourceCount={sourceCounts[paper.id]} onDelete={onDelete} />
      ))}
    </div>
  );
}
