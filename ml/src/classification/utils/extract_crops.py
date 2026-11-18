from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from src.config import Settings, load_settings
from src.detection.utils.helpers import yolo_to_xyxy

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def category_by_class_id(settings: Settings) -> dict[int, str]:
    """Derive class_id -> super-category mapping from detection.class_map order."""
    seen: list[str] = []
    for target in settings.detection.class_map.values():
        cat = target.split(".", 1)[0]
        if cat not in seen:
            seen.append(cat)
    return dict(enumerate(seen))


def build_image_index(search_dirs: list[Path]) -> dict[str, Path]:
    """Index all image files by stem across raw and shared image directories."""
    index: dict[str, Path] = {}
    for root in search_dirs:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in _IMAGE_EXTS:
                index.setdefault(path.stem, path)
    return index


def main() -> None:
    """Extract padded object crops from train/val splits for 2-stage classification."""
    parser = argparse.ArgumentParser(
        description="Extract object crops for classification."
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/crops/raw"))
    parser.add_argument(
        "--margin", type=float, default=0.08, help="Context padding ratio"
    )
    parser.add_argument(
        "--min-side", type=int, default=16, help="Minimum crop side in pixels"
    )
    args = parser.parse_args()

    settings = load_settings()
    id_to_cat = category_by_class_id(settings)
    labels_dir = settings.paths.labels
    splits_dir = settings.paths.splits

    raw_dir = settings.paths._abs(settings.paths.raw_dir)
    image_index = build_image_index([raw_dir, settings.paths.images_dir])
    print(
        f"Indexed {len(image_index)} images across {raw_dir} and {settings.paths.images_dir}"
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for cat in id_to_cat.values():
        (args.out_dir / cat).mkdir(parents=True, exist_ok=True)

    manifest_path = args.out_dir / "crops_manifest.jsonl"
    counts: dict[str, dict[str, int]] = {"train": {}, "val": {}}

    with manifest_path.open("w", encoding="utf-8") as mf:
        for split in ("train", "val"):
            split_file = splits_dir / f"{split}.txt"
            if not split_file.is_file():
                print(f"[WARN] Split file not found: {split_file}")
                continue

            entries = [
                line.strip()
                for line in split_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            for entry in entries:
                entry_path = Path(entry)
                image_id = entry_path.stem
                label_file = labels_dir / f"{image_id}.txt"
                if not label_file.is_file():
                    continue

                img_path = (
                    entry_path if entry_path.is_file() else image_index.get(image_id)
                )
                if img_path is None:
                    continue

                with Image.open(img_path) as img:
                    img = img.convert("RGB")
                    img_w, img_h = img.size

                    for idx, line in enumerate(
                        label_file.read_text(encoding="utf-8").splitlines()
                    ):
                        parts = line.strip().split()
                        if len(parts) < 5:
                            continue

                        category = id_to_cat.get(int(parts[0]))
                        if category is None:
                            continue

                        cx, cy, w, h = map(float, parts[1:5])
                        x1, y1, x2, y2 = yolo_to_xyxy(
                            cx, cy, w, h, img_w, img_h, args.margin
                        )

                        if (x2 - x1) < args.min_side or (y2 - y1) < args.min_side:
                            continue

                        crop_filename = f"{split}_{image_id}_{idx:03d}.jpg"
                        crop_rel_path = f"{category}/{crop_filename}"
                        img.crop((x1, y1, x2, y2)).save(
                            args.out_dir / crop_rel_path, quality=95
                        )

                        counts[split][category] = counts[split].get(category, 0) + 1
                        record = {
                            "crop_id": f"{image_id}_{idx:03d}",
                            "split": split,
                            "category": category,
                            "image_id": image_id,
                            "box_idx": idx,
                            "bbox_xyxy": [x1, y1, x2, y2],
                            "path": crop_rel_path,
                        }
                        mf.write(json.dumps(record, ensure_ascii=False) + "\n")

    print("Extraction complete:", json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
