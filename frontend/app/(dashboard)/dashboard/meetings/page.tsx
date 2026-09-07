"use client";
// Meetings page: lists meetings and their processing status.

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { usePageTitle } from "@/lib/hooks";
import { PageContainer, PageHeader, Section } from "@/components/layout";
import {
  IN_PROGRESS_STATUSES,
  MeetingCard,
  MeetingCardSkeleton,
} from "../components";
import { FileText } from "lucide-react";

type Workspace = {
  id: string;
  name: string;
  role: string;
};

type Meeting = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  source_media_type?: string;
};

export default function MeetingsPage() {
  const { isCheckingAuth } = useRequireAuth();
  usePageTitle("Meetings — MeetMind");

  const {
    data: workspaces,
    isLoading: workspacesLoading,
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
    data: meetings,
    isLoading: meetingsLoading,
    isError: meetingsError,
  } = useQuery({
    queryKey: ["meetings", workspaceId],
    queryFn: async () => {
      const response = await apiClient.get<Meeting[]>(
        `/api/v1/workspaces/${workspaceId}/meetings`
      );
      return response.data;
    },
    enabled: !!workspaceId,
    refetchInterval: (query) => {
      const current = query.state.data as Meeting[] | undefined;
      return current?.some((m) => IN_PROGRESS_STATUSES.includes(m.status)) ? 5000 : false;
    },
  });

  if (isCheckingAuth || workspacesLoading) {
    return (
      <PageContainer>
        <div className="flex h-[60vh] items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-3 border-primary border-t-transparent" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="Meetings"
        description="Every meeting you've uploaded across your workspace."
      />

      <Section spacing="normal">
        {meetingsLoading && (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <MeetingCardSkeleton key={i} />
            ))}
          </div>
        )}

        {meetingsError && (
          <div className="text-center py-12">
            <div className="mx-auto h-16 w-16 rounded-full bg-destructive/10 flex items-center justify-center">
              <FileText className="h-8 w-8 text-destructive" />
            </div>
            <h3 className="mt-4 text-lg font-medium">Couldn&apos;t load meetings</h3>
            <p className="mt-1 text-muted-foreground">Try refreshing the page.</p>
          </div>
        )}

        {meetings?.length === 0 && !meetingsLoading && !meetingsError && (
          <div className="text-center py-16">
            <div className="mx-auto h-20 w-20 rounded-2xl bg-muted flex items-center justify-center">
              <FileText className="h-10 w-10 text-muted-foreground" />
            </div>
            <h3 className="mt-6 text-xl font-semibold">No meetings yet</h3>
            <p className="mt-2 text-muted-foreground max-w-md mx-auto">
              Upload your first meeting recording from the Dashboard to get started.
            </p>
          </div>
        )}

        {meetings && meetings.length > 0 && (
          <div className="space-y-3">
            {meetings.map((meeting) => (
              <MeetingCard key={meeting.id} meeting={meeting} workspaceId={workspaceId} />
            ))}
          </div>
        )}
      </Section>
    </PageContainer>
  );
}
