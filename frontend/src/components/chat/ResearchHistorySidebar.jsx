"use client";

import React, { useState, useMemo } from "react";
import {
  Clock,
  Plus,
  Search,
  X,
  MessageSquare,
  Layers,
  Pencil,
  Trash2,
  AlertTriangle,
  Loader2,
  Calendar,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  groupConversationsByDate,
  formatRelativeTime,
  filterConversations,
} from "@/lib/researchWorkspace.mjs";

export function ResearchHistorySidebar({
  conversations = [],
  isLoading = false,
  activeId = null,
  onSelectConversation,
  onNewResearch,
  onRenameConversation,
  onDeleteConversation,
  isDeleting = false,
  isUpdating = false,
  onClose,
  className = "",
}) {
  const [localSearch, setLocalSearch] = useState("");
  const [renamingConv, setRenamingConv] = useState(null);
  const [newTitle, setNewTitle] = useState("");
  const [deletingConv, setDeletingConv] = useState(null);

  // Client-side instant filtering
  const filtered = useMemo(() => {
    return filterConversations(conversations, localSearch);
  }, [conversations, localSearch]);

  const groups = useMemo(() => {
    return groupConversationsByDate(filtered);
  }, [filtered]);

  const handleOpenRename = (conv, e) => {
    e.stopPropagation();
    setRenamingConv(conv);
    setNewTitle(conv.title || "");
  };

  const handleConfirmRename = async () => {
    if (!renamingConv || !newTitle.trim()) return;
    try {
      await onRenameConversation?.(renamingConv.id, newTitle.trim());
      setRenamingConv(null);
    } catch {
      // Handled by caller/mutation
    }
  };

  const handleOpenDelete = (conv, e) => {
    e.stopPropagation();
    setDeletingConv(conv);
  };

  const handleConfirmDelete = async () => {
    if (!deletingConv) return;
    try {
      await onDeleteConversation?.(deletingConv.id);
      setDeletingConv(null);
    } catch {
      // Handled by caller/mutation
    }
  };

  return (
    <>
      <aside
        aria-label="Research history"
        className={`flex h-full w-full shrink-0 flex-col border-r border-[var(--rl-border)] bg-white sm:w-72 md:w-80 ${className}`}
      >
        {/* Header Bar */}
        <div className="border-b border-slate-200 bg-white p-3 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--rl-selected)] text-[var(--rl-primary)]">
                <Clock className="h-4 w-4" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-[var(--rl-ink)]">
                  Research History
                </h2>
                <p className="text-[10px] text-[var(--rl-muted)]">
                  {conversations.length} saved session{conversations.length === 1 ? "" : "s"}
                </p>
              </div>
            </div>
            {onClose && (
              <button
                type="button"
                aria-label="Close history sidebar"
                onClick={onClose}
                className="rounded-md p-1.5 text-slate-500 hover:bg-[var(--rl-tint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)]"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* New Research Button */}
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={onNewResearch}
            className="w-full h-9 justify-center gap-2 bg-[var(--rl-primary)] text-white hover:bg-[#1f659c] text-xs font-medium shadow-xs"
          >
            <Plus className="h-4 w-4" />
            <span>New Research</span>
          </Button>

          {/* Search History Box */}
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              placeholder="Search previous sessions..."
              aria-label="Search conversation history"
              className="h-8 w-full rounded-md border border-slate-200 bg-slate-50 pl-8 pr-7 text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)]"
            />
            {localSearch && (
              <button
                type="button"
                onClick={() => setLocalSearch("")}
                aria-label="Clear search"
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Conversation List Scroll Area */}
        <ScrollArea className="flex-1 p-2">
          {isLoading ? (
            <div className="space-y-2 p-2" aria-label="Loading research history">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100" />
              ))}
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-400 space-y-2">
              <MessageSquare className="mx-auto h-8 w-8 text-slate-300" />
              <p className="font-semibold text-slate-700">No research history</p>
              <p className="text-[11px] text-slate-500">
                Ask a question to start your first grounded research session.
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 space-y-2">
              <Search className="mx-auto h-6 w-6 text-slate-300" />
              <p>No sessions match &ldquo;{localSearch}&rdquo;</p>
              <button
                type="button"
                onClick={() => setLocalSearch("")}
                className="text-[11px] text-[var(--rl-primary)] hover:underline"
              >
                Clear search
              </button>
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {groups.map((group) => (
                <div key={group.label} className="space-y-1">
                  <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    <Calendar className="h-3 w-3" />
                    <span>{group.label}</span>
                  </div>

                  <div className="space-y-1">
                    {group.items.map((conv) => {
                      const isActive = conv.id === activeId;
                      const projectCount = (conv.paper_ids || []).length;
                      const messageCount = conv.message_count;

                      return (
                        <div
                          key={conv.id}
                          role="button"
                          tabIndex={0}
                          aria-current={isActive ? "page" : undefined}
                          onClick={() => onSelectConversation(conv.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              onSelectConversation(conv.id);
                            }
                          }}
                          className={`group relative flex flex-col gap-1 rounded-lg border p-2.5 text-left transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-primary)] ${
                            isActive
                              ? "border-[var(--rl-primary)] bg-[var(--rl-selected)] text-[var(--rl-ink)] shadow-2xs"
                              : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50 text-slate-800"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-1.5">
                            <span
                              className={`truncate text-xs font-semibold leading-tight ${
                                isActive ? "text-[var(--rl-primary)]" : "text-slate-900"
                              }`}
                              title={conv.title || "Untitled research"}
                            >
                              {conv.title || "Untitled research"}
                            </span>

                            {/* Hover Actions: Rename & Delete */}
                            <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 shrink-0 transition-opacity">
                              <button
                                type="button"
                                title="Rename research session"
                                aria-label={`Rename ${conv.title || "session"}`}
                                onClick={(e) => handleOpenRename(conv, e)}
                                className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                              >
                                <Pencil className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                title="Delete research session"
                                aria-label={`Delete ${conv.title || "session"}`}
                                onClick={(e) => handleOpenDelete(conv, e)}
                                className="rounded p-1 text-slate-400 hover:bg-rose-100 hover:text-rose-600"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                          </div>

                          <div className="flex items-center justify-between text-[10px] text-slate-500 font-normal">
                            <div className="flex items-center gap-1.5 truncate">
                              <span className="flex items-center gap-1">
                                <Layers className="h-2.5 w-2.5 text-slate-400" />
                                {projectCount} {projectCount === 1 ? "project" : "projects"}
                              </span>
                              {typeof messageCount === "number" && messageCount > 0 && (
                                <>
                                  <span>·</span>
                                  <span>{messageCount} {messageCount === 1 ? "turn" : "turns"}</span>
                                </>
                              )}
                            </div>
                            <span className="shrink-0 text-slate-400 font-mono">
                              {formatRelativeTime(conv.updated_at || conv.created_at)}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </aside>

      {/* Rename Dialog */}
      <Dialog open={!!renamingConv} onOpenChange={(open) => !open && setRenamingConv(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rename Research Session</DialogTitle>
            <DialogDescription>
              Enter a descriptive title for this research thread.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="e.g. Distributed Consensus Algorithms"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleConfirmRename();
                }
              }}
            />
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRenamingConv(null)}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleConfirmRename}
              disabled={isUpdating || !newTitle.trim()}
              className="bg-[var(--rl-primary)] text-white hover:bg-[#1f659c]"
            >
              {isUpdating && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Save title
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingConv} onOpenChange={(open) => !open && setDeletingConv(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader className="items-center text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-100 text-rose-600 mb-1">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <DialogTitle>Delete Research Session?</DialogTitle>
            <DialogDescription className="text-xs">
              This will permanently delete &ldquo;<strong>{deletingConv?.title}</strong>&rdquo; and all associated message turns. Source papers and ChromaDB vectors will remain in your library.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-3 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setDeletingConv(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={handleConfirmDelete}
              disabled={isDeleting}
              className="bg-rose-600 text-white hover:bg-rose-700"
            >
              {isDeleting && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Delete session
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

