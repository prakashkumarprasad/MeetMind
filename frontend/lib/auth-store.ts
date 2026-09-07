// Zustand store for auth state, session restore, login/logout, and CSRF-header refresh.

import { create } from "zustand";
import axios from "axios";
import { X_REQUESTED_WITH_HEADER, X_REQUESTED_WITH_VALUE } from "./csrf";

type AuthState = {
  accessToken: string | null;
  isRestoringSession: boolean;
  setAccessToken: (token: string) => void;
  finishRestoringSession: () => void;
  logout: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  isRestoringSession: true,
  setAccessToken: (token) => set({ accessToken: token }),
  finishRestoringSession: () => set({ isRestoringSession: false }),
  logout: async () => {
    try {
      await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/logout`,
        {},
        {
          withCredentials: true,
          headers: { [X_REQUESTED_WITH_HEADER]: X_REQUESTED_WITH_VALUE },
        }
      );
    } catch {

    }
    sessionStorage.setItem("justLoggedOut", "1");
    set({ accessToken: null });
  },
}));
