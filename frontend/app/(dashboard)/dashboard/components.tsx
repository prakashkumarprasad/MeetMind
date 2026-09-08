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
  converting: { label: "Processing", color: "bg-cyan-500" },
  transcribing: { label: "Transcribing", color: "bg-purple-500" },
  transcribing_done: { label: "Transcribing", color: "bg-purple-500" },
  summarizing: { label: "Summarizing", color: "bg-orange-500" },
  failed: { label: "Failed", color: "bg-red-500" },
};

export function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || {
    label: status,
    color: "bg-gray-500",
  };

  const isProcessing = IN_PROGRESS_STATUSES.includes(status);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        "transition-all duration-200"
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          config.color,
          isProcessing && "animate-pulse"
        )}
      />
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

type ProgressStep = {
  status: string;
  label: string;
};

export function getProcessingSteps(mediaType: MediaType): ProgressStep[] {
  const steps: ProgressStep[] = [
    { status: "pending", label: "Queued" },
    { status: "validating", label: "Validating" },
    { status: "transcribing", label: "Transcribing" },
    { status: "summarizing", label: "Summarizing" },
  ];

  if (mediaType === "video") {
    steps.splice(2, 0, {
      status: "converting",
      label: "Converting video to audio",
    });
  }

  return steps;
}

export function getProcessingPercent(
  status: string,
  mediaType: MediaType
): number {
  const steps = getProcessingSteps(mediaType);
  const index = steps.findIndex((step) => step.status === status);

  if (index === -1) {
    return 10;
  }

  return 10 + Math.round((index / (steps.length - 1)) * 80);
}

function getMediaAwareStage(
  status: string,
  mediaType: MediaType
): { label: string; percent: number } {
  if (status === "converting" && mediaType === "audio") {
    return {
      label: "Processing audio",
      percent: 40,
    };
  }

  if (status === "converting" && mediaType === "video") {
    return {
      label: "Converting video to audio",
      percent: 35,
    };
  }

  // The generic helper provides the label, while the media-aware helper
  // provides the correct progress percentage for the selected pipeline.
  const { label } = getProcessingProgress(status);

  return {
    label,
    percent: getProcessingPercent(status, mediaType),
  };
}

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
  const currentIndex = steps.findIndex((step) => step.status === status);
  const { label, percent } = getMediaAwareStage(status, mediaType);

  return (
    <div className={cn("w-full", className)}>
      <div className="mb-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
        <div className="flex items-start gap-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />

          <span>
            Your meeting is being processed. Transcription and AI summarization
            can take a few minutes depending on the recording length. Please
            don&apos;t upload it again — your meeting is still being processed.
          </span>
        </div>
      </div>

      {isVideo && (
        <p className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-700 dark:text-amber-400">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />

          <span>
            Video recordings take a little longer because the recording is
            first converted to audio before transcription.
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
        {steps.map((step, index) => {
          const done = currentIndex !== -1 && index < currentIndex;
          const active = index === currentIndex;

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
              {index > 0 && (
                <span className="text-muted-foreground/40">›</span>
              )}

              {done ? (
                <Check className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    active
                      ? "animate-pulse bg-primary"
                      : "bg-muted-foreground/40"
                  )}
                />
              )}

              {step.label}
            </li>
          );
        })}
      </ol>

      <p className="mt-3 text-xs text-muted-foreground">
        This page updates automatically as your meeting progresses.
      </p>
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
    <Card className="transition-shadow duration-300 hover:shadow-lg">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              {title}
            </p>

            <p className="mt-1 text-3xl font-bold tracking-tight">
              {value}
            </p>

            {trend && (
              <div className="mt-2 flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
                <span className="font-medium">{trend}</span>
                <span className="text-muted-foreground">
                  {trendLabel}
                </span>
              </div>
            )}
          </div>

          <div className={cn("rounded-xl p-3", bgColor, iconColor)}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function calculateTotalHours(
  meetings:
    | {
        id: string;
        title: string;
        status: string;
        created_at: string;
      }[]
    | undefined
): string {
  if (!meetings || meetings.length === 0) {
    return "0h";
  }

  const estimatedHours = meetings.length * 0.5;

  return estimatedHours >= 1
    ? `${estimatedHours.toFixed(1)}h`
    : `${Math.round(estimatedHours * 60)}m`;
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
        "group cursor-pointer transition-all duration-200",
        "border-border/50 hover:border-primary/30 hover:shadow-lg"
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
                <h3 className="truncate font-medium text-foreground">
                  {meeting.title}
                </h3>

                <StatusBadge status={meeting.status} />
              </div>

              <p className="mt-1 text-sm text-muted-foreground">
                {formatDate(meeting.created_at)}
              </p>

              {isProcessing && (
                <MeetingProcessingPanel
                  status={meeting.status}
                  mediaType={
                    meeting.source_media_type === "video"
                      ? "video"
                      : "audio"
                  }
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
            <div className="h-5 w-3/4 rounded bg-muted" />
            <div className="h-4 w-1/2 rounded bg-muted" />
            <div className="h-6 w-1/4 rounded-full bg-muted" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}