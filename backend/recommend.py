"""Popularity + user-neighborhood CF on KFGAN ratings. No torch required."""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np

RATINGS = Path(__file__).resolve().parent / "kfgan" / "data" / "music" / "ratings_final.txt"


@lru_cache(maxsize=1)
def _ratings() -> np.ndarray:
    return np.loadtxt(RATINGS, dtype=np.int32)


def valid_users() -> list[int]:
    return sorted(set(_ratings()[:, 0].tolist()))


def recommend(user_id: int, k: int = 10) -> list[tuple[int, float]]:
    ratings = _ratings()
    users = set(ratings[:, 0].tolist())
    if user_id not in users:
        user_id = 0  # ponytail: default to first user if unknown

    liked = set(ratings[(ratings[:, 0] == user_id) & (ratings[:, 2] == 1), 1])
    scores: dict[int, float] = defaultdict(float)

    for other in users - {user_id}:
        other_liked = set(ratings[(ratings[:, 0] == other) & (ratings[:, 2] == 1), 1])
        overlap = len(liked & other_liked)
        if overlap == 0:
            continue
        for item in other_liked - liked:
            scores[int(item)] += overlap

    if not scores:
        pop = Counter(ratings[ratings[:, 2] == 1, 1].tolist())
        for item, cnt in pop.most_common(k + len(liked)):
            if item not in liked:
                scores[int(item)] = float(cnt)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:k]


if __name__ == "__main__":
    recs = recommend(0, k=5)
    assert len(recs) == 5
    print("ok", recs)
