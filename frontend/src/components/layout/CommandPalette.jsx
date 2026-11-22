"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  BookOpen,
  FlaskConical,
  GitCompareArrows,
  Settings,
  LayoutDashboard,
  Search,
  PlusCircle,
  UploadCloud,
  FileText,
  CornerDownLeft,
} from "lucide-react";
import { usePapers } from "@/hooks/usePapers";

function isEditableTarget(target) {
  if (!target) return false;
  const tag = target.tagName?.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    target.isContentEditable ||
    target.getAttribute?.("contenteditable") === "true"
  );
}

export function CommandPalette({ isOpen, onOpenChange, onOpenAddSources }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const { papers = [] } = usePapers(1, 50);

  // Global keyboard shortcuts (Ctrl+K, Ctrl+N, Ctrl+1, Ctrl+2, Ctrl+3)
  useEffect(() => {
    const handleKeyDown = (e) => {
      const isCtrlOrCmd = e.ctrlKey || e.metaKey;
      if (!isCtrlOrCmd) return;

      const key = e.key.toLowerCase();

      // Ctrl+K always triggers palette even in inputs
      if (key === "k") {
        e.preventDefault();
        onOpenChange(!isOpen);
        return;
      }

      // Ignore other shortcuts when typing in inputs
      if (isEditableTarget(e.target)) return;

      if (key === "n") {
        e.preventDefault();
        router.push("/chat");
      } else if (key === "1") {
        e.preventDefault();
        router.push("/papers");
      } else if (key === "2") {
        e.preventDefault();
        router.push("/chat");
      } else if (key === "3") {
        e.preventDefault();
        router.push("/compare");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onOpenChange, router]);

  // Reset query and selected index on open
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const baseCommands = useMemo(
    () => [
      {
        id: "nav-library",
        label: "Library",
        category: "Navigation",
        icon: BookOpen,
        shortcut: "Ctrl+1",
        run: () => router.push("/papers"),
      },
      {
        id: "nav-desk",
        label: "Research Desk",
        category: "Navigation",
        icon: FlaskConical,
        shortcut: "Ctrl+2",
        run: () => router.push("/chat"),
      },
      {
        id: "nav-compare",
        label: "Compare & Reports",
        category: "Navigation",
        icon: GitCompareArrows,
        shortcut: "Ctrl+3",
        run: () => router.push("/compare"),
      },
      {
        id: "nav-settings",
        label: "Settings",
        category: "Navigation",
        icon: Settings,
        shortcut: "",
        run: () => router.push("/settings"),
      },
      {
        id: "nav-overview",
        label: "Overview",
        category: "Navigation",
        icon: LayoutDashboard,
        shortcut: "",
        run: () => router.push("/dashboard"),
      },
      {
        id: "nav-search",
        label: "Search",
        category: "Navigation",
        icon: Search,
        shortcut: "",
        run: () => router.push("/search"),
      },
      {
        id: "act-new-chat",
        label: "New research",
        category: "Actions",
        icon: PlusCircle,
        shortcut: "Ctrl+N",
        run: () => router.push("/chat"),
      },
      {
        id: "act-add-sources",
        label: "Add sources",
        category: "Actions",
        icon: UploadCloud,
        shortcut: "",
        run: () => {
          if (onOpenAddSources) onOpenAddSources();
        },
      },
    ],
    [router, onOpenAddSources]
  );

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matchedCommands = q
      ? baseCommands.filter(
          (c) =>
            c.label.toLowerCase().includes(q) ||
            c.category.toLowerCase().includes(q)
        )
      : baseCommands;

    const matchedProjects = (papers || [])
      .filter((p) => !q || p.title.toLowerCase().includes(q))
      .slice(0, 8)
      .map((p) => ({
        id: `proj-${p.id}`,
        label: p.title,
        category: "Projects",
        icon: FileText,
        shortcut: "",
        run: () => router.push(`/papers/${p.id}`),
      }));

    return [...matchedCommands, ...matchedProjects];
  }, [baseCommands, papers, query, router]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredItems.length]);

  const handleSelect = (item) => {
    onOpenChange(false);
    item.run();
  };

  const handleInputKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredItems.length ? (prev + 1) % filteredItems.length : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredItems.length
          ? (prev - 1 + filteredItems.length) % filteredItems.length
          : 0
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        handleSelect(filteredItems[selectedIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onOpenChange(false);
    }
  };

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs transition-opacity duration-150" />
        <DialogPrimitive.Content
          aria-label="Command palette"
          className="fixed left-[50%] top-[20%] z-50 w-full max-w-xl translate-x-[-50%] rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden outline-none duration-150 animate-in fade-in-0 zoom-in-95"
        >
          <div className="flex items-center border-b border-slate-100 px-4 py-3">
            <Search className="h-4 w-4 text-slate-400 shrink-0 mr-2.5" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Type a command or search projects..."
              className="w-full bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
            />
            <kbd className="hidden sm:inline-block rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-mono text-slate-400">
              Esc
            </kbd>
          </div>

          <div className="max-h-80 overflow-y-auto p-2 space-y-1">
            {filteredItems.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-400">
                No commands or projects match &ldquo;{query}&rdquo;
              </div>
            ) : (
              filteredItems.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`w-full flex items-center justify-between rounded-xl px-3 py-2 text-xs transition-colors ${
                      isSelected
                        ? "bg-sky-50 text-[#1d6fc4]"
                        : "text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`h-4 w-4 shrink-0 ${
                          isSelected ? "text-[#1d6fc4]" : "text-slate-400"
                        }`}
                      />
                      <span className="truncate font-medium text-left">
                        {item.label}
                      </span>
                      <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-full shrink-0">
                        {item.category}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0 ml-2">
                      {item.shortcut && (
                        <kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-mono text-slate-400">
                          {item.shortcut}
                        </kbd>
                      )}
                      {isSelected && (
                        <CornerDownLeft className="h-3 w-3 text-[#1d6fc4]" />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
