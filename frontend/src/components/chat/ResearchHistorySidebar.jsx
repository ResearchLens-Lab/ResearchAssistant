"use client";

import React, { useState, useMemo } from "react";
import {
  Search,
  X,
  MessageSquare,
  Layers,
  Pencil,
  Trash2,
  Folder,
  FileText,
  Calendar,
  MoreHorizontal,
  ExternalLink,
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
  filterConversations,
} from "@/lib/researchWorkspace.mjs";
import { formatResearchTimestamp } from "@/utils/researchTime.mjs";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { EditPaperModal } from "@/components/papers/EditPaperModal";
import { AddSourcesModal } from "@/components/upload/AddSourcesModal";
import Link from "next/link";

function formatSessionTime(dateString) {
  return formatResearchTimestamp(dateString, { todayPrefix: "", yesterdayPrefix: "Yday" });
}

export function ResearchHistorySidebar({
  conversations = [],
  isLoading = false,
  activeId = null,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  isDeleting = false,
  isUpdating = false,
  onClose,
  className = "",
  papers = [],
  documentsByPaper = {},
  selectedPaperIds = [],
  onSelectPaper,
  onUpdatePaper,
  onDeletePaper,
  isDeletingPaper = false,
}) {
  const [localSearch, setLocalSearch] = useState("");
  const [renamingConv, setRenamingConv] = useState(null);
  const [newTitle, setNewTitle] = useState("");
  const [deletingConv, setDeletingConv] = useState(null);
  const [editingPaper, setEditingPaper] = useState(null);
  const [managingSourcesPaper, setManagingSourcesPaper] = useState(null);
  const [deletingPaper, setDeletingPaper] = useState(null);
  const [projectError, setProjectError] = useState("");

  // Client-side instant filtering of conversations
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
      // Handled by caller
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
      // Handled by caller
    }
  };

  return (
    <>
      <aside
        aria-label="Research history"
        className={`flex h-full w-full min-w-0 flex-col overflow-hidden border-r border-slate-200/90 bg-white font-sans ${className}`}
      >
        {/* Search recent sessions */}
        <div className="border-b border-slate-200 bg-white p-3 shrink-0">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              placeholder="Search previous chats..."
              aria-label="Search conversation history"
              className="h-8 w-full rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-7 text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-400/30 font-serif"
            />
            {localSearch && (
              <button
                type="button"
                onClick={() => setLocalSearch("")}
                aria-label="Clear search"
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Project navigation stays compact; sources are managed in the scope panel. */}
        {papers.length > 0 && (
          <div className="shrink-0 border-b border-slate-100 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Folder className="h-3.5 w-3.5 text-[var(--rl-primary)]" />
                <span>Projects</span>
              </span>
            </div>
            <div className="mt-1.5 max-h-36 space-y-0.5 overflow-y-auto">
              {papers.map((p) => {
                const isSelected = selectedPaperIds.includes(p.id);
                const docs = documentsByPaper[p.id] || [];
                const indexedCount = docs.filter((doc) => doc.processing_status === "indexed").length;
                return <div key={p.id} className={`group flex min-w-0 items-center gap-1 rounded-lg px-2 py-1 ${isSelected ? "bg-sky-50 text-[var(--rl-primary)]" : "text-slate-700 hover:bg-slate-50"}`}>
                  <button type="button" onClick={() => onSelectPaper?.(p.id)} title={p.title} className="flex min-w-0 flex-1 items-center gap-2 text-left text-xs">
                    <Folder className="h-3.5 w-3.5 shrink-0" />
                    <span className="min-w-0 flex-1 truncate font-medium">{p.title}</span>
                    <span className="shrink-0 text-[10px] text-slate-400">{indexedCount}</span>
                  </button>
                  <DropdownMenu>
                  <DropdownMenuTrigger asChild><button type="button" aria-label={`Actions for ${p.title}`} title="Project actions" onClick={(event) => event.stopPropagation()} className="rounded p-1 text-slate-400 opacity-70 hover:bg-white hover:text-slate-700 hover:opacity-100 focus:opacity-100 focus-visible:opacity-100"><MoreHorizontal className="h-4 w-4" /></button></DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48 bg-white">
                      <DropdownMenuItem onSelect={() => onSelectPaper?.(p.id)}><Folder className="mr-2 h-3.5 w-3.5" />Use this project</DropdownMenuItem>
                      <DropdownMenuItem asChild><Link href={`/papers/${p.id}`}><ExternalLink className="mr-2 h-3.5 w-3.5" />Open project</Link></DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => setEditingPaper(p)}><Pencil className="mr-2 h-3.5 w-3.5" />Edit details</DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => setManagingSourcesPaper(p)}><FileText className="mr-2 h-3.5 w-3.5" />Manage sources</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onSelect={() => { setProjectError(""); setDeletingPaper(p); }} className="text-red-700 focus:text-red-700"><Trash2 className="mr-2 h-3.5 w-3.5" />Delete project</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>;
              })}
            </div>
            {projectError && <p role="alert" className="mt-2 text-[11px] text-red-700">{projectError}</p>}
          </div>
        )}

        {/* Conversation List Scroll Area (ChatGPT / Perplexity Style) */}
        <ScrollArea className="flex-1 p-2">
          <h2 className="mb-2 px-2 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Recent sessions</h2>
          {isLoading ? (
            <div className="space-y-2 p-2" aria-label="Loading research history">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-xl bg-slate-100" />
              ))}
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-400 space-y-2">
              <MessageSquare className="mx-auto h-7 w-7 text-slate-300" />
              <p className="font-semibold text-slate-700">No research history</p>
              <p className="text-[11px] text-slate-400">
                Type a question or slash command to start your first grounded session.
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 space-y-2">
              <Search className="mx-auto h-6 w-6 text-slate-300" />
              <p>No sessions match &ldquo;{localSearch}&rdquo;</p>
              <button
                type="button"
                onClick={() => setLocalSearch("")}
                className="text-[11px] text-[#1d6fc4] hover:underline"
              >
                Clear search
              </button>
            </div>
          ) : (
            <div className="space-y-3 pb-4">
              {groups.map((group) => (
                <div key={group.label} className="space-y-1">
                  <div className="flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    <Calendar className="h-3 w-3" />
                    <span>{group.label}</span>
                  </div>

                  <div className="space-y-1">
                    {group.items.map((conv) => {
                      const isActive = conv.id === activeId;
                      const messageCount = conv.message_count;
                      const timeDisplay = formatSessionTime(conv.updated_at || conv.created_at);

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
                          className={`group relative flex flex-col gap-1 rounded-xl border p-2.5 text-left transition-all cursor-pointer ${
                            isActive
                              ? "border-[#1d6fc4] bg-sky-50/70 text-slate-900 shadow-2xs ring-1 ring-sky-300/60"
                              : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50 text-slate-800"
                          }`}
                        >
                          {/* Title & Actions */}
                          <div className="flex min-w-0 items-start gap-1.5">
                            <span
                              className={`min-w-0 flex-1 break-words whitespace-normal text-xs font-semibold leading-snug ${
                                isActive ? "text-[#1d6fc4]" : "text-slate-900"
                              }`}
                              title={conv.title || "Untitled research"}
                            >
                              {conv.title || "Untitled research"}
                            </span>

                            {/* Keep session actions visible so deletion is discoverable. */}
                            <div className="flex shrink-0 items-center gap-0.5">
                              <button
                                type="button"
                                title="Rename research session"
                                aria-label={`Rename ${conv.title || "session"}`}
                                onClick={(e) => handleOpenRename(conv, e)}
                                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-400 hover:bg-slate-200 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 transition-colors"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                title="Delete research session"
                                aria-label={`Delete ${conv.title || "session"}`}
                                onClick={(e) => handleOpenDelete(conv, e)}
                                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-400 hover:bg-rose-100 hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300 transition-colors"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>

                          {/* Footer: Date & Timing + Message Turns */}
                          <div className="flex items-center justify-between text-[10px] text-slate-400">
                            <span className="truncate flex items-center gap-1">
                              <Layers className="h-2.5 w-2.5 text-slate-400" />
                              <span>{messageCount ? `${messageCount} turns` : "1 turn"}</span>
                            </span>
                            {timeDisplay && (
                              <span className="shrink-0 font-mono text-[10px] text-slate-400">
                                {timeDisplay}
                              </span>
                            )}
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
        <DialogContent className="sm:max-w-md font-serif">
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
              placeholder="e.g. Distributed Operating System Design"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleConfirmRename();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setRenamingConv(null)}
              className="rounded-xl font-serif"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              onClick={handleConfirmRename}
              disabled={isUpdating || !newTitle.trim()}
              className="bg-[#1d6fc4] hover:bg-[#185ea8] text-white rounded-xl font-serif"
            >
              {isUpdating ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingConv} onOpenChange={(open) => !open && setDeletingConv(null)}>
        <DialogContent className="sm:max-w-md font-serif">
          <DialogHeader>
            <DialogTitle>Delete Research Session?</DialogTitle>
            <DialogDescription>
              This will permanently delete &ldquo;{deletingConv?.title || "this session"}&rdquo; and all its verified citations. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeletingConv(null)}
              className="rounded-xl font-serif"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={isDeleting}
              className="rounded-xl font-serif"
            >
              {isDeleting ? "Deleting..." : "Delete session"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <EditPaperModal
        isOpen={!!editingPaper}
        paper={editingPaper}
        onClose={() => setEditingPaper(null)}
        onSubmit={onUpdatePaper}
      />
      <AddSourcesModal
        isOpen={Boolean(managingSourcesPaper)}
        onClose={() => setManagingSourcesPaper(null)}
        preselectedPaperId={managingSourcesPaper?.id || null}
        papers={papers}
      />

      <Dialog open={!!deletingPaper} onOpenChange={(open) => !open && setDeletingPaper(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete “{deletingPaper?.title}”?</DialogTitle>
            <DialogDescription>
              This permanently removes the project and its document records. When the search index is available, its vector and lexical entries are cleared first; then the database records are deleted and stored PDFs are removed after the database change succeeds. If index cleanup fails, the deletion stops. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {projectError && <p role="alert" className="text-sm text-red-700">{projectError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeletingPaper(null)}>Cancel</Button>
            <Button type="button" variant="destructive" disabled={isDeletingPaper} onClick={async () => {
              try {
                await onDeletePaper?.(deletingPaper.id);
                setDeletingPaper(null);
              } catch (error) {
                setProjectError(error?.message || "The project could not be deleted. Please try again.");
              }
            }}>{isDeletingPaper ? "Deleting…" : "Delete project"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

