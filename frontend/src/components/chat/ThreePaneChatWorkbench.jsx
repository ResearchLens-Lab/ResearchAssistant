"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useChat } from "@/hooks/useChat";
import { usePapers } from "@/hooks/usePapers";
import { papersService } from "@/services/papers.service";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { useCitationStore } from "@/store/citationStore";
import { ResearchHistorySidebar } from "./ResearchHistorySidebar";
import { PaperScopeRail } from "./PaperScopeRail";
import { MessageItem } from "./MessageItem";
import { ChatInputBar } from "./ChatInputBar";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sparkles,
  Plus,
  AlertCircle,
  Download,
  GitCompare,
  PanelLeft,
  PanelRight,
  Clock,
  Layers,
  Pencil,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ArrowRight,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  buildResearchBrief,
  aggregateConversationSources,
  indexedPaperIds,
} from "@/lib/researchWorkspace.mjs";
import Link from "next/link";

/** @param {{ conversationId?: string | null }} props */
export function ThreePaneChatWorkbench({ conversationId = null }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryPaperId = searchParams?.get("paper_id");

  // Chat hook
  const {
    conversations,
    isLoadingConversations,
    conversation,
    messages,
    isLoadingMessages,
    sendMessage,
    isSendingMessage,
    sendError,
    cancelMessage,
    updateConversation,
    isUpdatingConversation,
    deleteConversation,
    isDeletingConversation,
  } = useChat(conversationId);

  // Source scope & citations
  const { selectedPaperIds, selectPapers } = useChatScopeStore();
  const {
    sources,
    setSources,
    setResearchTrace,
    clearSources,
    isDrawerOpen,
    openDrawer,
    closeDrawer,
  } = useCitationStore();

  // Library papers for scope resolution
  const { papers, isLoading: isLoadingPapers } = usePapers(1, 50);
  const paperIds = useMemo(() => papers.map((p) => p.id), [papers]);
  const documentsQuery = useQuery({
    queryKey: ["paperDocumentsByPapers", paperIds],
    queryFn: () => papersService.getDocumentsByPapers(paperIds),
    enabled: paperIds.length > 0,
    staleTime: 10_000,
  });
  const documentsByPaper = documentsQuery.data || {};
  const entries = useMemo(
    () =>
      papers.map((paper) => ({
        paper,
        documents: documentsByPaper[paper.id] || [],
      })),
    [papers, documentsByPaper]
  );
  const selectableIds = useMemo(() => indexedPaperIds(entries), [entries]);

  // Layout UI states
  const [leftTab, setLeftTab] = useState("history"); // "history" | "scope"
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const [mobilePanel, setMobilePanel] = useState(null); // null | "history" | "scope" | "evidence"
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [inlineTitle, setInlineTitle] = useState("");

  const messagesEndRef = useRef(null);
  const lastSyncedMsgIdRef = useRef(null);

  // 1. Sync query param paper_id if present
  useEffect(() => {
    if (queryPaperId && !selectedPaperIds.includes(queryPaperId)) {
      selectPapers([queryPaperId]);
    }
  }, [queryPaperId, selectedPaperIds, selectPapers]);

  // 2. Sync conversation paper_ids when reopening an existing conversation
  const convPaperIds = conversation?.paper_ids;
  useEffect(() => {
    if (convPaperIds && convPaperIds.length > 0) {
      selectPapers(convPaperIds);
    }
  }, [convPaperIds, selectPapers]);

  // 3. Default to all available indexed papers when starting a fresh research desk inquiry
  useEffect(() => {
    if (
      !conversationId &&
      !queryPaperId &&
      selectedPaperIds.length === 0 &&
      selectableIds.length > 0
    ) {
      selectPapers(selectableIds);
    }
  }, [
    conversationId,
    queryPaperId,
    selectedPaperIds.length,
    selectableIds,
    selectPapers,
  ]);

  // 4. Reset drawer and synchronization refs when conversation changes
  useEffect(() => {
    lastSyncedMsgIdRef.current = null;
    clearSources();
    closeDrawer();
    setMobilePanel(null);
  }, [conversationId, clearSources, closeDrawer]);

  // 5. Aggregate all conversation sources across assistant turns
  useEffect(() => {
    if (!isLoadingMessages && messages.length > 0) {
      const lastAssistantMsg = [...messages]
        .reverse()
        .find((m) => m.role === "assistant" && !m.pending);

      if (lastAssistantMsg && lastAssistantMsg.id !== lastSyncedMsgIdRef.current) {
        lastSyncedMsgIdRef.current = lastAssistantMsg.id;
        const allAggregated = aggregateConversationSources(messages);
        setSources(
          allAggregated.length > 0 ? allAggregated : lastAssistantMsg.sources || []
        );
        setResearchTrace(lastAssistantMsg.meta?.research || null);
      }
    }
  }, [messages, isLoadingMessages, setSources, setResearchTrace]);

  // Auto-scroll to bottom of chat on new message or streaming token
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSendingMessage]);

  // Handlers
  const handleSendMessage = async (question) => {
    try {
      const res = await sendMessage({
        question,
        paper_ids: selectedPaperIds,
        conversation_id: conversationId || null,
      });

      if (!conversationId && res.conversation_id) {
        router.push(`/chat/${res.conversation_id}`);
      }
      if (res.metadata?.research) setResearchTrace(res.metadata.research);
    } catch (error) {
      throw error;
    }
  };

  const handleSelectConversation = (id) => {
    if (id !== conversationId) {
      router.push(`/chat/${id}`);
      setMobilePanel(null);
    }
  };

  const handleNewResearch = () => {
    router.push("/chat");
    setMobilePanel(null);
  };

  const handleRenameSession = async (id, title) => {
    await updateConversation({ id, title });
  };

  const handleDeleteSession = async (id) => {
    await deleteConversation(id);
    if (conversationId === id) {
      router.push("/chat");
    }
  };

  const handleOpenInlineRename = () => {
    setInlineTitle(conversation?.title || "");
    setRenameDialogOpen(true);
  };

  const handleSaveInlineRename = async () => {
    if (!conversationId || !inlineTitle.trim()) return;
    await updateConversation({ id: conversationId, title: inlineTitle.trim() });
    setRenameDialogOpen(false);
  };

  const handleExportBrief = () => {
    const groundedMessages = messages.filter(
      (message) =>
        !message.pending && message.role === "assistant" && message.sources?.length
    );
    const markdown = buildResearchBrief(
      groundedMessages,
      conversation?.title || "Research brief"
    );
    const url = URL.createObjectURL(
      new Blob([markdown], { type: "text/markdown;charset=utf-8" })
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(conversation?.title || "research-brief")
      .trim()
      .replace(/[^a-z0-9-]+/gi, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase() || "research-brief"}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Scope summary text
  const selectedPapersList = useMemo(() => {
    return papers.filter((p) => selectedPaperIds.includes(p.id));
  }, [papers, selectedPaperIds]);

  const totalIndexedChunksInScope = useMemo(() => {
    let count = 0;
    for (const paperId of selectedPaperIds) {
      const docs = documentsByPaper[paperId] || [];
      for (const d of docs) {
        if (d.processing_status === "indexed") {
          count += d.chunk_count || 0;
        }
      }
    }
    return count;
  }, [selectedPaperIds, documentsByPaper]);

  const scopeLabel = useMemo(() => {
    if (isLoadingPapers) return "Checking source library…";
    if (papers.length === 0) return "No projects in library";
    if (selectableIds.length === 0) return "No indexed sources available";
    if (selectedPaperIds.length === 0) return "0 projects selected (select below)";
    if (selectedPaperIds.length === 1 && selectedPapersList[0]) {
      const p = selectedPapersList[0];
      return `${p.title} (${totalIndexedChunksInScope.toLocaleString()} chunks in scope)`;
    }
    return `${selectedPaperIds.length} projects in scope (${totalIndexedChunksInScope.toLocaleString()} chunks)`;
  }, [
    isLoadingPapers,
    papers.length,
    selectableIds.length,
    selectedPaperIds.length,
    selectedPapersList,
    totalIndexedChunksInScope,
  ]);

  return (
    <div className="relative flex h-full min-h-0 w-full overflow-hidden bg-[var(--rl-canvas)]">
      {/* Pane 1: Desktop Left Persistent Sidebar (History & Scope tabs) */}
      {isLeftSidebarOpen && (
        <div className="hidden lg:flex h-full w-84 xl:w-88 min-w-0 shrink-0 flex-col border-r border-[var(--rl-border)] bg-white z-10 shadow-xs">
          {/* Top Switcher Tabs */}
          <div className="flex border-b border-slate-200 bg-slate-50/80 p-2 gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => setLeftTab("history")}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md text-xs font-semibold transition-all ${
                leftTab === "history"
                  ? "bg-white text-[var(--rl-primary)] shadow-2xs border border-slate-200"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              <Clock className="h-3.5 w-3.5" />
              <span>Sessions</span>
              {conversations.length > 0 && (
                <span className="rounded-full bg-slate-100 px-1.5 py-0.2 text-[10px] text-slate-600">
                  {conversations.length}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setLeftTab("scope")}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md text-xs font-semibold transition-all ${
                leftTab === "scope"
                  ? "bg-white text-[var(--rl-primary)] shadow-2xs border border-slate-200"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>Source Scope</span>
              <span
                className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                  selectedPaperIds.length > 0
                    ? "bg-emerald-100 text-emerald-800 font-bold"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {selectedPaperIds.length}
              </span>
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {leftTab === "history" ? (
              <ResearchHistorySidebar
                conversations={conversations}
                isLoading={isLoadingConversations}
                activeId={conversationId}
                onSelectConversation={handleSelectConversation}
                onNewResearch={handleNewResearch}
                onRenameConversation={handleRenameSession}
                onDeleteConversation={handleDeleteSession}
                isDeleting={isDeletingConversation}
                isUpdating={isUpdatingConversation}
                className="w-full min-w-0 border-r-0"
              />
            ) : (
              <PaperScopeRail className="w-full min-w-0 border-r-0" />
            )}
          </div>
        </div>
      )}

      {/* Pane 2: Center Thread Canvas */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Thread Header Bar */}
        <div className="flex min-h-14 items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 sm:px-4 shrink-0">
          <div className="flex items-center gap-2 overflow-hidden min-w-0">
            {/* Desktop Left Sidebar Toggle */}
            <button
              type="button"
              onClick={() => setIsLeftSidebarOpen((prev) => !prev)}
              aria-label={isLeftSidebarOpen ? "Collapse history sidebar" : "Expand history sidebar"}
              title={isLeftSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              className="hidden lg:inline-flex rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
            >
              <PanelLeft className="h-4 w-4" />
            </button>

            {/* Conversation Title & Inline Rename */}
            <div className="flex items-center gap-1.5 truncate">
              <span className="truncate text-sm font-semibold text-[var(--rl-ink)]">
                {conversation?.title || (conversationId ? "Research Session" : "Research Desk")}
              </span>
              {conversationId && (
                <button
                  type="button"
                  title="Rename research session"
                  onClick={handleOpenInlineRename}
                  className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                >
                  <Pencil className="h-3 w-3" />
                </button>
              )}
            </div>

            {/* Active Scope Pill Button */}
            <button
              type="button"
              onClick={() => {
                setIsLeftSidebarOpen(true);
                setLeftTab("scope");
                setMobilePanel("scope");
              }}
              title="Click to configure source scope"
              className={`hidden sm:inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs truncate max-w-xs transition-colors ${
                selectedPaperIds.length > 0
                  ? "border-emerald-200 bg-emerald-50/70 text-emerald-800 hover:bg-emerald-100"
                  : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
              }`}
            >
              <Layers className="h-3 w-3 shrink-0" />
              <span className="truncate">{scopeLabel}</span>
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-1.5 shrink-0">
            {conversationId && (
              <Button
                variant="soft"
                size="sm"
                asChild
                className="hidden md:inline-flex h-8 gap-1.5 text-xs"
              >
                <Link href={`/graph?conversation_id=${conversationId}`}>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Map</span>
                </Link>
              </Button>
            )}

            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleNewResearch}
              className="h-8 text-xs gap-1.5 bg-[var(--rl-primary)] text-white hover:bg-[#1f659c]"
            >
              <Plus className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New Research</span>
              <span className="sm:hidden">New</span>
            </Button>

            {/* Desktop Evidence Inspector Toggle */}
            <button
              type="button"
              onClick={() => setIsRightSidebarOpen((prev) => !prev)}
              aria-label={isRightSidebarOpen ? "Collapse evidence trail" : "Expand evidence trail"}
              title={isRightSidebarOpen ? "Collapse evidence trail" : "Expand evidence trail"}
              className={`hidden lg:inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs border transition-colors ${
                isRightSidebarOpen || sources.length > 0
                  ? "border-slate-300 bg-slate-50 text-[var(--rl-ink)]"
                  : "border-slate-200 text-slate-500 hover:bg-slate-50"
              }`}
            >
              <PanelRight className="h-3.5 w-3.5" />
              <span>Evidence ({sources.length})</span>
            </button>
          </div>
        </div>

        {/* Mobile / Tablet Quick Navigation Bar */}
        <div className="flex lg:hidden items-center gap-1.5 border-b border-[var(--rl-border)] bg-[var(--rl-tint)] px-3 py-2 overflow-x-auto shrink-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setMobilePanel("history")}
            className="h-7 gap-1 border-slate-300 bg-white text-xs shrink-0"
          >
            <Clock className="h-3 w-3" />
            <span>History ({conversations.length})</span>
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setMobilePanel("scope")}
            className="h-7 gap-1 border-slate-300 bg-white text-xs shrink-0"
          >
            <Layers className="h-3 w-3" />
            <span>Scope ({selectedPaperIds.length})</span>
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!sources.length}
            onClick={() => setMobilePanel("evidence")}
            className="h-7 gap-1 border-slate-300 bg-white text-xs shrink-0"
          >
            <PanelRight className="h-3 w-3" />
            <span>Evidence ({sources.length})</span>
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleExportBrief}
            disabled={
              !messages.some(
                (message) =>
                  message.role === "assistant" &&
                  !message.pending &&
                  message.sources?.length
              )
            }
            className="ml-auto h-7 gap-1 border-slate-300 bg-white text-xs shrink-0"
          >
            <Download className="h-3 w-3" />
            <span className="hidden sm:inline">Export brief</span>
          </Button>

          {selectedPaperIds.length >= 2 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                router.push(
                  `/compare?paper_ids=${encodeURIComponent(
                    selectedPaperIds.join(",")
                  )}`
                )
              }
              className="h-7 gap-1 border-slate-300 bg-white text-xs shrink-0"
            >
              <GitCompare className="h-3 w-3" />
              <span>Compare</span>
            </Button>
          )}
        </div>

        {/* Messages Stream */}
        <div className="flex-1 min-h-0 overflow-y-auto bg-[var(--rl-canvas)]">
          {isLoadingMessages ? (
            <div className="space-y-4 p-6" aria-label="Loading research messages">
              <div className="h-12 w-3/4 rounded-lg bg-slate-100 animate-pulse" />
              <div className="h-28 w-full rounded-lg bg-slate-100 animate-pulse" />
              <div className="h-12 w-2/3 rounded-lg bg-slate-100 animate-pulse" />
            </div>
          ) : messages.length === 0 && !sendError ? (
            /* Welcome / New Research Workspace Hero */
            <div className="min-h-full flex flex-col justify-center py-6 px-4 sm:px-6 pb-12 text-center text-slate-500 space-y-4 max-w-xl mx-auto">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--rl-selected)] text-[var(--rl-primary)] shadow-2xs">
                <Sparkles className="h-7 w-7 text-[var(--rl-primary)]" />
              </div>

              <div className="space-y-1.5">
                <h3 className="text-lg font-semibold text-slate-900 tracking-tight">
                  Evidence-First Research Desk
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed max-w-md mx-auto">
                  Ask targeted research inquiries across your indexed documents. Every answer is grounded in retrieved passages with verified citations and exact page numbers.
                </p>
              </div>

              {/* Active Scope Card */}
              <div className="w-full rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs text-left space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-[var(--rl-primary)]" />
                    Active Source Scope
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setIsLeftSidebarOpen(true);
                      setLeftTab("scope");
                      setMobilePanel("scope");
                    }}
                    className="text-[11px] text-[var(--rl-primary)] hover:underline flex items-center gap-0.5"
                  >
                    Change sources <ChevronRight className="h-3 w-3" />
                  </button>
                </div>

                {selectedPaperIds.length > 0 ? (
                  <div className="space-y-1 text-xs">
                    {selectedPapersList.map((p) => (
                      <div
                        key={p.id}
                        className="flex items-center justify-between py-1 px-2 rounded bg-slate-50 text-slate-700 font-medium"
                      >
                        <span className="truncate">{p.title}</span>
                        <span className="text-[10px] text-emerald-700 shrink-0 ml-2 font-mono flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          Ready
                        </span>
                      </div>
                    ))}
                    <p className="text-[10px] text-slate-400 pt-0.5">
                      {totalIndexedChunksInScope.toLocaleString()} indexed chunks available for vector retrieval.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-800 border border-amber-200 flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                    <div>
                      <p className="font-semibold">No research sources selected</p>
                      <p className="text-[11px] text-amber-700 mt-0.5">
                        Select one or more indexed projects from the Scope tab or upload files in the Research Library.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Starter Question Prompts */}
              <div className="space-y-1.5 w-full pt-1">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  Starter research prompts
                </span>
                <div className="flex flex-col gap-1.5">
                  {[
                    "What main contribution do the indexed passages describe, and what evidence supports it?",
                    "Compare the methods and experimental conditions described in the selected sources.",
                    "Extract the reported algorithms, datasets, metrics, and limitations with cited locators.",
                  ].map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleSendMessage(prompt).catch(() => {})}
                      disabled={selectedPaperIds.length === 0}
                      className="group flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-700 hover:border-slate-300 hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50"
                    >
                      <span className="truncate">&ldquo;{prompt}&rdquo;</span>
                      <ArrowRight className="h-3 w-3 text-slate-400 group-hover:text-slate-700 shrink-0 ml-2" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Rendered Messages Stream */
            <div className="divide-y divide-zinc-100 pb-8 dark:divide-zinc-900">
              {messages.map((msg) =>
                msg.pending ? (
                  <div key={msg.id}>
                    {msg.content ? <MessageItem message={msg} /> : null}
                    <div className="flex items-center gap-3 px-4 pb-3 bg-zinc-50/50">
                      <Sparkles className="h-4 w-4 animate-spin text-[var(--rl-primary)]" />
                      <p className="text-xs text-zinc-600">
                        {msg.progress || "Searching selected sources…"}
                      </p>
                    </div>
                  </div>
                ) : (
                  <MessageItem key={msg.id} message={msg} />
                )
              )}

              {sendError && (
                <div className="m-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>
                    {sendError?.message ||
                      "Failed to retrieve grounded answer. Please try again."}
                  </span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Composer Bar */}
        <ChatInputBar
          onSendMessage={handleSendMessage}
          onCancel={cancelMessage}
          isLoading={isSendingMessage}
        />
      </div>

      {/* Pane 3: Desktop Right Evidence & Source Inspector Rail */}
      {isRightSidebarOpen && (
        <div className="hidden lg:flex h-full w-96 shrink-0 border-l border-[var(--rl-border)] bg-white shadow-xs">
          <SourceInspectorRail
            className="w-full border-l-0"
            onClose={() => setIsRightSidebarOpen(false)}
          />
        </div>
      )}

      {/* Mobile / Tablet Drawers */}
      {(mobilePanel || isDrawerOpen) && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={
            mobilePanel === "history"
              ? "Research history"
              : mobilePanel === "scope"
              ? "Research sources"
              : "Evidence Trail"
          }
          className="fixed inset-x-0 bottom-0 top-16 z-40 flex bg-slate-950/35"
          onClick={() => {
            setMobilePanel(null);
            closeDrawer();
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setMobilePanel(null);
              closeDrawer();
            }
          }}
        >
          <div
            className={
              mobilePanel === "evidence" || isDrawerOpen
                ? "ml-auto h-full w-[min(26rem,94vw)] shadow-xl min-w-0"
                : "h-full w-[min(24rem,92vw)] shadow-xl min-w-0"
            }
            onClick={(event) => event.stopPropagation()}
          >
            {mobilePanel === "history" ? (
              <ResearchHistorySidebar
                conversations={conversations}
                isLoading={isLoadingConversations}
                activeId={conversationId}
                onSelectConversation={handleSelectConversation}
                onNewResearch={handleNewResearch}
                onRenameConversation={handleRenameSession}
                onDeleteConversation={handleDeleteSession}
                isDeleting={isDeletingConversation}
                isUpdating={isUpdatingConversation}
                onClose={() => setMobilePanel(null)}
              />
            ) : mobilePanel === "scope" ? (
              <PaperScopeRail onClose={() => setMobilePanel(null)} />
            ) : (
              <SourceInspectorRail
                onClose={() => {
                  setMobilePanel(null);
                  closeDrawer();
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* Inline Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rename Research Session</DialogTitle>
            <DialogDescription>
              Update the title for this active research conversation.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Input
              value={inlineTitle}
              onChange={(e) => setInlineTitle(e.target.value)}
              placeholder="e.g. Algorithms Complexity Analysis"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleSaveInlineRename();
                }
              }}
            />
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRenameDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleSaveInlineRename}
              disabled={isUpdatingConversation || !inlineTitle.trim()}
              className="bg-[var(--rl-primary)] text-white hover:bg-[#1f659c]"
            >
              Save title
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
