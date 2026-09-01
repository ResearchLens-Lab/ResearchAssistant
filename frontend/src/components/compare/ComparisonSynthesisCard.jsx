"use client";

import React from "react";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, Sparkles } from "lucide-react";

export function ComparisonSynthesisCard({ result }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 space-y-4 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
      <div className="flex items-center justify-between border-b border-zinc-100 pb-3 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
            Multi-Paper Comparative Analysis
          </h3>
        </div>

        <Badge variant="grounded" className="text-[10px] gap-1">
          <ShieldCheck className="h-3 w-3" />
          {result?.sources?.length || 0} cited sources
        </Badge>
      </div>

      <div className="pt-1">
        <GroundedAnswer content={result?.answer || ""} sources={result?.sources} />
      </div>
    </div>
  );
}
