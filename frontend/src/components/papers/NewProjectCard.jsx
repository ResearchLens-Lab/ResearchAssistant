"use client";

import React from "react";
import { Plus } from "lucide-react";

export function NewProjectCard({ onOpenCreate }) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Create a new research project"
      onClick={onOpenCreate}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpenCreate();
        }
      }}
      className="group relative flex flex-col items-center justify-center text-center rounded-3xl border border-sky-100/90 bg-white/40 hover:bg-white/80 hover:border-sky-200/90 p-5 min-h-[310px] font-serif cursor-pointer transition-all duration-200 shadow-[0_2px_12px_-2px_rgba(0,0,0,0.02)] hover:shadow-[0_14px_30px_-6px_rgba(29,111,196,0.12)] hover:-translate-y-1 outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-sky-200 bg-sky-50/80 text-sky-600 mb-3 group-hover:scale-105 group-hover:bg-sky-100 group-hover:border-sky-300 transition-all shadow-2xs">
        <Plus className="h-5 w-5 stroke-[1.8]" />
      </div>
      <h3 className="text-base font-semibold text-slate-800 font-serif">New project</h3>
      <p className="mt-1.5 max-w-[150px] text-xs leading-relaxed text-slate-400 font-serif">
        Start a space for a subject or study
      </p>
    </div>
  );
}
