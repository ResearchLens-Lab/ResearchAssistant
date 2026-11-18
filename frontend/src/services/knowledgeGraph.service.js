import { apiClient } from "./api.client";

export const knowledgeGraphService = {
  async getNodes(params = {}) {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set("q", params.q);
    if (params.node_type) searchParams.set("node_type", params.node_type);
    if (params.limit) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return apiClient(`/knowledge-graph/nodes${qs ? `?${qs}` : ""}`);
  },

  async getNodeDetail(nodeId) {
    return apiClient(`/knowledge-graph/nodes/${nodeId}`);
  },

  async getNodeRelationships(nodeId) {
    return apiClient(`/knowledge-graph/nodes/${nodeId}/relationships`);
  },

  async getNodeEvidence(nodeId) {
    return apiClient(`/knowledge-graph/nodes/${nodeId}/evidence`);
  },
};
