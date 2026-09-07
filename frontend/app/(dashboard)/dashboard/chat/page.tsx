"use client";
// Chat page: conversation UI against multi-meeting RAG.

import {
  useState,
  useEffect,
  useRef,
  type KeyboardEvent,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { usePageTitle } from "@/lib/hooks";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronUp,
  X,
  MessageSquare,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

type ChatSource = {
  meeting_id: string;
  meeting_title: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
};

type ChatSession = {
  id: string;
  title: string;
  updated_at: string;
};

type ChatMeeting = {
  id: string;
  title: string;
  created_at: string;
  summary_text: string | null;
};

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="text-sm leading-relaxed break-words min-w-0 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-2 flex flex-col gap-1">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-2 flex flex-col gap-1">
              {children}
            </ol>
          ),
          h1: ({ children }) => (
            <h1 className="text-base font-semibold mb-2 mt-3">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-semibold mb-2 mt-3">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold mb-1 mt-2">{children}</h3>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto mb-2">
              <table className="border-collapse text-xs w-full">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border px-2 py-1 bg-muted text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border px-2 py-1 align-top">{children}</td>
          ),
          code: ({ children }) => (
            <code className="bg-muted px-1 py-0.5 rounded text-xs">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}
function MeetingCatalog({
  meetings,
  selectedMeetingIds,
  onToggleMeeting,
  onClearAll,
}: {
  meetings: ChatMeeting[];
  selectedMeetingIds: string[];
  onToggleMeeting: (id: string) => void;
  onClearAll: () => void;
}) {
  if (meetings.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No completed meetings yet. Upload a recording to get started.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Available meetings</h3>
        {selectedMeetingIds.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearAll}
            className="text-xs h-6 px-2"
          >
            <X className="w-3 h-3 mr-1" />
            Clear all
          </Button>
        )}
      </div>
      <ScrollArea className="max-h-[200px] flex flex-col gap-1">
        {meetings.map((meeting) => {
          const isSelected = selectedMeetingIds.includes(meeting.id);
          return (
            <Button
              key={meeting.id}
              variant={isSelected ? "default" : "outline"}
              className="w-full justify-start text-left h-auto py-2 px-3 gap-2"
              onClick={() => onToggleMeeting(meeting.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{meeting.title}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {new Date(meeting.created_at).toLocaleDateString()}
                </p>
                {meeting.summary_text && (
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                    {meeting.summary_text}
                  </p>
                )}
              </div>
              {isSelected && <MessageSquare className="w-4 h-4 text-primary" />}
            </Button>
          );
        })}
      </ScrollArea>
    </div>
  );
}

function SelectedMeetingsBar({
  meetings,
  selectedMeetingIds,
  onRemoveMeeting,
}: {
  meetings: ChatMeeting[];
  selectedMeetingIds: string[];
  onRemoveMeeting: (id: string) => void;
}) {
  const selected = meetings.filter((m) => selectedMeetingIds.includes(m.id));
  if (selected.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mb-4 p-3 bg-muted/50 rounded-lg">
      <span className="text-xs text-muted-foreground mr-2">Context:</span>
      {selected.map((meeting) => (
        <Badge key={meeting.id} variant="secondary" className="gap-1">
          {meeting.title}
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 p-0"
            onClick={() => onRemoveMeeting(meeting.id)}
          >
            <X className="w-3 h-3" />
          </Button>
        </Badge>
      ))}
    </div>
  );
}
function relativeDayLabel(date: Date) {
  const now = new Date();
  const startOfDay = (d: Date) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(date)) / 86400000);
  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays <= 7) return "Previous 7 days";
  return "Older";
}

const GROUP_ORDER = ["Today", "Yesterday", "Previous 7 days", "Older"];

function groupSessions(sessions: ChatSession[]) {
  const map = new Map<string, ChatSession[]>();
  const sorted = [...sessions].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );
  for (const s of sorted) {
    const label = relativeDayLabel(new Date(s.updated_at));
    const arr = map.get(label) ?? [];
    arr.push(s);
    map.set(label, arr);
  }
  return GROUP_ORDER.filter((label) => map.has(label)).map((label) => ({
    label,
    items: map.get(label)!,
  }));
}

function ChatSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNewChat,
  collapsed,
  onToggleCollapsed,
  loading,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  loading: boolean;
}) {
  if (collapsed) {
    return (
      <aside className="flex h-full w-12 shrink-0 flex-col items-center border-r border-border bg-card py-3">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onToggleCollapsed}
          className="mb-2"
          aria-label="Expand chat history"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onNewChat}
          aria-label="New chat"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </aside>
    );
  }
  const groups = groupSessions(sessions);
  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-3">
        <h2 className="px-1 text-sm font-semibold truncate">Chat history</h2>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onToggleCollapsed}
          aria-label="Collapse chat history"
        >
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>
      <div className="px-3 py-3">
        <Button
          variant="secondary"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={onNewChat}
        >
          <Plus className="h-4 w-4" />
          New chat
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="px-2 pb-4">
          {loading && (
            <p className="px-2 py-1 text-xs text-muted-foreground">Loading…</p>
          )}
          {!loading && sessions.length === 0 && (
            <p className="px-2 py-1 text-xs text-muted-foreground">No chats yet.</p>
          )}
          {groups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="mb-1 px-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {group.label}
              </p>
              <div className="flex flex-col gap-0.5">
                {group.items.map((session) => {
                  const active = session.id === activeSessionId;
                  return (
                    <button
                      key={session.id}
                      type="button"
                      onClick={() => onSelect(session.id)}
                      className={cn(
                        "w-full rounded-lg px-2 py-2 text-left text-sm transition-colors select-none",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        active
                          ? "bg-primary/10 text-foreground"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      )}
                    >
                      <span className="block font-medium truncate">
                        {session.title || "Untitled chat"}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {new Date(session.updated_at).toLocaleString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
}
export default function ChatPage() {
  const { isCheckingAuth } = useRequireAuth();
  const queryClient = useQueryClient();
  usePageTitle("Chat — MeetMind");

  const {
    data: workspaces,
    isLoading: workspacesLoading,
    isError: workspacesError,
    refetch: refetchWorkspaces,
    isRefetching: workspacesRefetching,
  } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/workspaces");
      return response.data;
    },
    enabled: !isCheckingAuth,
  });

  const workspaceId = workspaces?.[0]?.id;

  const { data: chatMeetings = [] } = useQuery({
    queryKey: ["chat-meetings", workspaceId],
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/v1/workspaces/${workspaceId}/chat/meetings`
      );
      return response.data;
    },
    enabled: !!workspaceId,
  });

  const {
    data: sessions = [],
    isLoading: sessionsLoading,
  } = useQuery({
    queryKey: ["chat-sessions", workspaceId],
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/v1/workspaces/${workspaceId}/chat/sessions`
      );
      return response.data;
    },
    enabled: !!workspaceId,
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const [selectedMeetingIds, setSelectedMeetingIds] = useState<string[]>([]);
  const [showCatalog, setShowCatalog] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
async function sendMessage() {
    if (!input.trim() || !workspaceId || sending) return;
    const question = input.trim();
    setInput("");
    setSending(true);
    setError(null);
    setRateLimited(false);

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: question,
      },
    ]);
    try {
      const res = await apiClient.post(`/api/v1/workspaces/${workspaceId}/chat`, {
        question,
        session_id: sessionId,
        meeting_ids: selectedMeetingIds.length > 0 ? selectedMeetingIds : undefined,
      });
      const { session_id, answer, sources } = res.data;
      setSessionId(session_id);

      await queryClient.invalidateQueries({
        queryKey: ["chat-sessions", workspaceId],
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: answer,
          sources,
        },
      ]);
    } catch (err) {

      const error = err as {
        response?: {
          status?: number;
          data?: { detail?: string; retry_after_seconds?: number };
        };
      };
      if (error.response?.status === 429) {
        setRateLimited(true);
        const retry = error.response?.data?.retry_after_seconds ?? 60;
        setRetryAfter(retry);
        setError(`Rate limited. Try again in ${retry} seconds.`);
      } else {
        const detail =
          error.response?.data?.detail ?? "Something went wrong. Please try again.";
        setError(detail);
        toast.error(typeof detail === "string" ? detail : "Something went wrong. Please try again.");
      }
      setInput(question);
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function toggleMeeting(id: string) {
    setSelectedMeetingIds((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  }

  function removeMeeting(id: string) {
    setSelectedMeetingIds((prev) => prev.filter((m) => m !== id));
  }

  function clearAllMeetings() {
    setSelectedMeetingIds([]);
  }

  async function openSession(id: string) {
    if (id === sessionId) return;
    if (!workspaceId) return;
    setLoadingMessages(true);
    setError(null);
    try {
      const response = await apiClient.get(
        `/api/v1/workspaces/${workspaceId}/chat/sessions/${id}/messages`
      );
      setSessionId(id);
      setMessages(
        response.data.map(
          (m: { role: string; content: string; sources?: ChatSource[] }) => ({
            role: m.role === "assistant" ? "assistant" : "user",
            content: m.content,
            sources: m.sources ?? undefined,
          })
        )
      );
    } catch {
      setError("Couldn't load that conversation.");
      toast.error("Couldn't load that conversation.");
    } finally {
      setLoadingMessages(false);
    }
  }

  function newChat() {
    setSessionId(null);
    setMessages([]);
    setError(null);
    setInput("");
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, sending, loadingMessages]);

  if (isCheckingAuth || workspacesLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  }

  if (workspacesError || !workspaceId) {
    return (
      <div className="max-w-2xl mx-auto p-8 flex flex-col items-start gap-3">
        <p className="text-red-600">Couldn&apos;t load your account.</p>
        <Button
          variant="outline"
          onClick={() => refetchWorkspaces()}
          disabled={workspacesRefetching}
        >
          {workspacesRefetching ? "Retrying..." : "Retry"}
        </Button>
      </div>
    );
  }

  return (
<div className="flex h-[calc(100vh-1rem)] overflow-hidden lg:h-screen">
      <div className="md:hidden">
        <button
          type="button"
          onClick={() => setMobileHistoryOpen(true)}
          aria-label="Open chat history"
          className="fixed left-4 top-16 z-30 flex h-10 w-10 items-center justify-center rounded-xl bg-card border border-border shadow-lg text-foreground"
        >
          <PanelLeftOpen className="h-5 w-5" />
        </button>
        {mobileHistoryOpen && (
          <div
            className="fixed inset-0 z-40 md:hidden"
            onClick={() => setMobileHistoryOpen(false)}
          >
            <div
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
              onClick={() => setMobileHistoryOpen(false)}
              aria-hidden="true"
            />
            <div className="absolute inset-y-0 left-0 z-10 w-72 bg-card shadow-xl">
              <ChatSidebar
                sessions={sessions}
                activeSessionId={sessionId}
                onSelect={(id) => {
                  openSession(id);
                  setMobileHistoryOpen(false);
                }}
                onNewChat={() => {
                  newChat();
                  setMobileHistoryOpen(false);
                }}
                collapsed={false}
                onToggleCollapsed={() => setMobileHistoryOpen(false)}
                loading={sessionsLoading}
              />
            </div>
          </div>
        )}
      </div>

      <div className="hidden md:flex">
        <ChatSidebar
          sessions={sessions}
          activeSessionId={sessionId}
          onSelect={openSession}
          onNewChat={newChat}
          collapsed={!sidebarOpen}
          onToggleCollapsed={() => setSidebarOpen((o) => !o)}
          loading={sessionsLoading}
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col p-4">
        <div className="mx-auto flex w-full max-w-2xl min-h-0 flex-1 flex-col">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-semibold flex items-center gap-2">
              <MessageSquare className="w-5 h-5" />
              Meeting Chat
            </h1>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCatalog(!showCatalog)}
              className="gap-1"
            >
              {showCatalog ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
              Meetings
            </Button>
          </div>
          {showCatalog && (
            <div className="mb-4">
              <MeetingCatalog
                meetings={chatMeetings}
                selectedMeetingIds={selectedMeetingIds}
                onToggleMeeting={toggleMeeting}
                onClearAll={clearAllMeetings}
              />
            </div>
          )}
          <SelectedMeetingsBar
            meetings={chatMeetings}
            selectedMeetingIds={selectedMeetingIds}
            onRemoveMeeting={removeMeeting}
          />
          {rateLimited && retryAfter && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex items-center justify-between">
              <span>
                Rate limited. Please wait {retryAfter}s before sending another
                message.
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setRateLimited(false);
                  setRetryAfter(null);
                }}
              >
                Dismiss
              </Button>
            </div>
          )}
          {error && !rateLimited && (
            <p className="text-sm text-destructive mb-2">{error}</p>
          )}
<div className="flex-1 min-h-0 mb-4">
            <ScrollArea className="h-full">
              <div className="space-y-4 p-1">
                {messages.length === 0 && !loadingMessages && (
                  <p className="text-sm text-muted-foreground">
                    Ask a question about your meetings to get started.
                  </p>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={m.role === "user" ? "text-right" : "text-left"}
                  >
                    {m.role === "user" ? (
                      <div className="inline-block rounded-lg px-3 py-2 max-w-[70%] text-sm bg-primary text-primary-foreground whitespace-pre-wrap break-words cursor-text">
                        {m.content}
                      </div>
                    ) : (
                      <div className="inline-block rounded-lg px-3 py-2 max-w-[80%] bg-muted text-left break-words cursor-text">
                        <MarkdownContent content={m.content} />
                      </div>
                    )}
                    {m.sources && m.sources.length > 0 && (
                      <div className="mt-1 text-xs text-muted-foreground space-x-2">
                        {m.sources.map((s) => (
                          <span key={s.meeting_id}>📎 {s.meeting_title}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {sending && (
                  <div className="text-left">
                    <div className="inline-block rounded-lg px-3 py-2 bg-muted text-sm text-muted-foreground">
                      Thinking…
                    </div>
                  </div>
                )}
                {loadingMessages && (
                  <div className="text-left">
                    <div className="inline-block rounded-lg px-3 py-2 bg-muted text-sm text-muted-foreground">
                      Loading conversation…
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </ScrollArea>
          </div>
          <div className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={rateLimited ? `Wait ${retryAfter}s…` : "Ask about your meetings…"}
              rows={2}
              disabled={sending || rateLimited}
            />
            <Button
              onClick={sendMessage}
              disabled={sending || !input.trim() || rateLimited}
            >
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
