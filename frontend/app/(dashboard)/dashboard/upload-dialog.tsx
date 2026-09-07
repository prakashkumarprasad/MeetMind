"use client";
// Upload dialog: requests a presigned upload from the API and uploads the file
// straight to S3 with a single multipart/form-data POST (via XMLHttpRequest for
// upload progress + cancel support). No multipart chunking.

import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const SUPPORTED_MIME_TYPES: Record<string, string> = {
  "audio/mpeg": "audio/mpeg",
  "audio/mp3": "audio/mpeg",
  "audio/wav": "audio/wav",
  "audio/x-wav": "audio/wav",
  "audio/mp4": "audio/mp4",
  "audio/x-m4a": "audio/x-m4a",
  "audio/ogg": "audio/ogg",
  "audio/webm": "audio/webm",
  "video/mp4": "video/mp4",
  "video/webm": "video/webm",
  "video/quicktime": "video/quicktime",
};

const MIME_BY_EXTENSION: Record<string, string> = {
  mp3: "audio/mpeg",
  wav: "audio/wav",
  m4a: "audio/mp4",
  ogg: "audio/ogg",
  webm: "audio/webm",
  mp4: "video/mp4",
  mov: "video/quicktime",
};

type UploadResponse = {
  meeting_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
};

function inferContentType(file: File): string | null {
  const fromMime = SUPPORTED_MIME_TYPES[file.type];
  if (fromMime) return fromMime;

  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const fromExt = MIME_BY_EXTENSION[ext];
  if (fromExt) return fromExt;

  return null;
}

function getErrorMessage(error: unknown): string {
  const err = error as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg ?? "Invalid input").join(", ");
  }
  if (typeof detail === "string" && detail) return detail;
  return err?.message || "Upload failed. Please try again.";
}

export function UploadDialog({ workspaceId, className }: { workspaceId: string; className?: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const cancelledRef = useRef(false);

  const resetInputs = () => {
    setFile(null);
    setTitle("");
    setSuccess(null);
    setError(null);
  };

  const handleCancel = () => {
    if (!uploading) return;
    cancelledRef.current = true;
    setStatus("Cancelling...");
    xhrRef.current?.abort();
  };

  const uploadToS3 = (file: File, data: UploadResponse) => {
    return new Promise<void>((resolve, reject) => {
      const formData = new FormData();
      Object.entries(data.upload_fields).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", file, file.name);

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;
      xhr.open("POST", data.upload_url);
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) setProgress(Math.round((evt.loaded / evt.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`Upload failed with status ${xhr.status}.`));
      };
      xhr.onerror = () => reject(new Error("Network error while uploading. Please try again."));
      xhr.onabort = () => reject(new Error("Upload cancelled."));
      xhr.send(formData);
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || uploading) return;

    const contentTypes = inferContentType(file);
    if (!contentTypes) {
      const message =
        "Unsupported file type. Please upload an audio recording (.mp3, .wav, .m4a, .ogg, .webm) or a video (.mp4, .mov, .webm).";
      setError(message);
      toast.error(message);
      return;
    }

    const meetingTitle = title.trim() || file.name.replace(/\.[^.]+$/, "");
    cancelledRef.current = false;

    try {
      setUploading(true);
      setProgress(0);
      setError(null);
      setSuccess(null);
      setStatus("Preparing upload...");

      const { data } = await apiClient.post<UploadResponse>(
        `/api/v1/workspaces/${workspaceId}/meetings`,
        {
          title: meetingTitle,
          file_size_bytes: file.size,
          content_type: contentTypes,
        }
      );

      setStatus("Uploading to storage...");
      await uploadToS3(file, data);

      setStatus("Starting transcription...");
      await apiClient.post(
        `/api/v1/workspaces/${workspaceId}/meetings/${data.meeting_id}/confirm-upload`
      );

      setSuccess(
        `"${meetingTitle}" is uploading. It will be converted to audio shortly.`
      );
      toast.success("Meeting uploaded successfully");
      resetInputs();
      queryClient.invalidateQueries({ queryKey: ["meetings", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
    } catch (err) {
      if (cancelledRef.current) {
        setSuccess(null);
      } else {
        console.error("Upload failed:", err);
        const message = getErrorMessage(err);
        setError(message);
        toast.error(message);
      }
    } finally {
      if (cancelledRef.current) resetInputs();
      setUploading(false);
      setStatus("");
      setProgress(0);
      xhrRef.current = null;
      cancelledRef.current = false;
    }
  };

  return (
    <div className={cn("rounded-lg border border-border bg-background p-6 max-w-md", className)}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Label htmlFor="file-upload" className="block text-sm font-medium">
            Select recording
          </Label>
          <Input
            id="file-upload"
            type="file"
            accept="audio/*,video/*,.mp3,.wav,.m4a,.ogg,.webm,.mp4,.mov"
            onChange={(e) => {
              const selected = e.target.files?.[0] ?? null;
              setFile(selected);
              setError(null);
              setSuccess(null);
              if (selected && !title.trim()) {
                setTitle(selected.name.replace(/\.[^.]+$/, ""));
              }
            }}
            className="mt-1 block w-full rounded-md border-input bg-background px-3.5 pb-2.5 text-sm ring-offset-background file:cursor-pointer file:select-none file:rounded-md"
          />
        </div>

        <div>
          <Label htmlFor="meeting-title" className="block text-sm font-medium">
            Meeting title
          </Label>
          <Input
            id="meeting-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Weekly product sync"
            className="mt-1 block w-full rounded-md border-input bg-background px-3.5 py-2 text-sm"
          />
        </div>

        {uploading && (
          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>{status || "Uploading to storage..."}</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="mt-2 flex justify-end">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                disabled={!uploading}
                className="text-muted-foreground hover:text-destructive"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {error && !uploading && <p className="text-sm text-destructive">{error}</p>}
        {success && !uploading && (
          <p className="text-sm text-green-600 dark:text-green-400">{success}</p>
        )}

        <Button type="submit" disabled={!file || uploading} className="w-full">
          {uploading ? (
            <>
              <svg
                className="mr-2 h-4 w-4 animate-spin text-current"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                />
              </svg>
              Uploading...
            </>
          ) : (
            "Upload"
          )}
        </Button>
      </form>
    </div>
  );
}
