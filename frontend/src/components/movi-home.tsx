"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthPanel } from "@/components/auth-panel";
import {
  clearAccountTaste,
  fetchAccountTaste,
  fetchGenres,
  getStoredUser,
  syncMovieToAccount,
  type AuthUser,
} from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const TASTE_KEY = "movi-taste";
const MOVIE_CACHE_KEY = "movi-movie-cache";

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

type TasteProfile = {
  watched: number[];
};

type RecFilters = {
  era: "all" | "new" | "classic";
  genreId: number | null;
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
    const raw = localStorage.getItem(TASTE_KEY);
    if (!raw) return { watched: [] };
    const parsed = JSON.parse(raw) as { watched?: number[]; liked?: number[] };
    if (Array.isArray(parsed.watched)) return { watched: parsed.watched };
    const merged = [...(parsed.liked ?? []), ...(parsed.watched ?? [])];
    return { watched: [...new Set(merged)] };
  } catch {
    return { watched: [] };
  }
}

function saveGuestTaste(profile: TasteProfile) {
  localStorage.setItem(TASTE_KEY, JSON.stringify(profile));
}

function loadMovieCache(): Record<number, Movie> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(MOVIE_CACHE_KEY) ?? "{}") as Record<number, Movie>;
  } catch {
    return {};
  }
}

function saveMovieCache(cache: Record<number, Movie>) {
  localStorage.setItem(MOVIE_CACHE_KEY, JSON.stringify(cache));
}

function cacheMovies(cache: Record<number, Movie>, movies: Movie[]): Record<number, Movie> {
  const next = { ...cache };
  for (const m of movies) next[m.tmdb_id] = m;
  return next;
}

function EyeIcon({ filled }: { filled?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="taste-icon" aria-hidden>
      <path
        d="M12 5C7 5 2.73 8.11 1 12c1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7Zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function MoviePosterCard({
  movie,
  watched,
  onToggleWatched,
  onSelect,
  selected,
}: {
  movie: Movie;
  watched: boolean;
  onToggleWatched: () => void;
  onSelect?: () => void;
  selected?: boolean;
}) {
  const posterInner = (
    <div className="poster-media">
      {movie.poster_url ? (
        <Image
          src={movie.poster_url}
          alt=""
          fill
          className="object-cover"
          sizes="(max-width: 640px) 28vw, (max-width: 1024px) 20vw, 140px"
        />
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-ash">No image</div>
      )}
      <div className="poster-title">
        <p>{movie.title}</p>
        {movie.release_year ? <span className="poster-year">{movie.release_year}</span> : null}
      </div>
    </div>
  );

  return (
    <div
      className={`poster-card group ${watched ? "is-watched" : ""} ${selected ? "is-selected" : ""}`}
    >
      {onSelect ? (
        <button
          type="button"
          onClick={onSelect}
          aria-label={`View ${movie.title}`}
          className="poster-btn poster-btn-plain"
        >
          {posterInner}
        </button>
      ) : (
        <div className="poster-btn poster-btn-plain">{posterInner}</div>
      )}

      <button
        type="button"
        className={`poster-badge-checkbox ${watched ? "is-checked" : ""}`}
        aria-label={watched ? `Unmark ${movie.title} as watched` : `Mark ${movie.title} as watched`}
        aria-pressed={watched}
        onClick={(e) => {
          e.stopPropagation();
          onToggleWatched();
        }}
      >
        <svg viewBox="0 0 20 20" className="checkbox-icon" aria-hidden="true">
          {watched ? (
            <path
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              fill="currentColor"
            />
          ) : (
            <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" fill="none" />
          )}
        </svg>
      </button>
    </div>
  );
}

export function MoviHome() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [taste, setTaste] = useState<TasteProfile>({ watched: [] });
  const [movieCache, setMovieCache] = useState<Record<number, Movie>>({});
  const [trending, setTrending] = useState<Movie[]>([]);
  const [genres, setGenres] = useState<{ id: number; name: string }[]>([]);
  const [draftFilters, setDraftFilters] = useState<RecFilters>(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<RecFilters>(DEFAULT_FILTERS);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Movie[]>([]);
  const [searching, setSearching] = useState(false);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [selected, setSelected] = useState<Movie | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const filtersDirty =
    draftFilters.era !== appliedFilters.era || draftFilters.genreId !== appliedFilters.genreId;

  const applyTasteFromServer = useCallback((data: { watched: number[]; movies: Movie[] }) => {
    setTaste({ watched: data.watched });
    setMovieCache((prev) => {
      const next = cacheMovies(prev, data.movies);
      saveMovieCache(next);
      return next;
    });
  }, []);

  useEffect(() => {
    setUser(getStoredUser());
    setMovieCache(loadMovieCache());

    fetch(`${API}/movies/trending?k=20`)
      .then((r) => r.json())
      .then((d: { movies: Movie[] }) => {
        const list = dedupeMovies(d.movies);
        setTrending(list);
        setMovieCache((prev) => {
          const next = cacheMovies(prev, list);
          saveMovieCache(next);
          return next;
        });
      })
      .catch(() => setError("Could not load films. Start the backend on port 8000."));

    fetchGenres().then(setGenres);
  }, []);

  useEffect(() => {
    if (!user) {
      setTaste(loadGuestTaste());
      return;
    }
    fetchAccountTaste().then((data) => {
      if (data) applyTasteFromServer(data);
    });
  }, [user, applyTasteFromServer]);

  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = window.setTimeout(() => {
      fetch(`${API}/movies/search?q=${encodeURIComponent(q)}&k=16`)
        .then((r) => r.json())
        .then((d: { movies: Movie[] }) => {
          const list = dedupeMovies(d.movies);
          setSearchResults(list);
          setMovieCache((prev) => {
            const next = cacheMovies(prev, list);
            saveMovieCache(next);
            return next;
          });
        })
        .catch(() => setSearchResults([]))
        .finally(() => setSearching(false));
    }, 320);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  const loadPicks = useCallback(async (watchedIds: number[], recFilters: RecFilters) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ k: "8" });
      if (watchedIds.length) params.set("watched", watchedIds.join(","));
      if (recFilters.era !== "all") params.set("era", recFilters.era);
      if (recFilters.genreId) params.set("genre_id", String(recFilters.genreId));
      const res = await fetch(`${API}/recommend/for-you?${params}`);
      if (!res.ok) throw new Error("failed");
      const data = (await res.json()) as { movies: Movie[]; reason?: string };
      const unique = dedupeMovies(data.movies);
      setMovies(unique);
      setReason(data.reason ?? "");
      setSelected((prev) => {
        if (prev && unique.some((m) => m.tmdb_id === prev.tmdb_id)) return prev;
        return unique[0] ?? null;
      });
    } catch {
      setError(`Backend unreachable at ${API}`);
      setMovies([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPicks(taste.watched, appliedFilters);
  }, [taste.watched, appliedFilters, loadPicks]);

  const rememberMovie = (movie: Movie) => {
    setMovieCache((prev) => {
      const next = cacheMovies(prev, [movie]);
      saveMovieCache(next);
      return next;
    });
  };

  const toggleWatched = (movie: Movie) => {
    rememberMovie(movie);
    const nextWatched = taste.watched.includes(movie.tmdb_id)
      ? taste.watched.filter((x) => x !== movie.tmdb_id)
      : [...taste.watched, movie.tmdb_id];

    setTaste({ watched: nextWatched });
    if (!user) saveGuestTaste({ watched: nextWatched });
    else void syncMovieToAccount({ ...movie, watched: nextWatched.includes(movie.tmdb_id) });
  };

  const clearTaste = async () => {
    setTaste({ watched: [] });
    if (user) await clearAccountTaste();
    else saveGuestTaste({ watched: [] });
  };

  const applyFilters = () => {
    setAppliedFilters({ ...draftFilters });
  };

  const displayMovies = useMemo(() => {
    const base = searchQuery.trim().length >= 2 ? searchResults : trending;
    return dedupeMovies(base);
  }, [searchQuery, searchResults, trending]);

  const hasWatched = taste.watched.length > 0;

  const handleAuthChange = async (nextUser: AuthUser | null) => {
    setUser(nextUser);
    if (nextUser) {
      const data = await fetchAccountTaste();
      if (data) applyTasteFromServer(data);
    } else {
      setTaste(loadGuestTaste());
    }
  };

  return (
    <div className="cosmic-bg min-h-screen">
      <header className="sticky top-0 z-20 border-b border-charcoal/50 bg-void/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <span className="text-lg font-medium text-carbon-vellum">Movi</span>
            <span className="ml-2 hidden text-xs text-ash sm:inline">Search · mark watched · get picks</span>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <AuthPanel user={user} onAuthChange={handleAuthChange} />
            {hasWatched && (
              <button type="button" className="pill-ghost-sm" onClick={() => void clearTaste()}>
                Clear
              </button>
            )}
            <button
              type="button"
              className="pill-primary px-4 py-2 text-sm"
              onClick={() => loadPicks(taste.watched, appliedFilters)}
              disabled={loading}
            >
              {loading ? "…" : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6 sm:pt-8 lg:pt-10">
        <div className="mb-6 max-w-2xl sm:mb-8">
          <p className="eyebrow mb-2 sm:mb-3">WELCOME</p>
          <h1 className="text-2xl font-normal leading-tight tracking-tight text-carbon-vellum sm:text-3xl lg:text-4xl">
            What have you watched lately?
          </h1>
          <p className="mt-2 text-sm text-smoke sm:mt-3 sm:text-base">
            Search films and mark them watched using the circle checkbox on top right
            {user ? ` — synced to ${user.username}` : " — sign in to save across sessions"}.
          </p>
        </div>

        <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:items-start lg:gap-8">
          <section className="product-frame p-4 sm:p-5">
            <div className="mb-4 flex items-start gap-3">
              <span className="step-badge mt-0.5 shrink-0">1</span>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-medium text-carbon-vellum sm:text-lg">Your watch history</h2>
                <p className="mt-1 text-xs text-ash sm:text-sm">Tap the circular check mark on any card to mark as watched</p>
              </div>
            </div>

            <div className="mb-4">
              <label htmlFor="film-search" className="sr-only">
                Search films
              </label>
              <div className="search-field">
                <svg className="search-icon" viewBox="0 0 20 20" fill="none" aria-hidden>
                  <path
                    d="M9 3.5a5.5 5.5 0 1 0 3.47 9.79l3.2 3.2a.75.75 0 1 0 1.06-1.06l-3.2-3.2A5.5 5.5 0 0 0 9 3.5Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  />
                </svg>
                <input
                  id="film-search"
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search any film…"
                  className="search-input"
                  autoComplete="off"
                />
                {searchQuery && (
                  <button
                    type="button"
                    className="search-clear"
                    aria-label="Clear search"
                    onClick={() => setSearchQuery("")}
                  >
                    ×
                  </button>
                )}
              </div>
              {searchQuery.trim().length >= 2 && (
                <p className="mt-2 text-xs text-ash">
                  {searching ? "Searching…" : `${displayMovies.length} result(s)`}
                </p>
              )}
            </div>

            {displayMovies.length === 0 && searchQuery.trim().length >= 2 && !searching ? (
              <p className="rounded-lg border border-dashed border-twilight/50 px-3 py-4 text-center text-sm text-ash">
                No films found for &ldquo;{searchQuery.trim()}&rdquo;
              </p>
            ) : (
              <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 sm:gap-3 md:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4">
                {displayMovies.map((movie) => (
                  <li key={movie.tmdb_id}>
                    <MoviePosterCard
                      movie={movie}
                      watched={taste.watched.includes(movie.tmdb_id)}
                      onToggleWatched={() => toggleWatched(movie)}
                    />
                  </li>
                ))}
              </ul>
            )}

            {!hasWatched && searchQuery.trim().length < 2 && (
              <p className="mt-4 rounded-lg border border-dashed border-twilight/50 px-3 py-2 text-xs text-ash sm:text-sm">
                Mark films with the eye icon — trending picks show on the right until you do.
              </p>
            )}
          </section>

          <section className="lg:sticky lg:top-[4.25rem]">
            <div className="product-frame p-4 sm:p-5">
              <div className="mb-4 flex items-start gap-3">
                <span className="step-badge mt-0.5 shrink-0">2</span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-base font-medium text-carbon-vellum sm:text-lg">Recommended for you</h2>
                  {reason && <p className="mt-1 text-xs text-smoke sm:text-sm">{reason}</p>}
                  {error && <p className="mt-1 text-xs text-iris-glow sm:text-sm">{error}</p>}
                  {loading && <p className="mt-1 text-xs text-ash sm:text-sm">Finding films…</p>}
                </div>
              </div>

              <div className="filter-bar mb-4">
                <label className="filter-field">
                  <span className="filter-label">When</span>
                  <select
                    value={draftFilters.era}
                    onChange={(e) =>
                      setDraftFilters((f) => ({ ...f, era: e.target.value as RecFilters["era"] }))
                    }
                    className="filter-select"
                  >
                    <option value="all">All years</option>
                    <option value="new">New releases</option>
                    <option value="classic">Classics</option>
                  </select>
                </label>
                <label className="filter-field filter-field-grow">
                  <span className="filter-label">Genre</span>
                  <select
                    value={draftFilters.genreId ?? ""}
                    onChange={(e) =>
                      setDraftFilters((f) => ({
                        ...f,
                        genreId: e.target.value ? Number(e.target.value) : null,
                      }))
                    }
                    className="filter-select"
                  >
                    <option value="">All genres</option>
                    {genres.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="filter-apply"
                  onClick={applyFilters}
                  disabled={loading || !filtersDirty}
                >
                  Apply
                </button>
              </div>

              {!loading && movies.length === 0 && !error && (
                <p className="text-sm text-ash">No matches for these filters — try broadening them.</p>
              )}

              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3 lg:grid-cols-2 xl:grid-cols-4">
                {movies.map((movie) => (
                  <li key={movie.tmdb_id}>
                    <MoviePosterCard
                      movie={movie}
                      watched={taste.watched.includes(movie.tmdb_id)}
                      onToggleWatched={() => toggleWatched(movie)}
                      onSelect={() => setSelected(movie)}
                      selected={selected?.tmdb_id === movie.tmdb_id}
                    />
                  </li>
                ))}
              </ul>
            </div>

            {selected && (
              <div className="mt-4 product-frame p-4 sm:p-5">
                <p className="eyebrow mb-2 !text-specter-lilac">NOW VIEWING</p>
                <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
                  {selected.poster_url && (
                    <div className="relative mx-auto h-40 w-28 shrink-0 overflow-hidden rounded-[10px] border border-twilight sm:mx-0">
                      <Image src={selected.poster_url} alt="" fill className="object-cover" sizes="112px" />
                    </div>
                  )}
                  <div className="min-w-0 text-center sm:text-left">
                    <h3 className="text-lg font-medium text-carbon-vellum sm:text-xl">
                      {selected.title}
                      {selected.release_year ? (
                        <span className="ml-2 text-sm font-normal text-ash">({selected.release_year})</span>
                      ) : null}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-ash">{selected.overview}</p>
                    <button
                      type="button"
                      className={`detail-watched-btn mt-4 ${taste.watched.includes(selected.tmdb_id) ? "is-on" : ""}`}
                      onClick={() => toggleWatched(selected)}
                    >
                      <EyeIcon filled={taste.watched.includes(selected.tmdb_id)} />
                      {taste.watched.includes(selected.tmdb_id) ? "Marked as watched" : "Mark as watched"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
