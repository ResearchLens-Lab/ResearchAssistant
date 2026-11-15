"use client";

import React, { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowUp,
  Square,
  Table as TableIcon,
  PieChart as PieIcon,
  Workflow,
  GitCompare,
  BookOpen,
  Sparkles,
  Layers,
  ChevronDown,
} from "lucide-react";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

const SLASH_COMMANDS = [
  {
    cmd: "/table",
    label: "/table",
    title: "Tabular Synthesis",
    desc: "Generate findings in a cited comparison or summary table",
    icon: TableIcon,
    prompt: "/table ",
  },
  {
    cmd: "/pie",
    label: "/pie",
    title: "Distribution Pie Chart",
    desc: "Visualize topic distribution and scope proportions in an interactive pie chart",
    icon: PieIcon,
    prompt: "/pie ",
  },
  {
    cmd: "/flowchart",
    label: "/flowchart",
    title: "Process Flowchart",
    desc: "Generate an interactive flowchart showing stages and conceptual relationships",
    icon: Workflow,
    prompt: "/flowchart ",
  },
  {
    cmd: "/compare",
    label: "/compare",
    title: "Compare Sources",
    desc: "Compare methods, datasets, and conditions across retrieved evidence",
    icon: GitCompare,
    prompt: "/compare ",
  },
  {
    cmd: "/summary",
    label: "/summary",
    title: "Structured Outline",
    desc: "Extract a full section-by-section curriculum or document syllabus",
    icon: BookOpen,
    prompt: "/summary ",
  },
];

export function ChatInputBar({
  onSendMessage,
  onCancel,
  isLoading,
  answerMode = "EVIDENCE_FIRST",
  onAnswerModeChange,
  activeProjectName = null,
}) {
  const [input, setInput] = useState("");
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [selectedSlashIndex, setSelectedSlashIndex] = useState(0);
  const textareaRef = useRef(null);
  const slashMenuRef = useRef(null);
  const { selectedPaperIds } = useChatScopeStore();

  // Detect slash command typing
  useEffect(() => {
    if (input === "/" || (input.startsWith("/") && !input.includes(" "))) {
      setShowSlashMenu(true);
      setSelectedSlashIndex(0);
    } else {
      setShowSlashMenu(false);
    }
  }, [input]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const nextHeight = Math.min(textarea.scrollHeight, 180);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > 180 ? "auto" : "hidden";
  }, [input]);

  // Close slash menu on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (
        slashMenuRef.current &&
        !slashMenuRef.current.contains(event.target) &&
        !textareaRef.current?.contains(event.target)
      ) {
        setShowSlashMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleApplySlash = (slashItem) => {
    setInput(slashItem.prompt);
    setShowSlashMenu(false);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (event) => {
    if (showSlashMenu) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedSlashIndex((prev) => (prev + 1) % SLASH_COMMANDS.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelectedSlashIndex(
          (prev) => (prev - 1 + SLASH_COMMANDS.length) % SLASH_COMMANDS.length
        );
        return;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        handleApplySlash(SLASH_COMMANDS[selectedSlashIndex]);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setShowSlashMenu(false);
        return;
      }
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || selectedPaperIds.length === 0) return;
    setInput("");
    setShowSlashMenu(false);
    try {
      await onSendMessage(trimmed);
    } catch {
      setInput(trimmed);
    }
  };

  const docCount = selectedPaperIds.length;

  return (
    <div className="relative border-t border-slate-200/90 bg-white/95 backdrop-blur-xs px-3 py-2 sm:px-6 shrink-0 z-20">
      {/* Floating Slash Commands Autocomplete Popover */}
      {showSlashMenu && (
        <div
          ref={slashMenuRef}
          className="absolute bottom-full left-4 sm:left-8 mb-2 z-50 w-80 sm:w-96 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl font-serif animate-in fade-in slide-in-from-bottom-2 duration-150"
        >
          <div className="px-3 py-1.5 border-b border-slate-100 flex items-center justify-between text-[10px] text-slate-400 uppercase tracking-wider font-bold">
            <span>Research Presentation Modes</span>
            <span>Tab / Enter to select</span>
          </div>

          <div className="py-1 max-h-64 overflow-y-auto space-y-0.5">
            {SLASH_COMMANDS.map((item, index) => {
              const Icon = item.icon;
              const isSelected = selectedSlashIndex === index;
              return (
                <button
                  key={item.cmd}
                  type="button"
                  onClick={() => handleApplySlash(item)}
                  className={`w-full flex items-start gap-2.5 rounded-xl px-3 py-2 text-left transition-colors cursor-pointer ${
                    isSelected
                      ? "bg-sky-50/90 text-[#1d6fc4] ring-1 ring-sky-300/80"
                      : "hover:bg-slate-50 text-slate-800"
                  }`}
                >
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                      isSelected
                        ? "bg-[#1d6fc4] text-white"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs font-bold text-[#1d6fc4]">
                        {item.label}
                      </span>
                      <span className="text-xs font-bold text-slate-900">
                        {item.title}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 truncate leading-tight mt-0.5">
                      {item.desc}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Unified Input Box */}
      <div className="mx-auto w-full max-w-3xl">
        <div className="relative rounded-2xl border border-slate-200/90 bg-white p-2 shadow-xs transition-all duration-200 focus-within:border-sky-400 focus-within:ring-2 focus-within:ring-sky-100">
          {/* Text Input Area */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || docCount === 0}
            placeholder={
              docCount === 0
                ? "Select a project or source in the left panel to begin..."
                : "Ask a question about your selected research sources..."
            }
            className="w-full resize-none bg-transparent px-2.5 py-1.5 text-sm leading-relaxed text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 font-sans"
          />

          {/* Bottom Toolbar inside the box */}
          <div className="mt-0.5 flex items-center justify-between border-t border-slate-100 pt-1.5 font-sans">
            {/* Left Scope & Mode Indicator */}
            <div className="flex items-center gap-2 min-w-0">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" disabled={docCount === 0 || isLoading} className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50">
                    <Sparkles className="h-3.5 w-3.5 text-[var(--rl-primary)]" /> Research tools <ChevronDown className="h-3 w-3" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-64 bg-white">
                  {SLASH_COMMANDS.map((item) => {
                    const Icon = item.icon;
                    return <DropdownMenuItem key={item.cmd} onSelect={() => handleApplySlash(item)} className="gap-2.5 py-2">
                      <Icon className="h-4 w-4 text-[var(--rl-primary)]" />
                      <span className="min-w-0"><span className="block font-medium">{item.title}</span><span className="block truncate text-[10px] text-slate-500">{item.desc}</span></span>
                    </DropdownMenuItem>;
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
              <span className="inline-flex items-center gap-1 rounded-md bg-sky-50 border border-sky-200/70 px-2 py-0.5 text-[10px] font-semibold text-[#1d6fc4]">
                <Layers className="h-3 w-3" />
                <span className="truncate max-w-[160px] sm:max-w-[220px]">
                  {activeProjectName || `${docCount} document${docCount === 1 ? "" : "s"}`}
                </span>
              </span>

            </div>

            {/* Right Action: Send Button / Stop Button */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="hidden md:inline text-[10px] text-slate-400">
                Press Enter ↵
              </span>

              {isLoading ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={onCancel}
                  className="h-8 gap-1 rounded-xl border-rose-200 bg-rose-50 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                >
                  <Square className="h-3 w-3 fill-current" />
                  <span>Stop</span>
                </Button>
              ) : (
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!input.trim() || docCount === 0}
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#1d6fc4] text-white hover:bg-[#185ea8] disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs transition-transform active:scale-95 cursor-pointer"
                  title="Send research inquiry"
                  aria-label="Send question"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Warning if no document selected */}
        {docCount === 0 && (
          <p className="mt-1.5 text-center text-xs text-amber-800 font-serif">
            Select a project with indexed documents in the left sidebar to start asking questions.
          </p>
        )}
      </div>
    </div>
  );
}
