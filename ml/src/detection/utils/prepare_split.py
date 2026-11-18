from __future__ import annotations

import random as rnd
from collections import defaultdict
from pathlib import Path
from src.config import get_settings
from src.io.common import read_manifest

paths_config = get_settings().paths


def build_splits(
    val_ratio: float = 0.20, test_ratio: float = 0.05, seed: int = 42
) -> None:
    """Split labeled images into train / validation / test sets by sequence."""
    if val_ratio < 0 or test_ratio < 0 or val_ratio + test_ratio >= 1:
        raise ValueError("Invalid split ratios.")
    manifest = read_manifest(paths_config.manifest_file)

    by_seq: dict[str, list[Path]] = defaultdict(list)

    for rec in manifest.values():
        if not rec.save_path:
            continue

        img_path = paths_config.raw_dir / rec.save_path
        lbl_path = paths_config.labels_dir / f"{img_path.stem}.txt"

        if img_path.exists() and lbl_path.exists():
            seq_key = rec.sequence_id or rec.image_id
            by_seq[seq_key].append(img_path.resolve())

    if not by_seq:
        raise ValueError("No labeled images found.")

    rng = rnd.Random(seed)

    # shuffle groups
    sequences = list(by_seq.values())
    rng.shuffle(sequences)

    # sort by group size
    sequences.sort(key=len, reverse=True)

    n_total = sum(len(group) for group in sequences)

    targets = {
        "train": round(n_total * (1 - val_ratio - test_ratio)),
        "val": round(n_total * val_ratio),
        "test": round(n_total * test_ratio),
    }

    splits: dict[str, list[Path]] = {
        "train": [],
        "val": [],
        "test": [],
    }

    # assign sequences
    for group in sequences:
        split = max(
            targets,
            key=lambda name: (targets[name] - len(splits[name]))
            / max(targets[name], 1),
        )

        splits[split].extend(group)

    paths_config.splits_dir.mkdir(parents=True, exist_ok=True)

    for split, images in splits.items():
        rng.shuffle(images)

        out_file = paths_config.splits_dir / f"{split}.txt"
        out_file.write_text(
            "\n".join(str(path) for path in images) + "\n",
            encoding="utf-8",
        )

        actual_ratio = len(images) / n_total

        print(
            f"{split}: {len(images)} images "
            f"({actual_ratio:.1%}, target: "
            f"{targets[split] / n_total:.1%}) -> {out_file}"
        )

    print(f"\nTotal: {n_total} images")
    print(f"Sequences: {len(sequences)}")


if __name__ == "__main__":
    build_splits()
