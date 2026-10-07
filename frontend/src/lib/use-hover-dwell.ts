"use client";

import { useCallback, useRef } from "react";

const MIN_HOVER_MS = 1500;

export type HoverDwellResult = {
  tmdbId: number;
  durationMs: number;
};

type Options = {
  onDwell: (result: HoverDwellResult) => void;
  minMs?: number;
};

export function useHoverDwell({ onDwell, minMs = MIN_HOVER_MS }: Options) {
  const timerRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);
  const activeIdRef = useRef<number | null>(null);
  const firedRef = useRef(false);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const finish = useCallback(
    (tmdbId: number, reason: "leave" | "cancel") => {
      clearTimer();
      const started = startRef.current;
      startRef.current = null;
      activeIdRef.current = null;

      if (started === null || reason === "cancel") {
        firedRef.current = false;
        return;
      }

      const durationMs = Date.now() - started;
      if (!firedRef.current && durationMs >= minMs) {
        firedRef.current = true;
        onDwell({ tmdbId, durationMs });
      } else {
        firedRef.current = false;
      }
    },
    [clearTimer, minMs, onDwell],
  );

  const onPointerEnter = useCallback(
    (tmdbId: number) => {
      clearTimer();
      firedRef.current = false;
      startRef.current = Date.now();
      activeIdRef.current = tmdbId;
      timerRef.current = window.setTimeout(() => {
        if (activeIdRef.current === tmdbId && startRef.current !== null) {
          const durationMs = Date.now() - startRef.current;
          if (durationMs >= minMs) {
            firedRef.current = true;
            onDwell({ tmdbId, durationMs });
          }
        }
      }, minMs);
    },
    [clearTimer, minMs, onDwell],
  );

  const onPointerLeave = useCallback(
    (tmdbId: number) => {
      if (activeIdRef.current === tmdbId) {
        finish(tmdbId, "leave");
      }
    },
    [finish],
  );

  const onPointerCancel = useCallback(
    (tmdbId: number) => {
      if (activeIdRef.current === tmdbId) {
        finish(tmdbId, "cancel");
      }
    },
    [finish],
  );

  return { onPointerEnter, onPointerLeave, onPointerCancel };
}
