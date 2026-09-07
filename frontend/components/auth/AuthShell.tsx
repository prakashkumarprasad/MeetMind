"use client";
// Layout shell for the login/signup pages.

import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

export function AuthShell({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-dvh flex-1 items-center justify-center overflow-hidden bg-background px-4 py-10 sm:px-6">
      {}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm">
        <Link
          href="/"
          aria-label="Go to MeetMind home"
          className="mb-7 flex select-none items-center justify-center gap-2 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <div className="flex h-9 w-9 select-none items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <span className="select-none text-xl font-bold">M</span>
          </div>
          <span className="select-none font-heading text-xl font-semibold text-foreground">
            MeetMind
          </span>
        </Link>

        <Card className="w-full shadow-2xl">
          <CardHeader className="text-center">
            <CardTitle className="text-lg">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>

        {footer && (
          <div className="mt-5 text-center text-sm text-muted-foreground">{footer}</div>
        )}
      </div>
    </div>
  );
}
