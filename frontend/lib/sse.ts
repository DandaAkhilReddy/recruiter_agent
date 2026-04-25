"use client";

import { useEffect, useRef } from "react";

import type { SseEvent } from "@/types/api";

/** Subscribe to the recruiter-agent SSE stream for a single job.
 *  Calls `onEvent` for each parsed event; closes on `done` or unmount. */
export function useJobStream(url: string | null, onEvent: (e: SseEvent) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    if (!url) return;
    const es = new EventSource(url);
    const handle = (raw: MessageEvent) => {
      try {
        const parsed = JSON.parse(raw.data) as SseEvent;
        cb.current(parsed);
        if (parsed.type === "done") es.close();
      } catch {
        // ignore non-JSON keepalive frames
      }
    };
    // Backend emits typed events (event: turn, event: judge, etc.). Wire all.
    const types = [
      "outreach_started",
      "turn",
      "conversation_done",
      "conversation_failed",
      "judge",
      "judge_failed",
      "error",
      "done",
      "message",
    ];
    types.forEach((t) => es.addEventListener(t, handle as EventListener));
    es.onerror = () => {
      // Let the browser auto-reconnect; nothing to do here for the demo.
    };
    return () => {
      es.close();
    };
  }, [url]);
}
