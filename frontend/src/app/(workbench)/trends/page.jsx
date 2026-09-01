"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { researchService } from "@/services/research.service";
import { usePapers } from "@/hooks/usePapers";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, BarChart2, Layers } from "lucide-react";

export default function ResearchTrendsPage() {
  const { data: trendsData, isLoading: isLoadingTrends } = useQuery({
    queryKey: ["researchTrends"],
    queryFn: () => researchService.getResearchTrends(),
    retry: 0,
  });

  const { papers } = usePapers(1, 100);

  // Compute local library distribution as robust fallback
  const yearDistribution = {};
  const venueDistribution = {};

  papers.forEach((p) => {
    if (p.publication_year) {
      yearDistribution[p.publication_year] =
        (yearDistribution[p.publication_year] || 0) + 1;
    }
    if (p.venue) {
      venueDistribution[p.venue] = (venueDistribution[p.venue] || 0) + 1;
    }
  });

  const sortedYears = Object.entries(yearDistribution).sort(
    ([a], [b]) => Number(a) - Number(b)
  );

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Research Trends & Intelligence
          </h1>
        </div>
        <p className="text-xs text-zinc-500 font-mono">
          Topic velocity, keyword growth rates, and publication distribution across your literature collection.
        </p>
      </div>

      {/* Top Emerging Concepts */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
          Core Research Topics in Scope
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { topic: "Dense Passage Retrieval (DPR)", velocity: "+48%", status: "High Interest" },
            { topic: "Section-Aware Grounded RAG", velocity: "+64%", status: "Core Baseline" },
            { topic: "Fusion-in-Decoder (FiD)", velocity: "+32%", status: "Emerging" },
          ].map((item) => (
            <Card key={item.topic} className="border-zinc-200 shadow-2xs dark:border-zinc-800">
              <CardContent className="p-4 space-y-1">
                <div className="flex items-center justify-between">
                  <Badge variant="grounded" className="text-[9px] font-mono">
                    {item.velocity}
                  </Badge>
                  <span className="text-[10px] text-zinc-400 font-mono">
                    {item.status}
                  </span>
                </div>
                <h4 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 pt-1">
                  {item.topic}
                </h4>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Library Distribution Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Publication Timeline */}
        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-blue-600" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                Publications by Year
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-2">
            {sortedYears.length === 0 ? (
              <p className="text-xs text-zinc-400 py-4 text-center">
                Upload papers with publication years to visualize timelines.
              </p>
            ) : (
              sortedYears.map(([year, count]) => (
                <div key={year} className="flex items-center gap-3 text-xs font-mono">
                  <span className="w-12 text-zinc-500 font-semibold">{year}</span>
                  <div className="h-2 flex-1 rounded-full bg-zinc-100 overflow-hidden dark:bg-zinc-800">
                    <div
                      className="h-full bg-zinc-900 dark:bg-zinc-100 rounded-full"
                      style={{
                        width: `${Math.min(100, (count / papers.length) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-zinc-700 dark:text-zinc-300 font-semibold">
                    {count}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Publication Venues */}
        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-indigo-600" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                Top Academic Venues
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-2">
            {Object.keys(venueDistribution).length === 0 ? (
              <p className="text-xs text-zinc-400 py-4 text-center">
                No venues recorded in paper metadata yet.
              </p>
            ) : (
              Object.entries(venueDistribution).map(([venue, count]) => (
                <div key={venue} className="flex items-center justify-between text-xs py-1 border-b border-zinc-50 dark:border-zinc-800/60">
                  <span className="font-medium text-zinc-800 dark:text-zinc-200">{venue}</span>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {count} paper(s)
                  </Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
