"use client";

import React, { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ArrowUp, GitCompareArrows, ListChecks, Table as TableIcon } from "lucide-react";
import { useChatScopeStore } from "@/store/chatScopeStore";

export function ChatInputBar({ onSendMessage, onCancel, isLoading, answerMode = "DOCUMENTS_GENERAL", onAnswerModeChange }) {
  const [input, setInput] = useState("");
  const textareaRef = useRef(null);
  const { selectedPaperIds } = useChatScopeStore();

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || selectedPaperIds.length === 0) return;
    setInput("");
    try {
      await onSendMessage(trimmed);
    } catch {
      setInput(trimmed);
    }
  };

  const addPrompt = (prompt) => {
    setInput((previous) => previous ? `${previous} ${prompt}` : prompt);
    textareaRef.current?.focus();
  };

  const promptActions = [
    { label: "Use a table", icon: TableIcon, prompt: "Present the relevant findings in a concise table with citations." },
    { label: "Compare methods", icon: GitCompareArrows, prompt: "Compare the methods and experimental conditions reported in the selected sources." },
    { label: "Extract fields", icon: ListChecks, prompt: "Extract methods, datasets, metrics, and reported limitations in a cited table." },
  ];

  return (
    <div className="border-t border-[var(--rl-border)] bg-white p-3 sm:p-4 shrink-0 z-10">
      <div className="mx-auto max-w-4xl space-y-2">
        <div className="flex items-center justify-between gap-3">
          <label className="flex shrink-0 items-center gap-2 text-xs text-[var(--rl-muted)]">
            Answer mode
            <select aria-label="Answer mode" value={answerMode} onChange={(event) => onAnswerModeChange?.(event.target.value)} disabled={isLoading} className="h-8 rounded-lg border border-[var(--rl-border)] bg-white px-2 text-xs font-medium text-[var(--rl-ink)]">
              <option value="DOCUMENTS_GENERAL">Documents + general knowledge</option>
              <option value="DOCUMENTS_ONLY">Documents only</option>
            </select>
          </label>
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {promptActions.map(({ label, icon: Icon, prompt }) => <button key={label} type="button" onClick={() => addPrompt(prompt)} disabled={selectedPaperIds.length === 0 || isLoading} className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-full bg-[var(--rl-tint)] px-3 text-xs font-medium text-[var(--rl-muted)] transition-colors hover:bg-[var(--rl-selected)] hover:text-[var(--rl-primary)] disabled:cursor-not-allowed disabled:opacity-50"><Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}</button>)}
          </div>
          <span className="hidden shrink-0 text-xs text-[var(--rl-muted)] sm:block">{selectedPaperIds.length} indexed project{selectedPaperIds.length === 1 ? "" : "s"} in scope</span>
        </div>

        <div className="relative flex items-end rounded-2xl border border-[var(--rl-border)] bg-white p-2 shadow-sm focus-within:border-[var(--rl-sky)] focus-within:ring-2 focus-within:ring-sky-100">
          <textarea
            ref={textareaRef}
            rows={2}
            aria-label="Research question"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || selectedPaperIds.length === 0}
            placeholder={selectedPaperIds.length === 0 ? "Select indexed sources from the Sources panel to begin…" : `Ask across ${selectedPaperIds.length} selected project${selectedPaperIds.length === 1 ? "" : "s"}…`}
            className="max-h-40 min-h-14 flex-1 resize-y bg-transparent px-3 py-2 text-sm leading-6 text-[var(--rl-ink)] placeholder:text-[var(--rl-muted)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          {isLoading ? <Button type="button" size="sm" variant="outline" onClick={onCancel} className="h-10 shrink-0 px-4 text-sm">Stop research</Button> : <Button type="button" size="sm" variant="workbench" onClick={handleSubmit} disabled={!input.trim() || selectedPaperIds.length === 0} className="h-10 shrink-0 gap-1.5 px-4 text-sm"><span>Ask</span><ArrowUp className="h-4 w-4" aria-hidden="true" /></Button>}
        </div>

        {selectedPaperIds.length === 0 && <p role="status" className="text-xs text-amber-800">Select at least one indexed project in Sources to scope your question.</p>}
        {isLoading && <p role="status" className="text-xs text-[var(--rl-muted)]">Research is in progress. Your question remains visible above.</p>}
      </div>
    </div>
  );
}
