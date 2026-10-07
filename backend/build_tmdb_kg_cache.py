"""Warm TMDB KG cache for fallback catalog movies. Run: python build_tmdb_kg_cache.py"""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from kg.tmdb_graph import movie_graph  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "fallback_movies.json"


def main() -> None:
    movies = json.loads(DATA.read_text(encoding="utf-8"))
    ok = 0
    for row in movies:
        tmdb_id = int(row["tmdb_id"])
        graph = movie_graph(tmdb_id, use_cache=False)
        if graph:
            ok += 1
            print(f"cached {tmdb_id} {graph['title']} ({len(graph['edges'])} edges)")
        else:
            print(f"skip {tmdb_id} (no TMDB credentials or API error)")
    print(f"done: {ok}/{len(movies)}")


if __name__ == "__main__":
    main()
