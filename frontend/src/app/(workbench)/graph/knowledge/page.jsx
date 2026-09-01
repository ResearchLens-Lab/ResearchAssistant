"use client";

import React from "react";
import { ServiceFallbackNotice } from "@/components/graph/ServiceFallbackNotice";
import { Network } from "lucide-react";

export default function KnowledgeGraphPage() {
  return (
    <div className="p-6 md:p-8 space-y-6 max-w-5xl mx-auto">
      <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
        <div className="flex items-center gap-2">
          <Network className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Global Knowledge Graph Explorer
          </h1>
        </div>
        <p className="text-xs text-zinc-500 font-mono">
          Semantic concept clustering and literature topology across your research domain.
        </p>
      </div>

      <div className="py-8">
        <ServiceFallbackNotice
          title="Knowledge Graph Reasoning in Integration"
          description="Global entity resolution and concept clustering are connected to the Neo4j backend boundary."
        />
      </div>
    </div>
  );
}
