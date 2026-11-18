from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from src.config import get_settings
from src.detection.training.common.dataset import STAGE1_ID2LABEL, load_split_records


def export_split_to_coco(
    split_name: str, split_file: Path, labels_dir: Path, out_dir: Path
) -> Path:
    """Export a dataset split to COCO annotation format."""
    records = load_split_records(split_file, labels_dir)
    categories = [
        {
            "id": cid,
            "name": name,
            "category": name.split(".", 1)[0],
        }
        for cid, name in sorted(STAGE1_ID2LABEL.items())
    ]

    images_json: list[dict] = []
    annotations_json: list[dict] = []
    ann_id = 1

    for img_id, (img_path, bboxes, class_ids) in enumerate(records, start=1):
        with Image.open(img_path) as im:
            w, h = im.size

        images_json.append(
            {
                "id": img_id,
                "file_name": str(img_path.resolve()),
                "width": w,
                "height": h,
            }
        )

        for (xc, yc, bw, bh), class_id in zip(bboxes, class_ids, strict=True):
            abs_w = bw * w
            abs_h = bh * h
            abs_x = (xc - bw / 2.0) * w
            abs_y = (yc - bh / 2.0) * h
            annotations_json.append(
                {
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": class_id,
                    "bbox": [
                        round(abs_x, 2),
                        round(abs_y, 2),
                        round(abs_w, 2),
                        round(abs_h, 2),
                    ],
                    "area": round(abs_w * abs_h, 2),
                    "iscrowd": 0,
                }
            )
            ann_id += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"instances_{split_name}.json"
    payload = {
        "images": images_json,
        "annotations": annotations_json,
        "categories": categories,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"Exported {split_name}: {len(images_json)} images, {len(annotations_json)} boxes -> {out_file}"
    )
    return out_file


def export_all() -> None:
    """Export all available dataset splits to COCO format."""
    paths = get_settings().paths
    coco_dir = paths.data_dir / "coco"
    for split in ("train", "val", "test"):
        split_file = paths.splits / f"{split}.txt"
        if split_file.exists():
            export_split_to_coco(split, split_file, paths.labels, coco_dir)


if __name__ == "__main__":
    export_all()
