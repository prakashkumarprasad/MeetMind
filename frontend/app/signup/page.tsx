"use client";
// Signup page.

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

export default function SignupPage() {
  const router = useRouter();
  const setAccessToken = useAuthStore((state) => state.setAccessToken);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    document.title = "Sign up — MeetMind";
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
        "Google sign-up failed. Please try again.";
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
      const response = await apiClient.post("/api/v1/auth/signup", {
        full_name: fullName,
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
        message = "Too many sign-up attempts. Please try again in a few minutes.";
      } else if (Array.isArray(detail)) {
        message = detail[0]?.msg || "Please check your input.";
      } else {
        message =
          detail && typeof detail === "string"
            ? detail
            : "Something went wrong. Please try again.";
      }
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      description="Start turning your meetings into notes, action items, and answers."
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Log in
          </Link>
          <p className="mt-3 text-xs text-muted-foreground">
            By signing up, you agree to our{" "}
            <Link
              href="/terms"
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              Terms
            </Link>{" "}
            and{" "}
            <Link
              href="/privacy"
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              Privacy Policy
            </Link>
            .
          </p>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="fullName">Full name</Label>
          <Input
            id="fullName"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </div>

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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={12}
            aria-invalid={!!error}
            required
          />
          <p className="text-xs text-muted-foreground">At least 12 characters.</p>
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isLoading} className={cn("w-full")}>
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Creating account...
            </>
          ) : (
            "Sign up"
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
        label="Sign up with Google"
      />
    </AuthShell>
  );
}
