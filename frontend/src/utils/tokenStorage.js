/**
 * ResearchLens Desktop — Secure Token Storage Abstraction
 * Enforces in-memory token lifecycle with OS-backed DPAPI safeStorage persistence
 * via Electron IPC. Prohibits plaintext persistent localStorage token fallbacks.
 */

const SESSION_STORAGE_ACCESS_KEY = "rl_sess_access";
const SESSION_STORAGE_REFRESH_KEY = "rl_sess_refresh";

let inMemoryAccessToken = null;
let inMemoryRefreshToken = null;
let initialized = false;
let persistEnabled = true;

function hasDesktopBridge() {
  return typeof window !== "undefined" && Boolean(window["researchLensDesktop"]);
}

export const tokenStorage = {
  async init() {
    if (initialized) return;
    initialized = true;

    if (hasDesktopBridge() && window["researchLensDesktop"].getProfile) {
      try {
        const profile = await window["researchLensDesktop"].getProfile();
        persistEnabled = profile?.rememberMe !== false;
        if (!persistEnabled && window["researchLensDesktop"].clearSession) {
          await window["researchLensDesktop"].clearSession();
        }
      } catch {}
    }

    // 1. Primary path: Electron OS-level encrypted safeStorage via DPAPI
    if (persistEnabled && hasDesktopBridge() && window["researchLensDesktop"].getSession) {
      try {
        const session = await window["researchLensDesktop"].getSession();
        if (session && session.accessToken) {
          inMemoryAccessToken = session.accessToken;
          inMemoryRefreshToken = session.refreshToken || null;
          return;
        }
      } catch (err) {
        // Fall back to ephemeral session storage if bridge fails
      }
    }

    // 2. Ephemeral browser fallback for non-desktop dev mode (sessionStorage only, never localStorage)
    if (typeof window !== "undefined") {
      try {
        inMemoryAccessToken = sessionStorage.getItem(SESSION_STORAGE_ACCESS_KEY);
        inMemoryRefreshToken = sessionStorage.getItem(SESSION_STORAGE_REFRESH_KEY);
      } catch {
        // Storage access restricted
      }
    }
  },

  getAccessToken() {
    if (inMemoryAccessToken) return inMemoryAccessToken;
    if (typeof window !== "undefined" && !hasDesktopBridge()) {
      try {
        inMemoryAccessToken = sessionStorage.getItem(SESSION_STORAGE_ACCESS_KEY);
      } catch {}
    }
    return inMemoryAccessToken;
  },

  setAccessToken(token) {
    inMemoryAccessToken = token;
    this._persistSecureSession();
  },

  getRefreshToken() {
    if (inMemoryRefreshToken) return inMemoryRefreshToken;
    if (typeof window !== "undefined" && !hasDesktopBridge()) {
      try {
        inMemoryRefreshToken = sessionStorage.getItem(SESSION_STORAGE_REFRESH_KEY);
      } catch {}
    }
    return inMemoryRefreshToken;
  },

  setRefreshToken(token) {
    inMemoryRefreshToken = token;
    this._persistSecureSession();
  },

  setTokens(accessToken, refreshToken) {
    inMemoryAccessToken = accessToken;
    inMemoryRefreshToken = refreshToken;
    this._persistSecureSession();
  },

  clear() {
    inMemoryAccessToken = null;
    inMemoryRefreshToken = null;

    if (hasDesktopBridge() && window["researchLensDesktop"].clearSession) {
      try {
        window["researchLensDesktop"].clearSession();
      } catch {}
    }

    if (typeof window !== "undefined") {
      try {
        sessionStorage.removeItem(SESSION_STORAGE_ACCESS_KEY);
        sessionStorage.removeItem(SESSION_STORAGE_REFRESH_KEY);
        // Clean up any legacy plaintext tokens from previous versions
        localStorage.removeItem("researchlens_access_token");
        localStorage.removeItem("researchlens_refresh_token");
      } catch {}
    }
  },

  setPersist(value) {
    persistEnabled = Boolean(value);
  },

  isAuthenticated() {
    return Boolean(this.getAccessToken());
  },

  getToken() {
    return this.getAccessToken();
  },

  _persistSecureSession() {
    if (hasDesktopBridge() && window["researchLensDesktop"].saveSession) {
      if (!persistEnabled) {
        window["researchLensDesktop"].clearSession?.().catch(() => {});
        return;
      }
      if (inMemoryAccessToken) {
        window["researchLensDesktop"].saveSession({
          accessToken: inMemoryAccessToken,
          refreshToken: inMemoryRefreshToken,
        }).catch(() => {});
      } else {
        window["researchLensDesktop"].clearSession().catch(() => {});
      }
      return;
    }

    // Ephemeral session storage for dev browser preview
    if (typeof window !== "undefined") {
      try {
        if (inMemoryAccessToken) {
          sessionStorage.setItem(SESSION_STORAGE_ACCESS_KEY, inMemoryAccessToken);
        } else {
          sessionStorage.removeItem(SESSION_STORAGE_ACCESS_KEY);
        }
        if (inMemoryRefreshToken) {
          sessionStorage.setItem(SESSION_STORAGE_REFRESH_KEY, inMemoryRefreshToken);
        } else {
          sessionStorage.removeItem(SESSION_STORAGE_REFRESH_KEY);
        }
      } catch {}
    }
  },
};
