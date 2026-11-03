"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";
import { User, ShieldCheck, Sparkles, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

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

export function MessageItem({ message }) {
  const isAssistant = message.role === "assistant";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group flex w-full gap-3 py-4 transition-colors ${
        isAssistant
          ? "border-b border-zinc-100 bg-transparent dark:border-zinc-850"
          : "border-b border-zinc-100/70 bg-zinc-50/50 dark:border-zinc-900 dark:bg-zinc-950/40"
      } px-4 md:px-6`}
    >
      {/* Avatar */}
      <div className="shrink-0 pt-0.5">
        {isAssistant ? (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--rl-selected)] text-[var(--rl-primary)]">
            <Sparkles className="h-4 w-4" />
          </div>
        ) : (
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-200 text-zinc-700 font-semibold text-xs dark:bg-zinc-800 dark:text-zinc-300">
            <User className="h-4 w-4" />
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className="flex-1 space-y-2 overflow-hidden">
        {/* Header Ribbon */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
              {isAssistant ? "ResearchLens Assistant" : "Researcher"}
            </span>

            {isAssistant && message.sources && message.sources.length > 0 && (
              <Badge variant="grounded" className="text-[9px] px-1.5 py-0 gap-1">
                <ShieldCheck className="h-2.5 w-2.5" />
                {message.sources.length} sources cited
              </Badge>
            )}
            {isAssistant && (message.meta?.answer_mode || message.metadata?.answer_mode) && (() => {
              const mode = message.meta?.answer_mode || message.metadata?.answer_mode;
              const reason = message.meta?.generation_reason || message.metadata?.generation_reason;
              const label = mode === "generated" ? "Gemini synthesis"
                : mode === "evidence_fallback" ? "Evidence only · synthesis unavailable"
                  : reason === "direct_factual_lookup" ? "Evidence only · direct lookup"
                    : reason === "insufficient_evidence" ? "Evidence only · insufficient support"
                  : mode === "mock" ? "Test response" : "Evidence only";
              return <Badge variant="outline" title={reason ? `Reason: ${reason.replaceAll("_", " ")}` : undefined}
                className="text-[9px] px-1.5 py-0">{label}</Badge>;
            })()}
          </div>

          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-zinc-400 hover:text-zinc-700"
              onClick={handleCopy}
              title="Copy message"
            >
              {copied ? (
                <Check className="h-3 w-3 text-emerald-600" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
          </div>
        </div>

        {/* Body */}
        {isAssistant ? (
          <GroundedAnswer content={message.content} sources={message.sources} />
        ) : (
          <p className="text-xs text-zinc-800 leading-relaxed dark:text-zinc-200 whitespace-pre-wrap">
            {message.content}
          </p>
        )}
      </div>
    </div>
  );
}
