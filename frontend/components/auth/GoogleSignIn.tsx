"use client";
// Google Sign-In button that exchanges a Google ID token for MeetMind auth.
// The GSI client script is loaded and initialized exactly once per page load
// (module-level flags), so re-mounting this component (login -> dashboard ->
// login) no longer re-initializes google.accounts.id or emits the
// "initialize() is called multiple times" warning.

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

type GsiId = {
  initialize: (config: {
    client_id?: string;
    callback: (response: { credential: string }) => void;
  }) => void;
  renderButton: (element: HTMLElement, options: object) => void;
};

type WindowWithGoogle = Window & {
  google?: { accounts: { id: GsiId } };
};

let gsiScriptLoaded = false;
let gsiInitialized = false;

function mountButton(el: HTMLElement, width: number) {
  if (el.hasChildNodes()) return;
  const google = (window as WindowWithGoogle).google;
  if (!google?.accounts?.id) return;
  google.accounts.id.renderButton(el, {
    theme: "outline",
    size: "large",
    shape: "pill",
    width,
    text: "continue_with",
  });
}

function ensureInitialized(
  onCredentialRef: React.MutableRefObject<(credential: string) => void>
) {
  const google = (window as WindowWithGoogle).google;
  if (!google?.accounts?.id || gsiInitialized) return;
  google.accounts.id.initialize({
    client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
    callback: (response) => onCredentialRef.current(response.credential),
  });
  gsiInitialized = true;
}

export function GoogleSignIn({
  onCredential,
  isLoading,
  label = "Sign in with Google",
  width = 280,
}: {
  onCredential: (credential: string) => void;
  isLoading?: boolean;
  label?: string;
  width?: number;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const onCredentialRef = useRef(onCredential);

  useEffect(() => {
    onCredentialRef.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    if (isLoading || !mountRef.current) return;

    const google = (window as WindowWithGoogle).google;
    if (google?.accounts?.id) {
      ensureInitialized(onCredentialRef);
      mountButton(mountRef.current, width);
      return;
    }

    if (gsiScriptLoaded) return;
    gsiScriptLoaded = true;

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      ensureInitialized(onCredentialRef);
      if (mountRef.current) mountButton(mountRef.current, width);
    };
    document.body.appendChild(script);
  }, [isLoading, width]);

  if (isLoading) {
    return (
      <Button type="button" disabled className="w-full" variant="outline">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label === "Sign in with Google" ? "Signing in..." : "Signing up..."}
      </Button>
    );
  }

  return <div ref={mountRef} className="flex justify-center" />;
}
