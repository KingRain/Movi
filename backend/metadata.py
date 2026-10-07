"""Movie metadata via TMDB (API key or read token), static fallback otherwise."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DATA_DIR = Path(__file__).resolve().parent / "data"
TMDB_IMG = "https://image.tmdb.org/t/p/w342"
FALLBACK: list[dict] = json.loads((DATA_DIR / "fallback_movies.json").read_text())


def item_to_catalog_index(item_id: int) -> int:
    return item_id % len(FALLBACK)


def _tmdb_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@lru_cache(maxsize=256)
def tmdb_movie_detail(tmdb_id: int) -> dict | None:
    """Credits, keywords, and collection for KG expansion."""
    key = os.environ.get("TMDB_API_KEY", "").strip()
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    if not key and not token:
        return None

    params: dict[str, str] = {"append_to_response": "credits,keywords"}
    if key:
        params["api_key"] = key
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?{urlencode(params)}"

    try:
        with urlopen(Request(url, headers=_tmdb_headers()), timeout=12) as resp:
            data = json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None

    credits = data.get("credits") or {}
    directors = [
        {"id": p["id"], "name": p.get("name", "Director")}
        for p in credits.get("crew") or []
        if p.get("job") == "Director"
    ]
    cast_top = [
        {"id": p["id"], "name": p.get("name", "Actor")}
        for p in (credits.get("cast") or [])[:3]
    ]
    keywords = [k.get("name") for k in (data.get("keywords") or {}).get("keywords", []) if k.get("name")]
    belongs = data.get("belongs_to_collection")
    collection = (
        {"id": belongs["id"], "name": belongs.get("name", "Collection")}
        if belongs
        else None
    )

    return {
        "tmdb_id": data.get("id", tmdb_id),
        "title": data.get("title", "Unknown"),
        "overview": data.get("overview", ""),
        "genre_ids": [int(g["id"]) for g in (data.get("genres") or []) if "id" in g],
        "keywords": keywords[:12],
        "directors": directors,
        "cast_top": cast_top,
        "collection": collection,
    }


@lru_cache(maxsize=512)
def tmdb_by_id(tmdb_id: int) -> dict | None:
    key = os.environ.get("TMDB_API_KEY", "").strip()
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    if not key and not token:
        return None

    params: dict[str, str] = {}
    if key:
        params["api_key"] = key
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    if params:
        url = f"{url}?{urlencode(params)}"

    try:
        with urlopen(Request(url, headers=_tmdb_headers()), timeout=10) as resp:
            data = json.loads(resp.read().decode())
        genres = data.get("genres") or []
        return {
            "tmdb_id": data.get("id", tmdb_id),
            "title": data.get("title", "Unknown"),
            "overview": data.get("overview", ""),
            "poster_url": f"{TMDB_IMG}{data['poster_path']}" if data.get("poster_path") else None,
            "genre_ids": [g["id"] for g in genres if "id" in g],
        }
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None


def movie_for_item(item_id: int, score: float | None = None) -> dict:
    base = FALLBACK[item_to_catalog_index(item_id)]
    live = tmdb_by_id(int(base["tmdb_id"]))
    meta = live or {
        "tmdb_id": base["tmdb_id"],
        "title": base["title"],
        "overview": base.get("overview", ""),
        "poster_url": f"{TMDB_IMG}{base['poster_path']}" if base.get("poster_path") else None,
    }
    return {
        "id": item_id,
        "tmdb_id": meta["tmdb_id"],
        "title": meta["title"],
        "overview": meta.get("overview", ""),
        "poster_url": meta.get("poster_url"),
        "score": score,
    }


if __name__ == "__main__":
    m = movie_for_item(7, score=0.91)
    assert m["title"] and m["poster_url"]
    live = tmdb_by_id(550)
    assert live and live["title"]
    print("ok", m["title"], "| live:", live["title"])
