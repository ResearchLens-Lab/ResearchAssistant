import { apiClient } from "./api.client";

export const researchService = {
  async getPaperGraph(paperId) {
    return apiClient(`/research/papers/${paperId}/graph`, {
      method: "GET",
    });
  },

  async getRelatedPapers(paperId) {
    return apiClient(`/research/papers/${paperId}/related`, {
      method: "GET",
    });
  },

  async getResearchTrends() {
    return apiClient("/research/trends", {
      method: "GET",
    });
  },

  async getHealth() {
    return apiClient("/health", {
      method: "GET",
    });
  },

  async getReadiness() {
    return apiClient("/health/ready", {
      method: "GET",
    });
  },

  async getLocalModelStatus() {
    return apiClient("/system/model", {
      method: "GET",
    });
  },
};
