"use client";

import React from "react";
import { PaperCard } from "./PaperCard";
import { NewProjectCard } from "./NewProjectCard";
import { Skeleton } from "@/components/ui/skeleton";

export function PaperGrid({
  papers,
  isLoading,
  onDelete,
  onEdit,
  onOpenAddSource,
  sourceCounts = {},
  onOpenCreate,
  showNewProjectCard = true,
}) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 items-stretch">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="min-h-[310px] rounded-3xl border border-slate-100 bg-white p-5 space-y-3">
            <Skeleton className="h-10 w-10 rounded-full" />
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-3.5 w-1/2" />
            <div className="pt-6 space-y-2">
              <Skeleton className="h-8 w-full rounded-xl" />
              <Skeleton className="h-8 w-full rounded-xl" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 items-stretch">
      {/* 1st Card: "New project" Card matching reference */}
      {showNewProjectCard && onOpenCreate && (
        <NewProjectCard onOpenCreate={onOpenCreate} />
      )}

      {/* Project Cards with 01, 02, 03... watermarks */}
      {papers.map((paper, index) => (
        <PaperCard
          key={paper.id}
          paper={paper}
          index={index}
          sourceCount={sourceCounts[paper.id]}
          onDelete={onDelete}
          onEdit={onEdit}
          onOpenAddSource={onOpenAddSource}
        />
      ))}
    </div>
  );
}
