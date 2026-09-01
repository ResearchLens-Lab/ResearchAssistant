import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { authService } from "@/services/auth.service";

export function useAuth() {
  const queryClient = useQueryClient();
  const { user, isAuthenticated, isLoading, login, logout, setUser } = useAuthStore();

  const registerMutation = useMutation({
    mutationFn: (payload) => authService.register(payload),
    onSuccess: async () => {
      queryClient.clear();
    },
  });

  const loginMutation = useMutation({
    mutationFn: (payload) => login(payload),
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => logout(),
    onSuccess: () => {
      queryClient.clear();
    },
  });

  const updateProfileMutation = useMutation({
    mutationFn: (payload) => authService.updateProfile(payload),
    onSuccess: (updatedUser) => {
      setUser(updatedUser);
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });

  return {
    user,
    isAuthenticated,
    isLoading,
    register: registerMutation.mutateAsync,
    isRegistering: registerMutation.isPending,
    registerError: registerMutation.error,
    login: loginMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    loginError: loginMutation.error,
    logout: logoutMutation.mutateAsync,
    isLoggingOut: logoutMutation.isPending,
    updateProfile: updateProfileMutation.mutateAsync,
    isUpdatingProfile: updateProfileMutation.isPending,
    updateProfileError: updateProfileMutation.error,
  };
}
