"""Unified entity/relation registry and TMDB movie KG triple export."""
from __future__ import annotations

import json
from pathlib import Path

from guest import _api
from metadata import tmdb_movie_detail

DATA_DIR = Path(__file__).resolve().parent / "data"
KG_EXPANDED_PATH = DATA_DIR / "kg_expanded.txt"
REGISTRY_PATH = DATA_DIR / "kg_registry.json"

RELATIONS = {
    "directed_by": 0,
    "starred_by": 1,
    "has_genre": 2,
    "belongs_to_collection": 3,
    "has_keyword": 4,
    "r_watched": 5,
    "r_trailer_complete": 6,
    "r_trailer_start": 7,
    "r_hover_deep": 8,
}

RELATION_NAMES = {v: k for k, v in RELATIONS.items()}


class EntityRegistry:
    def __init__(self) -> None:
        self._entities: dict[str, int] = {}
        self._labels: dict[int, str] = {}

    def id_for(self, kind: str, key: str | int, label: str) -> int:
        compound = f"{kind}:{key}"
        if compound not in self._entities:
            idx = len(self._entities)
            self._entities[compound] = idx
            self._labels[idx] = label
        return self._entities[compound]

    def label(self, entity_id: int) -> str:
        return self._labels.get(entity_id, f"entity_{entity_id}")

    def to_json(self) -> dict:
        return {
            "relations": RELATIONS,
            "entities": self._entities,
            "labels": {str(k): v for k, v in self._labels.items()},
        }


def _movie_entity(reg: EntityRegistry, tmdb_id: int, title: str) -> int:
    return reg.id_for("movie", tmdb_id, title)


def triples_for_movie(tmdb_id: int, reg: EntityRegistry | None = None) -> list[tuple[int, int, int]]:
    reg = reg or EntityRegistry()
    detail = tmdb_movie_detail(tmdb_id)
    if not detail:
        return []

    movie_e = _movie_entity(reg, tmdb_id, detail["title"])
    triples: list[tuple[int, int, int]] = []

    for gid in detail.get("genre_ids") or []:
        ge = reg.id_for("genre", gid, f"genre_{gid}")
        triples.append((movie_e, RELATIONS["has_genre"], ge))
        triples.append((ge, RELATIONS["has_genre"], movie_e))

    for kw in detail.get("keywords") or []:
        ke = reg.id_for("keyword", kw, kw)
        triples.append((movie_e, RELATIONS["has_keyword"], ke))
        triples.append((ke, RELATIONS["has_keyword"], movie_e))

    collection = detail.get("collection")
    if collection:
        ce = reg.id_for("collection", collection["id"], collection["name"])
        triples.append((movie_e, RELATIONS["belongs_to_collection"], ce))
        triples.append((ce, RELATIONS["belongs_to_collection"], movie_e))

    for person in detail.get("directors") or []:
        pe = reg.id_for("person", person["id"], person["name"])
        triples.append((movie_e, RELATIONS["directed_by"], pe))
        triples.append((pe, RELATIONS["directed_by"], movie_e))

    for person in detail.get("cast_top") or []:
        pe = reg.id_for("person", person["id"], person["name"])
        triples.append((movie_e, RELATIONS["starred_by"], pe))
        triples.append((pe, RELATIONS["starred_by"], movie_e))

    return triples


def build_kg_file(tmdb_ids: list[int]) -> int:
    reg = EntityRegistry()
    all_triples: list[tuple[int, int, int]] = []
    for tid in tmdb_ids:
        all_triples.extend(triples_for_movie(tid, reg))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with KG_EXPANDED_PATH.open("w", encoding="utf-8") as fh:
        for h, r, t in all_triples:
            fh.write(f"{h}\t{r}\t{t}\n")

    REGISTRY_PATH.write_text(json.dumps(reg.to_json(), indent=2), encoding="utf-8")
    return len(all_triples)


def relation_label(relation_id: int) -> str:
    return RELATION_NAMES.get(relation_id, f"rel_{relation_id}")
