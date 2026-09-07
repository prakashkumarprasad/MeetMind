"use client";
// App navigation sidebar with workspace name and links.

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  User,
  LogOut,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useMediaQuery } from "@/lib/hooks";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Meetings", href: "/dashboard/meetings", icon: FileText },
  { name: "Chat", href: "/dashboard/chat", icon: MessageSquare },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
];

type AuthUser = {
  id: string;
  email: string;
  full_name: string | null;
};

export function Sidebar({
  open = false,
  onClose,
}: {
  open?: boolean;
  onClose?: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const response = await apiClient.get<AuthUser>("/api/v1/auth/me");
      return response.data;
    },
    retry: false,
  });

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const effectiveCollapsed = isDesktop && collapsed;

  const handleNavigate = () => {
    if (!isDesktop) onClose?.();
  };

  return (
    <motion.aside
      initial={false}
      animate={{ width: effectiveCollapsed ? 72 : 260 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className={cn(
        "fixed left-0 top-0 z-40 h-screen bg-sidebar border-r border-sidebar-border",
        "flex flex-col transition-all duration-300",
        effectiveCollapsed ? "w-[72px]" : "w-[260px]",
        "lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <SidebarBrand
        collapsed={effectiveCollapsed}
        onToggle={() => setCollapsed((c) => !c)}
        onNavigate={handleNavigate}
      />
      <SidebarNav
        collapsed={effectiveCollapsed}
        pathname={pathname}
        onNavigate={handleNavigate}
      />
      <SidebarUser collapsed={effectiveCollapsed} user={user} onLogout={handleLogout} />
    </motion.aside>
  );
}

function SidebarBrand({
  collapsed,
  onToggle,
  onNavigate,
}: {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate: () => void;
}) {
  return (
    <div className="flex h-16 items-center justify-between px-4 border-b border-sidebar-border">
      <motion.div
        initial={false}
        animate={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : "auto" }}
        transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
        className={cn("flex items-center gap-2 overflow-hidden", collapsed && "w-0")}
      >
        <Link
          href="/dashboard"
          onClick={onNavigate}
          className={cn(
            "flex items-center gap-2 rounded-lg focus-visible:outline-none",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          )}
          aria-label="Go to dashboard"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <span className="text-xl font-bold">M</span>
          </div>
          <span className="font-heading text-lg font-semibold text-sidebar-foreground whitespace-nowrap select-none">
            MeetMind
          </span>
        </Link>
      </motion.div>
      <button
        onClick={onToggle}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground",
          "hover:bg-accent hover:text-accent-foreground transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        )}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </div>
  );
}

function SidebarNav({
  collapsed,
  pathname,
  onNavigate,
}: {
  collapsed: boolean;
  pathname: string;
  onNavigate: () => void;
}) {
  return (
    <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
      <AnimatePresence mode="wait">
        {!collapsed && (
          <motion.div
            key="nav-expanded"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <div className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Main
            </div>
            {navigation.map((item) => (
              <NavItem key={item.name} item={item} pathname={pathname} onNavigate={onNavigate} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {collapsed && (
          <motion.div
            key="nav-collapsed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            {navigation.map((item) => (
              <NavItemCollapsed key={item.name} item={item} pathname={pathname} onNavigate={onNavigate} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

function NavItem({ item, pathname, onNavigate }: { item: typeof navigation[0]; pathname: string; onNavigate: () => void }) {

  const isActive =
    pathname === item.href ||
    (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 select-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isActive
          ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
          : "text-sidebar-foreground/70 hover:bg-accent hover:text-accent-foreground"
      )}
    >
      <item.icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
      <span>{item.name}</span>
      {isActive && (
        <motion.span
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="ml-auto flex h-5 w-5 items-center justify-center"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
        </motion.span>
      )}
    </Link>
  );
}

function NavItemCollapsed({ item, pathname, onNavigate }: { item: typeof navigation[0]; pathname: string; onNavigate: () => void }) {
  const isActive =
    pathname === item.href ||
    (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "relative flex h-10 w-10 items-center justify-center mx-auto rounded-xl transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isActive
          ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
      title={item.name}
    >
      <item.icon className="h-5 w-5" aria-hidden="true" />
    </Link>
  );
}

function SidebarUser({
  collapsed,
  user,
  onLogout,
}: {
  collapsed: boolean;
  user?: { id: string; email: string; full_name: string | null };
  onLogout: () => void;
}) {
  const displayName = user?.full_name || user?.email?.split("@")[0] || "Account";
  const email = user?.email || "";
  return (
    <div className="border-t border-sidebar-border p-3">
      <AnimatePresence mode="wait">
        {!collapsed ? (
          <motion.div
            key="user-expanded"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <div className="flex items-center gap-3 px-2 py-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <User className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-sidebar-foreground truncate select-none">{displayName}</p>
                {email && <p className="text-xs text-muted-foreground truncate select-none">{email}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <Link
                href="/dashboard/settings"
                className={cn(
                  "flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium select-none",
                  "text-muted-foreground hover:text-sidebar-foreground hover:bg-accent",
                  "transition-colors"
                )}
              >
                <Settings className="h-4 w-4" />
                <span>Settings</span>
              </Link>
              <button
                onClick={onLogout}
                className={cn(
                  "flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium select-none",
                  "text-muted-foreground hover:text-destructive hover:bg-destructive/10",
                  "transition-colors"
                )}
              >
                <LogOut className="h-4 w-4" />
                <span>Sign out</span>
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="user-collapsed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex h-10 w-10 items-center justify-center mx-auto rounded-xl bg-primary/10 text-primary">
              <User className="h-5 w-5" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
