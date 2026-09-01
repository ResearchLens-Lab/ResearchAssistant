"use client";

import React, { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ArrowUp, Sparkles, Table as TableIcon, Hash } from "lucide-react";
import { useChatScopeStore } from "@/store/chatScopeStore";

export function ChatInputBar({ onSendMessage, isLoading }) {
  const [input, setInput] = useState("");
  const textareaRef = useRef(null);
  const { selectedPaperIds } = useChatScopeStore();

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || selectedPaperIds.length === 0) return;
    setInput("");
    await onSendMessage(trimmed);
  };

  const addModifier = (modifier) => {
    setInput((prev) => (prev ? `${prev} ${modifier}` : modifier));
    textareaRef.current?.focus();
  };

  return (
    <div className="border-t border-zinc-200 bg-white p-3 md:p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mx-auto max-w-4xl space-y-2">
        {/* Modifier Chips / Helper Bar */}
        <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => addModifier("#table output")}
              className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-zinc-600 hover:bg-zinc-200 transition-colors dark:bg-zinc-800 dark:text-zinc-300"
            >
              <TableIcon className="h-3 w-3" />
              <span>table output</span>
            </button>

            <button
              type="button"
              onClick={() => addModifier("#compare methodology")}
              className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-zinc-600 hover:bg-zinc-200 transition-colors dark:bg-zinc-800 dark:text-zinc-300"
            >
              <Hash className="h-3 w-3" />
              <span>methodology</span>
            </button>

            <button
              type="button"
              onClick={() => addModifier("#cite strict")}
              className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-zinc-600 hover:bg-zinc-200 transition-colors dark:bg-zinc-800 dark:text-zinc-300"
            >
              <Sparkles className="h-3 w-3" />
              <span>cite strict</span>
            </button>
          </div>

          <div className="hidden sm:flex items-center gap-2 text-[10px] text-zinc-400">
            <span>retrieval grounded</span>
            <span>•</span>
            <span>ChromaDB context</span>
          </div>
        </div>

        {/* Input Box Container */}
        <div className="relative flex items-end rounded-xl border border-zinc-300 bg-zinc-50/50 p-2 focus-within:border-zinc-900 focus-within:bg-white focus-within:ring-1 focus-within:ring-zinc-900 shadow-2xs dark:border-zinc-700 dark:bg-zinc-950 dark:focus-within:border-zinc-200">
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || selectedPaperIds.length === 0}
            placeholder={
              selectedPaperIds.length === 0
                ? "Select at least one paper from the left scope to ask..."
                : `Ask across the ${selectedPaperIds.length} selected paper(s)...`
            }
            className="flex-1 resize-none bg-transparent px-2 py-1 text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:text-zinc-100"
          />

          <Button
            type="button"
            size="sm"
            onClick={handleSubmit}
            disabled={
              !input.trim() || isLoading || selectedPaperIds.length === 0
            }
            className="h-8 gap-1 rounded-lg bg-zinc-900 text-white hover:bg-zinc-800 shrink-0 font-medium text-xs px-3 shadow-2xs"
          >
            {isLoading ? (
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <>
                <span>Ask</span>
                <ArrowUp className="h-3.5 w-3.5" />
              </>
            )}
          </Button>
        </div>

        {selectedPaperIds.length === 0 && (
          <p className="text-[11px] text-amber-600 font-mono">
            ⚠️ Check at least 1 paper in the left panel to scope your research question.
          </p>
        )}
      </div>
    </div>
  );
}
