from __future__ import annotations

import random as rnd
from collections import defaultdict
from pathlib import Path
from src.io.common import read_manifest
from src.config import get_settings

paths_config = get_settings().paths


def build_splits(
    val_ratio: float = 0.20, test_ratio: float = 0.05, seed: int = 42
) -> None:
    """Split images on train / validation / test samples (keep only images with label)."""
    manifest = read_manifest(paths_config.manifest_file)

    by_seq: dict[str, list[Path]] = defaultdict(list)
    matched = 0

    for rec in manifest.values():
        if not rec.save_path:
            continue

        img_path = paths_config.raw_dir / rec.save_path
        lbl_path = paths_config.labels_dir / f"{img_path.stem}.txt"

        if img_path.exists() and lbl_path.exists():
            seq_key = rec.sequence_id or rec.image_id
            by_seq[seq_key].append(img_path.resolve())
            matched += 1

    sequence = list(by_seq.keys())
    rng = rnd.Random(seed)
    rng.shuffle(sequence)

    n_total = matched
    n_test = max(1, int(n_total * test_ratio))
    n_val = max(1, int(n_total * val_ratio))

    splits: dict[str, list[Path]] = {"train": [], "val": [], "test": []}

    for seq in sequence:
        imgs = by_seq[seq]
        if len(splits["test"]) < n_test:
            splits["test"].extend(imgs)
        if len(splits["val"]) < n_val:
            splits["val"].extend(imgs)
        else:
            splits["train"].extend(imgs)

    paths_config.splits_dir.mkdir(parents=True, exist_ok=True)
    for split, sample in splits.items():
        out_file = paths_config.splits_dir / f"{split}.txt"
        out_file.write_text(
            "\n".join(str(path for path in sample)) + "\n", encoding="utf-8"
        )
        print(f"{split}: {len(sample)} images -> {out_file}")


if __name__ == "__main__":
    build_splits()
