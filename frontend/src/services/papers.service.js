import { apiClient } from "./api.client";

export const papersService = {
  async list(page = 1, pageSize = 20) {
    return apiClient(`/papers?page=${page}&page_size=${pageSize}`, {
      method: "GET",
    });
  },

  async getById(id) {
    return apiClient(`/papers/${id}`, {
      method: "GET",
    });
  },

  async create(payload) {
    return apiClient("/papers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async update(id, payload) {
    return apiClient(`/papers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async delete(id) {
    return apiClient(`/papers/${id}`, {
      method: "DELETE",
    });
  },

  async summarize(paperId, focusArea) {
    return apiClient(`/papers/${paperId}/summary`, {
      method: "POST",
      body: JSON.stringify({ focus_area: focusArea || null }),
    });
  },

  async compare(payload) {
    return apiClient("/papers/compare", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getDocuments(paperId) {
    return apiClient(`/papers/${paperId}/documents`, {
      method: "GET",
    });
  },
};
