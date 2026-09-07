"use client";
// Settings page: account and workspace management.

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";
import { useRequireAuth } from "@/lib/use-require-auth";
import { usePageTitle } from "@/lib/hooks";
import { PageContainer, PageHeader, Section } from "@/components/layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { User, LogOut, Building2 } from "lucide-react";

type AuthUser = {
  id: string;
  email: string;
  full_name: string | null;
};

type Workspace = {
  id: string;
  name: string;
  role: string;
};

export default function SettingsPage() {
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);
  const { isCheckingAuth } = useRequireAuth();
  usePageTitle("Settings — MeetMind");

  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await apiClient.get<AuthUser>("/api/v1/auth/me");
      return response.data;
    },
    enabled: !isCheckingAuth,
    retry: false,
  });

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await apiClient.get<Workspace[]>("/api/v1/workspaces");
      return response.data;
    },
    enabled: !isCheckingAuth,
  });

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        description="Manage your account and workspace."
      />

      <Section spacing="normal" className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <User className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold">Account</h3>
                <p className="text-sm text-muted-foreground">
                  {user?.full_name || "Logged in"}
                </p>
              </div>
            </div>
            <dl className="mt-6 space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="font-medium">{user?.email || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Workspace</dt>
                <dd className="font-medium">{workspaces?.[0]?.name || "—"}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <h3 className="flex items-center gap-2 font-semibold">
              <Building2 className="h-5 w-5" /> Workspaces
            </h3>
            <ul className="mt-4 space-y-2 text-sm">
              {(workspaces ?? []).map((w) => (
                <li
                  key={w.id}
                  className="flex items-center justify-between rounded-lg border px-3 py-2"
                >
                  <span className="font-medium">{w.name}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs capitalize">
                    {w.role}
                  </span>
                </li>
              ))}
            </ul>
            <Button variant="outline" onClick={handleLogout} className="mt-6 w-full">
              <LogOut className="mr-1 h-4 w-4" /> Sign out
            </Button>
          </CardContent>
        </Card>
      </Section>
    </PageContainer>
  );
}
