import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { chatService } from "@/services/chat.service";
import { useRef, useState, useMemo } from "react";
import { applyChatStreamEvent } from "@/lib/researchWorkspace.mjs";

export function useChat(conversationId = null, searchQuery = "") {
  const queryClient = useQueryClient();
  const [pendingMessages, setPendingMessages] = useState([]);
  const [streamError, setStreamError] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef(null);

  const conversationsQuery = useQuery({
    queryKey: ["conversations", searchQuery],
    queryFn: () => chatService.listConversations(1, 100, searchQuery),
    staleTime: 10_000,
  });

  const conversationQuery = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => chatService.getConversation(conversationId),
    enabled: !!conversationId,
    staleTime: 30_000,
  });

  const messagesQuery = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => chatService.getMessages(conversationId, 1, 100),
    enabled: !!conversationId,
    staleTime: 30_000,
  });

  const sendMessageMutation = useMutation({
    mutationFn: (payload) => chatService.askQuestion(payload),
    onSuccess: (data) => {
      if (data.conversation_id) {
        queryClient.invalidateQueries({ queryKey: ["messages", data.conversation_id] });
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
      }
    },
  });

  const createConversationMutation = useMutation({
    /** @param {{ title: string, paperIds: string[] }} variables */
    mutationFn: ({ title, paperIds }) => chatService.createConversation(title, paperIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const updateConversationMutation = useMutation({
    /** @param {{ id: string, title?: string, paperIds?: string[] }} variables */
    mutationFn: ({ id, title, paperIds }) => chatService.updateConversation(id, { title, paper_ids: paperIds }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (variables.id) {
        queryClient.invalidateQueries({ queryKey: ["conversation", variables.id] });
      }
    },
  });

  const deleteConversationMutation = useMutation({
    mutationFn: (id) => chatService.deleteConversation(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.removeQueries({ queryKey: ["conversation", id] });
      queryClient.removeQueries({ queryKey: ["messages", id] });
    },
  });

  const sendMessage = async (payload) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const assistantId = `pending-assistant-${Date.now()}`;
    const temp = [
      { id: `pending-user-${Date.now()}`, role: "user", content: payload.question, optimistic: true },
      { id: assistantId, role: "assistant", content: "", pending: true, optimistic: true, progress: "Starting research…" },
    ];
    setPendingMessages(temp);
    setStreamError(null);
    setIsStreaming(true);
    try {
      const data = await chatService.streamQuestion(payload, (event) => {
        const labels = {
          planning_started: "Planning the research question…",
          planning_completed: "Research plan ready",
          retrieval_started: "Searching selected sources…",
          additional_retrieval: "Looking for missing evidence…",
          sources_found: `Found ${event.data?.count ?? 0} evidence passages`,
          evidence_ready: "Evidence collected; preparing an answer…",
          generation_skipped: "Answering with a directly retrieved passage…",
          generation_started: event.data?.provider === "ollama" ? "Generating with local Qwen; CPU answers can take a little longer…" : "Drafting an evidence-based answer…",
          verification_started: "Checking claims and citations…",
          verification_completed: "Evidence check complete",
        };
        if (event.type === "token") {
          setPendingMessages((current) => current.map((m) => m.id === assistantId ? applyChatStreamEvent(m, event) : m));
        } else if (event.type === "completed") {
          setPendingMessages((current) => current.map((m) => m.id === assistantId ? applyChatStreamEvent(m, event) : m));
        } else if (labels[event.type]) setPendingMessages((current) => current.map((m) => m.id === assistantId ? { ...m, progress: labels[event.type] } : m));
      }, controller.signal);
      if (data.conversation_id) {
        await queryClient.invalidateQueries({ queryKey: ["messages", data.conversation_id], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
      }
      return data;
    } catch (error) {
      if (error.name !== "AbortError") setStreamError(error);
      throw error;
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setPendingMessages([]);
      setIsStreaming(false);
    }
  };

  const rawMessages = Array.isArray(messagesQuery.data)
    ? messagesQuery.data
    : messagesQuery.data?.items || null;

  const messages = useMemo(() => {
    return [...(rawMessages || []), ...pendingMessages];
  }, [rawMessages, pendingMessages]);

  return {
    conversations: Array.isArray(conversationsQuery.data)
      ? conversationsQuery.data
      : conversationsQuery.data?.items || [],
    isLoadingConversations: conversationsQuery.isLoading,
    refetchConversations: conversationsQuery.refetch,
    conversation: conversationQuery.data,
    isLoadingConversation: conversationQuery.isLoading,
    messages,
    isLoadingMessages: messagesQuery.isLoading,
    sendMessage,
    isSendingMessage: isStreaming || sendMessageMutation.isPending,
    sendError: streamError || sendMessageMutation.error,
    cancelMessage: () => abortRef.current?.abort(),
    createConversation: createConversationMutation.mutateAsync,
    isCreatingConversation: createConversationMutation.isPending,
    updateConversation: updateConversationMutation.mutateAsync,
    isUpdatingConversation: updateConversationMutation.isPending,
    deleteConversation: deleteConversationMutation.mutateAsync,
    isDeletingConversation: deleteConversationMutation.isPending,
  };
}
