import { apiClient, refreshAccessToken, AppApiError } from "./api.client";
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

  async uploadBatch(files, paperId, onUploadProgress, abortSignal = null) {
    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    formData.append("paper_id", paperId);
    const send = (token) => new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/documents/upload/batch`);
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

  async cancel(id) {
    return apiClient(`/documents/${encodeURIComponent(id)}/cancel`, { method: "POST" });
  },

  async getSystemOverview() {
    return apiClient("/system/overview", { method: "GET" });
  },
};
