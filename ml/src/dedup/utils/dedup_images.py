from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image

from src.config import get_settings
from src.geometry.helpers import distance_m
from src.io.common import (
    ImageRecord,
    read_manifest,
    upsert_manifest,
)

paths_config = get_settings().paths


def dhash(image_path: Path, hash_size: int = 8) -> int:
    """Calculate 64-bits difference hash for image."""
    with Image.open(image_path) as img:
        gray = img.convert("L").resize(
            (hash_size + 1, hash_size), Image.Resampling.LANCZOS
        )
        pixels = list(gray.get_flattened_data())
    bits = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            bits = (bits << 1) | int(pixels[offset + col] > pixels[offset + col + 1])
    return bits


def hamming_dist(h1: int, h2: int) -> int:
    return (h1 ^ h2).bit_count()


def angle_diff(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def deduplicate(
    min_dist_m: float = 2.0,
    max_angle_deg: float = 15.0,
    max_hash_dist: int = 6,
    delete_files: bool = False,
) -> None:
    records = list(read_manifest(paths_config.manifest_file).values())
    records.sort(key=lambda r: (r.width or 0) * (r.height or 0), reverse=True)

    kept: list[tuple[ImageRecord, int]] = []
    removed: list[ImageRecord] = []

    for rec in records:
        if not rec.save_path:
            continue
        img_path = paths_config.raw_dir / rec.save_path
        if not img_path.exists():
            continue

        h = dhash(img_path)
        is_dup = False

        for k_rec, k_hash in kept:
            if hamming_dist(h, k_hash) <= max_hash_dist:
                is_dup = True
                break

            if (
                distance_m(rec.lat, rec.lon, k_rec.lat, k_rec.lon) < min_dist_m
                and angle_diff(rec.heading, k_rec.heading) < max_angle_deg
            ):
                is_dup = True
                break

        if is_dup:
            removed.append(rec)
        else:
            kept.append((rec, h))

    print(f"Total: {len(records)} | Left: {len(kept)} | Removed: {len(removed)}")

    if delete_files:
        for rec in removed:
            p = paths_config.raw_dir / rec.save_path
            if p.exists():
                p.unlink()

        paths_config.manifest_file.unlink(missing_ok=True)
        upsert_manifest([r for r, _ in kept], paths_config.manifest_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Remove duplicates from the disk and manifest",
    )
    parser.add_argument(
        "--hash-dist",
        type=int,
        default=6,
        help="dHash similarity threshold (0-64; 5-8 for duplicates)",
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        default=2.0,
        help="Min. distance between frames with the same direction (m)",
    )
    args = parser.parse_args()

    deduplicate(
        min_dist_m=args.min_dist, max_hash_dist=args.hash_dist, delete_files=args.apply
    )
