import { apiClient } from "./api.client";

export const chatService = {
  async askQuestion(payload) {
    return apiClient("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listConversations(page = 1, pageSize = 20) {
    return apiClient(`/conversations?page=${page}&page_size=${pageSize}`, {
      method: "GET",
    });
  },

  async getConversation(id) {
    return apiClient(`/conversations/${id}`, {
      method: "GET",
    });
  },

  async getMessages(conversationId, page = 1, pageSize = 50) {
    return apiClient(`/conversations/${conversationId}/messages?page=${page}&page_size=${pageSize}`, {
      method: "GET",
    });
  },

  async createConversation(title, paperIds = []) {
    return apiClient("/conversations", {
      method: "POST",
      body: JSON.stringify({
        title,
        paper_ids: paperIds,
      }),
    });
  },

  async deleteConversation(id) {
    return apiClient(`/conversations/${id}`, {
      method: "DELETE",
    });
  },
};
