"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { papersService } from "@/services/papers.service";
import {
  Trash2,
  Pencil,
  ArrowRight,
  FileText,
  Clock,
  AlertTriangle,
  Star,
  Shield,
  Code2,
  Atom,
  Cpu,
  FlaskConical,
  Compass,
  BookOpen,
} from "lucide-react";
import { formatDate } from "@/utils/formatters";
import { projectHref } from "@/lib/researchWorkspace.mjs";

function getCategoryIcon(title = "") {
  const lower = title.toLowerCase();
  if (lower.includes("cyber") || lower.includes("secur")) return Shield;
  if (
    lower.includes("algo") ||
    lower.includes("code") ||
    lower.includes("program") ||
    lower.includes("comput")
  )
    return Code2;
  if (lower.includes("ai") || lower.includes("model") || lower.includes("neural") || lower.includes("data"))
    return Cpu;
  if (lower.includes("sci") || lower.includes("phys") || lower.includes("chem") || lower.includes("quant"))
    return Atom;
  if (lower.includes("lab") || lower.includes("exper")) return FlaskConical;
  if (lower.includes("explor") || lower.includes("survey") || lower.includes("map")) return Compass;
  if (lower.includes("thakur") || lower.includes("lead") || lower.includes("star")) return Star;

  // Deterministic scholarly icon based on char code sum
  const fallbacks = [Star, BookOpen, Compass, Shield, Code2];
  const hash = title.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return fallbacks[hash % fallbacks.length];
}

export function PaperCard({
  paper,
  sourceCount,
  onDelete,
  onEdit,
  onOpenAddSource,
  index = 0,
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const targetHref = projectHref(paper.id);

  const prefetchProject = () => {
    try {
      router.prefetch(targetHref);
      queryClient.prefetchQuery({
        queryKey: ["paper", paper.id],
        queryFn: () => papersService.getById(paper.id),
        staleTime: 60_000,
      });
      queryClient.prefetchQuery({
        queryKey: ["paperDocuments", paper.id],
        queryFn: () => papersService.getDocuments(paper.id),
        staleTime: 30_000,
      });
    } catch (_) {}
  };

  const openProject = () => router.push(targetHref);
  const descriptionText = paper.description || paper.abstract;
  const CategoryIcon = getCategoryIcon(paper.title);
  const watermark = String(index + 1).padStart(2, "0");

  return (
    <div
      role="link"
      tabIndex={0}
      aria-label={`Open research project: ${paper.title}`}
      onClick={openProject}
      onMouseEnter={prefetchProject}
      onFocus={prefetchProject}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openProject();
        }
      }}
      className="group relative flex flex-col justify-between rounded-3xl border border-slate-100 bg-white p-5 min-h-[310px] shadow-[0_10px_30px_-6px_rgba(0,0,0,0.05),0_4px_12px_-2px_rgba(0,0,0,0.02)] hover:shadow-[0_18px_36px_-6px_rgba(29,111,196,0.14)] hover:border-sky-200/90 hover:-translate-y-1 active:translate-y-0 transition-all duration-200 cursor-pointer overflow-hidden outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
    >
      <div className="relative z-10 flex flex-col justify-between h-full space-y-3">
        <div>
          {/* Card Top Row: Category Icon on Left, Edit & Delete on Right */}
          <div className="flex items-start justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-sky-200/80 bg-sky-50/70 text-sky-600 shadow-2xs">
              <CategoryIcon className="h-4.5 w-4.5 stroke-[1.6]" />
            </div>

            <div className="flex items-center gap-0.5">
              {onEdit && (
                <button
                  type="button"
                  aria-label={`Edit ${paper.title}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onEdit(paper);
                  }}
                  className="rounded-lg p-1.5 text-slate-300 hover:text-sky-600 hover:bg-sky-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  title="Edit project name and description"
                >
                  <Pencil className="h-3.5 w-3.5 stroke-[1.6]" />
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  aria-label={`Delete ${paper.title}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(paper.id);
                  }}
                  className="rounded-lg p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
                  title="Delete project"
                >
                  <Trash2 className="h-3.5 w-3.5 stroke-[1.5]" />
                </button>
              )}
            </div>
          </div>

          {/* Project Title */}
          <h3 className="mt-3 text-base sm:text-[17px] font-bold leading-snug text-slate-900 group-hover:text-[#1d6fc4] transition-colors line-clamp-2">
            {paper.title}
          </h3>

          {/* Description / Workspace Subtitle */}
          <p className="mt-1 text-xs italic text-slate-400 line-clamp-2 leading-relaxed">
            {descriptionText ? `${descriptionText} · Private workspace` : "No description yet · Private workspace"}
          </p>

          {/* Sources Section */}
          <div className="mt-3.5">
            {sourceCount == null ? (
              <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono py-1">
                <Clock className="h-3.5 w-3.5 animate-spin" />
                <span>Checking sources…</span>
              </div>
            ) : sourceCount.total === 0 ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (onOpenAddSource) onOpenAddSource(paper.id);
                  else router.push(`/papers/upload?paperId=${paper.id}`);
                }}
                className="block w-full py-2 rounded-xl border border-slate-100 bg-slate-50/70 text-xs font-medium text-slate-400 hover:text-sky-600 hover:bg-sky-50/60 hover:border-sky-100 text-center transition-all"
              >
                + Add your first source
              </button>
            ) : (
              <div className="space-y-1.5" onClick={(e) => e.stopPropagation()}>
                {(sourceCount.documents || []).slice(0, 2).map((doc) => {
                  const isReady = doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0);
                  const isProcessing =
                    doc.processing_status === "processing" || doc.processing_status === "uploaded";
                  const isFailed = doc.processing_status === "failed";

                  return (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between gap-2 rounded-xl bg-slate-50/80 border border-slate-100/90 px-2.5 py-1.5 text-xs text-slate-700 shadow-2xs"
                    >
                      <div className="flex items-center gap-1.5 min-w-0">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400 stroke-[1.6]" />
                        <span className="truncate font-medium text-slate-700 text-[11px]" title={doc.filename}>
                          {doc.filename}
                        </span>
                      </div>

                      <span className="shrink-0 flex items-center gap-1 text-[11px] font-medium">
                        {isReady && (
                          <span className="inline-flex items-center gap-1 text-sky-600">
                            <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                            Ready
                          </span>
                        )}
                        {isProcessing && (
                          <span className="inline-flex items-center gap-1 text-amber-600">
                            <Clock className="h-3 w-3 animate-spin" />
                            Processing
                          </span>
                        )}
                        {isFailed && (
                          <span className="inline-flex items-center gap-1 text-rose-600">
                            <AlertTriangle className="h-3 w-3" />
                            Failed
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}

                {/* Show more badge when sources > 2 */}
                {sourceCount.total > 2 ? (
                  <div className="flex items-center justify-between text-[11px] pt-1">
                    <span className="font-medium text-sky-700 bg-sky-50 border border-sky-100 px-2 py-0.5 rounded-full text-[11px]">
                      +{sourceCount.total - 2} more {sourceCount.total - 2 === 1 ? "source" : "sources"}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onOpenAddSource) onOpenAddSource(paper.id);
                        else router.push(`/papers/upload?paperId=${paper.id}`);
                      }}
                      className="text-slate-400 hover:text-sky-600 font-medium transition-colors text-[11px]"
                    >
                      + Add source
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onOpenAddSource) onOpenAddSource(paper.id);
                      else router.push(`/papers/upload?paperId=${paper.id}`);
                    }}
                    className="block text-center text-[11px] font-medium text-slate-400 hover:text-sky-600 py-0.5 transition-colors"
                  >
                    + Add source
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Card Footer: Date & Total Count on Left, Arrow Circle on Right */}
        <div className="pt-3 flex items-center justify-between border-t border-slate-100/80 text-xs text-slate-400">
          <span className="font-medium text-[11px]">
            {formatDate(paper.created_at)} · {sourceCount?.total || 0}{" "}
            {sourceCount?.total === 1 ? "source" : "sources"}
          </span>
          <span
            className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 text-slate-500 group-hover:border-sky-500 group-hover:bg-sky-50 group-hover:text-sky-600 transition-all"
            aria-hidden="true"
          >
            <ArrowRight className="h-3.5 w-3.5 stroke-[1.8]" />
          </span>
        </div>
      </div>
    </div>
  );
}
