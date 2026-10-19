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
  } = useChat(conversationId);

  const { selectedPaperIds, selectPapers } = useChatScopeStore();
  const { setSources, setResearchTrace, clearSources } = useCitationStore();
  const messagesEndRef = useRef(null);
  const [mobilePanel, setMobilePanel] = useState(null);

  // Sync query param paper_id if present
  useEffect(() => {
    if (queryPaperId && !selectedPaperIds.includes(queryPaperId)) {
      selectPapers([queryPaperId]);
    }
  }, [queryPaperId, selectedPaperIds, selectPapers]);

  // Sync conversation paper_ids if available
  useEffect(() => {
    if (conversation?.paper_ids && conversation.paper_ids.length > 0) {
      selectPapers(conversation.paper_ids);
    }
  }, [conversation, selectPapers]);

  // Load existing assistant sources into citation store on load
  useEffect(() => {
    if (messages.length > 0) {
      const lastAssistantMsg = [...messages].reverse().find((m) => m.role === "assistant" && !m.pending);
      if (lastAssistantMsg) {
        setSources(lastAssistantMsg.sources || []);
        setResearchTrace(lastAssistantMsg.meta?.research || null);
      }
    }
  }, [messages, setSources, setResearchTrace]);

  useEffect(() => { clearSources(); }, [conversationId, clearSources]);

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
    } catch (err) {
      console.error("Chat query error:", err);
    }
  };

  const handleNewThread = () => {
    router.push("/chat");
  };

  const handleExportBrief = () => {
    const markdown = buildResearchBrief(messages.filter((message) => !message.pending), conversation?.title || "Research brief");
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(conversation?.title || "research-brief").trim().replace(/[^a-z0-9-]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "research-brief"}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-[#f8faf9]">
      {/* Pane 1: Left Scope Rail */}
      <PaperScopeRail className="hidden xl:flex" />

      {/* Pane 2: Center Thread Canvas */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Thread Header Bar */}
        <div className="flex min-h-14 items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 sm:px-4 shrink-0">
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="truncate text-sm font-semibold text-slate-900 max-w-[240px] sm:max-w-[360px]">
              {conversation?.title || "Research workspace"}
            </span>
            <span className="hidden sm:inline text-[11px] text-slate-500">
              {selectedPaperIds.length} paper{selectedPaperIds.length === 1 ? "" : "s"} in scope
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleExportBrief} disabled={!messages.some((message) => message.role === "assistant" && !message.pending)} className="hidden sm:inline-flex h-8 gap-1.5 border-slate-300 text-xs">
              <Download className="h-3.5 w-3.5" /> Research brief
            </Button>
            {selectedPaperIds.length >= 2 && <Button variant="outline" size="sm" onClick={() => router.push(`/compare?paper_ids=${encodeURIComponent(selectedPaperIds.join(","))}`)} className="hidden sm:inline-flex h-8 gap-1.5 border-slate-300 text-xs">
              <GitCompare className="h-3.5 w-3.5" /> Compare
            </Button>}
            <Button
              variant="outline"
              size="sm"
              onClick={handleNewThread}
              className="h-7 text-xs gap-1.5"
            >
              <Plus className="h-3 w-3" />
              <span>New Thread</span>
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 xl:hidden">
          <Button type="button" variant="outline" size="sm" onClick={() => setMobilePanel("sources")} className="h-8 gap-1.5 border-slate-300 bg-white text-xs"><PanelLeft className="h-3.5 w-3.5" />Sources · {selectedPaperIds.length}</Button>
          <Button type="button" variant="outline" size="sm" onClick={() => setMobilePanel("evidence")} className="h-8 gap-1.5 border-slate-300 bg-white text-xs"><PanelRight className="h-3.5 w-3.5" />Evidence</Button>
          <Button type="button" variant="outline" size="sm" onClick={handleExportBrief} disabled={!messages.some((message) => message.role === "assistant" && !message.pending)} className="ml-auto h-8 gap-1.5 border-slate-300 bg-white text-xs"><Download className="h-3.5 w-3.5" />Export</Button>
          {selectedPaperIds.length >= 2 && <Button type="button" variant="outline" size="sm" onClick={() => router.push(`/compare?paper_ids=${encodeURIComponent(selectedPaperIds.join(","))}`)} className="h-8 gap-1.5 border-slate-300 bg-white text-xs"><GitCompare className="h-3.5 w-3.5" />Compare</Button>}
        </div>

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto">
          {isLoadingMessages ? (
            <div className="space-y-4 p-6">
              <div className="h-12 w-3/4 rounded-lg bg-zinc-100 animate-pulse" />
              <div className="h-28 w-full rounded-lg bg-zinc-100 animate-pulse" />
            </div>
          ) : messages.length === 0 && !sendError ? (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-400 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 shadow-2xs">
                <Sparkles className="h-6 w-6 text-indigo-600" />
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
                  "What is the main contribution of this paper?",
                  "Compare the dataset benchmarks and baseline accuracy",
                  "Explain the core methodology and architectural choices",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSendMessage(prompt)}
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
                    <Sparkles className="h-4 w-4 animate-spin text-indigo-500" />
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
          isLoading={isSendingMessage}
        />
      </div>

      {/* Pane 3: Right Live Evidence & Source Inspector Rail */}
      <SourceInspectorRail className="hidden xl:flex" />

      {mobilePanel && <div role="dialog" aria-modal="true" aria-label={mobilePanel === "sources" ? "Research sources" : "Evidence inspector"} className="absolute inset-0 z-40 flex bg-slate-950/35 xl:hidden" onClick={() => setMobilePanel(null)} onKeyDown={(event) => { if (event.key === "Escape") setMobilePanel(null); }}>
        <div className={mobilePanel === "sources" ? "h-full max-w-[90vw] shadow-xl" : "ml-auto h-full max-w-[90vw] shadow-xl"} onClick={(event) => event.stopPropagation()}>
          {mobilePanel === "sources" ? <PaperScopeRail onClose={() => setMobilePanel(null)} /> : <SourceInspectorRail onClose={() => setMobilePanel(null)} />}
        </div>
      </div>}
    </div>
  );
}
