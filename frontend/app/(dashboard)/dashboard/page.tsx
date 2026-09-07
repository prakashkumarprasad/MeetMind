"use client";
// Dashboard home page.

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";
import { useRequireAuth } from "@/lib/use-require-auth";
import { usePageTitle } from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { UploadDialog } from "./upload-dialog";
import { PageContainer, PageHeader, Section } from "@/components/layout";
import { ChevronDown, FileText, MessageSquare, LayoutDashboard } from "lucide-react";
import {
  IN_PROGRESS_STATUSES,
  StatCard,
  calculateTotalHours,
  MeetingCard,
  MeetingCardSkeleton,
} from "./components";

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

export default function DashboardPage() {
  const { isCheckingAuth } = useRequireAuth();
  const router = useRouter();
  usePageTitle("Dashboard — MeetMind");
  const logout = useAuthStore((state) => state.logout);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const {
    data: workspaces,
    isLoading: workspacesLoading,
    isError: workspacesError,
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
      const currentMeetings = query.state.data as Meeting[] | undefined;
      const stillProcessing = currentMeetings?.some((m) =>
        IN_PROGRESS_STATUSES.includes(m.status)
      );
      return stillProcessing ? 5000 : false;
    },
  });

  if (isCheckingAuth || workspacesLoading) {
    return (
      <PageContainer>
        <div className="flex h-[60vh] items-center justify-center">
          <div className="text-center">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-3 border-primary border-t-transparent" />
            <p className="mt-4 text-muted-foreground">Loading your workspace...</p>
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
            <div className="mx-auto h-16 w-16 rounded-full bg-destructive/10 flex items-center justify-center">
              <FileText className="h-8 w-8 text-destructive" />
            </div>
            <h2 className="mt-4 text-xl font-semibold">Couldn&apos;t load your account</h2>
            <p className="mt-2 text-muted-foreground">Try refreshing the page or sign in again.</p>
            <Button onClick={handleLogout} className="mt-6" variant="outline">
              Sign out
            </Button>
          </div>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="7xl">
      <PageHeader
        title="Dashboard"
        description="Overview of your meetings and workspace activity"
        action={
          <UploadDialog workspaceId={workspaceId} />
        }
      />

      <Section spacing="normal">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Meetings"
            value={meetings?.length || 0}
            icon={MessageSquare}
            trend="+12%"
            trendLabel="vs last month"
          />
          <StatCard
            title="Hours Recorded"
            value={calculateTotalHours(meetings)}
            icon={LayoutDashboard}
            trend="+8%"
            trendLabel="vs last month"
          />
          <StatCard
            title="Processing"
            value={meetings?.filter(m => IN_PROGRESS_STATUSES.includes(m.status)).length || 0}
            icon={FileText}
            iconColor="text-yellow-500"
            bgColor="bg-yellow-500/10"
          />
          <StatCard
            title="Completed"
            value={meetings?.filter((m) => ["ready", "completed"].includes(m.status)).length || 0}
            icon={FileText}
            iconColor="text-green-500"
            bgColor="bg-green-500/10"
          />
        </div>
      </Section>

      <Section spacing="compact">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h2 className="text-lg font-semibold">Recent Meetings</h2>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="hidden sm:flex">
              <ChevronDown className="h-4 w-4 mr-1" /> Sort by date
            </Button>
            <Button variant="outline" size="sm" className="hidden sm:flex">
              <ChevronDown className="h-4 w-4 mr-1" /> All statuses
            </Button>
          </div>
        </div>

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
              <MessageSquare className="h-10 w-10 text-muted-foreground" />
            </div>
            <h3 className="mt-6 text-xl font-semibold">No meetings yet</h3>
            <p className="mt-2 text-muted-foreground max-w-md mx-auto">
              Upload your first meeting recording to get started with AI-powered summaries,
              action items, and chat.
            </p>
            <UploadDialog workspaceId={workspaceId} className="mt-6" />
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
