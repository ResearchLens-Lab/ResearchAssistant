"use client";

import React from "react";
import Link from "next/link";
import { usePapers } from "@/hooks/usePapers";
import { useChat } from "@/hooks/useChat";
import { MetricsOverview } from "@/components/dashboard/MetricsOverview";
import { RecentPapers } from "@/components/dashboard/RecentPapers";
import { RecentConversations } from "@/components/dashboard/RecentConversations";
import { Button } from "@/components/ui/button";
import { UploadCloud, MessageSquareQuote, GitCompare } from "lucide-react";

export default function DashboardPage() {
  const { papers, pagination: papersPagination, isLoading: isLoadingPapers } = usePapers(1, 5);
  const { conversations, isLoadingConversations } = useChat();

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Workbench Welcome & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200/80 pb-5 dark:border-zinc-800">
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Research Workbench
          </h1>
          <p className="text-xs text-zinc-500 font-mono">
            Ground research questions against your indexed literature with section-aware vector RAG.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
            <Link href="/compare">
              <GitCompare className="h-3.5 w-3.5 text-zinc-500" />
              <span>Compare Papers</span>
            </Link>
          </Button>

          <Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
            <Link href="/chat">
              <MessageSquareQuote className="h-3.5 w-3.5 text-zinc-500" />
              <span>Grounded Chat</span>
            </Link>
          </Button>

          <Button
            variant="workbench"
            size="sm"
            asChild
            className="gap-1.5 text-xs bg-zinc-900 text-white"
          >
            <Link href="/papers/upload">
              <UploadCloud className="h-3.5 w-3.5" />
              <span>Upload PDF</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Metrics Ribbon */}
      <MetricsOverview
        paperCount={papersPagination.total}
        conversationCount={conversations.length}
      />

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentPapers papers={papers} isLoading={isLoadingPapers} />
        <RecentConversations
          conversations={conversations}
          isLoading={isLoadingConversations}
        />
      </div>
    </div>
  );
}
