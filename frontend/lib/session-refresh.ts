// Single-flight refresh-token helper shared by the axios interceptor and the
// session-restore effect. Guarantees only ONE /auth/refresh request runs at a
// time per tab, so a burst of 401s can't trigger the token-rotation race that
// used to log users out randomly.

import axios from "axios";
import { useAuthStore } from "./auth-store";
import { X_REQUESTED_WITH_HEADER, X_REQUESTED_WITH_VALUE } from "./csrf";

let refreshPromise: Promise<string> | null = null;

function isAxiosShaped(error: unknown): error is { response?: { status?: number } } {
  return typeof error === "object" && error !== null;
}

export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/refresh`,
        {},
        {
          withCredentials: true,
          headers: { [X_REQUESTED_WITH_HEADER]: X_REQUESTED_WITH_VALUE },
        }
      )
      .then((response) => {
        const token = response.data.access_token as string;
        useAuthStore.getState().setAccessToken(token);
        return token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export function refreshStatus(error: unknown): number | undefined {
  if (isAxiosShaped(error)) return error.response?.status;
  return undefined;
}
