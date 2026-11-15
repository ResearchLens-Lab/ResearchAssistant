"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Copy, Check, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatResearchTimestamp } from "@/utils/researchTime.mjs";

const GroundedAnswer = dynamic(
  () => import("./GroundedAnswer").then((mod) => mod.GroundedAnswer),
  {
    ssr: false,
    loading: () => (
      <div className="space-y-2 py-2">
        <div className="h-4 w-3/4 animate-pulse rounded bg-zinc-100" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-zinc-100" />
      </div>
    ),
  }
);

function formatTimestamp(timestamp) {
  return formatResearchTimestamp(timestamp);
}

export function MessageItem({ message, onFollowUp, autoSelectFirstCitation = false, researchQuestion = "" }) {
  const isAssistant = message.role === "assistant";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formattedTime = formatTimestamp(message.created_at);

  return (
    <div className="group w-full px-4 py-3 sm:px-6">
      <div className={`mx-auto flex w-full max-w-3xl ${isAssistant ? "items-start gap-3" : "justify-end"}`}>
        {isAssistant && (
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[var(--rl-primary)]">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
        )}

        <div className={`min-w-0 ${isAssistant ? "flex-1" : "max-w-[88%] sm:max-w-[78%]"}`}>
          {isAssistant ? (
            <div className="mb-2 flex min-h-7 flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-xs font-semibold text-slate-800">
                ResearchLens
              </span>
              {formattedTime && <span className="text-[10px] text-slate-400">{formattedTime}</span>}
              {message.sources?.length > 0 && (
                <Badge variant="grounded" className="text-[10px] px-1.5 py-0 gap-1">
                  {message.sources.length} source{message.sources.length === 1 ? "" : "s"} cited
                </Badge>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto h-6 w-6 text-slate-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-slate-700"
                onClick={handleCopy}
                title="Copy answer"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          ) : (
            <>
              <div className="rounded-2xl rounded-br-md bg-[var(--rl-primary)] px-4 py-3 text-sm leading-relaxed text-white shadow-sm whitespace-pre-wrap">
                {message.content}
              </div>
              <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-slate-400">
                {formattedTime && <><Clock className="h-3 w-3" /><span>{formattedTime}</span></>}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5 text-slate-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-slate-700"
                  onClick={handleCopy}
                  title="Copy question"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
                </Button>
              </div>
            </>
          )}

          {isAssistant ? (
            <div className="min-w-0">
              <GroundedAnswer content={message.content} sources={message.sources} autoSelectFirstCitation={autoSelectFirstCitation} question={researchQuestion} researchPlan={message.meta?.research || message.metadata?.research || null} />
              {(message.meta?.follow_up_suggestions || message.metadata?.follow_up_suggestions)?.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-1.5">
                  <span className="mr-0.5 text-[10px] font-medium text-slate-400">Explore further:</span>
                  {(message.meta?.follow_up_suggestions || message.metadata?.follow_up_suggestions).map((chip, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onFollowUp?.(chip)}
                      className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white px-2.5 py-1 text-[11px] font-medium text-sky-800 transition-colors hover:border-sky-300 hover:bg-sky-50"
                    >
                      <span>{chip}</span><span className="text-sky-500">&rarr;</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
