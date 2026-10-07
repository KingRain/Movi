"""Build kg_expanded.txt from fallback catalog. Run: python build_kg_expanded.py"""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from kg_builder import build_kg_file  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "fallback_movies.json"


def main() -> None:
    movies = json.loads(DATA.read_text(encoding="utf-8"))
    ids = [int(m["tmdb_id"]) for m in movies]
    count = build_kg_file(ids)
    print(f"wrote {count} triples for {len(ids)} movies")


if __name__ == "__main__":
    main()
