// Wrapper shell for legal-document pages.

import type { ReactNode } from "react";
import Link from "next/link";
import { PublicFooter } from "@/components/public-footer";

export function LegalShell({
  title,
  lastUpdated,
  children,
}: {
  title: string;
  lastUpdated?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col flex-1">
      {}
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Link
          href="/"
          aria-label="Go to MeetMind home"
          className="flex items-center gap-2"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <span className="text-xl font-bold">M</span>
          </div>
          <span className="font-heading text-xl font-semibold text-foreground select-none">
            MeetMind
          </span>
        </Link>
      </header>

      {}
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 pb-20">
        <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground text-balance">
          {title}
        </h1>
        {lastUpdated ? (
          <p className="mt-3 text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Last updated: {lastUpdated}
          </p>
        ) : null}

        {
}
        <div className="mt-12 space-y-16">{children}</div>
      </main>

      <PublicFooter />
    </div>
  );
}
