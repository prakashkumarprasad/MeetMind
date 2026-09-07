"use client";
// Hook for setting document.title on client components.

import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title;
  }, [title]);
}
