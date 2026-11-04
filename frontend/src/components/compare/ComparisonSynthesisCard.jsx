"use client";

import React from "react";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Download, GitCompare, Sparkles } from "lucide-react";
import { parseComparisonMarkdown, buildResearchBrief, summarizeClaimChecks } from "@/lib/researchWorkspace.mjs";

export function ComparisonSynthesisCard({ result, question, paperTitles = [] }) {
  const answer = result?.answer || "";
  const matrix = parseComparisonMarkdown(answer);
  const research = result?.metadata?.research || {};
  const sufficiency = research?.sufficiency?.status;
  const checks = research?.claim_verification?.items || [];
  const claimSummary = summarizeClaimChecks(research);
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
    <section className="overflow-hidden rounded-2xl border border-[var(--rl-border)] bg-white shadow-[0_1px_3px_rgba(32,52,73,0.04),0_8px_24px_-10px_rgba(38,120,184,0.12)]" aria-label="Evidence-backed paper comparison">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] px-4 py-4 sm:px-5">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><GitCompare className="h-4 w-4" aria-hidden="true" /></span>
          <div><h2 className="text-base font-semibold text-[var(--rl-ink)]">Cross-paper matrix</h2><p className="text-xs text-[var(--rl-muted)]">{question ? `Focus: ${question}` : "Generated from selected papers and linked passages"}</p></div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-1.5 border-[var(--rl-border)] text-xs text-[var(--rl-muted)]"><Sparkles className="h-3 w-3 text-[var(--rl-primary)]" />{result?.sources?.length || 0} evidence passages</Badge>
          <button type="button" onClick={exportMarkdown} disabled={!result?.sources?.length} title={!result?.sources?.length ? "A source-linked brief requires returned evidence citations" : undefined} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[var(--rl-border)] px-3 text-xs font-medium text-[var(--rl-ink)] hover:bg-[var(--rl-tint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)] disabled:cursor-not-allowed disabled:opacity-50"><Download className="h-3.5 w-3.5" aria-hidden="true" />Export brief</button>
        </div>
      </header>

      {hasDisagreements && <div role="status" className="flex gap-2 border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900 sm:px-5"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>The selected passages report differing findings or conditions. Review the linked citations and study settings before drawing a conclusion.</span></div>}

      <div className="grid gap-3 border-b border-[var(--rl-border)] p-4 sm:grid-cols-2 sm:px-5">
        <section className="rounded-xl bg-[var(--rl-tint)] p-3.5" aria-label="Evidence coverage">
          <h3 className="text-xs font-semibold text-[var(--rl-ink)]">Retrieved evidence</h3>
          <p className="mt-1 text-sm text-[var(--rl-muted)]">{result?.metadata?.research?.evidence_count ?? result?.sources?.length ?? 0} passages · coverage: <span className="font-medium text-[var(--rl-ink)]">{sufficiency || "not recorded"}</span></p>
          <p className="mt-1 text-[10px] leading-4 text-[var(--rl-muted)]">Coverage indicates how well retrieval matched the question. It does not prove that a claim is true.</p>
        </section>
        <section className="rounded-xl bg-[var(--rl-tint)] p-3.5" aria-label="Claim checks">
          <h3 className="text-xs font-semibold text-[var(--rl-ink)]">Claim review</h3>
          {claimSummary.available ? <><p className="mt-1 text-sm text-[var(--rl-muted)]">{claimSummary.supported} supported · {claimSummary.partial} partial · {claimSummary.issues} needing review</p><p className="mt-1 text-[10px] leading-4 text-[var(--rl-muted)]">{research.claim_verification?.method?.includes("heuristic") ? "Lexical/numeric screening only; inspect the cited passage to judge meaning." : "Automated support checks can be fallible; inspect citations for context."}</p></> : <p className="mt-1 text-sm text-[var(--rl-muted)]">Claim checks are unavailable. Citations still link to the retrieved passages.</p>}
        </section>
      </div>

      {paperTitles.length > 0 && <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--rl-border)] px-4 py-3 sm:px-5"><span className="mr-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--rl-muted)]">Compared sources</span>{paperTitles.map((title) => <span key={title} title={title} className="max-w-64 truncate rounded-full border border-[var(--rl-border)] bg-white px-2.5 py-1 text-[10px] text-[var(--rl-ink)]">{title}</span>)}</div>}

      {matrix ? <>
        <div className="overflow-x-auto" tabIndex={0} aria-label="Scrollable comparison matrix">
          <table className="min-w-[760px] w-full border-collapse text-left text-sm">
            <thead className="bg-[var(--rl-tint)]"><tr>{matrix.headers.map((header, index) => <th key={`${header}-${index}`} scope="col" className="border-b border-[var(--rl-border)] px-3 py-3 font-semibold text-[var(--rl-ink)] sm:px-4">{header}</th>)}</tr></thead>
            <tbody>{matrix.rows.map((row, rowIndex) => <tr key={`${row[0]}-${rowIndex}`} className="align-top odd:bg-white even:bg-[var(--rl-tint)]/50">{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`} className={`border-b border-slate-100 px-3 py-3 leading-relaxed text-[var(--rl-ink)] sm:px-4 ${cellIndex === 0 ? "min-w-36 font-semibold" : "min-w-48"}`}><GroundedAnswer content={cell} sources={result?.sources} /></td>)}</tr>)}</tbody>
          </table>
        </div>
        {matrix.synthesis && <div className="border-t border-[var(--rl-border)] bg-[var(--rl-tint)]/60 px-4 py-4 sm:px-5"><h3 className="mb-2 text-sm font-semibold text-[var(--rl-ink)]">Synthesis</h3><GroundedAnswer content={matrix.synthesis} sources={result?.sources} /></div>}
      </> : <div className="p-4 sm:p-5"><p className="mb-3 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-tint)] p-3 text-sm text-[var(--rl-muted)]">The provider returned a narrative comparison instead of a matrix. The answer is shown with its citations.</p><GroundedAnswer content={answer} sources={result?.sources} /></div>}

      <footer className="border-t border-slate-100 px-4 py-3 text-xs leading-relaxed text-[var(--rl-muted)] sm:px-5">Cells preserve the generated findings and citation IDs. “Not reported in the selected sources” means the retrieved passages did not provide that information. Open any citation to inspect its document, location, and full excerpt.</footer>
    </section>
  );
}
