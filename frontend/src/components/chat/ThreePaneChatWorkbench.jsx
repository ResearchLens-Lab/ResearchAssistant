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
  const { selectedPaperIds, selectedDocumentIds, selectPapers } = useChatScopeStore();
  const {
    sources,
    setSources,
    setResearchTrace,
    clearSources,
    isDrawerOpen,
    openDrawer,
    closeDrawer,
    setConversationMessages,
  } = useCitationStore();

  // Library papers for scope resolution
  const { papers, isLoading: isLoadingPapers, updatePaper, deletePaper, isDeleting: isDeletingPaper } = usePapers(1, 50);
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

  const scopeLine = useMemo(() => {
    const projectNames = (selectedPaperIds || [])
      .map((id) => papers.find((p) => p.id === id)?.title)
      .filter(Boolean);
    const projectNamesText = projectNames.length > 0 ? projectNames.join(", ") : "Selected projects";
    const docCount = selectedDocumentIds?.length;
    const docCountText = docCount ? `${docCount} document${docCount === 1 ? "" : "s"}` : "";
    return `Searched: ${projectNamesText}${docCountText ? ` · ${docCountText}` : ""}`;
  }, [selectedPaperIds, selectedDocumentIds, papers]);

  // Layout UI states
  const [leftTab, setLeftTab] = useState("history"); // "history" | "scope"
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true);
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(380);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const [mobilePanel, setMobilePanel] = useState(null); // null | "history" | "scope" | "evidence"
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [inlineTitle, setInlineTitle] = useState("");
  const [answerMode, setAnswerMode] = useState("EVIDENCE_FIRST");
  const [isOpeningFirstConversation, setIsOpeningFirstConversation] = useState(false);

  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const lastSyncedMsgIdRef = useRef(null);

  useEffect(() => {
    const savedWidth = Number(window.localStorage.getItem("research-desk-sidebar-width"));
    if (Number.isFinite(savedWidth) && savedWidth >= 360 && savedWidth <= 540) {
      setLeftSidebarWidth(savedWidth);
    } else {
      setLeftSidebarWidth(380);
    }
  }, []);

  useEffect(() => {
    const syncDesktopEvidenceLayout = () => setIsRightSidebarOpen(window.innerWidth >= 1100);
    syncDesktopEvidenceLayout();
    window.addEventListener("resize", syncDesktopEvidenceLayout);
    return () => window.removeEventListener("resize", syncDesktopEvidenceLayout);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("research-desk-sidebar-width", String(Math.max(360, Math.min(540, leftSidebarWidth))));
  }, [leftSidebarWidth]);

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
  const conversationSources = useMemo(() => {
    return aggregateConversationSources(messages);
  }, [messages]);
  const { latestAssistantMessageId, questionByAssistantId } = useMemo(() => {
    let latestQuestion = "";
    const questionById = new Map();
    let latestId = null;
    for (const message of messages) {
      if (message.role === "user") latestQuestion = message.content || "";
      else if (message.role === "assistant") {
        latestId = message.id;
        questionById.set(message.id, latestQuestion);
      }
    }
    return { latestAssistantMessageId: latestId, questionByAssistantId: questionById };
  }, [messages]);

  useEffect(() => {
    setConversationMessages(messages);
    if (!isLoadingMessages && messages.length > 0) {
      const lastAssistantMsg = [...messages]
        .reverse()
        .find((m) => m.role === "assistant");

      if (lastAssistantMsg) {
        // Link Evidence & Sources panel directly to active turn's citations
        setSources(Array.isArray(lastAssistantMsg.sources) ? lastAssistantMsg.sources : []);
        if (!lastAssistantMsg.pending && lastAssistantMsg.id !== lastSyncedMsgIdRef.current) {
          lastSyncedMsgIdRef.current = lastAssistantMsg.id;
          setResearchTrace(lastAssistantMsg.meta?.research || null);
        }
      }
    } else if (!isLoadingMessages && messages.length === 0) {
      setSources([]);
    }
  }, [messages, isLoadingMessages, setSources, setResearchTrace, setConversationMessages]);

  // Smart auto-scroll: smoothly scroll to bottom if user is near bottom or active message streaming
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom <= 200 || isSendingMessage) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isSendingMessage]);

  // Handlers
  const handleSendMessage = async (question) => {
    if (!conversationId) setIsOpeningFirstConversation(true);
    try {
      const res = await sendMessage({
        question,
        paper_ids: selectedPaperIds,
        document_ids: selectedDocumentIds && selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined,
        conversation_id: conversationId || null,
        answer_mode: answerMode,
      });

      if (!conversationId && res.conversation_id) {
        router.push(`/chat/${res.conversation_id}`);
      } else {
        setIsOpeningFirstConversation(false);
      }
      if (res.metadata?.research) setResearchTrace(res.metadata.research);
    } catch (error) {
      setIsOpeningFirstConversation(false);
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

  const handleDeletePaper = async (id) => {
    await deletePaper(id);
    if (selectedPaperIds.includes(id)) {
      selectPapers(selectedPaperIds.filter((paperId) => paperId !== id));
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
        if (d.processing_status === "indexed" || ((d.processing_status === "needs_review" || d.processing_status === "partial") && (d.chunk_count || 0) > 0)) {
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
      const sourceCount = (documentsByPaper[p.id] || []).filter((doc) => doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0)).length;
      return `${p.title} · ${sourceCount} source${sourceCount === 1 ? "" : "s"} · ${totalIndexedChunksInScope.toLocaleString()} ${totalIndexedChunksInScope === 1 ? "chunk" : "chunks"}`;
    }
    return `${selectedPaperIds.length} projects in scope (${totalIndexedChunksInScope.toLocaleString()} chunks)`;
  }, [
    isLoadingPapers,
    papers.length,
    selectableIds.length,
    selectedPaperIds.length,
    selectedPapersList,
    totalIndexedChunksInScope,
    documentsByPaper,
  ]);

  const activeProjectTitle = selectedPapersList.length === 1
    ? selectedPapersList[0].title
    : selectedPapersList.length > 1
      ? `${selectedPapersList[0].title} + ${selectedPapersList.length - 1} more`
      : "your research library";
  const indexedSourceCount = useMemo(
    () => selectedPaperIds.reduce((count, id) => count + (documentsByPaper[id] || []).filter((doc) => doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0)).length, 0),
    [selectedPaperIds, documentsByPaper]
  );

  const handleOpenScope = () => {
    setIsLeftSidebarOpen(true);
    setLeftTab("scope");
    if (window.innerWidth < 1024) setMobilePanel("scope");
    else setMobilePanel(null);
  };

  return (
    <div className="relative flex h-full min-h-0 w-full overflow-hidden bg-[var(--rl-canvas)]">
      {/* Pane 1: Desktop research navigation */}
      <div className={`relative hidden lg:flex h-full shrink-0 flex-col overflow-hidden border-r border-[var(--rl-border)] bg-white z-10 transition-[width] duration-200 ${isLeftSidebarOpen ? "min-w-0" : "w-16"}`} style={isLeftSidebarOpen ? { width: leftSidebarWidth } : undefined}>
        <div className="shrink-0 border-b border-slate-100 p-3 space-y-2">
          <Button
            type="button"
            onClick={handleNewResearch}
            className="h-9 w-full justify-center gap-2 rounded-xl bg-[var(--rl-primary)] text-sm font-semibold text-white shadow-sm hover:bg-[#185ea8]"
          >
            <Plus className="h-4 w-4" />
            {isLeftSidebarOpen && <span>New research</span>}
          </Button>

          {isLeftSidebarOpen && (
            <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium text-slate-600">
              <button
                type="button"
                onClick={() => setLeftTab("history")}
                className={`flex-1 py-1.5 px-2 rounded-md transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer ${leftTab === "history"
                    ? "bg-white text-slate-900 font-semibold shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                  }`}
              >
                <Clock className="h-3.5 w-3.5" />
                <span>Sessions</span>
              </button>
              <button
                type="button"
                onClick={() => setLeftTab("scope")}
                className={`flex-1 py-1.5 px-2 rounded-md transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer ${leftTab === "scope"
                    ? "bg-white text-slate-900 font-semibold shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                  }`}
              >
                <Layers className="h-3.5 w-3.5" />
                <span>Sources {selectedDocumentIds.length > 0 ? `(${selectedDocumentIds.length})` : (selectableIds.length > 0 ? `(${selectableIds.length})` : "")}</span>
              </button>
            </div>
          )}
        </div>
        {/* Tab Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {!isLeftSidebarOpen ? (
            <div className="flex flex-col items-center gap-2 p-2">
              <button type="button" onClick={() => { setIsLeftSidebarOpen(true); setLeftTab("history"); }} title="Recent sessions" aria-label="Recent sessions" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"><Clock className="h-4 w-4" /></button>
              <button type="button" onClick={() => { setIsLeftSidebarOpen(true); setLeftTab("scope"); }} title="Projects and sources" aria-label="Projects and sources" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"><Layers className="h-4 w-4" /></button>
            </div>
          ) : leftTab === "history" ? (
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
              papers={papers}
              documentsByPaper={documentsByPaper}
              selectedPaperIds={selectedPaperIds}
              onSelectPaper={(id) => selectPapers([id])}
              onUpdatePaper={updatePaper}
              onDeletePaper={handleDeletePaper}
              isDeletingPaper={isDeletingPaper}
            />
          ) : (
            <PaperScopeRail className="w-full min-w-0 border-r-0" onClose={() => setLeftTab("history")} />
          )}
        </div>
        <div
          hidden={!isLeftSidebarOpen}
          role="separator"
          aria-label="Resize research sidebar"
          aria-orientation="vertical"
          aria-valuemin={360}
          aria-valuemax={540}
          aria-valuenow={leftSidebarWidth}
          tabIndex={0}
          onPointerDown={(event) => event.currentTarget.setPointerCapture(event.pointerId)}
          onPointerMove={(event) => {
            if (event.buttons !== 1) return;
            const bounds = event.currentTarget.parentElement.getBoundingClientRect();
            setLeftSidebarWidth(Math.max(360, Math.min(540, event.clientX - bounds.left)));
          }}
          onKeyDown={(event) => {
            const direction = event.key === "ArrowRight" ? 16 : event.key === "ArrowLeft" ? -16 : 0;
            if (!direction) return;
            event.preventDefault();
            setLeftSidebarWidth((width) => Math.max(360, Math.min(540, width + direction)));
          }}
          className="absolute right-0 top-0 z-20 h-full w-1.5 cursor-col-resize touch-none border-r border-transparent transition-colors hover:border-sky-400 hover:bg-sky-100/60 focus-visible:bg-sky-100"
        />
      </div>

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
              <span title={conversation?.title || "Research Desk"} className="truncate text-sm font-semibold text-[var(--rl-ink)]">
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
              onClick={handleOpenScope}
              title="Click to configure source scope"
              className={`hidden sm:inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs truncate max-w-xs transition-colors ${selectedPaperIds.length > 0
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
                <Link
                  href={`/graph?conversation_id=${conversationId}`}
                  title="See how your questions and cited sources connect"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Research map</span>
                </Link>
              </Button>
            )}

          </div>
        </div>

        {/* Mobile / Tablet Quick Navigation Bar */}
        <div className="flex lg:hidden items-center gap-1.5 border-b border-[var(--rl-border)] bg-[var(--rl-tint)] px-3 py-2 overflow-x-auto shrink-0">
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={handleNewResearch}
            className="h-7 gap-1 border-0 bg-[var(--rl-primary)] text-xs text-white hover:bg-[#185ea8] shrink-0"
          >
            <Plus className="h-3 w-3" />
            <span>New</span>
          </Button>

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
        <div ref={chatContainerRef} className="flex-1 min-h-0 overflow-y-auto bg-[var(--rl-canvas)]">
          {isLoadingMessages || (isOpeningFirstConversation && messages.length === 0) ? (
            <div className="space-y-4 p-6" aria-label="Loading research messages">
              <div className="h-12 w-3/4 rounded-lg bg-slate-100 animate-pulse" />
              <div className="h-28 w-full rounded-lg bg-slate-100 animate-pulse" />
              <div className="h-12 w-2/3 rounded-lg bg-slate-100 animate-pulse" />
            </div>
          ) : messages.length === 0 && !sendError && !isSendingMessage ? (
            /* Welcome / New Research Workspace Hero */
            <div className="min-h-full flex flex-col justify-center items-center px-5 text-center pb-8">
              <div className="w-full max-w-2xl space-y-3">
                <h3 className="max-w-full truncate text-lg sm:text-2xl font-semibold tracking-tight text-slate-900" title={`What would you like to research in ${activeProjectTitle}?`}>
                  What would you like to research in <span className="text-[var(--rl-primary)]">{activeProjectTitle}</span>?
                </h3>
                <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-slate-500">
                  <span>{selectedPaperIds.length ? `${selectedPaperIds.length} project${selectedPaperIds.length === 1 ? "" : "s"}` : "No project selected"}</span>
                  <span aria-hidden="true">·</span>
                  <span>{indexedSourceCount} indexed source{indexedSourceCount === 1 ? "" : "s"}</span>
                  <span aria-hidden="true">·</span>
                  <span>{totalIndexedChunksInScope.toLocaleString()} searchable chunks</span>
                  <button type="button" onClick={handleOpenScope} className="ml-1 font-medium text-[var(--rl-primary)] hover:underline">Change scope</button>
                </div>
                <p className="text-xs text-slate-400">Ask a question about your sources. Answers include evidence and citations.</p>
              </div>
            </div>
          ) : (
            /* Rendered Messages Stream */
            <div className="pb-8">
              {messages.map((msg) =>
                msg.pending ? (
                  <div key={msg.id}>
                    {msg.content ? (
                      <MessageItem
                        message={msg}
                        autoSelectFirstCitation={msg.id === latestAssistantMessageId}
                        researchQuestion={questionByAssistantId.get(msg.id) || ""}
                        scopeLine={scopeLine}
                        onFollowUp={(query) => handleSendMessage(query).catch(() => { })}
                      />
                    ) : null}
                    <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 pb-3 text-slate-600">
                      <Sparkles className="h-4 w-4 animate-spin text-[var(--rl-primary)]" />
                      <p className="text-xs text-zinc-600">
                        {msg.progress || "Searching selected sources…"}
                      </p>
                    </div>
                  </div>
                ) : (
                  <MessageItem
                    key={msg.id}
                    message={msg}
                    autoSelectFirstCitation={msg.id === latestAssistantMessageId}
                    researchQuestion={questionByAssistantId.get(msg.id) || ""}
                    scopeLine={scopeLine}
                    onFollowUp={(query) => handleSendMessage(query).catch(() => { })}
                  />
                )
              )}

              {sendError && (
                <div className="mx-auto my-3 flex max-w-3xl items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
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
          answerMode={answerMode}
          onAnswerModeChange={setAnswerMode}
          activeProjectName={activeProjectTitle}
        />
      </div>

      {/* Pane 3: Desktop Right Evidence & Source Inspector Rail */}
      <div className="hidden min-[1100px]:flex h-full w-[min(22.5rem,24vw)] min-w-[330px] max-w-[360px] shrink-0 border-l border-[var(--rl-border)] bg-white">
        <SourceInspectorRail className="w-full border-l-0" />
      </div>

      {isDrawerOpen && (
        <div className="fixed inset-y-16 right-0 z-40 hidden w-full justify-end bg-slate-950/25 min-[1024px]:flex min-[1100px]:hidden">
          <div className="h-full w-[min(23rem,90vw)] border-l border-[var(--rl-border)] bg-white shadow-xl">
            <SourceInspectorRail />
          </div>
        </div>
      )}

      {/* Mobile / Tablet Drawers */}
      {(mobilePanel || (isDrawerOpen && !isRightSidebarOpen)) && (
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
          className="fixed inset-x-0 bottom-0 top-16 z-40 flex bg-slate-950/35 min-[1024px]:hidden"
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
                : "h-full w-[min(28rem,94vw)] max-w-[28rem] shadow-xl min-w-0"
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
              className="bg-[var(--rl-primary)] text-white hover:bg-[#185ea8]"
            >
              Save title
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
