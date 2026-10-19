import { apiClient, refreshAccessToken } from "./api.client";
import { tokenStorage } from "@/utils/tokenStorage";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const chatService = {
  async streamQuestion(payload, onEvent, signal) {
    const token = tokenStorage.getAccessToken();
    const makeRequest = (accessToken) => fetch(`${BASE_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
      body: JSON.stringify(payload),
      signal,
    });
    let response = await makeRequest(token);
    if (response.status === 401 && tokenStorage.getRefreshToken()) {
      const renewed = await refreshAccessToken();
      if (renewed) response = await makeRequest(renewed);
      else if (typeof window !== "undefined") window.location.href = "/login";
    }
    if (!response.ok || !response.body) {
      const message = await response.text();
      throw new Error(message || `Chat stream failed (${response.status})`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let completed = null;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (const frame of frames) {
          const data = frame.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
          if (!data) continue;
          const event = JSON.parse(data);
          onEvent?.(event);
          if (event.type === "completed") completed = event.data;
          if (event.type === "error") throw new Error(event.data?.message || "Chat stream failed");
        }
      }
    } finally {
      reader.releaseLock();
    }
    if (!completed) throw new Error("The chat stream ended before a response was persisted.");
    return completed;
  },
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
