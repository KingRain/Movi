"""Aggregate raw interaction telemetry into multi-behavior KG tiers."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from typing import Any

from db import connect

BEHAVIOR_RELATIONS = {
    "r_watched": 5,
    "r_trailer_complete": 6,
    "r_trailer_start": 7,
    "r_hover_deep": 8,
}

RELATION_WEIGHT = {
    "r_watched": 1.0,
    "r_trailer_complete": 0.85,
    "r_trailer_start": 0.45,
    "r_hover_deep": 0.35,
}


def _map_event_to_type(event_type: str, duration_ms: int, completion_ratio: float) -> str:
    if event_type == "hover":
        return "hover_deep" if duration_ms >= 3000 else "hover"
    if event_type == "trailer_complete":
        return "trailer_complete"
    if event_type == "trailer_progress":
        if completion_ratio >= 0.5:
            return "trailer_complete"
        if 1000 <= duration_ms <= 10_000:
            return "trailer_start"
        return "trailer_progress"
    return event_type


def _tier_relation(interaction_type: str) -> str | None:
    if interaction_type == "hover_deep":
        return "r_hover_deep"
    if interaction_type == "trailer_start":
        return "r_trailer_start"
    if interaction_type == "trailer_complete":
        return "r_trailer_complete"
    if interaction_type == "watched":
        return "r_watched"
    return None


def insert_interactions(
    rows: list[dict[str, Any]],
    *,
    user_id: int | None,
    guest_token: str | None,
) -> int:
    if not rows:
        return 0
    if user_id is None and not guest_token:
        raise ValueError("user_id or guest_token required")

    inserted = 0
    with connect() as conn:
        for row in rows:
            event_type = str(row["event_type"])
            duration_ms = int(row.get("duration_ms") or 0)
            completion_ratio = float(row.get("completion_ratio") or 0.0)
            interaction_type = _map_event_to_type(event_type, duration_ms, completion_ratio)
            weight = float(RELATION_WEIGHT.get(_tier_relation(interaction_type) or "", 0.2))
            conn.execute(
                """
                INSERT INTO user_interactions
                  (user_id, guest_token, tmdb_id, interaction_type, duration_ms, completion_ratio, weight)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    guest_token,
                    int(row["tmdb_id"]),
                    interaction_type,
                    duration_ms,
                    completion_ratio,
                    weight,
                ),
            )
            inserted += 1
        conn.commit()
    return inserted


def aggregate_for_subject(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> dict[int, dict[str, Any]]:
    """Per tmdb_id: best tier, max weight, totals."""
    if user_id is None and not guest_token:
        return {}

    clause = "user_id = ?" if user_id is not None else "guest_token = ?"
    param: int | str = user_id if user_id is not None else guest_token  # type: ignore[assignment]

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT tmdb_id, interaction_type, duration_ms, completion_ratio, weight
            FROM user_interactions
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT 500
            """,
            (param,),
        ).fetchall()

    by_movie: dict[int, dict[str, Any]] = {}
    for row in rows:
        tid = int(row["tmdb_id"])
        rel = _tier_relation(str(row["interaction_type"]))
        entry = by_movie.setdefault(
            tid,
            {
                "tmdb_id": tid,
                "relations": set(),
                "weight": 0.0,
                "duration_ms": 0,
                "completion_ratio": 0.0,
            },
        )
        entry["duration_ms"] = max(entry["duration_ms"], int(row["duration_ms"]))
        entry["completion_ratio"] = max(entry["completion_ratio"], float(row["completion_ratio"]))
        if rel:
            entry["relations"].add(rel)
            entry["weight"] = max(entry["weight"], float(row["weight"]))
    return by_movie


def intent_seed_tmdb_ids(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
    min_weight: float = 0.3,
) -> list[tuple[int, float]]:
    agg = aggregate_for_subject(user_id=user_id, guest_token=guest_token)
    seeds = [(tid, data["weight"]) for tid, data in agg.items() if data["weight"] >= min_weight]
    seeds.sort(key=lambda x: x[1], reverse=True)
    return seeds


def behavior_triples_for_user(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> list[tuple[int, int, int]]:
    """Return (user_entity, relation_id, movie_entity) triples for explain/scoring hooks."""
    agg = aggregate_for_subject(user_id=user_id, guest_token=guest_token)
    user_entity = user_id if user_id is not None else abs(hash(guest_token or "")) % 10_000_000
    triples: list[tuple[int, int, int]] = []
    for tid, data in agg.items():
        for rel_name in data["relations"]:
            rel_id = BEHAVIOR_RELATIONS.get(rel_name)
            if rel_id is None:
                continue
            triples.append((user_entity, rel_id, int(tid)))
    return triples


def clear_interactions(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> int:
    if user_id is None and not guest_token:
        raise ValueError("user_id or guest_token required")
    clause = "user_id = ?" if user_id is not None else "guest_token = ?"
    param: int | str = user_id if user_id is not None else guest_token  # type: ignore[assignment]
    with connect() as conn:
        cur = conn.execute(f"DELETE FROM user_interactions WHERE {clause}", (param,))
        conn.commit()
        return int(cur.rowcount)


def ensure_guest_token(token: str | None) -> str:
    import secrets

    return token.strip() if token else secrets.token_urlsafe(24)


def register_guest_token(token: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO guest_sessions (token) VALUES (?)",
            (token,),
        )
        conn.commit()


def export_aggregated_json(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> str:
    agg = aggregate_for_subject(user_id=user_id, guest_token=guest_token)
    serializable = {
        str(k): {
            **v,
            "relations": sorted(v["relations"]),
        }
        for k, v in agg.items()
    }
    return json.dumps(serializable, indent=2)
