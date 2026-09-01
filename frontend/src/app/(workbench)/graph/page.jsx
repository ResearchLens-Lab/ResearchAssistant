"use client";

import React from "react";
import { ServiceFallbackNotice } from "@/components/graph/ServiceFallbackNotice";
import { Network } from "lucide-react";

export default function CitationGraphPage() {
  return (
    <div className="p-6 md:p-8 space-y-6 max-w-5xl mx-auto">
      <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
        <div className="flex items-center gap-2">
          <Network className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Citation Network & Knowledge Graph
          </h1>
        </div>
        <p className="text-xs text-zinc-500 font-mono">
          Explore cross-paper citation links, author collaborations, and concept relationships.
        </p>
      </div>

      <div className="py-8">
        <ServiceFallbackNotice
          title="Neo4j Citation Graph Engine in Integration"
          description="The graph reasoning service is currently connecting to the backend boundary. Grounded RAG retrieval across ChromaDB remains operational for all papers."
        />
      </div>
    </div>
  );
}
