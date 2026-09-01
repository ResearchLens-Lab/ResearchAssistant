import React from "react";
import { Badge } from "@/components/ui/badge";
import { Cpu } from "lucide-react";

export function IngestConfigPanel() {
  return (
    <div className="space-y-4 rounded-lg border border-zinc-200 bg-white p-4 text-xs dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="flex items-center gap-2 border-b border-zinc-100 pb-2.5 font-semibold text-zinc-900 dark:border-zinc-800 dark:text-zinc-100">
        <Cpu className="h-4 w-4 text-indigo-600" />
        <span>RAG Ingestion Configuration</span>
      </div>

      <div className="space-y-2.5 text-[11px] font-mono">
        <div className="flex justify-between border-b border-zinc-100 pb-1.5 dark:border-zinc-800">
          <span className="text-zinc-500">Chunking Strategy:</span>
          <Badge variant="secondary" className="text-[10px] font-mono font-semibold">
            section-aware
          </Badge>
        </div>

        <div className="flex justify-between border-b border-zinc-100 pb-1.5 dark:border-zinc-800">
          <span className="text-zinc-500">Target Chunk Size:</span>
          <span className="text-zinc-800 font-semibold dark:text-zinc-200">500 tokens</span>
        </div>

        <div className="flex justify-between border-b border-zinc-100 pb-1.5 dark:border-zinc-800">
          <span className="text-zinc-500">Chunk Overlap:</span>
          <span className="text-zinc-800 font-semibold dark:text-zinc-200">80 tokens</span>
        </div>

        <div className="flex justify-between border-b border-zinc-100 pb-1.5 dark:border-zinc-800">
          <span className="text-zinc-500">Vector Store:</span>
          <span className="text-zinc-800 font-semibold dark:text-zinc-200">ChromaDB</span>
        </div>

        <div className="flex justify-between">
          <span className="text-zinc-500">Chunk Hash Format:</span>
          <span className="text-[10px] text-zinc-400">
            {`{paper_id}_c{idx}_p{p1-p2}`}
          </span>
        </div>
      </div>

      <div className="rounded-md bg-zinc-50 p-2.5 text-[11px] text-zinc-600 border border-zinc-200/80 dark:bg-zinc-800/60 dark:border-zinc-700 dark:text-zinc-300">
        <p className="font-semibold text-zinc-800 dark:text-zinc-100 mb-1">
          Provenance Guarantee
        </p>
        Academic sections and start/end page boundaries are preserved across every chunk for 100% verifiable citations.
      </div>
    </div>
  );
}
