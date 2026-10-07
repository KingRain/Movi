"use client";

import { useEffect, useRef } from "react";
import { sendInteractionEvent } from "@/lib/auth";

const ASSUMED_TRAILER_MS = 90_000;

/** Track trailer watch time and emit progress / complete for the KG. */
export function useTrailerWatchTelemetry(tmdbId: number | null, active: boolean) {
  const watchStartRef = useRef<number | null>(null);
  const watchSentRef = useRef(0);

  useEffect(() => {
    if (!active || tmdbId === null) {
      watchStartRef.current = null;
      watchSentRef.current = 0;
      return undefined;
    }

    watchStartRef.current = Date.now();
    watchSentRef.current = 0;

    sendInteractionEvent({
      tmdb_id: tmdbId,
      event_type: "trailer_progress",
      duration_ms: 500,
      completion_ratio: 0.16,
    });

    const tick = window.setInterval(() => {
      if (!watchStartRef.current || tmdbId === null) return;
      const watchMs = Date.now() - watchStartRef.current;
      if (watchMs - watchSentRef.current >= 2500) {
        watchSentRef.current = watchMs;
        const ratio = Math.min(1, watchMs / ASSUMED_TRAILER_MS);
        sendInteractionEvent({
          tmdb_id: tmdbId,
          event_type: ratio >= 0.5 ? "trailer_complete" : "trailer_progress",
          duration_ms: watchMs,
          completion_ratio: ratio,
        });
      }
    }, 1000);

    return () => {
      window.clearInterval(tick);
      if (watchStartRef.current && tmdbId !== null) {
        const watchMs = Date.now() - watchStartRef.current;
        const ratio = Math.min(1, watchMs / ASSUMED_TRAILER_MS);
        sendInteractionEvent({
          tmdb_id: tmdbId,
          event_type: ratio >= 0.5 ? "trailer_complete" : "trailer_progress",
          duration_ms: watchMs,
          completion_ratio: ratio,
        });
      }
    };
  }, [active, tmdbId]);
}
