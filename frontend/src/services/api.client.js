import { tokenStorage } from "@/utils/tokenStorage";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function refreshAccessToken() {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) return null;
  const response = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    tokenStorage.clear();
    return null;
  }
  const values = await response.json();
  tokenStorage.setTokens(values.access_token, values.refresh_token);
  return values.access_token;
}

export class AppApiError extends Error {
  constructor(message, code, statusCode, requestId = null, details = null) {
    super(message);
    this.name = "AppApiError";
    this.code = code;
    this.statusCode = statusCode;
    this.requestId = requestId;
    this.details = details;
  }
}

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

export async function apiClient(endpoint, options = {}) {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = tokenStorage.getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401 && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/refresh")) {
    const refreshToken = tokenStorage.getRefreshToken();
    if (refreshToken) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((newAccessToken) => {
          if (newAccessToken) {
            headers.set("Authorization", `Bearer ${newAccessToken}`);
          }
          return fetch(url, { ...options, headers }).then(handleResponse);
        });
      }

      isRefreshing = true;

      try {
        const refreshResp = await fetch(`${BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (refreshResp.ok) {
          const tokenData = await refreshResp.json();
          tokenStorage.setTokens(tokenData.access_token, tokenData.refresh_token);
          processQueue(null, tokenData.access_token);

          headers.set("Authorization", `Bearer ${tokenData.access_token}`);
          const retryResp = await fetch(url, { ...options, headers });
          return handleResponse(retryResp);
        } else {
          tokenStorage.clear();
          processQueue(new Error("Refresh failed"), null);
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
        }
      } catch (err) {
        tokenStorage.clear();
        processQueue(err, null);
      } finally {
        isRefreshing = false;
      }
    }
  }

  return handleResponse(response);
}

async function handleResponse(response) {
  if (response.status === 204) {
    return {};
  }

  const contentType = response.headers.get("content-type");
  const isJson = contentType && contentType.includes("application/json");
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorDetail = data?.error;

    throw new AppApiError(
      errorDetail?.message || (typeof data === "string" ? data : response.statusText || "Request failed"),
      errorDetail?.code || "API_ERROR",
      response.status,
      errorDetail?.request_id,
      errorDetail?.details
    );
  }

  return data;
}
