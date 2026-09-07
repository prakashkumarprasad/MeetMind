// Dashboard layout wrapping routes with the app PageWrapper.

import { PageWrapper } from "@/components/layout";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PageWrapper>{children}</PageWrapper>;
}
