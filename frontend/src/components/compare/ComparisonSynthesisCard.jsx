"use client";

import React from "react";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Download, GitCompare, Sparkles } from "lucide-react";
import { parseComparisonMarkdown } from "@/lib/researchWorkspace.mjs";
import { buildResearchBrief } from "@/lib/researchWorkspace.mjs";

export function ComparisonSynthesisCard({ result, question }) {
  const answer = result?.answer || "";
  const matrix = parseComparisonMarkdown(answer);
  const sufficiency = result?.metadata?.research?.sufficiency?.status;
  const checks = result?.metadata?.research?.claim_verification?.items || [];
  const hasDisagreements = sufficiency === "conflicting" || checks.some((item) => item.status === "contradicted");
  const exportMarkdown = () => {
    const markdown = buildResearchBrief([
      { role: "user", content: question || "Compare the selected research papers." },
      { role: "assistant", content: answer, sources: result?.sources || [], meta: { research: result?.metadata?.research || {} } },
    ], "Cross-paper research brief");
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "cross-paper-research-brief.md";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" aria-label="Evidence-backed paper comparison">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-50 text-teal-800"><GitCompare className="h-4 w-4" /></span>
          <div><h2 className="text-sm font-semibold text-slate-900">Cross-paper matrix</h2><p className="text-[11px] text-slate-500">Generated from selected papers and linked passages</p></div>
        </div>
        <div className="flex items-center gap-2"><Badge variant="outline" className="gap-1.5 border-slate-200 text-[10px] text-slate-600"><Sparkles className="h-3 w-3 text-teal-700" />{result?.sources?.length || 0} evidence passages</Badge><button type="button" onClick={exportMarkdown} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-300 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"><Download className="h-3.5 w-3.5" />Export</button></div>
      </header>

      {hasDisagreements && <div role="status" className="flex gap-2 border-b border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-900 sm:px-5"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>The selected passages report differing findings or conditions. Compare the citations and study settings before drawing a conclusion.</span></div>}

      {matrix ? <>
        <div className="overflow-x-auto">
          <table className="min-w-[760px] w-full border-collapse text-left text-xs">
            <thead className="bg-slate-50"><tr>{matrix.headers.map((header, index) => <th key={`${header}-${index}`} scope="col" className="border-b border-slate-200 px-3 py-3 font-semibold text-slate-700 sm:px-4">{header}</th>)}</tr></thead>
            <tbody>{matrix.rows.map((row, rowIndex) => <tr key={`${row[0]}-${rowIndex}`} className="align-top odd:bg-white even:bg-slate-50/60">{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`} className={`border-b border-slate-100 px-3 py-3 leading-relaxed text-slate-700 sm:px-4 ${cellIndex === 0 ? "min-w-36 font-semibold text-slate-900" : "min-w-48"}`}><GroundedAnswer content={cell} sources={result?.sources} /></td>)}</tr>)}</tbody>
          </table>
        </div>
        {matrix.synthesis && <div className="border-t border-slate-200 bg-[#fbfcfb] px-4 py-4 sm:px-5"><h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">Synthesis</h3><GroundedAnswer content={matrix.synthesis} sources={result?.sources} /></div>}
      </> : <div className="p-4 sm:p-5"><p className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">The provider returned a narrative comparison instead of a matrix. The original answer is shown with its citations.</p><GroundedAnswer content={answer} sources={result?.sources} /></div>}

      <footer className="border-t border-slate-100 px-4 py-2.5 text-[10px] leading-relaxed text-slate-500 sm:px-5">Cells preserve the model’s reported findings and citation IDs. “Not reported” means the selected retrieved passages did not provide the field.</footer>
    </section>
  );
}
