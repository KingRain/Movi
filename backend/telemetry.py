"""Micro-behavior telemetry ingestion and multi-behavior weighting."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from db import connect, init_db

init_db()

# Interaction tiers and baseline weights
INTERACTION_WEIGHTS = {
    "watched": 1.0,
    "trailer_complete": 0.85,
    "trailer_start": 0.45,
    "hover_deep": 0.25,
}

# Relation indices for KG multi-behavior modeling
KG_BEHAVIOR_RELATIONS = {
    "r_watched": 10,
    "r_trailer_complete": 11,
    "r_trailer_start": 12,
    "r_hover_deep": 13,
}


def classify_interaction(
    event_type: str,
    duration_ms: int,
    completion_ratio: float = 0.0,
) -> tuple[str, float]:
    """Classifies raw telemetry into a behavior tier and base weight."""
    ev = event_type.strip().lower()
    if ev == "watched":
        return "watched", INTERACTION_WEIGHTS["watched"]

    if ev in {"trailer", "trailer_progress", "trailer_complete"}:
        if completion_ratio >= 0.50 or duration_ms >= 30_000:
            return "trailer_complete", INTERACTION_WEIGHTS["trailer_complete"]
        if duration_ms >= 2000 or completion_ratio >= 0.05:
            return "trailer_start", INTERACTION_WEIGHTS["trailer_start"]
        return "hover_deep", INTERACTION_WEIGHTS["hover_deep"]

    # Hover events: intentionality threshold >= 1500ms
    if ev == "hover":
        if duration_ms >= 1500:
            return "hover_deep", INTERACTION_WEIGHTS["hover_deep"]
        return "hover_shallow", 0.05

    return "hover_deep", INTERACTION_WEIGHTS["hover_deep"]


def record_interaction(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
    tmdb_id: int,
    event_type: str,
    duration_ms: int = 0,
    completion_ratio: float = 0.0,
) -> dict[str, Any]:
    tier, base_weight = classify_interaction(event_type, duration_ms, completion_ratio)

    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO user_interactions (
                user_id, guest_token, tmdb_id, interaction_type,
                duration_ms, completion_ratio, weight
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                guest_token,
                int(tmdb_id),
                tier,
                int(duration_ms),
                float(completion_ratio),
                float(base_weight),
            ),
        )
        conn.commit()
        interaction_id = cur.lastrowid

    return {
        "id": interaction_id,
        "tmdb_id": tmdb_id,
        "interaction_type": tier,
        "weight": base_weight,
    }


def record_batch_interactions(
    items: list[dict[str, Any]],
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> int:
    if not items:
        return 0

    rows: list[tuple[int | None, str | None, int, str, int, float, float]] = []
    for item in items:
        tmdb_id = int(item.get("tmdb_id", 0))
        if tmdb_id <= 0:
            continue
        ev = str(item.get("event_type") or "hover")
        dur = int(item.get("duration_ms") or 0)
        comp = float(item.get("completion_ratio") or 0.0)
        tier, weight = classify_interaction(ev, dur, comp)
        rows.append((user_id, guest_token, tmdb_id, tier, dur, comp, weight))

    if not rows:
        return 0

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO user_interactions (
                user_id, guest_token, tmdb_id, interaction_type,
                duration_ms, completion_ratio, weight
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def get_user_micro_behaviors(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
    limit: int = 50,
) -> dict[int, dict[str, Any]]:
    """
    Returns aggregated interaction scores and tiers keyed by tmdb_id.
    Includes time-decay so recent micro-behaviors carry higher weight.
    """
    if not user_id and not guest_token:
        return {}

    with connect() as conn:
        if user_id:
            rows = conn.execute(
                """
                SELECT tmdb_id, interaction_type, duration_ms, completion_ratio, weight, created_at
                FROM user_interactions
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT tmdb_id, interaction_type, duration_ms, completion_ratio, weight, created_at
                FROM user_interactions
                WHERE guest_token = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (guest_token, limit),
            ).fetchall()

    aggregated: dict[int, dict[str, Any]] = {}
    now = datetime.now(timezone.utc)

    for row in rows:
        tid = int(row["tmdb_id"])
        tier = row["interaction_type"]
        weight = float(row["weight"])
        created_str = row["created_at"]
        
        # Calculate recency decay: lambda = 0.0001 per minute (~half-life ~5 days)
        decay = 1.0
        try:
            # SQLite default is UTC string
            created_dt = datetime.fromisoformat(created_str.replace(" ", "T")).replace(tzinfo=timezone.utc)
            minutes_old = max(0.0, (now - created_dt).total_seconds() / 60.0)
            decay = math.exp(-0.0001 * minutes_old)
        except Exception:
            decay = 1.0

        effective_weight = weight * decay

        if tid not in aggregated:
            aggregated[tid] = {
                "tmdb_id": tid,
                "best_tier": tier,
                "weight": effective_weight,
                "total_duration_ms": int(row["duration_ms"]),
                "max_completion": float(row["completion_ratio"]),
                "count": 1,
            }
        else:
            agg = aggregated[tid]
            agg["total_duration_ms"] += int(row["duration_ms"])
            agg["max_completion"] = max(agg["max_completion"], float(row["completion_ratio"]))
            agg["count"] += 1
            # Keep highest tier weight and boost slightly with repeated interactions
            if effective_weight > agg["weight"]:
                agg["best_tier"] = tier
                agg["weight"] = min(1.0, effective_weight + 0.05 * (agg["count"] - 1))
            else:
                agg["weight"] = min(1.0, agg["weight"] + 0.05)

    return aggregated


import secrets


def ensure_guest_token(token: str | None = None) -> str:
    t = (token or "").strip()
    if len(t) >= 12:
        return t
    return secrets.token_urlsafe(24)


def register_guest_token(token: str) -> None:
    t = (token or "").strip()
    if not t:
        return
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO guest_sessions (token) VALUES (?)",
            (t,),
        )
        conn.commit()


def insert_interactions(
    payload: list[dict[str, Any]],
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> int:
    return record_batch_interactions(payload, user_id=user_id, guest_token=guest_token)


def intent_seed_tmdb_ids(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
    min_weight: float = 0.20,
) -> list[tuple[int, float]]:
    behaviors = get_user_micro_behaviors(user_id=user_id, guest_token=guest_token)
    seeds = [
        (tid, round(info["weight"], 3))
        for tid, info in behaviors.items()
        if info["weight"] >= min_weight
    ]
    seeds.sort(key=lambda x: x[1], reverse=True)
    return seeds


def clear_interactions(
    *,
    user_id: int | None = None,
    guest_token: str | None = None,
) -> int:
    if not user_id and not guest_token:
        return 0
    with connect() as conn:
        if user_id:
            cur = conn.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        else:
            cur = conn.execute("DELETE FROM user_interactions WHERE guest_token = ?", (guest_token,))
        conn.commit()
        return cur.rowcount

