"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CinemaHeader } from "@/components/cinema-header";
import { MoviePosterCard } from "@/components/movie-poster-card";
import { useMoviUser } from "@/components/movi-user-provider";
import { MovieRow } from "@/components/movie-row";
import { TrailerModal, type TrailerModalState } from "@/components/trailer-modal";
import { buildCatalogRows } from "@/lib/row-catalog";
import {
  fetchAccountTaste,
  fetchGenres,
  getGuestToken,
  getToken,
  installTelemetryBeacon,
  MOVIE_CACHE_STORAGE_KEY,
  onTelemetryFlushed,
  syncMovieToAccount,
  TASTE_STORAGE_KEY,
} from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Movie = {
  id: number;
  tmdb_id: number;
  title: string;
  overview: string;
  poster_url: string | null;
  release_year?: number | null;
  genre_ids?: number[];
  score?: number | null;
};

type TasteProfile = { watched: number[] };

type RecFilters = {
  era: "all" | "new" | "classic";
  genreId: number | null;
};

type GenreSection = {
  genre_id: number;
  name: string;
  movies: Movie[];
};

const DEFAULT_FILTERS: RecFilters = { era: "all", genreId: null };

function dedupeMovies(list: Movie[]): Movie[] {
  const seen = new Set<number>();
  return list.filter((m) => {
    if (seen.has(m.tmdb_id)) return false;
    seen.add(m.tmdb_id);
    return true;
  });
}

function loadGuestTaste(): TasteProfile {
  if (typeof window === "undefined") return { watched: [] };
  try {
    const raw = localStorage.getItem(TASTE_STORAGE_KEY);
    if (!raw) return { watched: [] };
    const parsed = JSON.parse(raw) as { watched?: number[]; liked?: number[] };
    if (Array.isArray(parsed.watched)) return { watched: parsed.watched };
    return { watched: [...new Set([...(parsed.liked ?? []), ...(parsed.watched ?? [])])] };
  } catch {
    return { watched: [] };
  }
}

function saveGuestTaste(profile: TasteProfile) {
  localStorage.setItem(TASTE_STORAGE_KEY, JSON.stringify(profile));
}

function loadMovieCache(): Record<number, Movie> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(MOVIE_CACHE_STORAGE_KEY) ?? "{}") as Record<number, Movie>;
  } catch {
    return {};
  }
}

function saveMovieCache(cache: Record<number, Movie>) {
  localStorage.setItem(MOVIE_CACHE_STORAGE_KEY, JSON.stringify(cache));
}

function cacheMovies(cache: Record<number, Movie>, movies: Movie[]): Record<number, Movie> {
  const next = { ...cache };
  for (const m of movies) next[m.tmdb_id] = m;
  return next;
}

function matchLabel(score: number | null | undefined, rank: number): string | null {
  if (score != null && score > 0) {
    return `${Math.min(99, Math.round(score * 10 + 70))}% Match`;
  }
  if (rank === 0) return "Top Pick";
  return null;
}

export function MoviHome() {
  const { user, setUser } = useMoviUser();
  const [taste, setTaste] = useState<TasteProfile>({ watched: [] });
  const [movieCache, setMovieCache] = useState<Record<number, Movie>>({});
  const [genres, setGenres] = useState<{ id: number; name: string }[]>([]);
  const [draftFilters, setDraftFilters] = useState<RecFilters>(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<RecFilters>(DEFAULT_FILTERS);
  const [movies, setMovies] = useState<Movie[]>([]);
  const moviesRef = useRef<Movie[]>([]);
  moviesRef.current = movies;
  const [recent, setRecent] = useState<Movie[]>([]);
  const [topRated, setTopRated] = useState<Movie[]>([]);
  const [genreSections, setGenreSections] = useState<GenreSection[]>([]);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [focusedInstanceId, setFocusedInstanceId] = useState<string | null>(null);
  const [playingInstanceId, setPlayingInstanceId] = useState<string | null>(null);
  const [trailerKeys, setTrailerKeys] = useState<Record<number, string>>({});
  const [trailerLoadingInstanceId, setTrailerLoadingInstanceId] = useState<string | null>(null);
  const [trailerModal, setTrailerModal] = useState<TrailerModalState | null>(null);
  const [trailerLoading, setTrailerLoading] = useState(false);
  const playingInstanceRef = useRef<string | null>(null);
  const trailerKeysRef = useRef(trailerKeys);
  trailerKeysRef.current = trailerKeys;

  const fetchTrailerKey = useCallback(async (tmdbId: number): Promise<string | null> => {
    const cached = trailerKeysRef.current[tmdbId];
    if (cached) return cached;
    try {
      const res = await fetch(`${API}/movies/${tmdbId}/videos`);
      if (!res.ok) return null;
      const data = (await res.json()) as { key?: string };
      if (data.key) {
        setTrailerKeys((prev) => ({ ...prev, [tmdbId]: data.key! }));
        return data.key;
      }
    } catch {
      /* ignore */
    }
    return null;
  }, []);

  const openTrailerFor = useCallback(async (movie: Movie) => {
    setTrailerLoading(true);
    setTrailerModal({ tmdbId: movie.tmdb_id, title: movie.title, youtubeKey: "" });
    const key = await fetchTrailerKey(movie.tmdb_id);
    if (key) {
      setTrailerModal({ tmdbId: movie.tmdb_id, title: movie.title, youtubeKey: key });
    }
    setTrailerLoading(false);
  }, [fetchTrailerKey]);

  const activateInlineTrailer = useCallback(
    async (movie: Movie, instanceId: string) => {
      playingInstanceRef.current = instanceId;
      setPlayingInstanceId(instanceId);
      setFocusedInstanceId(instanceId);
      if (trailerKeys[movie.tmdb_id]) return;
      setTrailerLoadingInstanceId(instanceId);
      const key = await fetchTrailerKey(movie.tmdb_id);
      setTrailerLoadingInstanceId(null);
      if (playingInstanceRef.current !== instanceId) return;
      if (!key) {
        playingInstanceRef.current = null;
        setPlayingInstanceId(null);
        setFocusedInstanceId((id) => (id === instanceId ? null : id));
      }
    },
    [fetchTrailerKey],
  );

  const deactivateInlineTrailer = useCallback((instanceId: string) => {
    if (playingInstanceRef.current === instanceId) {
      playingInstanceRef.current = null;
      setPlayingInstanceId(null);
    }
    setFocusedInstanceId((id) => (id === instanceId ? null : id));
  }, []);

  const applyTasteFromServer = useCallback((data: { watched: number[]; movies: Movie[] }) => {
    setTaste({ watched: data.watched });
    setMovieCache((prev) => {
      const next = cacheMovies(prev, data.movies);
      saveMovieCache(next);
      return next;
    });
  }, []);

  const cacheAll = useCallback((list: Movie[]) => {
    setMovieCache((prev) => cacheMovies(prev, list));
  }, []);

  useEffect(() => installTelemetryBeacon(), []);

  useEffect(() => {
    setMovieCache(loadMovieCache());

    fetch(`${API}/movies/browse?k=22`)
      .then((r) => r.json())
      .then(
        (d: {
          recent: Movie[];
          top_rated: Movie[];
          genres: GenreSection[];
        }) => {
          setRecent(dedupeMovies(d.recent ?? []));
          setTopRated(dedupeMovies(d.top_rated ?? []));
          setGenreSections(d.genres ?? []);
          cacheAll([
            ...(d.recent ?? []),
            ...(d.top_rated ?? []),
            ...(d.genres ?? []).flatMap((g) => g.movies),
          ]);
        },
      )
      .catch(() => setError("Could not load catalog. Start the backend on port 8000."));

    fetchGenres().then(setGenres);
  }, [cacheAll]);

  useEffect(() => {
    if (!user) {
      setTaste(loadGuestTaste());
      return;
    }
    fetchAccountTaste().then((data) => {
      if (data) applyTasteFromServer(data);
    });
  }, [user, applyTasteFromServer]);

  const loadPicks = useCallback(async (watchedIds: number[], recFilters: RecFilters) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ k: "18" });
      if (watchedIds.length) params.set("watched", watchedIds.join(","));
      if (recFilters.era !== "all") params.set("era", recFilters.era);
      if (recFilters.genreId) params.set("genre_id", String(recFilters.genreId));
      const headers: HeadersInit = {};
      const token = getToken();
      if (token) headers.Authorization = `Bearer ${token}`;
      else headers["X-Guest-Token"] = getGuestToken();
      const res = await fetch(`${API}/recommend/for-you?${params}`, { headers });
      if (!res.ok) throw new Error("failed");
      const data = (await res.json()) as { movies: Movie[]; reason?: string };
      const unique = dedupeMovies(data.movies ?? []);
      setMovies(unique);
      setReason(data.reason ?? "");
      cacheAll(unique);
    } catch {
      if (moviesRef.current.length === 0) {
        setError(`Backend unreachable at ${API}`);
      }
    } finally {
      setLoading(false);
    }
  }, [cacheAll]);

  useEffect(() => {
    loadPicks(taste.watched, appliedFilters);
  }, [taste.watched, appliedFilters, loadPicks]);

  useEffect(() => {
    let debounce: number | null = null;
    const unsub = onTelemetryFlushed(() => {
      if (debounce !== null) window.clearTimeout(debounce);
      debounce = window.setTimeout(() => {
        void loadPicks(taste.watched, appliedFilters);
      }, 800);
    });
    return () => {
      unsub();
      if (debounce !== null) window.clearTimeout(debounce);
    };
  }, [loadPicks, taste.watched, appliedFilters]);

  const toggleWatched = (movie: Movie) => {
    setMovieCache((prev) => {
      const next = cacheMovies(prev, [movie]);
      saveMovieCache(next);
      return next;
    });
    const nextWatched = taste.watched.includes(movie.tmdb_id)
      ? taste.watched.filter((x) => x !== movie.tmdb_id)
      : [...taste.watched, movie.tmdb_id];
    setTaste({ watched: nextWatched });
    if (!user) saveGuestTaste({ watched: nextWatched });
    else void syncMovieToAccount({ ...movie, watched: nextWatched.includes(movie.tmdb_id) });
  };

  const catalogRows = useMemo(
    () => buildCatalogRows(movies, recent, topRated, genreSections),
    [movies, recent, topRated, genreSections],
  );

  const heroMovie = movies[0] ?? catalogRows.recentRow[0] ?? catalogRows.topRatedRow[0] ?? null;

  const renderCard = (movie: Movie, rowId: string, rank = 0, showMatch = false) => {
    const instanceId = `${rowId}-${movie.tmdb_id}`;
    return (
      <MoviePosterCard
        key={instanceId}
        movie={movie}
        watched={taste.watched.includes(movie.tmdb_id)}
        focused={focusedInstanceId === instanceId}
        matchBadge={showMatch ? matchLabel(movie.score, rank) : null}
        youtubeKey={trailerKeys[movie.tmdb_id] ?? null}
        trailerLoading={trailerLoadingInstanceId === instanceId}
        isInlinePlaying={playingInstanceId === instanceId}
        onToggleWatched={() => toggleWatched(movie)}
        onHoverFocus={(active) => {
          if (active) setFocusedInstanceId(instanceId);
          else setFocusedInstanceId((id) => (id === instanceId ? null : id));
        }}
        onTrailerActivate={() => void activateInlineTrailer(movie, instanceId)}
        onTrailerDeactivate={() => deactivateInlineTrailer(instanceId)}
        onPrefetchTrailer={() => void fetchTrailerKey(movie.tmdb_id)}
      />
    );
  };

  return (
    <div className="cinema-shell">
      <section className="cinema-hero">
        {heroMovie?.poster_url ? (
          <Image
            src={heroMovie.poster_url}
            alt=""
            fill
            priority
            className="cinema-hero-bg object-cover"
            sizes="100vw"
          />
        ) : null}
        <div className="cinema-hero-scrim" aria-hidden />

        <CinemaHeader variant="overlay" />

        {heroMovie ? (
          <div className="cinema-hero-copy">
            <p className="cinema-hero-kicker">
              Knowledge-graph recommendations · hover &amp; trailer signals shape your first row
            </p>
            <h1 className="cinema-hero-title">{heroMovie.title.toUpperCase()}</h1>
            <p className="cinema-hero-desc">
              {heroMovie.overview ||
                "Mark what you've watched, preview trailers, and Movi ranks films in Recommended for You below."}
            </p>
            <div className="cinema-hero-actions">
              <button
                type="button"
                className="cinema-btn-watch"
                onClick={() => void openTrailerFor(heroMovie)}
              >
                <span aria-hidden>▶</span> Watch trailer
              </button>
              <button
                type="button"
                className="cinema-btn-info"
                onClick={() => toggleWatched(heroMovie)}
              >
                {taste.watched.includes(heroMovie.tmdb_id) ? "In My List" : "＋ My List"}
              </button>
            </div>
          </div>
        ) : null}
      </section>

      <main className="cinema-rows">
        <div className="hub-filters cinema-filters">
          <select
            value={draftFilters.era}
            onChange={(e) => setDraftFilters((f) => ({ ...f, era: e.target.value as RecFilters["era"] }))}
            className="hub-filter-select"
          >
            <option value="all">All years</option>
            <option value="new">New releases</option>
            <option value="classic">Classics</option>
          </select>
          <select
            value={draftFilters.genreId ?? ""}
            onChange={(e) =>
              setDraftFilters((f) => ({
                ...f,
                genreId: e.target.value ? Number(e.target.value) : null,
              }))
            }
            className="hub-filter-select"
          >
            <option value="">All genres</option>
            {genres.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="hub-filter-apply"
            onClick={() => setAppliedFilters({ ...draftFilters })}
            disabled={loading}
          >
            Apply to recommendations
          </button>
          <button type="button" className="hub-filter-ghost" onClick={() => loadPicks(taste.watched, appliedFilters)}>
            Refresh picks
          </button>
        </div>

        {error ? <p className="hub-error">{error}</p> : null}

        <MovieRow
          eyebrow="FOR YOU"
          title="Recommendations"
          subtitle={
            loading
              ? "Updating from watches, hovers, and trailers…"
              : reason || "Your personalized row — everything else is browse catalog below"
          }
        >
          {loading && movies.length === 0 ? (
            <div className="swimlane-skeleton" aria-busy="true">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="hub-card-skeleton" />
              ))}
            </div>
          ) : movies.length === 0 ? (
            <p className="swimlane-empty">Mark films or preview trailers to personalize this row.</p>
          ) : (
            movies.map((m, i) => renderCard(m, "recs", i, true))
          )}
        </MovieRow>

        <div id="catalog">
          <MovieRow eyebrow="NOW PLAYING" title="In Theaters Now">
            {catalogRows.recentRow.map((m) => renderCard(m, "recent"))}
          </MovieRow>

          <MovieRow eyebrow="TOP CHARTS" title="Top Rated">
            {catalogRows.topRatedRow.map((m) => renderCard(m, "top"))}
          </MovieRow>

          {catalogRows.genreRows.map((section) =>
            section.movies.length > 0 ? (
              <MovieRow key={section.genre_id} title={section.name}>
                {section.movies.map((m) => renderCard(m, `genre-${section.genre_id}`))}
              </MovieRow>
            ) : null,
          )}
        </div>
      </main>

      <TrailerModal
        state={trailerModal}
        loading={trailerLoading}
        onClose={() => {
          setTrailerModal(null);
          setTrailerLoading(false);
        }}
      />
    </div>
  );
}
