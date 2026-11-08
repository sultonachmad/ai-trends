"use client";

import { useState } from "react";

import type { UploadedFile } from "@/lib/upload-client";

interface FileListProps {
  files: UploadedFile[];
  onDelete?: (id: string) => void;
  onDownload?: (id: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${exponent === 0 ? value : value.toFixed(1)} ${units[exponent]}`;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function fileIcon(contentType: string): string {
  if (contentType.startsWith("image/")) return "🖼️";
  if (contentType.startsWith("video/")) return "🎞️";
  if (contentType.startsWith("audio/")) return "🎵";
  if (contentType === "application/pdf") return "📄";
  if (contentType.includes("zip") || contentType.includes("compressed")) return "🗜️";
  if (contentType.startsWith("text/")) return "📝";
  return "📁";
}

/**
 * Renders a list of uploaded files with download/delete actions.
 *
 * Presentational only — `files` is owned by the parent (e.g. fetched via
 * `listFiles()` from `lib/upload-client.ts`). `onDelete` / `onDownload` are
 * expected to update that state and/or call the matching `deleteFile()` /
 * `downloadFile()` client functions; this component does not call the API
 * directly.
 *
 * Delete requires two clicks: the first arms a "Confirm delete?" state for
 * that row, the second (or a click elsewhere / blur) either confirms or
 * cancels it.
 */
export function FileList({ files, onDelete, onDownload }: FileListProps) {
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  if (files.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
        No files uploaded yet.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 dark:divide-gray-800 dark:border-gray-800">
      {files.map((file) => {
        const isPendingDelete = pendingDeleteId === file.id;

        return (
          <li key={file.id} className="flex items-center justify-between gap-4 px-4 py-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="text-xl" aria-hidden="true">
                {fileIcon(file.content_type)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                  {file.name}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {formatBytes(file.size)} • {formatDate(file.uploaded_at)}
                </p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {onDownload && (
                <button
                  type="button"
                  onClick={() => onDownload(file.id)}
                  className="inline-flex items-center rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                >
                  Download
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  onClick={() => {
                    if (isPendingDelete) {
                      setPendingDeleteId(null);
                      onDelete(file.id);
                      return;
                    }
                    setPendingDeleteId(file.id);
                  }}
                  onBlur={() =>
                    setPendingDeleteId((current) => (current === file.id ? null : current))
                  }
                  className={`inline-flex items-center rounded-md border px-3 py-1.5 text-xs font-medium ${
                    isPendingDelete
                      ? "border-red-600 bg-red-600 text-white hover:bg-red-700"
                      : "border-red-300 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/30"
                  }`}
                >
                  {isPendingDelete ? "Confirm delete?" : "Delete"}
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
