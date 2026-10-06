"""KFGAN inference wrapper. Does not modify kfgan/src."""
from __future__ import annotations

import os
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np

KFGAN_SRC = Path(__file__).resolve().parent / "kfgan" / "src"
CHECKPOINT = Path(__file__).resolve().parent / "checkpoints" / "model.pt"


def _kfgan_imports():
    os.chdir(KFGAN_SRC)
    if str(KFGAN_SRC) not in sys.path:
        sys.path.insert(0, str(KFGAN_SRC))
    from data_loader import load_data  # noqa: WPS433
    from model import FGKAN  # noqa: WPS433
    from train import (  # noqa: WPS433
        _get_feed_data,
        _get_topk_feed_data,
        _get_user_record,
    )

    return load_data, FGKAN, _get_feed_data, _get_topk_feed_data, _get_user_record


class Engine:
    def __init__(self) -> None:
        self._ready = False
        self._model = None
        self._args: Namespace | None = None
        self._data_info = None
        self._helpers = None

    @property
    def ready(self) -> bool:
        return CHECKPOINT.exists()

    def _load(self) -> None:
        if self._ready:
            return
        try:
            import torch
        except ImportError as e:
            raise RuntimeError(
                "KFGAN checkpoint found but torch is not installed. "
                "Run: pip install -r requirements-train.txt"
            ) from e

        load_data, FGKAN, *helpers = _kfgan_imports()
        ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
        args = Namespace(**ckpt["args"])
        args.use_cuda = bool(torch.cuda.is_available())

        data_info = load_data(args)
        model = FGKAN(args, ckpt["n_entity"], ckpt["n_relation"])
        model.load_state_dict(ckpt["state_dict"])
        if args.use_cuda:
            model.cuda()
        model.eval()

        self._args = args
        self._data_info = data_info
        self._model = model
        self._helpers = helpers
        self._ready = True

    def recommend(self, user_id: int, k: int = 10) -> list[int] | list[tuple[int, float]]:
        if not self.ready:
            from recommend import recommend as cf_recommend

            return [i for i, _ in cf_recommend(user_id, k=k)]

        from recommend import recommend as cf_recommend

        # ponytail: CF shortlist first — full-catalog KFGAN scoring is too slow on CPU
        pool_size = int(os.environ.get("MOVI_SCORE_POOL", "32"))
        candidates = [i for i, _ in cf_recommend(user_id, k=max(k, pool_size))]
        if not candidates:
            return []
        scored = self._score_items(user_id, candidates)
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
        return ranked[:k]

    def _score_items(self, user_id: int, candidates: list[int]) -> dict[int, float]:
        self._load()
        get_feed, get_topk, _ = self._helpers
        args = self._args
        triple_sets = self._data_info[5:9]
        import torch

        scores: dict[int, float] = {}
        start = 0
        while start < len(candidates):
            batch = candidates[start : start + args.batch_size]
            if len(batch) < args.batch_size:
                batch = batch + [batch[-1]] * (args.batch_size - len(batch))
            input_data = get_topk(user_id, batch)
            with torch.no_grad():
                batch_scores, _ = self._model(
                    *get_feed(args, input_data, *triple_sets, 0, args.batch_size)
                )
            n = min(args.batch_size, len(candidates) - start)
            for item, score in zip(candidates[start : start + n], batch_scores[:n]):
                scores[int(item)] = float(score)
            start += args.batch_size
        return scores

    def explain(self, user_id: int, movie_id: int) -> dict:
        if not self.ready:
            return {
                "user_id": user_id,
                "movie_id": movie_id,
                "edges": [{"from": user_id, "to": movie_id, "rel": "stub"}],
            }
        self._load()
        user_triples = self._data_info[5].get(user_id, [])
        item_triples = self._data_info[6].get(movie_id, [])
        edges = []
        for layer in range(min(len(user_triples), len(item_triples))):
            h, r, t = user_triples[layer]
            edges.append({"from": int(h[0]), "rel": int(r[0]), "to": int(t[0]), "side": "user"})
        for layer in range(len(item_triples)):
            h, r, t = item_triples[layer]
            edges.append({"from": int(h[0]), "rel": int(r[0]), "to": int(t[0]), "side": "item"})
        return {"user_id": user_id, "movie_id": movie_id, "edges": edges}


engine = Engine()


if __name__ == "__main__":
    ids = engine.recommend(0, k=3)
    assert isinstance(ids, list)
    exp = engine.explain(0, 1)
    assert "edges" in exp
    print("ok", ids, len(exp["edges"]))
