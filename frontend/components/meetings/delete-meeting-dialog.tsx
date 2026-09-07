"use client";
// Confirmation dialog for deleting a meeting.

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function DeleteMeetingDialog({
  meetingId,
  meetingTitle,
  workspaceId,
  onDeleted,
  className,
}: {
  meetingId: string;
  meetingTitle: string;
  workspaceId: string;
  onDeleted?: () => void;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirmDelete() {
    if (deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await apiClient.delete(`/api/v1/workspaces/${workspaceId}/meetings/${meetingId}`);
      await queryClient.invalidateQueries({ queryKey: ["meetings", workspaceId] });
      setOpen(false);
      toast.success(`Deleted "${meetingTitle}"`);
      onDeleted?.();
    } catch {
      const message = "Failed to delete this meeting. Please try again.";
      setError(message);
      toast.error(message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {

        if (!deleting) {
          setOpen(next);
          setError(null);
        }
      }}
    >
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            className={className}
            aria-label={`Delete meeting ${meetingTitle}`}
          />
        }
      >
        <Trash2 className="h-4 w-4" />
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete meeting</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &ldquo;{meetingTitle}&rdquo;? This
            permanently removes the recording, transcript, summary, and action
            items. This action can&apos;t be undone.
          </DialogDescription>
        </DialogHeader>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
