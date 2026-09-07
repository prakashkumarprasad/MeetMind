"use client";
// App shell: sidebar, top bar, and container/section/page-header primitives.

import { ReactNode, useState } from "react";
import { Sidebar } from "./Sidebar";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface PageWrapperProps {
  children: ReactNode;
  className?: string;
}

export function PageWrapper({ children, className }: PageWrapperProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      {}
      <motion.div
        initial={false}
        animate={{ opacity: sidebarOpen ? 1 : 0, pointerEvents: sidebarOpen ? "auto" : "none" }}
        className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden"
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      {}
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {}
      <main
        className={cn(
          "min-h-screen transition-all duration-250 ease-[0.4,0,0.2,1]",
          "lg:ml-[260px]",
          className
        )}
      >
        {}
        <div className="lg:hidden fixed top-4 left-4 z-50">
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-card border border-border shadow-lg text-foreground"
            aria-label="Open menu"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>

        <div className="pt-4 lg:pt-0">
          {children}
        </div>
      </main>
    </div>
  );
}

export function PageContainer({ 
  children, 
  className,
  maxWidth = "7xl"
}: { 
  children: ReactNode; 
  className?: string;
  maxWidth?: "7xl" | "6xl" | "5xl" | "4xl" | "full";
}) {
  const widths = {
    "7xl": "max-w-7xl",
    "6xl": "max-w-6xl", 
    "5xl": "max-w-5xl",
    "4xl": "max-w-4xl",
    "full": "max-w-full",
  };

  return (
    <div className={cn(
      "mx-auto px-4 sm:px-6 lg:px-8",
      widths[maxWidth],
      className
    )}>
      {children}
    </div>
  );
}

export function Section({ 
  children, 
  className,
  spacing = "normal"
}: { 
  children: ReactNode; 
  className?: string;
  spacing?: "compact" | "normal" | "comfortable" | "spacious";
}) {
  const spacings = {
    compact: "py-6",
    normal: "py-8 sm:py-12",
    comfortable: "py-12 sm:py-16",
    spacious: "py-16 sm:py-24",
  };

  return (
    <section className={cn(spacings[spacing], className)}>
      {children}
    </section>
  );
}

export function PageHeader({ 
  title,
  description,
  action,
  className
}: { 
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("mb-8 sm:mb-12", className)}>
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <motion.h1
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
            className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-foreground select-none"
          >
            {title}
          </motion.h1>
          {description && (
            <motion.p
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1], delay: 0.1 }}
              className="mt-2 text-lg text-muted-foreground max-w-2xl"
            >
              {description}
            </motion.p>
          )}
        </div>
        {action && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1], delay: 0.15 }}
            className="flex-shrink-0"
          >
            {action}
          </motion.div>
        )}
      </div>
    </header>
  );
}
