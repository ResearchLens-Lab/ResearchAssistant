"use client";

import React, { useEffect, useRef } from "react";
import { useChat } from "@/hooks/useChat";
import { useChatScopeStore } from "@/store/chatScopeStore";
import { useCitationStore } from "@/store/citationStore";
import { PaperScopeRail } from "./PaperScopeRail";
import { MessageItem } from "./MessageItem";
import { ChatInputBar } from "./ChatInputBar";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { Sparkles, Plus, AlertCircle } from "lucide-react";
import { useRouter } from "next/navigation";

export function ThreePaneChatWorkbench({ conversationId }) {
  const router = useRouter();
  const {
    messages,
    isLoadingMessages,
    sendMessage,
    isSendingMessage,
    sendError,
    conversation,
  } = useChat(conversationId);

  const { selectedPaperIds, selectPapers } = useChatScopeStore();
  const { setSources } = useCitationStore();
  const messagesEndRef = useRef(null);

  // Sync conversation paper_ids if available
  useEffect(() => {
    if (conversation?.paper_ids && conversation.paper_ids.length > 0) {
      selectPapers(conversation.paper_ids);
    }
  }, [conversation, selectPapers]);

  // Load existing assistant sources into citation store on load
  useEffect(() => {
    if (messages.length > 0) {
      const lastAssistantMsg = [...messages].reverse().find((m) => m.role === "assistant" && m.sources?.length);
      if (lastAssistantMsg && lastAssistantMsg.sources) {
        setSources(lastAssistantMsg.sources);
      }
    }
  }, [messages, setSources]);

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
    } catch (err) {
      console.error("Chat query error:", err);
    }
  };

  const handleNewThread = () => {
    router.push("/chat");
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-white dark:bg-zinc-950">
      {/* Pane 1: Left Scope Rail */}
      <PaperScopeRail />

      {/* Pane 2: Center Thread Canvas */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Thread Header Bar */}
        <div className="flex h-12 items-center justify-between border-b border-zinc-200 bg-white px-4 dark:border-zinc-800 dark:bg-zinc-900 shrink-0">
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="text-xs font-semibold text-zinc-900 truncate max-w-[280px] dark:text-zinc-100">
              {conversation?.title || "New Grounded Research Thread"}
            </span>
            <span className="text-[11px] font-mono text-zinc-400">
              ({selectedPaperIds.length} papers in scope)
            </span>
          </div>

          <div className="flex items-center gap-2">
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

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto">
          {isLoadingMessages ? (
            <div className="space-y-4 p-6">
              <div className="h-12 w-3/4 rounded-lg bg-zinc-100 animate-pulse" />
              <div className="h-28 w-full rounded-lg bg-zinc-100 animate-pulse" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-400 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 shadow-2xs">
                <Sparkles className="h-6 w-6 text-indigo-600" />
              </div>
              <div className="space-y-1 max-w-sm">
                <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                  Grounded Research Assistant
                </h4>
                <p className="text-xs text-zinc-500 leading-relaxed">
                  Select papers on the left and ask questions. Every answer is strictly grounded with verifiable inline citations.
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
              {messages.map((msg) => (
                <MessageItem key={msg.id} message={msg} />
              ))}

              {isSendingMessage && (
                <div className="flex items-center gap-3 p-4 bg-zinc-50/50">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 text-white">
                    <Sparkles className="h-4 w-4 animate-spin text-indigo-300" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-zinc-800">
                      Querying ChromaDB & synthesizing answer...
                    </p>
                    <p className="text-[11px] text-zinc-400 font-mono">
                      Matching section vectors & generating grounded citations
                    </p>
                  </div>
                </div>
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

        {/* Input Bar */}
        <ChatInputBar
          onSendMessage={handleSendMessage}
          isLoading={isSendingMessage}
        />
      </div>

      {/* Pane 3: Right Live Evidence & Source Inspector Rail */}
      <SourceInspectorRail />
    </div>
  );
}
