"""TMDB-backed movie knowledge graph (genres, cast, crew) with on-disk cache."""
from __future__ import annotations

import json
from pathlib import Path

from guest import _api

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "tmdb_kg"


def _cache_path(tmdb_id: int) -> Path:
    return CACHE_DIR / f"{tmdb_id}.json"


def _read_cache(tmdb_id: int) -> dict | None:
    path = _cache_path(tmdb_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_cache(tmdb_id: int, graph: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(tmdb_id).write_text(json.dumps(graph, indent=2), encoding="utf-8")


def _genre_name(genre_id: int, genre_lookup: dict[int, str]) -> str:
    return genre_lookup.get(genre_id, f"Genre {genre_id}")


def movie_graph(tmdb_id: int, *, use_cache: bool = True) -> dict | None:
    if use_cache:
        cached = _read_cache(tmdb_id)
        if cached is not None:
            return cached

    detail = _api(f"/movie/{tmdb_id}", {"append_to_response": "credits"})
    if not detail:
        return None

    genre_rows = _api("/genre/movie/list") or {}
    genre_lookup = {int(g["id"]): g["name"] for g in genre_rows.get("genres", [])}

    title = detail.get("title") or "Unknown"
    root_id = f"movie:{tmdb_id}"
    nodes: list[dict] = [{"id": root_id, "label": title, "kind": "movie"}]
    edges: list[dict] = []

    for gid in detail.get("genre_ids") or []:
        gid = int(gid)
        node_id = f"genre:{gid}"
        nodes.append({"id": node_id, "label": _genre_name(gid, genre_lookup), "kind": "genre"})
        edges.append(
            {
                "from": root_id,
                "to": node_id,
                "rel": "HAS_GENRE",
                "from_label": title,
                "to_label": _genre_name(gid, genre_lookup),
                "rel_name": "HAS_GENRE",
            }
        )

    credits = detail.get("credits") or {}
    for person in (credits.get("cast") or [])[:10]:
        pid = int(person["id"])
        name = person.get("name") or f"Person {pid}"
        node_id = f"person:{pid}"
        nodes.append({"id": node_id, "label": name, "kind": "person"})
        edges.append(
            {
                "from": node_id,
                "to": root_id,
                "rel": "ACTED_IN",
                "from_label": name,
                "to_label": title,
                "rel_name": "ACTED_IN",
            }
        )

    for person in credits.get("crew") or []:
        if person.get("job") != "Director":
            continue
        pid = int(person["id"])
        name = person.get("name") or f"Person {pid}"
        node_id = f"person:{pid}"
        if not any(n["id"] == node_id for n in nodes):
            nodes.append({"id": node_id, "label": name, "kind": "person"})
        edges.append(
            {
                "from": node_id,
                "to": root_id,
                "rel": "DIRECTED",
                "from_label": name,
                "to_label": title,
                "rel_name": "DIRECTED",
            }
        )

    graph = {
        "tmdb_id": tmdb_id,
        "title": title,
        "source": "tmdb",
        "nodes": nodes,
        "edges": edges,
    }
    write_cache(tmdb_id, graph)
    return graph


def taste_bridge_graph(watched_tmdb_ids: list[int], candidate_tmdb_id: int) -> dict | None:
    """Explain a pick via shared people/genres between watched films and the candidate."""
    candidate = movie_graph(candidate_tmdb_id)
    if not candidate:
        return None

    watched_graphs = [movie_graph(tid) for tid in watched_tmdb_ids[:12]]
    watched_graphs = [g for g in watched_graphs if g]

    cand_nodes = {n["id"]: n for n in candidate["nodes"]}
    bridges: list[dict] = []

    for wg in watched_graphs:
        w_root = f"movie:{wg['tmdb_id']}"
        w_title = wg["title"]
        w_neighbors = {e["from"] if e["to"] == w_root else e["to"] for e in wg["edges"]}
        w_neighbors |= {e["to"] if e["from"] == w_root else e["from"] for e in wg["edges"]}
        c_root = f"movie:{candidate_tmdb_id}"
        for edge in candidate["edges"]:
            other = edge["to"] if edge["from"] == c_root else edge["from"]
            if other in w_neighbors and other != c_root:
                node = cand_nodes.get(other) or {"id": other, "label": other, "kind": "unknown"}
                bridges.append(
                    {
                        "watched_tmdb_id": wg["tmdb_id"],
                        "watched_title": w_title,
                        "via_id": other,
                        "via_label": node.get("label", other),
                        "via_kind": node.get("kind", "unknown"),
                        "candidate_title": candidate["title"],
                    }
                )

    return {
        "candidate_tmdb_id": candidate_tmdb_id,
        "candidate_title": candidate["title"],
        "bridges": bridges,
        "candidate_graph": candidate,
    }
