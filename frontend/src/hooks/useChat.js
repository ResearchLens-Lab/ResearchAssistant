import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { chatService } from "@/services/chat.service";

export function useChat(conversationId = null) {
  const queryClient = useQueryClient();

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () => chatService.listConversations(1, 50),
  });

  const conversationQuery = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => chatService.getConversation(conversationId),
    enabled: !!conversationId,
  });

  const messagesQuery = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => chatService.getMessages(conversationId, 1, 100),
    enabled: !!conversationId,
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
    mutationFn: ({ title, paperIds }) => chatService.createConversation(title, paperIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const deleteConversationMutation = useMutation({
    mutationFn: (id) => chatService.deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  return {
    conversations: conversationsQuery.data?.items || [],
    isLoadingConversations: conversationsQuery.isLoading,
    conversation: conversationQuery.data,
    isLoadingConversation: conversationQuery.isLoading,
    messages: messagesQuery.data?.items || [],
    isLoadingMessages: messagesQuery.isLoading,
    sendMessage: sendMessageMutation.mutateAsync,
    isSendingMessage: sendMessageMutation.isPending,
    sendError: sendMessageMutation.error,
    createConversation: createConversationMutation.mutateAsync,
    isCreatingConversation: createConversationMutation.isPending,
    deleteConversation: deleteConversationMutation.mutateAsync,
    isDeletingConversation: deleteConversationMutation.isPending,
  };
}
