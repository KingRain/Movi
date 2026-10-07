"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { AuthPanel } from "@/components/auth-panel";
import { CinemaHeader } from "@/components/cinema-header";
import { useMoviUser } from "@/components/movi-user-provider";
import {
  MOVIE_CACHE_STORAGE_KEY,
  TASTE_STORAGE_KEY,
  clearAccountTaste,
  clearLocalMoviData,
  clearServerInteractions,
  fetchAccountTaste,
  type TasteMovie,
} from "@/lib/auth";

type TasteProfile = { watched: number[] };

function loadGuestTaste(): TasteProfile {
  if (typeof window === "undefined") return { watched: [] };
  try {
    const raw = localStorage.getItem(TASTE_STORAGE_KEY);
    if (!raw) return { watched: [] };
    const parsed = JSON.parse(raw) as { watched?: number[] };
    return { watched: parsed.watched ?? [] };
  } catch {
    return { watched: [] };
  }
}

function loadMovieCache(): Record<number, TasteMovie> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(MOVIE_CACHE_STORAGE_KEY) ?? "{}") as Record<number, TasteMovie>;
  } catch {
    return {};
  }
}

export function MoviProfilePage() {
  const { user, setUser } = useMoviUser();
  const [taste, setTaste] = useState<TasteProfile>({ watched: [] });
  const [cache, setCache] = useState<Record<number, TasteMovie>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (user) {
      const data = await fetchAccountTaste();
      if (data) {
        setTaste({ watched: data.watched });
        const next: Record<number, TasteMovie> = {};
        for (const m of data.movies) next[m.tmdb_id] = m;
        setCache(next);
        return;
      }
    }
    setTaste(loadGuestTaste());
    setCache(loadMovieCache());
  }, [user]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runAction = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setMessage("");
    try {
      await fn();
      setMessage("Done. Refresh home to see updated recommendations.");
      await refresh();
    } catch {
      setMessage("Something went wrong. Try again.");
    } finally {
      setBusy(null);
    }
  };

  const listMovies = taste.watched
    .map((id) => cache[id])
    .filter((m): m is TasteMovie => Boolean(m));

  return (
    <div className="cinema-shell cinema-page">
      <CinemaHeader variant="page" />

      <main className="profile-page">
        <p className="search-kicker">PROFILE</p>
        <h1 className="search-title">Your Movi account</h1>
        <p className="search-lead">
          Manage sign-in, your list, and clear local or server data used for recommendations.
        </p>

        {message ? <p className="profile-flash">{message}</p> : null}

        <section className="profile-section">
          <h2 className="profile-section-title">Account</h2>
          <AuthPanel user={user} onAuthChange={setUser} />
        </section>

        <section className="profile-section" id="my-list">
          <h2 className="profile-section-title">My List</h2>
          <p className="profile-section-sub">Films you marked as watched — they seed your recommendations.</p>
          {listMovies.length === 0 ? (
            <p className="profile-empty">Nothing here yet. Mark titles with + on the home rows.</p>
          ) : (
            <ul className="profile-list-grid">
              {listMovies.map((m) => (
                <li key={m.tmdb_id} className="profile-list-item">
                  <div className="profile-list-poster">
                    {m.poster_url ? (
                      <Image src={m.poster_url} alt="" fill className="object-cover" sizes="120px" />
                    ) : null}
                  </div>
                  <span className="profile-list-title">{m.title}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="profile-section">
          <h2 className="profile-section-title">Data &amp; privacy</h2>
          <p className="profile-section-sub">
            Clearing interaction history removes hovers and trailer signals from the knowledge graph. Clearing taste
            removes watched marks.
          </p>
          <div className="profile-actions">
            <button
              type="button"
              className="profile-action-btn"
              disabled={busy !== null}
              onClick={() =>
                void runAction("interactions", async () => {
                  await clearServerInteractions();
                })
              }
            >
              {busy === "interactions" ? "…" : "Clear interaction history (server)"}
            </button>
            <button
              type="button"
              className="profile-action-btn"
              disabled={busy !== null}
              onClick={() =>
                void runAction("taste", async () => {
                  if (user) await clearAccountTaste();
                  localStorage.setItem(TASTE_STORAGE_KEY, JSON.stringify({ watched: [] }));
                  setTaste({ watched: [] });
                })
              }
            >
              {busy === "taste" ? "…" : "Clear watched list & taste"}
            </button>
            <button
              type="button"
              className="profile-action-btn profile-action-danger"
              disabled={busy !== null}
              onClick={() =>
                void runAction("all", async () => {
                  if (user) {
                    await clearAccountTaste();
                    await clearServerInteractions();
                  } else {
                    await clearServerInteractions();
                  }
                  clearLocalMoviData();
                  setTaste({ watched: [] });
                  setCache({});
                })
              }
            >
              {busy === "all" ? "…" : "Reset all local & server data"}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
