"use client";

import { useTrailerWatchTelemetry } from "@/lib/use-trailer-watch-telemetry";

export type TrailerModalState = {
  tmdbId: number;
  title: string;
  youtubeKey: string;
};

type Props = {
  state: TrailerModalState | null;
  loading?: boolean;
  onClose: () => void;
};

export function TrailerModal({ state, loading, onClose }: Props) {
  useTrailerWatchTelemetry(state?.tmdbId ?? null, Boolean(state?.youtubeKey));

  if (!state && !loading) return null;

  const title = state?.title ?? "Trailer";

  return (
    <div className="trailer-modal-root" role="presentation">
      <button type="button" className="trailer-modal-backdrop" aria-label="Close trailer" onClick={onClose} />
      <div className="trailer-modal-panel" role="dialog" aria-label={title}>
        <div className="trailer-modal-head">
          <p className="trailer-modal-title">{title}</p>
          <button type="button" className="trailer-modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="trailer-modal-video">
          {loading || !state?.youtubeKey ? (
            <p className="trailer-modal-loading">{loading ? "Loading trailer…" : "No trailer found"}</p>
          ) : (
            <iframe
              title={`${state.title} trailer`}
              src={`https://www.youtube.com/embed/${state.youtubeKey}?autoplay=1&mute=0&controls=1&modestbranding=1&rel=0`}
              className="trailer-modal-iframe"
              allow="autoplay; encrypted-media; picture-in-picture"
            />
          )}
        </div>
      </div>
    </div>
  );
}
