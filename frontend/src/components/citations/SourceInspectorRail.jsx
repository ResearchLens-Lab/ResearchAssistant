"use client";

import React, { useState } from "react";
import { useCitationStore } from "@/store/citationStore";
import { SourceCard } from "./SourceCard";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronDown, ChevronRight, FileText, Layers, ShieldCheck, Sparkles } from "lucide-react";

export function SourceInspectorRail() {
  const { sources, activeSourceId, setActiveSource, activeTab, setActiveTab } = useCitationStore();
  const [showUncited, setShowUncited] = useState(false);

  const citedSources = sources.filter((s) => s.source_id);
  const uncitedSources = sources.filter((s) => !s.source_id);

  return (
    <aside className="flex h-full w-80 md:w-88 flex-col border-l border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-950/50 shrink-0 select-none">
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
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                <span className="font-semibold tracking-tight text-zinc-800 dark:text-zinc-200">
                  GROUNDING: {citedSources.length} CHUNKS
                </span>
              </div>
              <Badge variant="grounded" className="text-[9px] px-1.5 py-0">
                verified
              </Badge>
            </div>

            <ScrollArea className="flex-1 p-3">
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
                  {citedSources.map((source) => (
                    <SourceCard
                      key={source.source_id || source.chunk_id || Math.random()}
                      source={source}
                      isActive={activeSourceId === source.source_id}
                      onSelect={() => setActiveSource(source.source_id || null)}
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
              <div>• Strategy: Section-Aware Grounded RAG</div>
              <div>• Embedding: Dense Vector (ChromaDB)</div>
              <div>• Grounding: Strict Citation Mapping</div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
