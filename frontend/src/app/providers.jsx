"use client";

import React, { useEffect, useRef, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuthStore } from "@/store/authStore";
import { AuthSuccessToast } from "@/components/auth/AuthSuccessToast";
import { tokenStorage } from "@/utils/tokenStorage";

export function Providers({ children }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60 * 2,
            retry: (failureCount, error) => {
              if (
                error?.statusCode === 401 ||
                error?.statusCode === 403 ||
                error?.statusCode === 404
              ) {
                return false;
              }
              return failureCount < 2;
            },
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const checkAuth = useAuthStore((state) => state.checkAuth);
  const authCheckStarted = useRef(false);

  useEffect(() => {
    if (authCheckStarted.current) return;
    authCheckStarted.current = true;
    (async () => {
      try {
        await tokenStorage.init();
      } catch {}
      checkAuth();
    })();
  }, [checkAuth]);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>{children}<AuthSuccessToast /></TooltipProvider>
    </QueryClientProvider>
  );
}
