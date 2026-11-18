import React from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageSquare, ArrowUpRight } from "lucide-react";
import { formatDate } from "@/utils/formatters";

export function RecentConversations({ conversations, isLoading }) {
  return (
    <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
      <CardHeader className="flex flex-row items-center justify-between border-b border-zinc-100 p-4 pb-3 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
          <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
            Recent Chat Threads
          </CardTitle>
        </div>

        <Button variant="ghost" size="sm" asChild className="h-6 text-xs text-blue-600">
          <Link href="/chat">Open Chat →</Link>
        </Button>
      </CardHeader>

      <CardContent className="p-0 divide-y divide-zinc-100 dark:divide-zinc-800/80">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded bg-zinc-100 animate-pulse" />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <div className="py-10 text-center text-zinc-400 space-y-2">
            <p className="text-xs font-medium text-zinc-600">No chat sessions yet</p>
            <Button variant="outline" size="sm" asChild className="text-xs">
              <Link href="/chat">Start a grounded research chat</Link>
            </Button>
          </div>
        ) : (
          conversations.slice(0, 5).map((conv) => (
            <div
              key={conv.id}
              className="flex items-center justify-between p-3.5 hover:bg-zinc-50/75 transition-colors dark:hover:bg-zinc-800/50"
            >
              <div className="space-y-1 min-w-0 pr-4">
                <Link
                  href={`/chat/${conv.id}`}
                  className="text-xs font-semibold text-zinc-900 hover:text-blue-600 truncate block dark:text-zinc-100"
                >
                  {conv.title || "Untitled Grounded Thread"}
                </Link>
                <p className="text-[11px] text-zinc-400 font-mono">
                  {conv.paper_ids?.length || 0} scoped paper(s) • Updated {formatDate(conv.updated_at)}
                </p>
              </div>

              <Button variant="ghost" size="icon" asChild className="h-7 w-7 shrink-0">
                <Link href={`/chat/${conv.id}`}>
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
