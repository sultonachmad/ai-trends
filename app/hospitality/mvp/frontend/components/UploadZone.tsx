"use client";

import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from "react";

type ZoneState = "idle" | "dragging" | "uploading" | "error";

interface UploadZoneProps {
  /** Called with the selected/dropped file. Throw (or reject) to surface the error state. */
  onUpload: (file: File) => Promise<void>;
  /** Native `<input accept>` filter, e.g. `"image/*,.pdf"`. Omit to accept any file. */
  accept?: string;
  /** Client-side size guard, in megabytes. The server must still validate independently. */
  maxSizeMB?: number;
  /** Zone call-to-action text. */
  label?: string;
}

const DEFAULT_MAX_SIZE_MB = 50;

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${exponent === 0 ? value : value.toFixed(1)} ${units[exponent]}`;
}

/**
 * Drag-and-drop (or click-to-browse) file upload zone.
 *
 * This component owns file selection, client-side size validation, and
 * visual state only — the network call is delegated to `onUpload` (see
 * `lib/upload-client.ts`'s `uploadFile` for a ready-made implementation).
 * Because the upload call is caller-supplied, progress is shown as an
 * indeterminate bar rather than tracked byte-for-byte; wire an XHR-based
 * `onUpload` with `progress` events instead if exact progress is required.
 */
export function UploadZone({
  onUpload,
  accept,
  maxSizeMB = DEFAULT_MAX_SIZE_MB,
  label = "Drag and drop a file here, or click to browse",
}: UploadZoneProps) {
  const [state, setState] = useState<ZoneState>("idle");
  const [activeFile, setActiveFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      const maxBytes = maxSizeMB * 1024 * 1024;
      if (file.size > maxBytes) {
        setActiveFile(file);
        setErrorMessage(`"${file.name}" exceeds the ${maxSizeMB} MB limit`);
        setState("error");
        return;
      }

      setActiveFile(file);
      setErrorMessage(null);
      setState("uploading");

      try {
        await onUpload(file);
        setState("idle");
        setActiveFile(null);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Upload failed");
        setState("error");
      }
    },
    [maxSizeMB, onUpload],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      if (state === "uploading") return;
      const file = event.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile, state],
  );

  const handleDragOver = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      if (state !== "uploading") setState("dragging");
    },
    [state],
  );

  const handleDragLeave = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setState((current) => (current === "dragging" ? "idle" : current));
    },
    [],
  );

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = ""; // allow re-selecting the same file consecutively
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  const openBrowser = useCallback(() => {
    if (state !== "uploading") inputRef.current?.click();
  }, [state]);

  const isUploading = state === "uploading";
  const isError = state === "error";
  const isDragging = state === "dragging";

  const borderClasses = isError
    ? "border-red-400 bg-red-50 dark:border-red-500 dark:bg-red-950/30"
    : isDragging
      ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/30"
      : "border-gray-300 bg-gray-50 hover:border-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-gray-600";

  return (
    <div
      role="button"
      tabIndex={0}
      aria-busy={isUploading}
      onClick={openBrowser}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openBrowser();
        }
      }}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`flex min-h-[160px] w-full flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
        isUploading ? "cursor-wait" : "cursor-pointer"
      } ${borderClasses}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleInputChange}
        disabled={isUploading}
      />

      {isUploading && activeFile ? (
        <div className="w-full max-w-xs space-y-2">
          <p className="truncate text-sm font-medium text-gray-700 dark:text-gray-200">
            {activeFile.name}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">{formatBytes(activeFile.size)}</p>
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-blue-600" />
          </div>
        </div>
      ) : (
        <>
          <svg
            className={`h-8 w-8 ${isError ? "text-red-500" : "text-gray-400 dark:text-gray-500"}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
            />
          </svg>
          <p
            className={`text-sm ${
              isError ? "text-red-600 dark:text-red-400" : "text-gray-600 dark:text-gray-400"
            }`}
          >
            {isError && errorMessage ? errorMessage : label}
          </p>
          {isError && activeFile && (
            <p className="text-xs text-gray-500 dark:text-gray-500">
              {activeFile.name} — {formatBytes(activeFile.size)}
            </p>
          )}
          {!isError && (
            <p className="text-xs text-gray-400 dark:text-gray-600">Max {maxSizeMB} MB</p>
          )}
        </>
      )}
    </div>
  );
}
