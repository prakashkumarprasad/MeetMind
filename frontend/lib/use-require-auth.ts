"use client";
// Hook that redirects unauthenticated users to the login page.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "./auth-store";

export function useRequireAuth() {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const isRestoringSession = useAuthStore((state) => state.isRestoringSession);

  useEffect(() => {
    if (!isRestoringSession && !accessToken) {
      router.push("/login");
    }
  }, [isRestoringSession, accessToken, router]);

  return { isCheckingAuth: isRestoringSession };
}
