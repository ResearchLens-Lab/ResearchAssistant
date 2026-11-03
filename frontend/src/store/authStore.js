import { create } from "zustand";
import { tokenStorage } from "@/utils/tokenStorage";
import { authService } from "@/services/auth.service";

export const useAuthStore = create((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),

  checkAuth: async () => {
    if (!tokenStorage.isAuthenticated()) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }

    try {
      set({ isLoading: true });
      const user = await authService.getMe();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      tokenStorage.clear();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
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
