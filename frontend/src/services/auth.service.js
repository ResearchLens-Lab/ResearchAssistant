import { apiClient } from "./api.client";
import { tokenStorage } from "@/utils/tokenStorage";

export const authService = {
  async register(payload) {
    return apiClient("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async login(payload) {
    const data = await apiClient("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (data.access_token && data.refresh_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token);
    }
    return data;
  },

  async getMe() {
    return apiClient("/auth/me", {
      method: "GET",
    });
  },

  async refreshToken(refreshToken) {
    const data = await apiClient("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (data.access_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token || refreshToken);
    }
    return data;
  },

  async logout() {
    try {
      await apiClient("/auth/logout", {
        method: "POST",
      });
    } finally {
      tokenStorage.clear();
    }
  },

  async updateProfile(payload) {
    return apiClient("/users/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};
