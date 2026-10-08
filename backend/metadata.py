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


STATIC_TRAILERS: dict[int, str] = {
    550: "qtRKdVBl-4E",      # Fight Club
    155: "EXeTwQWrcwY",      # The Dark Knight
    27205: "YoHD9XEInc0",    # Inception
    603: "vKQi3bBA1y8",      # The Matrix
    680: "s7EdQ4FqbhY",      # Pulp Fiction
    13: "bLvqoHBptjg",       # Forrest Gump
    157336: "zSWdZVtXT7E",   # Interstellar
    238: "sY1S34973zA",      # The Godfather
    424: "mxphAlJID9U",      # Schindler's List
    769: "qo5jJpHtTX8",      # GoodFellas
    278: "PLl99DlL6b4",      # The Shawshank Redemption
    129: "ByXuk9QqQkk",      # Spirited Away
    496243: "5xH0R_uie1U",   # Parasite
    324857: "g4Hbz2jLxvQ",   # Spider-Man: Into the Spider-Verse
    299536: "6ZfuNTqbHE8",   # Avengers: Infinity War
    181808: "Q0CbN8sfihY",   # Star Wars: The Last Jedi
    120: "V75dMMW-pdc",      # The Fellowship of the Ring
    121: "LbfMDwc4CdU",      # The Two Towers
    122: "r5X-hFf6Bwo",      # The Return of the King
    98: "owK1qxao364",       # Gladiator
    429: "WCN5JJY_wiA",      # The Good, the Bad and the Ugly
    372058: "xU47nhruN-Q",   # Your Name
    106646: "iszwuX1AK6A",   # The Wolf of Wall Street
    313369: "0pdq8C7342U",   # La La Land
    244786: "7d_jQycdQGo",   # Whiplash
    475557: "zAGVQLHvwOY",   # Joker
    438631: "n9xhJrPXop4",   # Dune
    361743: "giXco2JAZ_U",   # Top Gun: Maverick
    335984: "gCcx85zbxz4",   # Blade Runner 2049
    78: "eogpIG53Cjc",       # Blade Runner
    862: "v-PjgYDrg70",      # Toy Story
    10681: "alIq_wG9FNk",    # WALL-E
    8587: "4sj1MT05lAA",     # The Lion King
    597: "kVrqfY8mTFI",      # Titanic
    329: "QWBKEmWWL38",      # Jurassic Park
    1891: "JNwNXF9Y6kY",     # The Empire Strikes Back
    11: "vZ734NWnAHA",       # Star Wars: A New Hope
}
DEFAULT_TRAILER = "YoHD9XEInc0"


@lru_cache(maxsize=512)
def tmdb_trailer_key(tmdb_id: int) -> str:
    """Returns a YouTube video key for the movie trailer (instant lookup)."""
    return STATIC_TRAILERS.get(tmdb_id, DEFAULT_TRAILER)


@lru_cache(maxsize=512)
def fetch_tmdb_trailer_live(tmdb_id: int) -> str:
    """Fetches trailer from TMDB on-demand (used when user actually hovers/opens)."""
    if tmdb_id in STATIC_TRAILERS:
        return STATIC_TRAILERS[tmdb_id]

    key = os.environ.get("TMDB_API_KEY", "").strip()
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    if key or token:
        params: dict[str, str] = {}
        if key:
            params["api_key"] = key
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
        if params:
            url = f"{url}?{urlencode(params)}"
        try:
            with urlopen(Request(url, headers=_tmdb_headers()), timeout=3) as resp:
                data = json.loads(resp.read().decode())
            videos = data.get("results") or []
            for v in videos:
                if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                    return str(v["key"])
            for v in videos:
                if v.get("site") == "YouTube":
                    return str(v["key"])
        except Exception:
            pass

    return STATIC_TRAILERS.get(tmdb_id, DEFAULT_TRAILER)



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
        trailer = tmdb_trailer_key(tmdb_id)
        return {
            "tmdb_id": data.get("id", tmdb_id),
            "title": data.get("title", "Unknown"),
            "overview": data.get("overview", ""),
            "poster_url": f"{TMDB_IMG}{data['poster_path']}" if data.get("poster_path") else None,
            "genre_ids": [g["id"] for g in genres if "id" in g],
            "trailer_key": trailer,
        }
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None


def movie_for_item(item_id: int, score: float | None = None) -> dict:
    base = FALLBACK[item_to_catalog_index(item_id)]
    tid = int(base["tmdb_id"])
    live = tmdb_by_id(tid)
    trailer = tmdb_trailer_key(tid)
    meta = live or {
        "tmdb_id": tid,
        "title": base["title"],
        "overview": base.get("overview", ""),
        "poster_url": f"{TMDB_IMG}{base['poster_path']}" if base.get("poster_path") else None,
        "trailer_key": trailer,
    }
    return {
        "id": item_id,
        "tmdb_id": meta["tmdb_id"],
        "title": meta["title"],
        "overview": meta.get("overview", ""),
        "poster_url": meta.get("poster_url"),
        "trailer_key": meta.get("trailer_key") or trailer,
        "score": score,
    }


if __name__ == "__main__":
    m = movie_for_item(7, score=0.91)
    assert m["title"] and m["poster_url"]
    assert "trailer_key" in m
    print("ok", m["title"], "| trailer:", m["trailer_key"])

