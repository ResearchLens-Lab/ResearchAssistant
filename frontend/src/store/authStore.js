import { create } from "zustand";
import { tokenStorage } from "@/utils/tokenStorage";
import { authService } from "@/services/auth.service";

export const useAuthStore = create((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  isUnreachable: false,

  setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false, isUnreachable: false }),

  checkAuth: async () => {
    if (!tokenStorage.isAuthenticated()) {
      set({ user: null, isAuthenticated: false, isLoading: false, isUnreachable: false });
      return;
    }

    set({ isLoading: true, isUnreachable: false });
    const startTime = Date.now();
    const maxTotalMs = 9500;

    for (let attempt = 0; attempt < 3; attempt++) {
      const elapsed = Date.now() - startTime;
      const remaining = maxTotalMs - elapsed;
      if (remaining <= 500) break;
      const attemptTimeout = Math.min(4000, remaining);

      let timeoutTimer = null;
      try {
        const timeoutPromise = new Promise((_, reject) => {
          timeoutTimer = setTimeout(() => {
            const timeoutError = new Error("Connection timed out");
            timeoutError.code = "TIMEOUT";
            timeoutError.statusCode = 504;
            reject(timeoutError);
          }, attemptTimeout);
        });

        const user = await Promise.race([authService.getMe(), timeoutPromise]);
        if (timeoutTimer) clearTimeout(timeoutTimer);
        set({ user, isAuthenticated: true, isLoading: false, isUnreachable: false });
        return;
      } catch (error) {
        if (timeoutTimer) clearTimeout(timeoutTimer);
        const status = error?.statusCode || error?.status;
        if (status === 401 || status === 403) {
          tokenStorage.clear();
          set({ user: null, isAuthenticated: false, isLoading: false, isUnreachable: false });
          return;
        }
        if (attempt < 2) {
          await new Promise((resolve) => setTimeout(resolve, 600));
        }
      }
    }
    // Cap total waiting: dead/unreachable backend does NOT clear tokens in storage
    set({ user: null, isAuthenticated: false, isLoading: false, isUnreachable: true });
  },

  login: async (payload) => {
    set({ isLoading: true });
    try {
      const response = await authService.login(payload);
      // Current servers include the verified profile with the token response;
      // retain /me fallback compatibility with an older backend deployment.
      const user = response.user || await authService.getMe();
      set({ user, isAuthenticated: true, isLoading: false });
      return user;
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      await authService.logout();
    } finally {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
