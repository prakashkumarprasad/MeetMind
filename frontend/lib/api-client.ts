// Axios instance (withCredentials) configured with the CSRF header.

import axios from "axios";
import { useAuthStore } from "./auth-store";
import { X_REQUESTED_WITH_HEADER, X_REQUESTED_WITH_VALUE } from "./csrf";
import { refreshAccessToken, refreshStatus } from "./session-refresh";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  config.headers[X_REQUESTED_WITH_HEADER] = X_REQUESTED_WITH_VALUE;
  const accessToken = useAuthStore.getState().accessToken;
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const newAccessToken = await refreshAccessToken();
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Only treat a definitive 401 (token genuinely invalidated) as a
        // logout. Transient failures (network down, 5xx) must NOT kill the
        // session - that used to log users out randomly.
        if (refreshStatus(refreshError) === 401) {
          useAuthStore.getState().logout();
          if (typeof window !== "undefined") {
            try {
              sessionStorage.setItem("sessionExpired", "1");
            } catch {
              // Storage unavailable; still redirect below.
            }
            window.location.replace("/login");
          }
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
