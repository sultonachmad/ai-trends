"use client";

/**
 * Call `task` now and then every `intervalMs`, while `enabled` and the tab is visible.
 *
 * - Never overlaps: the next run is scheduled only after the previous one settles.
 * - Pauses when the tab is hidden and runs at once when it becomes visible again.
 * - Stops on unmount. A failing run is reported to `onError` and polling continues.
 * - Restarts, running at once, whenever `restartKey` changes (e.g. a new filter).
 */

import { useEffect, useRef } from "react";

export function usePolling(
  task: () => Promise<void>,
  intervalMs: number,
  enabled: boolean = true,
  onError?: (error: unknown) => void,
  restartKey?: string | number | null,
): void {
  const taskRef = useRef(task);
  const errorRef = useRef(onError);

  useEffect(() => {
    taskRef.current = task;
    errorRef.current = onError;
  }, [task, onError]);

  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let running = false;

    const run = async () => {
      if (stopped || running || document.hidden) return;
      running = true;
      try {
        await taskRef.current();
      } catch (error) {
        errorRef.current?.(error);
      } finally {
        running = false;
        if (!stopped) timer = setTimeout(run, intervalMs);
      }
    };

    const onVisibility = () => {
      if (document.hidden) return;
      clearTimeout(timer);
      void run();
    };

    void run();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [intervalMs, enabled, restartKey]);
}
