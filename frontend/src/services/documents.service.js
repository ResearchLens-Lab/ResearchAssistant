import { apiClient } from "./api.client";

export const documentsService = {
  async upload(file, paperId = null) {
    const formData = new FormData();
    formData.append("file", file);
    if (paperId) {
      formData.append("paper_id", paperId);
    }

    return apiClient("/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  async getById(id) {
    return apiClient(`/documents/${id}`, {
      method: "GET",
    });
  },
};
