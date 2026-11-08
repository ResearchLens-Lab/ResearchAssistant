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

export function MessageItem({ message, onFollowUp }) {
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
              const provider = message.meta?.generation_provider || message.metadata?.generation_provider || message.meta?.llm_provider || message.metadata?.llm_provider;
              const reason = message.meta?.generation_reason || message.metadata?.generation_reason;
              let label = "Extractive Mode";
              let badgeVariant = "outline";
              if (mode === "general_knowledge") {
                label = "General knowledge · not from documents";
                badgeVariant = "outline";
              } else if (mode === "general_knowledge_unavailable") {
                label = "Documents checked · local model unavailable";
                badgeVariant = "outline";
              } else if (mode === "LOCAL_QWEN" || provider === "ollama") {
                label = "Local Qwen (qwen3.5:0.8b)";
                badgeVariant = "secondary";
              } else if (mode === "generated" || provider === "gemini") {
                label = "Gemini synthesis";
              } else if (mode === "EXTRACTIVE" || mode === "evidence_only") {
                label = "Extractive Mode";
              } else if (mode === "evidence_fallback") {
                label = "Extractive Fallback";
              } else if (mode === "mock") {
                label = "Test Response";
              }
              return (
                <Badge
                  variant={badgeVariant}
                  title={reason ? `Reason: ${reason.replaceAll("_", " ")}` : undefined}
                  className="text-[9px] px-1.5 py-0 font-medium"
                >
                  {label}
                </Badge>
              );
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
          <div>
            <GroundedAnswer content={message.content} sources={message.sources} />
            {/* Interactive Contextual Follow-Up Chips */}
            {(message.meta?.follow_up_suggestions || message.metadata?.follow_up_suggestions)?.length > 0 && (
              <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-zinc-800 flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] text-slate-400 font-medium mr-0.5">Explore further:</span>
                {(message.meta?.follow_up_suggestions || message.metadata?.follow_up_suggestions).map((chip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onFollowUp && onFollowUp(chip)}
                    className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50/80 px-2.5 py-0.5 text-[11px] font-medium text-sky-800 hover:bg-sky-100 hover:border-sky-300 transition-colors shadow-2xs cursor-pointer active:scale-95"
                  >
                    <span>{chip}</span>
                    <span className="text-sky-500 font-bold text-xs">&rarr;</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-800 leading-relaxed dark:text-zinc-200 whitespace-pre-wrap">
            {message.content}
          </p>
        )}
      </div>
    </div>
  );
}
