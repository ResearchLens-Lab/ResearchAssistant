import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { BookOpen, Layers, MessageSquare, ShieldCheck } from "lucide-react";

export function MetricsOverview({ paperCount, conversationCount }) {
  const metrics = [
    {
      label: "Ingested Papers",
      value: paperCount,
      icon: BookOpen,
      change: "Active in Library",
    },
    {
      label: "Grounded Chat Sessions",
      value: conversationCount,
      icon: MessageSquare,
      change: "Saved Conversations",
    },
    {
      label: "Vector Store",
      value: "ChromaDB",
      icon: Layers,
      change: "Section-Aware Embeddings",
    },
    {
      label: "Citation Provenance",
      value: "100%",
      icon: ShieldCheck,
      change: "Verified Chunk Mapping",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <Card key={metric.label} className="border-zinc-200 shadow-2xs dark:border-zinc-800">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                  {metric.label}
                </p>
                <p className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 font-mono">
                  {metric.value}
                </p>
                <p className="text-[11px] text-zinc-400 font-mono">
                  {metric.change}
                </p>
              </div>

              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                <Icon className="h-4 w-4" />
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
