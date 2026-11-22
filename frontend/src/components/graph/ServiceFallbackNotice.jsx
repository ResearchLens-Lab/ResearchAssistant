import React from "react";
import { Network, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function ServiceFallbackNotice({
  title = "Knowledge Graph Engine in Development",
  description = "The Neo4j citation network and multi-hop entity reasoning service is currently being integrated into the ResearchLens boundary. Grounded RAG Q&A and vector similarity across ChromaDB remain fully active.",
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center space-y-4 max-w-xl mx-auto dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-zinc-800 dark:text-indigo-400">
        <Network className="h-6 w-6" />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-center gap-2">
          <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
            {title}
          </h3>
          <Badge variant="warning" className="text-[11px] font-mono">
            503 Boundary Stub
          </Badge>
        </div>
        <p className="text-xs text-zinc-500 leading-relaxed max-w-md mx-auto">
          {description}
        </p>
      </div>

      <div className="rounded-lg bg-zinc-50 p-3.5 text-left text-xs text-zinc-600 border border-zinc-200/80 space-y-2 dark:bg-zinc-950 dark:border-zinc-800 dark:text-zinc-400 font-mono text-[11px]">
        <div className="flex items-center gap-2 font-semibold text-zinc-800 dark:text-zinc-200">
          <Layers className="h-3.5 w-3.5 text-indigo-500" />
          <span>Active Architecture Capabilities</span>
        </div>
        <ul className="space-y-1 pl-4 list-disc text-[11px] text-zinc-500">
          <li>PostgreSQL document & conversation persistence (Active)</li>
          <li>Section-aware chunking with start/end page provenance (Active)</li>
          <li>ChromaDB dense vector indexing & grounded generation (Active)</li>
          <li>Neo4j Graph API (/api/v1/research/*) (Connecting)</li>
        </ul>
      </div>
    </div>
  );
}
