"use client";
// Meeting detail page: transcript, summary, and action items.

import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { usePageTitle } from "@/lib/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DeleteMeetingDialog } from "@/components/meetings/delete-meeting-dialog";
import { PageContainer } from "@/components/layout";
import { formatDateTime } from "@/lib/utils";
import {
  IN_PROGRESS_STATUSES,
  MeetingProcessingPanel,
  StatusBadge,
} from "@/app/(dashboard)/dashboard/components";
import { ChevronLeft, Loader2 } from "lucide-react";

type Workspace = {
  id: string;
  name: string;
  role: string;
};

type ActionItem = {
  id: string;
  description: string;
  owner: string | null;
  due_date: string | null;
};

type MeetingDetail = {
  id: string;
  title: string;
  status:
    | "pending"
    | "validating"
    | "converting"
    | "transcribing"
    | "summarizing"
    | "ready"
    | "failed";
  created_at: string;
  transcript_text: string | null;
  summary_text: string | null;
  error_message: string | null;
  action_items: ActionItem[];
  source_media_type: string;
};

function MeetingDetailSkeleton() {
  return (
    <div className="mt-4">
      <Skeleton className="h-8 w-2/3 mb-2" />
      <Skeleton className="h-4 w-1/3 mb-6" />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-24" />
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function MeetingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: meetingId } = use(params);
  const { isCheckingAuth } = useRequireAuth();
  const router = useRouter();
  usePageTitle("Meeting — MeetMind");

  const {
    data: workspaces,
    isLoading: workspacesLoading,
    isError: workspacesError,
    refetch: refetchWorkspaces,
    isRefetching: workspacesRefetching,
  } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await apiClient.get<Workspace[]>("/api/v1/workspaces");
      return response.data;
    },
    enabled: !isCheckingAuth,
  });

  const workspaceId = workspaces?.[0]?.id;

  const {
    data: meeting,
    isLoading: meetingLoading,
    isError: meetingError,
    refetch: refetchMeeting,
    isRefetching: meetingRefetching,
  } = useQuery({
    queryKey: ["meeting", workspaceId, meetingId],
    queryFn: async () => {
      const response = await apiClient.get<MeetingDetail>(
        `/api/v1/workspaces/${workspaceId}/meetings/${meetingId}`
      );
      return response.data;
    },
    enabled: !!workspaceId && !!meetingId,
    refetchInterval: (query) => {
      const current = query.state.data as MeetingDetail | undefined;
      return current && IN_PROGRESS_STATUSES.includes(current.status) ? 5000 : false;
    },
  });
if (isCheckingAuth || workspacesLoading) {
    return (
      <PageContainer>
        <div className="flex h-[60vh] items-center justify-center">
          <div className="text-center">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-3 border-primary border-t-transparent" />
            <p className="mt-4 text-muted-foreground">Loading meeting...</p>
          </div>
        </div>
      </PageContainer>
    );
  }

  if (workspacesError || !workspaceId) {
    return (
      <PageContainer>
        <div className="flex h-[60vh] items-center justify-center">
          <div className="text-center">
            <p className="text-red-600">Couldn&apos;t load your account.</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => refetchWorkspaces()}
              disabled={workspacesRefetching}
            >
              {workspacesRefetching ? "Retrying..." : "Retry"}
            </Button>
          </div>
        </div>
      </PageContainer>
    );
  }

  return (
<PageContainer maxWidth="5xl">
      <Link
        href="/dashboard/meetings"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mt-2"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to meetings
      </Link>

      {meetingLoading && <MeetingDetailSkeleton />}

      {meetingError && !meetingLoading && (
        <div className="mt-4 flex flex-col items-start gap-3">
          <p className="text-red-600">Couldn&apos;t load this meeting.</p>
          <Button
            variant="outline"
            onClick={() => refetchMeeting()}
            disabled={meetingRefetching}
          >
            {meetingRefetching ? "Retrying..." : "Retry"}
          </Button>
        </div>
      )}

      {meeting && (
        <div className="mt-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-semibold cursor-text">{meeting.title}</h1>
                <StatusBadge status={meeting.status} />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {formatDateTime(meeting.created_at)}
              </p>
            </div>
            <DeleteMeetingDialog
              meetingId={meeting.id}
              meetingTitle={meeting.title}
              workspaceId={workspaceId}
              onDeleted={() => router.push("/dashboard/meetings")}
              className="shrink-0 self-start text-muted-foreground hover:text-destructive"
            />
          </div>
{IN_PROGRESS_STATUSES.includes(meeting.status) && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  Processing your meeting
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <MeetingProcessingPanel
                  status={meeting.status}
                  mediaType={meeting.source_media_type === "video" ? "video" : "audio"}
                />
                <p className="mt-3 text-xs text-muted-foreground">
                  This page updates automatically as progress is made.
                </p>
              </CardContent>
            </Card>
          )}

          {meeting.status === "failed" && (
            <Card className="mt-6 border-destructive/30">
              <CardHeader>
                <CardTitle className="text-base text-destructive">
                  Processing failed
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-start gap-3 text-sm text-muted-foreground">
                <span>
                  {meeting.error_message ||
                    "Something went wrong while processing this meeting."}
                </span>
                <Button variant="outline" size="sm" onClick={() => refetchMeeting()}>
                  {meetingRefetching ? "Retrying..." : "Retry"}
                </Button>
              </CardContent>
            </Card>
          )}

          {meeting.status === "ready" && (
            <div className="mt-6 flex flex-col gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Summary</CardTitle>
                </CardHeader>
                <CardContent className="text-sm whitespace-pre-wrap cursor-text">
                  {meeting.summary_text || "No summary available."}
                </CardContent>
              </Card>

              {meeting.action_items.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Action items</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="flex flex-col gap-3 text-sm">
                      {meeting.action_items.map((item) => (
                        <li
                          key={item.id}
                          className="border-b pb-2 last:border-b-0 last:pb-0"
                        >
                          <p className="cursor-text">{item.description}</p>
                          {(item.owner || item.due_date) && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {item.owner && <span>Owner: {item.owner}</span>}
                              {item.owner && item.due_date && <span> · </span>}
                              {item.due_date && <span>Due: {item.due_date}</span>}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Transcript</CardTitle>
                </CardHeader>
                <CardContent className="text-sm whitespace-pre-wrap cursor-text">
                  {meeting.transcript_text || "No transcript available."}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
