import { apiClient, refreshAccessToken } from "./api.client";
import { tokenStorage } from "@/utils/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function openAuthenticatedPdfSource(source) {
  if (!source?.document_id || !/\.pdf$/i.test(source.filename || "")) return false;
  const tab = window.open("about:blank", "_blank");
  if (!tab) return false;
  try {
    const endpoint = `${API_BASE}/documents/${encodeURIComponent(source.document_id)}/file`;
    const request = (token) => fetch(endpoint, { headers: { Authorization: `Bearer ${token}` } });
    let response = await request(tokenStorage.getAccessToken());
    if (response.status === 401 && tokenStorage.getRefreshToken()) {
      const renewed = await refreshAccessToken();
      if (renewed) response = await request(renewed);
    }
    if (!response.ok) throw new Error(`Source request failed (${response.status})`);
    const url = URL.createObjectURL(await response.blob());
    const page = source.page_start || source.page;
    tab.location.href = `${url}${page ? `#page=${page}` : ""}`;
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return true;
  } catch (error) {
    tab.close();
    throw error;
  }
}

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

  async uploadBatch(files, paperId) {
    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    formData.append("paper_id", paperId);
    return apiClient("/documents/upload/batch", { method: "POST", body: formData });
  },

  async getById(id) {
    return apiClient(`/documents/${id}`, {
      method: "GET",
    });
  },
};
