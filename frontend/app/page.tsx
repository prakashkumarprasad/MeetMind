// Public marketing/landing page.

import type { Metadata } from "next";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import {
  FileText,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Mic,
  Wand2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PublicFooter } from "@/components/public-footer";

const features = [
  {
    icon: Mic,
    title: "AI transcriptions",
    description:
      "Upload audio or video recordings and get accurate, searchable transcripts automatically.",
  },
  {
    icon: Wand2,
    title: "Meeting summaries",
    description:
      "Every meeting is distilled into a clear summary with action items and owners.",
  },
  {
    icon: MessageSquare,
    title: "Chat with your meetings",
    description:
      "Ask questions across all your recordings and get sourced, grounded answers.",
  },
];

export const metadata: Metadata = {
  title: "MeetMind — AI meeting intelligence",
  description:
    "MeetMind transcribes your audio and video recordings, summarizes the discussion, and lets you chat with your meetings.",
};

export default function Home() {
  return (
    <div className="flex flex-col flex-1">
      {}
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <span className="text-xl font-bold">M</span>
          </div>
          <span className="font-heading text-xl font-semibold text-foreground select-none">
            MeetMind
          </span>
        </div>
        <nav className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Log in
          </Link>
          <Link href="/signup" className={buttonVariants({ size: "sm" })}>
            Get started
          </Link>
        </nav>
      </header>

      {}
      <section className="mx-auto w-full max-w-6xl px-6 py-24 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          AI meeting intelligence for your team
        </div>
        <h1 className="mx-auto mt-6 max-w-3xl font-heading text-4xl font-bold tracking-tight sm:text-6xl">
          Turn every meeting into{" "}
          <span className="text-primary">notes, action items, and answers</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          MeetMind transcribes your audio and video recordings, summarizes the
          discussion, and lets you chat with your meetings to find anything in
          seconds.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/signup"
            className={cn(buttonVariants({ size: "lg" }))}
          >
            Start free <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
          <Link
            href="/login"
            className={cn(buttonVariants({ size: "lg", variant: "outline" }))}
          >
            <FileText className="mr-1 h-4 w-4" /> View demo
          </Link>
        </div>
      </section>

      {}
      <section className="mx-auto w-full max-w-6xl px-6 pb-24">
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-2xl border border-border bg-card p-6"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <feature.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {}
      <PublicFooter />
    </div>
  );
}
