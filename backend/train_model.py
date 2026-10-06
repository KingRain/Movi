"""Train KFGAN and save checkpoint. Run from backend/: python train_model.py"""
from __future__ import annotations

import os
import sys
from argparse import Namespace
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

KFGAN_SRC = Path(__file__).resolve().parent / "kfgan" / "src"
CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"


def main() -> None:
    try:
        import torch
    except ImportError as e:
        raise SystemExit(
            "torch not installed. Run: pip install -r requirements-train.txt"
        ) from e

    os.chdir(KFGAN_SRC)
    sys.path.insert(0, str(KFGAN_SRC))

    import torch
    from data_loader import load_data
    from train import _get_feed_data, _get_feed_label, _init_model, train

    args = Namespace(
        dataset=os.environ.get("MOVI_DATASET", "music"),
        n_epoch=int(os.environ.get("MOVI_EPOCHS", "5")),
        batch_size=2048,
        n_layer=3,
        lr=0.004,
        l2_weight=1e-4,
        dim=128,
        user_triple_set_size=128,
        user_potential_triple_set_sampling_size=128,
        item_origin_triple_set_size=128,
        item_potential_triple_set_sampling_size=128,
        agg="concat",
        use_cuda=torch.cuda.is_available(),
        show_topk=False,
        random_flag=False,
    )
    max_batches = int(os.environ.get("MOVI_MAX_BATCHES", "0"))

    data_info = load_data(args)
    model, optimizer, loss_func = _init_model(args, data_info)
    train_data, _, _ = data_info[:3]
    triple_sets = data_info[5:9]

    device = "cuda" if args.use_cuda else "cpu"
    print(f"training on {device}, epochs={args.n_epoch}, max_batches={max_batches or 'all'}", flush=True)

    for step in range(args.n_epoch):
        import numpy as np

        np.random.shuffle(train_data)
        start = 0
        batch_num = 0
        while start < train_data.shape[0]:
            labels = _get_feed_label(args, train_data[start : start + args.batch_size, 2])
            scores, cl_loss = model(
                *_get_feed_data(args, train_data, *triple_sets, start, start + args.batch_size)
            )
            loss = loss_func(scores, labels) + cl_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            start += args.batch_size
            batch_num += 1
            print(f"epoch {step} batch {batch_num} loss={float(loss):.4f}", flush=True)
            if max_batches and batch_num >= max_batches:
                break
        print(f"epoch {step} done", flush=True)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / "model.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "args": vars(args),
            "n_entity": data_info[3],
            "n_relation": data_info[4],
        },
        path,
    )
    print(f"saved {path}")


if __name__ == "__main__":
    main()
