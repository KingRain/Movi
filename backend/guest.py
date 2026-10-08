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
        with urlopen(Request(url, headers=_headers()), timeout=4) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def _release_year(row: dict) -> int | None:
    raw = row.get("release_date") or ""
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return None


from metadata import tmdb_trailer_key


def _as_movie(row: dict, score: float | None = None) -> dict:
    mid = int(row["id"])
    return {
        "id": mid,
        "tmdb_id": mid,
        "title": row.get("title", "Unknown"),
        "overview": row.get("overview", ""),
        "poster_url": f"{TMDB_IMG}{row['poster_path']}" if row.get("poster_path") else None,
        "release_year": _release_year(row),
        "genre_ids": list(row.get("genre_ids") or []),
        "trailer_key": row.get("trailer_key") or tmdb_trailer_key(mid),
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


def _movies_from_results(data: dict | None, k: int) -> list[dict]:
    if not data:
        return []
    rows = _dedupe_rows(data.get("results", []))
    return [_as_movie(m) for m in rows if m.get("poster_path")][:k]


@lru_cache(maxsize=8)
def now_playing(k: int = 16) -> list[dict]:
    return _movies_from_results(_api("/movie/now_playing"), k)


@lru_cache(maxsize=8)
def top_rated(k: int = 16) -> list[dict]:
    """TMDB top-rated list (common stand-in for curated “best of” rows)."""
    return _movies_from_results(_api("/movie/top_rated"), k)


@lru_cache(maxsize=32)
def movies_by_genre(genre_id: int, k: int = 14) -> list[dict]:
    sort_options = ("popularity.desc", "vote_average.desc", "release_date.desc", "revenue.desc")
    sort_by = sort_options[genre_id % len(sort_options)]
    page = (genre_id % 5) + 1
    data = _api(
        "/discover/movie",
        {
            "with_genres": str(genre_id),
            "sort_by": sort_by,
            "include_adult": "false",
            "page": str(page),
        },
    )
    return _movies_from_results(data, k)


FEATURED_GENRES = [
    {"id": 28, "name": "Action"},
    {"id": 878, "name": "Sci-Fi"},
    {"id": 18, "name": "Drama"},
    {"id": 53, "name": "Thriller"},
    {"id": 35, "name": "Comedy"},
    {"id": 16, "name": "Animation"},
]


def _fallback_slice(start: int, count: int) -> list[dict]:
    from metadata import FALLBACK
    n = len(FALLBACK)
    return [
        _as_movie({
            "id": m["tmdb_id"],
            "title": m["title"],
            "overview": m.get("overview", ""),
            "poster_path": m.get("poster_path"),
            "release_date": "2022-01-01",
        })
        for m in [FALLBACK[(start + i) % n] for i in range(count)]
    ]


@lru_cache(maxsize=4)
def browse_catalog(k_per_genre: int = 14) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    def fetch_genre(g: dict) -> dict:
        m = movies_by_genre(int(g["id"]), k_per_genre)
        if not m:
            m = _fallback_slice(g["id"], k_per_genre)
        return {"genre_id": g["id"], "name": g["name"], "movies": m}

    with ThreadPoolExecutor(max_workers=8) as ex:
        fut_recent = ex.submit(now_playing, k_per_genre)
        fut_top = ex.submit(top_rated, k_per_genre)
        fut_genres = [ex.submit(fetch_genre, g) for g in FEATURED_GENRES]

        recent = fut_recent.result() or _fallback_slice(0, k_per_genre)
        top = fut_top.result() or _fallback_slice(7, k_per_genre)
        genre_rows = [f.result() for f in fut_genres]

    return {
        "recent": recent,
        "top_rated": top,
        "genres": [g for g in genre_rows if g.get("movies")],
    }



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


def movie_videos(tmdb_id: int) -> dict | None:
    data = _api(f"/movie/{tmdb_id}/videos")
    if not data:
        return None
    results = data.get("results") or []
    for clip in results:
        if clip.get("site") == "YouTube" and clip.get("type") in {"Trailer", "Teaser"}:
            return {
                "tmdb_id": tmdb_id,
                "key": clip.get("key"),
                "name": clip.get("name", "Trailer"),
                "type": clip.get("type"),
                "youtube_url": f"https://www.youtube.com/watch?v={clip['key']}" if clip.get("key") else None,
            }
    return None


def recommend_for_watched(
    watched_tmdb_ids: list[int],
    k: int = 8,
    era: str = "all",
    genre_id: int | None = None,
    implicit_seeds: list[tuple[int, float]] | None = None,
) -> dict:
    """Because you watched X → TMDB similar movies, ranked by vote_average."""
    watched = {int(i) for i in watched_tmdb_ids if i > 0}
    implicit = implicit_seeds or []
    seed_ids = set(watched)
    for tid, weight in implicit:
        if weight >= 0.35:
            seed_ids.add(int(tid))
    has_filters = era != "all" or genre_id is not None
    pool_size = max(k * 8, 48) if has_filters else max(k * 5, 32)

    if not seed_ids:
        movies = _apply_filters(trending(pool_size), era, genre_id)[:k]
        return {
            "movies": movies,
            "mode": "trending",
            "reason": _reason_text(0, era, genre_id, trending=True),
        }

    scores: dict[int, float] = defaultdict(float)
    details: dict[int, dict] = {}

    boosts: dict[int, float] = {}
    for mid in seed_ids:
        b = 1.0
        for tid, w in implicit:
            if int(tid) == int(mid):
                b = max(b, w)
        boosts[mid] = b

    from concurrent.futures import ThreadPoolExecutor

    def fetch_rec(mid: int):
        return mid, _api(f"/movie/{mid}/recommendations")

    active_seeds = list(seed_ids)[:6]
    with ThreadPoolExecutor(max_workers=min(6, len(active_seeds) or 1)) as ex:
        rec_results = list(ex.map(fetch_rec, active_seeds))

    for mid, data in rec_results:
        if not data:
            continue
        boost = boosts.get(mid, 1.0)
        for rank, row in enumerate(data.get("results", [])[:25]):
            tid = int(row["id"])
            if tid in watched:
                continue
            scores[tid] += boost * (25 - rank) * float(row.get("vote_average") or 0)
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
        "implicit_seeds": [tid for tid, _ in implicit[:8]],
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
