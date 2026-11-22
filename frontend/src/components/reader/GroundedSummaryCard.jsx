"use client";

import React, { useState } from "react";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BookOpen, ShieldCheck, AlertCircle, RefreshCw, Sparkles, ArrowRight, Download, Check, Eye, ChevronUp } from "lucide-react";
import { useCitationStore } from "@/store/citationStore";
import { papersService } from "@/services/papers.service";
import { formatDate } from "@/utils/formatters";

export function GroundedSummaryCard({
  summary,
  isLoading,
  onGenerate,
  error,
  hasIndexedSources = true,
  isCheckingSources = false,
  isSourceError = false,
  onAskInDesk,
  paperId,
  isExpanded = false,
  onViewSavedSummary,
  onCollapseSummary,
  notice = "",
}) {
  const { setSources } = useCitationStore();
  const [isExporting, setIsExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState("");
  const [exportError, setExportError] = useState("");

  const handleGenerate = async () => {
    const res = await onGenerate();
    if (res?.sources) {
      setSources(res.sources);
    }
  };

  const handleExport = async () => {
    if (!paperId || isExporting) return;
    setIsExporting(true);
    setExportNotice("");
    setExportError("");
    try {
      const res = await papersService.exportSummary(paperId);
      setExportNotice(res?.filename ? `Saved to project folder: ${res.filename}` : "Summary exported to project folder.");
      setTimeout(() => setExportNotice(""), 5000);
    } catch (err) {
      setExportError(err?.message || "Failed exporting summary to project folder.");
      setTimeout(() => setExportError(""), 5000);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-5 space-y-4 shadow-2xs min-h-[340px]">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <BookOpen className="h-4 w-4 text-[#1d6fc4]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
            Grounded summary
          </h3>
          {summary && (
            <Badge variant="grounded" className="text-[11px] gap-1">
              <ShieldCheck className="h-3 w-3" />
              {summary.sources?.length || 0} citations
            </Badge>
          )}
          {summary?.generated_at && (
            <span className="text-[11px] text-slate-500 font-medium">
              Saved {formatDate(summary.generated_at)}
            </span>
          )}
          {summary?.is_stale && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-medium text-amber-700 border border-amber-200">
              Sources changed · Regenerate recommended
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isExpanded && summary && paperId && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={isExporting || isLoading}
              title="Export this grounded summary and citations audit trail to your project folder"
              className="h-7 text-xs gap-1.5 rounded-full text-slate-700 hover:text-slate-900"
            >
              {isExporting ? (
                <>
                  <RefreshCw className="h-3 w-3 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Download className="h-3.5 w-3.5 text-[#1d6fc4]" />
                  <span>Save summary</span>
                </>
              )}
            </Button>
          )}

          {isExpanded && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleGenerate}
              disabled={isLoading || !hasIndexedSources}
              title={!hasIndexedSources ? "Add and index a source before generating a grounded summary" : undefined}
              className="h-7 text-xs gap-1.5 rounded-full"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-3 w-3 animate-spin" />
                  <span>Synthesizing from ChromaDB...</span>
                </>
              ) : (
                <>
                  <RefreshCw className="h-3 w-3" />
                  <span>Regenerate</span>
                </>
              )}
            </Button>
          )}

          {isExpanded && onCollapseSummary && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onCollapseSummary}
              title="Hide expanded summary view"
              className="h-7 text-xs gap-1 rounded-full text-slate-500 hover:text-slate-800"
            >
              <ChevronUp className="h-3.5 w-3.5" />
              <span>Hide</span>
            </Button>
          )}
        </div>
      </div>

      {notice && (
        <div className="flex items-center gap-2 rounded-xl bg-sky-50 p-2.5 text-xs text-sky-800 border border-sky-200">
          <BookOpen className="h-4 w-4 shrink-0 text-[#1d6fc4]" />
          <span>{notice}</span>
        </div>
      )}

      {exportNotice && (
        <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-2.5 text-xs text-emerald-800 border border-emerald-200">
          <Check className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>{exportNotice}</span>
        </div>
      )}

      {exportError && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 p-2.5 text-xs text-red-700 border border-red-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 p-3 text-xs text-red-700 border border-red-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message || "Failed to generate summary from RAG."}</span>
        </div>
      )}

      {isSourceError ? (
        <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          Project source status is unavailable. Retry the source list before generating a summary.
        </p>
      ) : isCheckingSources ? (
        <div aria-label="Loading project sources" aria-busy="true" className="space-y-2 py-4">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" />
        </div>
      ) : isExpanded && summary ? (
        <div className="pt-1 space-y-4">
          <GroundedAnswer content={summary.answer} sources={summary.sources} />
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 flex-wrap gap-2">
            <span className="text-[11px] text-slate-400">
              Click any citation badge to view source excerpt
            </span>
            {onAskInDesk && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onAskInDesk}
                className="h-7 text-xs text-[#1d6fc4] hover:bg-sky-50 gap-1 rounded-full"
              >
                <span>Ask questions in Research Desk</span>
                <ArrowRight className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>
      ) : !isLoading ? (
        <div className="py-12 text-center text-slate-400 space-y-4">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-[#1d6fc4]">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              {summary ? "Grounded Summary Ready" : (hasIndexedSources ? "No grounded summary generated yet" : "No indexed sources yet")}
            </p>
            <p className="text-[11px] text-slate-400 max-w-sm mx-auto leading-relaxed mt-1">
              {hasIndexedSources
                ? "Synthesize key arguments and research evidence across your project sources with precise citation links."
                : "Upload and index at least one source document in the left pane to generate a cited synthesis."}
            </p>
          </div>
          {hasIndexedSources && (
            <div className="flex items-center justify-center gap-3 pt-2 flex-wrap">
              <Button
                variant="workbench"
                size="sm"
                onClick={handleGenerate}
                disabled={isLoading}
                className="h-8 text-xs gap-1.5 rounded-full px-4"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>{summary ? "Regenerate grounded summary" : "Generate grounded summary"}</span>
              </Button>

              {summary && onViewSavedSummary && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onViewSavedSummary}
                  className="h-8 text-xs gap-1.5 rounded-full px-4 text-slate-700 hover:text-slate-900 border-slate-300"
                >
                  <Eye className="h-3.5 w-3.5 text-[#1d6fc4]" />
                  <span>View saved summary</span>
                </Button>
              )}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
