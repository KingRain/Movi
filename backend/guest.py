"""Recommendations for real visitors via TMDB (no dataset user ID needed)."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

TMDB_IMG = "https://image.tmdb.org/t/p/w342"
CURRENT_YEAR = datetime.now().year
NEW_CUTOFF = CURRENT_YEAR - 5
CLASSIC_CUTOFF = 2000


def _headers() -> dict[str, str]:
    h = {"Accept": "application/json"}
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _api(path: str, params: dict | None = None) -> dict | None:
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if not key and not os.environ.get("TMDB_READ_TOKEN", "").strip():
        return None
    q = dict(params or {})
    if key:
        q["api_key"] = key
    url = f"https://api.themoviedb.org/3{path}?{urlencode(q)}"
    try:
        with urlopen(Request(url, headers=_headers()), timeout=12) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def _release_year(row: dict) -> int | None:
    raw = row.get("release_date") or ""
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return None


def _as_movie(row: dict, score: float | None = None) -> dict:
    return {
        "id": row["id"],
        "tmdb_id": row["id"],
        "title": row.get("title", "Unknown"),
        "overview": row.get("overview", ""),
        "poster_url": f"{TMDB_IMG}{row['poster_path']}" if row.get("poster_path") else None,
        "release_year": _release_year(row),
        "genre_ids": list(row.get("genre_ids") or []),
        "score": round(score, 3) if score is not None else None,
    }


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[int] = set()
    out: list[dict] = []
    for row in rows:
        tid = int(row.get("id", 0))
        if tid <= 0 or tid in seen:
            continue
        seen.add(tid)
        out.append(row)
    return out


def _passes_era(movie: dict, era: str) -> bool:
    if era == "all":
        return True
    year = movie.get("release_year")
    if year is None:
        return era != "classic"
    if era == "new":
        return year >= NEW_CUTOFF
    if era == "classic":
        return year < CLASSIC_CUTOFF
    return True


def _passes_genre(movie: dict, genre_id: int | None) -> bool:
    if not genre_id:
        return True
    return genre_id in (movie.get("genre_ids") or [])


def _apply_filters(movies: list[dict], era: str, genre_id: int | None) -> list[dict]:
    return [m for m in movies if _passes_era(m, era) and _passes_genre(m, genre_id)]


@lru_cache(maxsize=1)
def movie_genres() -> list[dict]:
    data = _api("/genre/movie/list")
    if not data:
        return []
    return sorted(data.get("genres", []), key=lambda g: g.get("name", ""))


@lru_cache(maxsize=1)
def trending(k: int = 20) -> list[dict]:
    data = _api("/trending/movie/week")
    if not data:
        return []
    rows = _dedupe_rows(data.get("results", []))
    movies = [_as_movie(m) for m in rows if m.get("poster_path")]
    return movies[:k]


@lru_cache(maxsize=64)
def search_movies(query: str, k: int = 12) -> list[dict]:
    q = query.strip()
    if len(q) < 2:
        return []
    data = _api("/search/movie", {"query": q, "include_adult": "false"})
    if data and data.get("results"):
        rows = _dedupe_rows(data.get("results", []))
        movies = [_as_movie(m) for m in rows if m.get("poster_path")]
        if movies:
            return movies[:k]

    # Fallback search in static catalog
    from metadata import FALLBACK
    q_lower = q.lower()
    matches = [
        _as_movie({
            "id": m["tmdb_id"],
            "title": m["title"],
            "overview": m.get("overview", ""),
            "poster_path": m.get("poster_path"),
            "release_date": "2020-01-01"
        })
        for m in FALLBACK
        if q_lower in m["title"].lower() or q_lower in m.get("overview", "").lower()
    ]
    return matches[:k]


def _reason_text(
    watched_count: int,
    era: str,
    genre_id: int | None,
    *,
    trending: bool,
) -> str:
    if trending:
        base = "Mark films you've watched — until then, here is what is popular."
    else:
        base = f"Based on {watched_count} film(s) you've watched"

    filter_bits: list[str] = []
    if era == "new":
        filter_bits.append(f"new releases ({NEW_CUTOFF}+)")
    elif era == "classic":
        filter_bits.append(f"classics (before {CLASSIC_CUTOFF})")
    if genre_id:
        names = {g["id"]: g["name"] for g in movie_genres()}
        if genre_id in names:
            filter_bits.append(names[genre_id])

    if filter_bits:
        return f"{base} · {' · '.join(filter_bits)}"
    return base


def recommend_for_watched(
    watched_tmdb_ids: list[int],
    k: int = 8,
    era: str = "all",
    genre_id: int | None = None,
) -> dict:
    """Because you watched X → TMDB similar movies, ranked by vote_average."""
    watched = {int(i) for i in watched_tmdb_ids if i > 0}
    has_filters = era != "all" or genre_id is not None
    pool_size = max(k * 8, 48) if has_filters else max(k * 5, 32)

    if not watched:
        movies = _apply_filters(trending(pool_size), era, genre_id)[:k]
        return {
            "movies": movies,
            "mode": "trending",
            "reason": _reason_text(0, era, genre_id, trending=True),
        }

    scores: dict[int, float] = defaultdict(float)
    details: dict[int, dict] = {}

    for mid in watched:
        data = _api(f"/movie/{mid}/recommendations")
        if not data:
            continue
        for rank, row in enumerate(data.get("results", [])[:25]):
            tid = int(row["id"])
            if tid in watched:
                continue
            scores[tid] += (25 - rank) * float(row.get("vote_average") or 0)
            details.setdefault(tid, row)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    pool: list[dict] = []
    seen_scores: set[int] = set()
    for tid, sc in ranked:
        if tid in seen_scores:
            continue
        seen_scores.add(tid)
        pool.append(_as_movie(details[tid], score=sc))

    if len(pool) < pool_size:
        seen = watched | {m["tmdb_id"] for m in pool}
        for row in trending(50):
            if row["tmdb_id"] not in seen:
                pool.append(row)
                seen.add(row["tmdb_id"])
            if len(pool) >= pool_size:
                break

    movies = _apply_filters(pool, era, genre_id)[:k]

    return {
        "movies": movies,
        "mode": "taste",
        "reason": _reason_text(len(watched), era, genre_id, trending=False),
        "watched": list(watched),
    }


def recommend_for_likes(
    liked_tmdb_ids: list[int],
    k: int = 8,
    watched_tmdb_ids: list[int] | None = None,
    era: str = "all",
    genre_id: int | None = None,
) -> dict:
    seeds = list({*(watched_tmdb_ids or []), *liked_tmdb_ids})
    return recommend_for_watched(seeds, k=k, era=era, genre_id=genre_id)


if __name__ == "__main__":
    r = recommend_for_likes([550, 155, 27205], k=3, era="classic")
    assert len(r["movies"]) >= 1
    print("ok", r["mode"], r["movies"][0]["title"])
