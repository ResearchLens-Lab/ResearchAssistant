import { tokenStorage } from "@/utils/tokenStorage";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

let _cachedDesktopConfig = null;

export async function resolveDesktopConfig() {
  if (typeof window === "undefined" || !window["researchLensDesktop"]) return null;
  if (_cachedDesktopConfig) return _cachedDesktopConfig;
  try {
    _cachedDesktopConfig = await window["researchLensDesktop"].getRuntimeConfig();
    return _cachedDesktopConfig;
  } catch {
    return null;
  }
}

export async function refreshAccessToken() {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) return null;
  const desktop = await resolveDesktopConfig();
  const headers = new Headers({ "Content-Type": "application/json" });
  if (desktop?.requestKey) headers.set("X-ResearchLens-Desktop-Key", desktop.requestKey);
  const response = await fetch(`${desktop?.apiBaseUrl || BASE_URL}/auth/refresh`, {
    method: "POST",
    headers,
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
  const desktop = await resolveDesktopConfig();
  const apiBase = desktop?.apiBaseUrl || BASE_URL;
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${apiBase}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (desktop?.requestKey) headers.set("X-ResearchLens-Desktop-Key", desktop.requestKey);

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const isAuthEndpoint = endpoint.includes("/auth/login") || endpoint.includes("/auth/register");
  const token = tokenStorage.getAccessToken();
  if (token && !headers.has("Authorization") && !isAuthEndpoint) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const controller = typeof AbortController !== "undefined" && !options.signal ? new AbortController() : null;
  const timeoutMs = options.timeout ?? 20000;
  const timeoutId = controller ? setTimeout(() => controller.abort(new Error("Request timed out")), timeoutMs) : null;
  const signal = options.signal || controller?.signal;

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError" || err.message === "Request timed out") {
      throw new AppApiError("Connection to ResearchLens timed out. Please check your backend connection.", "TIMEOUT", 504);
    }
    throw err;
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }

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
        const refreshResp = await fetch(`${apiBase}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(desktop?.requestKey ? { "X-ResearchLens-Desktop-Key": desktop.requestKey } : {}) },
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
