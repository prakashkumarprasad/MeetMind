"use client";
// Contact page.

import { useState } from "react";
import Link from "next/link";
import { Mail, Send, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { PublicFooter } from "@/components/public-footer";

const CONTACT_EMAIL = "pp7373664@gmail.com";

const EMAIL_SUBJECT = encodeURIComponent("MeetMind Support");
const EMAIL_BODY = encodeURIComponent("Hi, I'd like to...");
const GMAIL_COMPOSE_URL = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(CONTACT_EMAIL)}&subject=${EMAIL_SUBJECT}&body=${EMAIL_BODY}`;
const OUTLOOK_COMPOSE_URL = `https://outlook.office.com/mail/?view=cm&to=${encodeURIComponent(CONTACT_EMAIL)}&subject=${EMAIL_SUBJECT}&body=${EMAIL_BODY}`;

export default function ContactPage() {
  const [copied, setCopied] = useState(false);

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(CONTACT_EMAIL);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {

    }
  }

  return (
    <div className="flex flex-col flex-1">
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

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-16 text-center">
        <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground">
          Get in touch
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Have a question, feedback, or a privacy request? We&apos;d love to
          hear from you. Send us an email and we&apos;ll get back to you as
          soon as we can.
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-4">
          <Dialog>
            <DialogTrigger
              render={
                <Button size="lg">
                  <Mail className="mr-2 h-4 w-4" />
                  Email us
                </Button>
              }
            />

            <DialogContent className="sm:max-w-xs">
              <DialogHeader>
                <DialogTitle>How would you like to email us?</DialogTitle>
                <DialogDescription>
                  Choose your preferred email client below.
                </DialogDescription>
              </DialogHeader>

              <div className="flex flex-col gap-2 pt-1">
                {}
                <DialogClose
                  render={
                    <button
                      type="button"
                      onClick={() => window.open(GMAIL_COMPOSE_URL, "_blank", "noopener,noreferrer")}
                      className="flex items-center gap-3 rounded-lg border border-border px-4 py-3 text-left transition-colors hover:bg-muted"
                    />
                  }
                >
                  <Mail className="h-5 w-5 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">Gmail</p>
                    <p className="text-xs text-muted-foreground">
                      Open in browser
                    </p>
                  </div>
                </DialogClose>

                {}
                <DialogClose
                  render={
                    <button
                      type="button"
                      onClick={() => window.open(OUTLOOK_COMPOSE_URL, "_blank", "noopener,noreferrer")}
                      className="flex items-center gap-3 rounded-lg border border-border px-4 py-3 text-left transition-colors hover:bg-muted"
                    />
                  }
                >
                  <Send className="h-5 w-5 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">Outlook</p>
                    <p className="text-xs text-muted-foreground">
                      Open in browser
                    </p>
                  </div>
                </DialogClose>

                {}
                <button
                  type="button"
                  onClick={copyEmail}
                  className="flex items-center gap-3 rounded-lg border border-border px-4 py-3 text-left transition-colors hover:bg-muted"
                >
                  {copied ? (
                    <Check className="h-5 w-5 shrink-0 text-primary" />
                  ) : (
                    <Copy className="h-5 w-5 shrink-0 text-muted-foreground" />
                  )}
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">
                      {copied ? "Copied!" : "Copy email address"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {CONTACT_EMAIL}
                    </p>
                  </div>
                </button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
