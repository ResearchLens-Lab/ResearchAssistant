"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, Pencil } from "lucide-react";

export function PaperMetadataHeader({ paper, onEdit }) {
  const description = paper.description || paper.abstract;

  return (
    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 font-serif">
      <div className="space-y-1 min-w-0">
        <div className="flex items-baseline gap-2.5 flex-wrap">
          <span className="text-[11px] uppercase font-bold tracking-wider text-slate-400 shrink-0">
            Project name:
          </span>
          <h1 className="text-2xl sm:text-[26px] font-serif font-bold text-slate-900 tracking-tight leading-snug">
            {paper.title}
          </h1>
        </div>

        <div className="flex items-baseline gap-2 flex-wrap text-xs sm:text-sm text-slate-600">
          <span className="text-[11px] uppercase font-bold tracking-wider text-slate-400 shrink-0">
            Project description:
          </span>
          <p className="italic text-slate-600 font-serif leading-relaxed">
            {description || <span className="text-slate-400 not-italic">No description provided yet</span>}
          </p>
        </div>
      </div>

      {onEdit && (
        <button
          type="button"
          onClick={onEdit}
          className="shrink-0 self-start inline-flex items-center gap-1.5 rounded-full border border-slate-200/90 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-[#1d6fc4] hover:border-sky-300 transition-colors shadow-2xs cursor-pointer"
          title="Edit project name or description"
        >
          <Pencil className="h-3.5 w-3.5" />
          <span>Edit project</span>
        </button>
      )}
    </div>
  );
}
