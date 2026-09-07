"use client";
// Shared dashboard UI: status badges, meeting cards, stat blocks, and status constants.

import Link from "next/link";
import { cn, formatDate } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Check, FileText, Info } from "lucide-react";
import { DeleteMeetingDialog } from "@/components/meetings/delete-meeting-dialog";

export const IN_PROGRESS_STATUSES = [
  "pending",
  "validating",
  "converting",
  "transcribing",
  "transcribing_done",
  "summarizing",
];

const statusConfig: Record<string, { label: string; color: string }> = {
  ready: { label: "Completed", color: "bg-green-500" },
  completed: { label: "Completed", color: "bg-green-500" },
  pending: { label: "Pending", color: "bg-yellow-500" },
  validating: { label: "Validating", color: "bg-blue-500" },
  converting: { label: "Converting", color: "bg-cyan-500" },
  transcribing: { label: "Transcribing", color: "bg-purple-500" },
  transcribing_done: { label: "Transcribing", color: "bg-purple-500" },
  summarizing: { label: "Summarizing", color: "bg-orange-500" },
  failed: { label: "Failed", color: "bg-red-500" },
};

export function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { label: status, color: "bg-gray-500" };
  const isProcessing = IN_PROGRESS_STATUSES.includes(status);

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
      "transition-all duration-200"
    )}>
      <span className={cn(
        "h-1.5 w-1.5 rounded-full",
        config.color,
        isProcessing && "animate-pulse"
      )} />
      {config.label}
    </span>
  );
}

const processingStageConfig: Record<
  string,
  { label: string; percent: number }
> = {
  pending: { label: "Queued", percent: 5 },
  validating: { label: "Validating file", percent: 15 },
  converting: { label: "Converting to audio", percent: 35 },
  transcribing: { label: "Transcribing audio", percent: 60 },
  transcribing_done: { label: "Transcribing audio", percent: 75 },
  summarizing: { label: "Generating summary", percent: 90 },
};

export function getProcessingProgress(status: string): {
  label: string;
  percent: number;
} {
  return (
    processingStageConfig[status] ?? {
      label: status || "Processing",
      percent: 10,
    }
  );
}

export function ProcessingProgress({
  status,
  showPercent = true,
  className,
}: {
  status: string;
  showPercent?: boolean;
  className?: string;
}) {
  const { label, percent } = getProcessingProgress(status);

  return (
    <div className={cn("w-full", className)}>
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}&hellip;</span>
        {showPercent && <span>{percent}%</span>}
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className="shimmer relative h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export type MediaType = "audio" | "video";

type ProgressStep = { status: string; label: string };

// The ordered pipeline shown to users for each media type. Video inserts an
// extra "convert to audio" step that audio-only uploads skip entirely.
export function getProcessingSteps(mediaType: MediaType): ProgressStep[] {
  const steps: ProgressStep[] = [
    { status: "pending", label: "Queued" },
    { status: "validating", label: "Validating" },
    { status: "transcribing", label: "Transcribing" },
    { status: "summarizing", label: "Summarizing" },
  ];
  if (mediaType === "video") {
    steps.splice(2, 0, { status: "converting", label: "Converting video to audio" });
  }
  return steps;
}

// Smoothly maps the current step's position in the media-specific pipeline to
// a 10–90% value, so all users see steady progress that never hits 100% early.
export function getProcessingPercent(status: string, mediaType: MediaType): number {
  const steps = getProcessingSteps(mediaType);
  const index = steps.findIndex((s) => s.status === status);
  if (index === -1) return 10;
  return 10 + Math.round((index / (steps.length - 1)) * 80);
}

// Shared progress UI used in BOTH the meeting cards and the meeting detail
// page, so the loading bar, per-step information, and video notice are always
// identical everywhere the user looks.
export function MeetingProcessingPanel({
  status,
  mediaType = "audio",
  className,
}: {
  status: string;
  mediaType?: MediaType;
  className?: string;
}) {
  const isVideo = mediaType === "video";
  const steps = getProcessingSteps(mediaType);
  const currentIndex = steps.findIndex((s) => s.status === status);
  const percent = getProcessingPercent(status, mediaType);
  const { label } = getProcessingProgress(status);

  return (
    <div className={cn("w-full", className)}>
      {isVideo && (
        <p className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-700 dark:text-amber-400">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Video meetings take a little longer — your recording is first converted
            to audio before it can be transcribed and summarized.
          </span>
        </p>
      )}

      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}&hellip;</span>
        <span>{percent}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className="shimmer relative h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>

      <ol className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {steps.map((step, i) => {
          const done = currentIndex !== -1 && i < currentIndex;
          const active = i === currentIndex;
          return (
            <li
              key={step.status}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs",
                done && "text-muted-foreground",
                active && "font-medium text-foreground",
                !done && !active && "text-muted-foreground/60"
              )}
            >
              {i > 0 && <span className="text-muted-foreground/40">›</span>}
              {done ? (
                <Check className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    active ? "animate-pulse bg-primary" : "bg-muted-foreground/40"
                  )}
                />
              )}
              {step.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  trendLabel,
  iconColor = "text-primary",
  bgColor = "bg-primary/10",
}: {
  title: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  trend?: string;
  trendLabel?: string;
  iconColor?: string;
  bgColor?: string;
}) {
  return (
    <Card className="hover:shadow-lg transition-shadow duration-300">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="mt-1 text-3xl font-bold tracking-tight">{value}</p>
            {trend && (
              <div className="mt-2 flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
                <span className="font-medium">{trend}</span>
                <span className="text-muted-foreground">{trendLabel}</span>
              </div>
            )}
          </div>
          <div className={cn("p-3 rounded-xl", bgColor, iconColor)}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function calculateTotalHours(meetings: { id: string; title: string; status: string; created_at: string }[] | undefined): string {
  if (!meetings || meetings.length === 0) return "0h";
  const estimatedHours = meetings.length * 0.5;
  return estimatedHours >= 1 ? `${estimatedHours.toFixed(1)}h` : `${Math.round(estimatedHours * 60)}m`;
}

export function MeetingCard({
  meeting,
  workspaceId,
  onDeleted,
}: {
  meeting: {
    id: string;
    title: string;
    status: string;
    created_at: string;
    source_media_type?: string;
  };
  workspaceId?: string;
  onDeleted?: () => void;
}) {
  const isProcessing = IN_PROGRESS_STATUSES.includes(meeting.status);
  const isFailed = meeting.status === "failed";

  const iconClass = cn(
    "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition-colors",
    isFailed
      ? "bg-destructive/10 text-destructive"
      : isProcessing
        ? "bg-primary/10 text-primary"
        : "bg-green-500/10 text-green-600 dark:text-green-500"
  );

  return (
    <Card
      className={cn(
        "group transition-all duration-200",
        "border-border/50 hover:border-primary/30 hover:shadow-lg",
        "cursor-pointer"
      )}
    >
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          <Link
            href={`/dashboard/meetings/${meeting.id}`}
            className={cn(
              "flex min-w-0 flex-1 items-start gap-4 rounded-lg",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            )}
          >
            <div
              className={cn(
                iconClass,
                "rounded-xl transition-transform duration-200 group-hover:scale-105"
              )}
              aria-label={`Open ${meeting.title}`}
            >
              <FileText className="h-6 w-6" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-medium text-foreground truncate">{meeting.title}</h3>
                <StatusBadge status={meeting.status} />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {formatDate(meeting.created_at)}
              </p>
              {isProcessing && (
                <MeetingProcessingPanel
                  status={meeting.status}
                  mediaType={meeting.source_media_type === "video" ? "video" : "audio"}
                  className="mt-3"
                />
              )}
            </div>
          </Link>

          {workspaceId && (
            <DeleteMeetingDialog
              meetingId={meeting.id}
              meetingTitle={meeting.title}
              workspaceId={workspaceId}
              onDeleted={onDeleted}
              className="shrink-0 self-center text-muted-foreground hover:text-destructive"
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function MeetingCardSkeleton() {
  return (
    <Card className="animate-pulse">
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          <div className="h-12 w-12 shrink-0 rounded-xl bg-muted" />
          <div className="flex-1 space-y-3">
            <div className="h-5 w-3/4 bg-muted rounded" />
            <div className="h-4 w-1/2 bg-muted rounded" />
            <div className="h-6 w-1/4 bg-muted rounded-full" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
