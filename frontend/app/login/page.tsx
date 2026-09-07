"use client";
// Login page.

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { isAxiosError } from "axios";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { AuthShell } from "@/components/auth/AuthShell";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { GoogleSignIn } from "@/components/auth/GoogleSignIn";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const setAccessToken = useAuthStore((state) => state.setAccessToken);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    document.title = "Log in — MeetMind";

    // Read sessionExpired in an effect (not in a useState initializer). Reading
    // it during the initial render would make the client's first paint differ
    // from the server-rendered HTML and cause React hydration mismatches.
    try {
      if (sessionStorage.getItem("sessionExpired") === "1") {
        sessionStorage.removeItem("sessionExpired");
        // Defer so the update happens after first paint (fixes hydration mismatch
        // and satisfies react-hooks/set-state-in-effect).
        window.setTimeout(() => {
          setError("Your session expired. Please log in again.");
        }, 0);
      }
    } catch {
      // Storage unavailable; skip the info banner.
    }
  }, []);

  const handleGoogleCredential = useCallback(async (credential: string) => {
    setError("");
    setIsLoading(true);
    try {
      const response = await apiClient.post("/api/v1/auth/google", { credential });
      setAccessToken(response.data.access_token);
      router.push("/dashboard");
    } catch (err) {
      const message =
        (isAxiosError(err) ? err.response?.data?.detail : undefined) ||
        "Google sign-in failed. Please try again.";
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, [router, setAccessToken]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await apiClient.post("/api/v1/auth/login", {
        email,
        password,
      });
      setAccessToken(response.data.access_token);
      router.push("/dashboard");
    } catch (err) {
      const status = isAxiosError(err) ? err.response?.status : undefined;
      const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
      let message: string;
      if (status === 429) {
        message = "Too many login attempts. Please try again in a few minutes.";
      } else if (Array.isArray(detail)) {
        message = detail[0]?.msg || "Please check your input.";
      } else {
        message =
          detail && typeof detail === "string"
            ? detail
            : "Invalid email or password.";
      }
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthShell
      title="Log in"
      description="Welcome back — your meeting intelligence is waiting."
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link
            href="/signup"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Sign up
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={!!error}
            required
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!error}
            required
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isLoading} className={cn("w-full")}>
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Logging in...
            </>
          ) : (
            "Log in"
          )}
        </Button>
      </form>

      <div className="my-4 flex items-center gap-2">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">OR</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <GoogleSignIn
        onCredential={handleGoogleCredential}
        isLoading={isLoading}
        label="Sign in with Google"
      />
    </AuthShell>
  );
}
