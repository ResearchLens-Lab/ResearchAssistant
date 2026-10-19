"use client";

import React, { useState } from "react";
import { useCitationStore } from "@/store/citationStore";
import { SourceCard } from "./SourceCard";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronDown, ChevronRight, FileText, Layers, ShieldCheck, Sparkles, X } from "lucide-react";
import { openAuthenticatedPdfSource } from "@/services/documents.service";
import { summarizeClaimChecks } from "@/lib/researchWorkspace.mjs";

export function SourceInspectorRail({ className = "", onClose }) {
  const { sources, activeSourceId, setActiveSource, activeTab, setActiveTab, researchTrace } = useCitationStore();
  const [showUncited, setShowUncited] = useState(false);
  const claimSummary = summarizeClaimChecks(researchTrace || {});
  const claimChecks = researchTrace?.claim_verification?.items || [];
  const sourceStatuses = (sourceId) => [...new Set(claimChecks.filter((item) => item.source_ids?.includes(sourceId)).map((item) => item.status))];

  const openSource = async (source) => {
    setActiveSource(source.source_id || null);
    try {
      await openAuthenticatedPdfSource(source);
    } catch (error) {
      console.error("Could not open source document", error);
    }
  };

  const citedSources = sources.filter((s) => s.source_id);
  const uncitedSources = sources.filter((s) => !s.source_id);

  return (
    <aside aria-label="Evidence inspector" className={`flex h-full w-80 max-w-full shrink-0 flex-col border-l border-slate-200 bg-[#f8faf9] ${className}`}>
      {/* Inspector Header Tabs */}
      <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900">
        <Tabs
          value={activeTab}
          onValueChange={(val) => setActiveTab(val)}
          className="w-full"
        >
          <div className="flex items-center justify-between">
            <TabsList className="h-7 bg-zinc-100 dark:bg-zinc-800">
              <TabsTrigger value="sources" className="text-xs px-2.5 py-0.5">
                Sources {citedSources.length > 0 ? `(${citedSources.length})` : ""}
              </TabsTrigger>
              <TabsTrigger value="library" className="text-xs px-2.5 py-0.5">
                Scope
              </TabsTrigger>
              <TabsTrigger value="notes" className="text-xs px-2.5 py-0.5">
                Trace
              </TabsTrigger>
            </TabsList>
            {onClose && <button autoFocus type="button" aria-label="Close evidence inspector" onClick={onClose} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"><X className="h-4 w-4" /></button>}
          </div>
        </Tabs>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "sources" && (
          <div className="flex h-full flex-col">
            {/* Grounding Verification Ribbon */}
            <div className="flex items-center justify-between border-b border-zinc-200/80 bg-zinc-100/70 px-3.5 py-2 text-[11px] font-mono text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-teal-700" />
                <span className="font-semibold tracking-tight text-zinc-800 dark:text-zinc-200">
                  EVIDENCE: {citedSources.length} PASSAGES
                </span>
              </div>
              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                {claimSummary.available ? `${claimSummary.supported} supported` : "IDs resolved"}
              </Badge>
            </div>

            <ScrollArea className="flex-1 p-3">
              <div className="mb-3 rounded-lg border border-slate-200 bg-white p-3">
                <h3 className="text-[11px] font-semibold text-slate-800">Claim support</h3>
                {claimSummary.available ? (
                  <>
                    <p className="mt-1 text-[10px] leading-relaxed text-slate-600">
                      {claimSummary.supported} supported · {claimSummary.partial} partial · {claimSummary.issues} needing review
                    </p>
                    <p className="mt-1 text-[10px] text-slate-400">
                      {researchTrace.claim_verification.method?.includes("heuristic")
                        ? "Lexical/numeric check only; this does not establish semantic entailment."
                        : "Provider support assessment is fallible; citation identity is checked separately."}
                    </p>
                    <ul className="mt-2 max-h-44 space-y-1.5 overflow-y-auto border-t border-slate-100 pt-2">
                      {claimChecks.map((item, index) => <li key={`${item.claim_text}-${index}`} className="text-[10px] leading-relaxed">
                        <span className={`mr-1 rounded px-1 py-0.5 font-medium ${item.status === "supported" ? "bg-emerald-50 text-emerald-800" : item.status === "partial" ? "bg-amber-50 text-amber-800" : "bg-rose-50 text-rose-800"}`}>{item.status.replaceAll("_", " ")}</span>
                        <span className="text-slate-700">{item.claim_text}</span>
                        {item.reason && <span className="mt-0.5 block text-slate-400">{item.reason}</span>}
                      </li>)}
                    </ul>
                  </>
                ) : <p className="mt-1 text-[10px] leading-relaxed text-slate-500">Claim-to-evidence checks are unavailable for this response. The passages below establish citation identity only.</p>}
              </div>
              {citedSources.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center text-zinc-400 space-y-2">
                  <FileText className="h-8 w-8 text-zinc-300 stroke-[1.5]" />
                  <p className="text-xs font-medium text-zinc-500">
                    No active citations
                  </p>
                  <p className="text-[11px] text-zinc-400 max-w-[200px]">
                    Ask a question in chat or generate a paper summary to inspect grounded evidence.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5 pb-4">
                  {citedSources.map((source, index) => (
                    <SourceCard
                      key={source.source_id || source.chunk_id || `${source.title || "source"}-${index}`}
                      source={source}
                      isActive={activeSourceId === source.source_id}
                      claimStatuses={sourceStatuses(source.source_id)}
                      onSelect={() => openSource(source)}
                    />
                  ))}

                  {/* Collapsible Retrieved but Uncited Section */}
                  {uncitedSources.length > 0 && (
                    <div className="mt-4 pt-2 border-t border-zinc-200 dark:border-zinc-800">
                      <button
                        onClick={() => setShowUncited(!showUncited)}
                        className="flex w-full items-center justify-between rounded-md p-1.5 text-left text-xs font-medium text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
                      >
                        <span className="text-[11px] font-mono">
                          Retrieved, not cited ({uncitedSources.length} chunks)
                        </span>
                        {showUncited ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </button>

                      {showUncited && (
                        <div className="mt-2 space-y-2">
                          {uncitedSources.map((source, i) => (
                            <SourceCard
                              key={source.chunk_id || i}
                              source={{ ...source, source_id: `Extra-${i + 1}` }}
                              isActive={false}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </ScrollArea>
          </div>
        )}

        {activeTab === "library" && (
          <div className="p-4 text-xs text-zinc-500 space-y-3">
            <div className="flex items-center gap-2 text-zinc-800 font-semibold">
              <Layers className="h-4 w-4 text-blue-600" />
              <span>Scope & Collection Index</span>
            </div>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              Targeted papers are automatically retrieved from ChromaDB with deterministic chunk embeddings.
            </p>
          </div>
        )}

        {activeTab === "notes" && (
          <div className="p-4 text-xs text-zinc-500 space-y-3">
            <div className="flex items-center gap-2 text-zinc-800 font-semibold">
              <Sparkles className="h-4 w-4 text-indigo-600" />
              <span>RAG Execution Trace</span>
            </div>
            <div className="rounded-md bg-zinc-100 p-2.5 font-mono text-[10px] space-y-1 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
              <div>Intent: {researchTrace?.intent || "No query yet"}</div>
              <div>Evidence: {researchTrace?.evidence_count ?? 0} passages</div>
              <div>Sufficiency: {researchTrace?.sufficiency?.status || "not assessed"} ({Math.round((researchTrace?.sufficiency?.coverage || 0) * 100)}% term coverage)</div>
              <div>Citation IDs checked: {researchTrace?.citation_verification?.valid_source_ids?.length ?? 0}</div>
              {researchTrace?.citation_verification?.invalid_source_ids?.length > 0 && (
                <div className="text-amber-700">Removed invalid tags: {researchTrace.citation_verification.invalid_source_ids.join(", ")}</div>
              )}
              <div className="text-zinc-500">Coverage is a lexical heuristic, not semantic entailment.</div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
