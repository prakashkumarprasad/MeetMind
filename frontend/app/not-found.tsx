// Custom 404 page.

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6 text-center">
      <Link
        href="/"
        aria-label="Go to MeetMind home"
        className="mb-8 flex select-none items-center gap-2 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <div className="flex h-9 w-9 select-none items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <span className="select-none text-xl font-bold">M</span>
        </div>
        <span className="select-none font-heading text-xl font-semibold text-foreground">
          MeetMind
        </span>
      </Link>

      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <Compass className="h-8 w-8" />
      </div>

      <h1 className="mt-6 font-heading text-4xl font-bold tracking-tight text-foreground">
        This page took a meeting and left
      </h1>
      <p className="mx-auto mt-3 max-w-md text-muted-foreground">
        The page you&apos;re looking for doesn&apos;t exist or has been moved.
        Head back to your dashboard to keep going.
      </p>

      <Link href="/dashboard" className={`${buttonVariants({ size: "lg" })} mt-8`}>
        Back to dashboard
      </Link>
    </div>
  );
}
