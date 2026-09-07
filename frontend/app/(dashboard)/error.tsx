"use client";
// Dashboard error boundary UI.

import { useEffect } from "react";
import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import { TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {

    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <TriangleAlert className="h-8 w-8" />
      </div>

      <h1 className="mt-6 font-heading text-3xl font-bold tracking-tight">
        Something went wrong
      </h1>
      <p className="mx-auto mt-3 max-w-md text-muted-foreground">
        An unexpected error happened on this page. You can try again, or head
        back to your dashboard.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button onClick={reset}>Try again</Button>
        <Link href="/dashboard" className={cn(buttonVariants({ variant: "outline" }))}>
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
