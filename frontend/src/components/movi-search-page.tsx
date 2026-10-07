"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CinemaHeader } from "@/components/cinema-header";
import { MoviePosterCard } from "@/components/movie-poster-card";
import { MovieRow } from "@/components/movie-row";
import { searchMovies, type TasteMovie } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Movie = TasteMovie & { id: number };

export function MoviSearchPage() {
  const searchParams = useSearchParams();
  const viewTv = searchParams.get("view") === "tv";

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Movie[]>([]);
  const [trending, setTrending] = useState<Movie[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    fetch(`${API}/movies/browse?k=12`)
      .then((r) => r.json())
      .then((d: { recent: Movie[] }) => setTrending(d.recent ?? []))
      .catch(() => setTrending([]));
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = window.setTimeout(() => {
      void searchMovies(q, 24).then((movies) => {
        setResults(movies as Movie[]);
        setSearching(false);
      });
    }, 320);
    return () => window.clearTimeout(timer);
  }, [query]);

  const noop = useCallback(() => undefined, []);

  const renderPortraitCard = (movie: Movie) => (
    <MoviePosterCard
      key={movie.tmdb_id}
      movie={movie}
      layout="portrait"
      watched={false}
      isInlinePlaying={false}
      onToggleWatched={noop}
      onHoverFocus={noop}
      onTrailerActivate={noop}
      onTrailerDeactivate={noop}
    />
  );

  return (
    <div className="cinema-shell cinema-page">
      <CinemaHeader variant="page" />

      <main className="search-page">
        <div className="search-hero">
          <p className="search-kicker">{viewTv ? "MOVI · TV" : "MOVI SEARCH"}</p>
          <h1 className="search-title">What are you watching?</h1>
          <p className="search-lead">
            {viewTv
              ? "Search TV-style catalogs — movie results for now while TV metadata is wired up."
              : "Search movies and shows, then pick up exactly where you left off."}
          </p>

          <label className="search-bar">
            <span className="search-bar-icon" aria-hidden>
              ⌕
            </span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search movies, shows, people…"
              className="search-bar-input"
              autoFocus
            />
          </label>
        </div>

        <div className="search-rows">
          {query.trim().length >= 2 ? (
            <MovieRow title="Results" subtitle={searching ? "Searching…" : `${results.length} matches`}>
              {results.length === 0 && !searching ? (
                <p className="swimlane-empty">No matches for that query.</p>
              ) : (
                results.map((m) => renderPortraitCard(m))
              )}
            </MovieRow>
          ) : (
            <MovieRow eyebrow="TRENDING" title="Trending now">
              {trending.map((m) => renderPortraitCard(m))}
            </MovieRow>
          )}
        </div>
      </main>
    </div>
  );
}
