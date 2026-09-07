"use client";
// Client providers: React Query client, auth session restore, and CSRF-header axios interceptor.

import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useAuthStore } from "@/lib/auth-store";
import { refreshAccessToken } from "@/lib/session-refresh";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const finishRestoringSession = useAuthStore((state) => state.finishRestoringSession);

  useEffect(() => {
    if (sessionStorage.getItem("justLoggedOut")) {
      sessionStorage.removeItem("justLoggedOut");
      finishRestoringSession();
      return;
    }

    // Uses the same single-flight helper as the axios interceptor so only one
    // /auth/refresh ever runs at a time per tab (avoids the rotation race bug).
    refreshAccessToken()
      .catch(() => {
        // No session or transient failure - leave the app unauthenticated but
        // finish restoring so guard hooks can redirect to /login.
      })
      .finally(() => {
        finishRestoringSession();
      });
  }, [finishRestoringSession]);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
}
