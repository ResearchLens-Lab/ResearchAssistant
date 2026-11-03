"use client";

import React, { useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { useCitationStore } from "@/store/citationStore";
import { PaperScopeRail } from "./PaperScopeRail";
import { MessageItem } from "./MessageItem";
import { ChatInputBar } from "./ChatInputBar";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { Sparkles, Plus, AlertCircle, Download, GitCompare, PanelLeft, PanelRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { buildResearchBrief } from "@/lib/researchWorkspace.mjs";
import Link from "next/link";

/** @param {{ conversationId?: string | null }} props */
export function ThreePaneChatWorkbench({ conversationId = null }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryPaperId = searchParams?.get("paper_id");

  const {
    messages,
    isLoadingMessages,
    sendMessage,
    isSendingMessage,
    sendError,
    conversation,
    cancelMessage,
  } = useChat(conversationId);

  const { selectedPaperIds, selectPapers } = useChatScopeStore();
  const { sources, setSources, setResearchTrace, clearSources, isDrawerOpen, closeDrawer } = useCitationStore();
  const messagesEndRef = useRef(null);
  const [mobilePanel, setMobilePanel] = useState(null);
  const lastSyncedMsgIdRef = useRef(null);

  // Sync query param paper_id if present
  useEffect(() => {
    if (queryPaperId && !selectedPaperIds.includes(queryPaperId)) {
      selectPapers([queryPaperId]);
    }
  }, [queryPaperId, selectedPaperIds, selectPapers]);

  // Sync conversation paper_ids if available
  const convPaperIds = conversation?.paper_ids;
  useEffect(() => {
    if (convPaperIds && convPaperIds.length > 0) {
      selectPapers(convPaperIds);
    }
  }, [convPaperIds, selectPapers]);

  useEffect(() => {
    lastSyncedMsgIdRef.current = null;
    clearSources();
    closeDrawer();
    setMobilePanel(null);
  }, [conversationId, clearSources, closeDrawer]);

  // Load existing assistant sources into citation store on load
  useEffect(() => {
    if (!isLoadingMessages && messages.length > 0) {
      const lastAssistantMsg = [...messages].reverse().find((m) => m.role === "assistant" && !m.pending);
      if (lastAssistantMsg && lastAssistantMsg.id !== lastSyncedMsgIdRef.current) {
        lastSyncedMsgIdRef.current = lastAssistantMsg.id;
        setSources(lastAssistantMsg.sources || []);
        setResearchTrace(lastAssistantMsg.meta?.research || null);
      }
    }
  }, [messages, isLoadingMessages, setSources, setResearchTrace]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSendingMessage]);

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

  const handleNewThread = () => {
    router.push("/chat");
  };

  const handleExportBrief = () => {
    const groundedMessages = messages.filter((message) => !message.pending && message.role === "assistant" && message.sources?.length);
    const markdown = buildResearchBrief(groundedMessages, conversation?.title || "Research brief");
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(conversation?.title || "research-brief").trim().replace(/[^a-z0-9-]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "research-brief"}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="relative flex h-[calc(100dvh-4rem)] w-full overflow-hidden bg-[var(--rl-canvas)]">
      {/* Pane 2: Center Thread Canvas */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Thread Header Bar */}
        <div className="flex min-h-14 items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 sm:px-4 shrink-0">
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="truncate text-sm font-semibold text-[var(--rl-ink)] max-w-[240px] sm:max-w-[480px]">
              {conversation?.title || "Research Desk"}
            </span>
            <span className="hidden sm:inline text-xs text-[var(--rl-muted)]">
              {selectedPaperIds.length} project{selectedPaperIds.length === 1 ? "" : "s"} in scope
            </span>
          </div>

          <div className="flex items-center gap-2">
            {conversationId && <Button variant="soft" size="sm" asChild className="hidden sm:inline-flex h-9 gap-1.5 text-xs"><Link href={`/graph?conversation_id=${conversationId}`}><Sparkles className="h-3.5 w-3.5" />Research Map</Link></Button>}
            <Button
              variant="tertiary"
              size="sm"
              onClick={handleNewThread}
              className="h-7 text-xs gap-1.5"
            >
              <Plus className="h-3 w-3" />
              <span>New Thread</span>
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2 border-b border-[var(--rl-border)] bg-[var(--rl-tint)] px-3 py-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setMobilePanel("sources")} className="h-8 gap-1.5 border-slate-300 bg-white text-xs"><PanelLeft className="h-3.5 w-3.5" />Sources · {selectedPaperIds.length}</Button>
          <Button type="button" variant="outline" size="sm" disabled={!sources.length} title={!sources.length ? "Ask a question to generate evidence before opening the Evidence Trail" : undefined} onClick={() => setMobilePanel("evidence")} className="h-8 gap-1.5 border-slate-300 bg-white text-xs"><PanelRight className="h-3.5 w-3.5" />Evidence</Button>
          <Button type="button" variant="outline" size="sm" onClick={handleExportBrief} disabled={!messages.some((message) => message.role === "assistant" && !message.pending && message.sources?.length)} title="Export a brief after a response includes source citations" className="ml-auto h-8 gap-1.5 border-slate-300 bg-white text-xs"><Download className="h-3.5 w-3.5" />Export brief</Button>
          {selectedPaperIds.length >= 2 && <Button type="button" variant="outline" size="sm" onClick={() => router.push(`/compare?paper_ids=${encodeURIComponent(selectedPaperIds.join(","))}`)} className="h-8 gap-1.5 border-slate-300 bg-white text-xs"><GitCompare className="h-3.5 w-3.5" />Compare</Button>}
        </div>

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto bg-[var(--rl-canvas)]">
          {isLoadingMessages ? (
            <div className="space-y-4 p-6">
              <div className="h-12 w-3/4 rounded-lg bg-zinc-100 animate-pulse" />
              <div className="h-28 w-full rounded-lg bg-zinc-100 animate-pulse" />
            </div>
          ) : messages.length === 0 && !sendError ? (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-400 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 shadow-2xs">
                <Sparkles className="h-6 w-6 text-[var(--rl-primary)]" />
              </div>
              <div className="space-y-1 max-w-sm">
                <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                  Evidence-first research
                </h4>
                <p className="text-xs text-zinc-500 leading-relaxed">
                  Select indexed sources and ask a focused question. Inspect the supporting passages and any verification limits alongside each answer.
                </p>
              </div>

              {/* Starter Prompt Badges */}
              <div className="mt-4 flex flex-wrap justify-center gap-1.5 max-w-md">
                {[
                  "What contribution do the indexed passages describe, and what evidence supports it?",
                  "Compare the methods and experimental conditions in the selected sources.",
                  "Extract the methods, datasets, metrics, and reported limitations in a cited table.",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSendMessage(prompt).catch(() => {})}
                    disabled={selectedPaperIds.length === 0}
                    className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-left text-xs text-zinc-700 hover:border-zinc-300 hover:bg-white transition-colors dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 disabled:opacity-50"
                  >
                    &ldquo;{prompt}&rdquo;
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {messages.map((msg) => msg.pending ? (
                <div key={msg.id}>
                  {msg.content ? <MessageItem message={msg} /> : null}
                  <div className="flex items-center gap-3 px-4 pb-3 bg-zinc-50/50">
                    <Sparkles className="h-4 w-4 animate-spin text-[var(--rl-primary)]" />
                    <p className="text-xs text-zinc-600">{msg.progress || "Searching selected sources…"}</p>
                  </div>
                </div>
              ) : (
                <MessageItem key={msg.id} message={msg} />
              ))}

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

        {/* Input Bar */}
        <ChatInputBar
          onSendMessage={handleSendMessage}
          onCancel={cancelMessage}
          isLoading={isSendingMessage}
        />
      </div>

      {/* Pane 3: Right Live Evidence & Source Inspector Rail */}
      {(mobilePanel || isDrawerOpen) && <div role="dialog" aria-modal="true" aria-label={mobilePanel === "sources" ? "Research sources" : "Evidence Trail"} className="fixed inset-x-0 bottom-0 top-16 z-40 flex bg-slate-950/35" onClick={() => { setMobilePanel(null); closeDrawer(); }} onKeyDown={(event) => { if (event.key === "Escape") { setMobilePanel(null); closeDrawer(); } }}>
        <div className={mobilePanel === "sources" ? "h-full w-[min(22rem,92vw)] shadow-xl" : "ml-auto h-full w-[min(26rem,94vw)] shadow-xl"} onClick={(event) => event.stopPropagation()}>
          {mobilePanel === "sources" ? <PaperScopeRail onClose={() => { setMobilePanel(null); closeDrawer(); }} /> : <SourceInspectorRail onClose={() => { setMobilePanel(null); closeDrawer(); }} />}
        </div>
      </div>}
    </div>
  );
}
