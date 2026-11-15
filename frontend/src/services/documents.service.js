import { apiClient, refreshAccessToken, AppApiError, resolveDesktopConfig } from "./api.client";
import { tokenStorage } from "@/utils/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function openAuthenticatedPdfSource(source, highlightedText = "") {
  if (!source?.document_id || !/\.pdf$/i.test(source.filename || "")) return false;
  const params = new URLSearchParams({
    document_id: source.document_id,
    filename: source.filename || "Research source.pdf",
    page: String(source.page_start || source.page || 1),
    end_page: String(source.page_end || source.page_start || source.page || 1),
  });
  const text = (highlightedText || source.evidence_excerpt || "").replace(/\s+/g, " ").trim();
  if (text) params.set("highlight", text);
  const tab = window.open(`/pdf-viewer?${params.toString()}`, "_blank");
  if (!tab) return false;
  tab.opener = null;
  return true;
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

  async uploadBatch(files, paperId, onUploadProgress, abortSignal = null) {
    const desktop = await resolveDesktopConfig();
    const targetUrl = `${desktop?.apiBaseUrl || API_BASE}/documents/upload/batch`;
    const desktopKey = desktop?.requestKey;

    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    formData.append("paper_id", paperId);
    const send = (token) => new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", targetUrl);
      if (desktopKey) xhr.setRequestHeader("X-ResearchLens-Desktop-Key", desktopKey);
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      if (abortSignal) {
        if (abortSignal.aborted) {
          reject(new Error("Upload was cancelled."));
          return;
        }
        abortSignal.addEventListener("abort", () => {
          xhr.abort();
          reject(new Error("Upload was cancelled."));
        });
      }
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) onUploadProgress?.({ loaded: event.loaded, total: event.total, percent: Math.min(100, Math.round(event.loaded * 100 / event.total)) });
      });
      xhr.addEventListener("error", () => reject(new Error("Upload connection failed. Check your connection and retry.")));
      xhr.addEventListener("abort", () => reject(new Error("Upload was cancelled.")));
      xhr.addEventListener("load", () => {
        let data;
        try { data = xhr.responseText ? JSON.parse(xhr.responseText) : {}; }
        catch { reject(new Error("The server returned an unreadable upload response.")); return; }
        if (xhr.status >= 200 && xhr.status < 300) { resolve(data); return; }
        const detail = data?.error;
        reject(new AppApiError(detail?.message || xhr.statusText || "Upload failed", detail?.code || "API_ERROR", xhr.status, detail?.request_id, detail?.details));
      });
      xhr.send(formData);
    });
    try {
      return await send(tokenStorage.getAccessToken());
    } catch (error) {
      if (error?.statusCode !== 401 || !tokenStorage.getRefreshToken()) throw error;
      const token = await refreshAccessToken();
      if (!token) throw error;
      return send(token);
    }
  },

  async getById(id) {
    return apiClient(`/documents/${id}`, {
      method: "GET",
    });
  },

  async retry(id) {
    return apiClient(`/documents/${encodeURIComponent(id)}/retry`, { method: "POST" });
  },

  async reindex(id) {
    return apiClient(`/documents/${encodeURIComponent(id)}/reindex`, { method: "POST" });
  },

  async cancel(id) {
    return apiClient(`/documents/${encodeURIComponent(id)}/cancel`, { method: "POST" });
  },

  async getSystemOverview() {
    return apiClient("/system/overview", { method: "GET" });
  },
};
