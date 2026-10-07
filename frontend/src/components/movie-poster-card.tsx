"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { sendInteractionEvent } from "@/lib/auth";
import { useHoverDwell } from "@/lib/use-hover-dwell";
import { useTrailerWatchTelemetry } from "@/lib/use-trailer-watch-telemetry";

export const CARD_TRAILER_DELAY_MS = 2400;

export type MovieCardData = {
  tmdb_id: number;
  title: string;
  poster_url: string | null;
};

type Props = {
  movie: MovieCardData;
  watched: boolean;
  focused?: boolean;
  matchBadge?: string | null;
  youtubeKey?: string | null;
  trailerLoading?: boolean;
  onToggleWatched: () => void;
  onHoverFocus: (active: boolean) => void;
  onTrailerActivate: () => void;
  onTrailerDeactivate: () => void;
  onPrefetchTrailer?: () => void;
  isInlinePlaying: boolean;
  layout?: "landscape" | "portrait";
};

function HoverCountdownRing({ progress }: { progress: number }) {
  const r = 14;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.min(1, Math.max(0, progress)));

  return (
    <svg className="hub-card-timer-svg" viewBox="0 0 36 36" aria-hidden>
      <circle className="hub-card-timer-track" cx="18" cy="18" r={r} />
      <circle
        className="hub-card-timer-progress"
        cx="18"
        cy="18"
        r={r}
        strokeDasharray={c}
        strokeDashoffset={offset}
      />
    </svg>
  );
}

export function MoviePosterCard({
  movie,
  watched,
  focused,
  matchBadge,
  youtubeKey,
  trailerLoading,
  onToggleWatched,
  onHoverFocus,
  onTrailerActivate,
  onTrailerDeactivate,
  onPrefetchTrailer,
  isInlinePlaying,
  layout = "landscape",
}: Props) {
  const [hoverProgress, setHoverProgress] = useState(0);
  const [muted, setMuted] = useState(true);
  const rafRef = useRef<number | null>(null);
  const hoverStartRef = useRef<number | null>(null);
  const activatedRef = useRef(false);

  const { onPointerEnter, onPointerLeave, onPointerCancel } = useHoverDwell({
    onDwell: ({ tmdbId, durationMs }) => {
      if (tmdbId !== movie.tmdb_id) return;
      sendInteractionEvent({ tmdb_id: tmdbId, event_type: "hover", duration_ms: durationMs });
    },
  });

  const stopCountdown = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    hoverStartRef.current = null;
    setHoverProgress(0);
    activatedRef.current = false;
  }, []);

  const startCountdown = useCallback(() => {
    stopCountdown();
    hoverStartRef.current = Date.now();
    onHoverFocus(true);

    const step = () => {
      const start = hoverStartRef.current;
      if (start === null) return;
      const elapsed = Date.now() - start;
      const p = elapsed / CARD_TRAILER_DELAY_MS;
      setHoverProgress(p);
      if (p >= 1 && !activatedRef.current) {
        activatedRef.current = true;
        onTrailerActivate();
      } else if (p < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);
  }, [onHoverFocus, onTrailerActivate, stopCountdown]);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  useEffect(() => {
    if (!isInlinePlaying) setMuted(true);
  }, [isInlinePlaying]);

  useTrailerWatchTelemetry(movie.tmdb_id, isInlinePlaying && Boolean(youtubeKey));

  const showTimer = hoverProgress > 0 && hoverProgress < 1 && !isInlinePlaying;
  const showPoster = !isInlinePlaying || !youtubeKey;

  return (
    <div
      className={`hub-card ${layout === "portrait" ? "hub-card--portrait" : ""} ${focused || isInlinePlaying ? "is-focused" : ""} ${isInlinePlaying ? "is-playing" : ""} ${watched ? "is-watched" : ""}`}
      onPointerEnter={() => {
        if (!isInlinePlaying) {
          onPrefetchTrailer?.();
          startCountdown();
        }
        onPointerEnter(movie.tmdb_id);
      }}
      onPointerLeave={() => {
        onPointerLeave(movie.tmdb_id);
        if (isInlinePlaying) {
          onTrailerDeactivate();
        } else {
          stopCountdown();
          onHoverFocus(false);
        }
      }}
      onPointerCancel={() => {
        onPointerCancel(movie.tmdb_id);
        if (isInlinePlaying) onTrailerDeactivate();
        else {
          stopCountdown();
          onHoverFocus(false);
        }
      }}
    >
      {matchBadge ? <span className="hub-match">{matchBadge}</span> : null}
      <div className="hub-poster">
        {showPoster && movie.poster_url ? (
          <Image src={movie.poster_url} alt="" fill className="object-cover" sizes="320px" />
        ) : showPoster ? (
          <div className="flex h-full items-center justify-center text-xs text-hub-muted">No image</div>
        ) : null}

        {isInlinePlaying && youtubeKey ? (
          <iframe
            title={`${movie.title} trailer`}
            src={`https://www.youtube.com/embed/${youtubeKey}?autoplay=1&mute=${muted ? 1 : 0}&controls=0&modestbranding=1&rel=0&loop=1&playlist=${youtubeKey}`}
            className="hub-card-iframe"
            allow="autoplay; encrypted-media; picture-in-picture"
          />
        ) : null}

        {trailerLoading && activatedRef.current ? (
          <div className="hub-card-loading">Loading trailer…</div>
        ) : null}

        {!isInlinePlaying ? (
          <div className="hub-card-label">
            <span>{movie.title}</span>
          </div>
        ) : null}

        {showTimer ? (
          <div className="hub-card-timer" aria-label="Preview loading">
            <HoverCountdownRing progress={hoverProgress} />
          </div>
        ) : null}

        {isInlinePlaying && youtubeKey ? (
          <button
            type="button"
            className="hub-card-mute"
            aria-label={muted ? "Unmute trailer" : "Mute trailer"}
            onClick={(e) => {
              e.stopPropagation();
              setMuted((m) => !m);
            }}
          >
            {muted ? "🔇" : "🔊"}
          </button>
        ) : null}
      </div>
      <button
        type="button"
        className={`hub-watched ${watched ? "is-on" : ""}`}
        aria-label={watched ? `Unmark ${movie.title}` : `Mark ${movie.title} watched`}
        onClick={(e) => {
          e.stopPropagation();
          onToggleWatched();
        }}
      >
        {watched ? "✓" : "+"}
      </button>
    </div>
  );
}
