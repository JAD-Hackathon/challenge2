from __future__ import annotations

from collections import Counter
from pathlib import Path

import albumentations as A
import numpy as np
from PIL import Image

from src.taxonomy import Taxonomy

STAGE1_ID2LABEL: dict[int, str] = {
    0: "sign.other",
    1: "light.street_lamp",
    2: "waste.general",
}
STAGE1_LABEL2ID: dict[str, int] = {v: k for k, v in STAGE1_ID2LABEL.items()}


def validate_stage1_taxonomy(taxonomy: Taxonomy) -> None:
    """Ensure all Stage-1 target labels exist in the loaded taxonomy."""
    for name in STAGE1_ID2LABEL.values():
        taxonomy.get(name)


def build_transforms(train: bool) -> A.Compose:
    """Shared augmentation pipeline for all detector architectures."""
    transforms = (
        [
            A.HorizontalFlip(p=0.5),
            A.Affine(
                scale=(0.85, 1.15),
                translate_percent=(-0.05, 0.05),
                rotate=(-5, 5),
                border_mode=0,
                p=0.5,
            ),
            A.ColorJitter(
                brightness=0.25, contrast=0.25, saturation=0.2, hue=0.05, p=0.6
            ),
            A.OneOf(
                [
                    A.MotionBlur(blur_limit=5, p=1.0),
                    A.GaussianBlur(blur_limit=3, p=1.0),
                ],
                p=0.2,
            ),
        ]
        if train
        else []
    )
    return A.Compose(
        transforms,
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_area=16,
            min_visibility=0.3,
        ),
    )


def load_split_records(
    split_file: Path,
    labels_dir: Path,
) -> list[tuple[Path, list[list[float]], list[int]]]:
    """Parse split file and corresponding YOLO .txt labels with clamped [0, 1] coords."""
    image_paths = [
        Path(line.strip())
        for line in split_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records: list[tuple[Path, list[list[float]], list[int]]] = []

    for img_path in image_paths:
        label_path = labels_dir / f"{img_path.stem}.txt"
        bboxes: list[list[float]] = []
        class_ids: list[int] = []

        if label_path.exists():
            for line in label_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                class_id = int(parts[0])
                if class_id not in STAGE1_ID2LABEL:
                    continue
                xc, yc, w, h = map(float, parts[1:])
                x1 = max(0.0, xc - w / 2.0)
                y1 = max(0.0, yc - h / 2.0)
                x2 = min(1.0, xc + w / 2.0)
                y2 = min(1.0, yc + h / 2.0)
                if x2 - x1 > 1e-4 and y2 - y1 > 1e-4:
                    bboxes.append([(x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1])
                    class_ids.append(class_id)

        records.append((img_path, bboxes, class_ids))

    return records


def compute_sample_weights(
    records: list[tuple[Path, list[list[float]], list[int]]],
    power: float = 0.5,
) -> list[float]:
    """Compute per-image weights to oversample rare classes."""
    class_counts: Counter[int] = Counter()
    for _, _, class_ids in records:
        class_counts.update(class_ids)

    total_boxes = sum(class_counts.values()) or 1
    n_classes = max(1, len(class_counts))
    class_weights = {
        class_id: (total_boxes / (n_classes * count)) ** power
        for class_id, count in class_counts.items()
    }
    print(f"Box distribution: {dict(class_counts)} | Sample weights: {class_weights}")

    weights: list[float] = []
    for _, _, class_ids in records:
        if not class_ids:
            weights.append(0.5)
        else:
            weights.append(max(class_weights[c] for c in class_ids))
    return weights


def read_rgb_array(img_path: Path) -> np.ndarray:
    """Load an image as an RGB NumPy array."""
    with Image.open(img_path) as img:
        return np.array(img.convert("RGB"))
