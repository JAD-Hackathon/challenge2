from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
from PIL import Image
from torchmetrics.detection.mean_ap import MeanAveragePrecision

from src.config import load_settings
from src.detection.base import Detector, build_detector
from src.detection.training.common.dataset import (
    STAGE1_ID2LABEL,
    STAGE1_LABEL2ID,
    load_split_records,
)
from src.taxonomy import get_taxonomy


def benchmark_detector(
    detector: Detector,
    split_file: Path,
    labels_dir: Path,
    batch_size: int = 4,
) -> dict[str, float]:
    """
    Benchmark an object detector on a dataset split.
    Computes mAP@50, mAP@50-95, per-class AP,
    and average inference latency per image.
    """
    records = load_split_records(split_file, labels_dir)
    metric = MeanAveragePrecision(
        box_format="xyxy", iou_type="bbox", class_metrics=True
    )

    # warmup
    if records:
        with Image.open(records[0][0]) as img:
            detector.detect(img.convert("RGB"))

    total_time_s = 0.0
    total_images = 0

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        pil_images: list[Image.Image] = []
        targets: list[dict[str, torch.Tensor]] = []

        for img_path, bboxes, class_ids in batch:
            img = Image.open(img_path).convert("RGB")
            w, h = img.size
            pil_images.append(img)

            boxes_xyxy: list[list[float]] = []
            for xc, yc, bw, bh in bboxes:
                boxes_xyxy.append(
                    [
                        (xc - bw / 2.0) * w,
                        (yc - bh / 2.0) * h,
                        (xc + bw / 2.0) * w,
                        (yc + bh / 2.0) * h,
                    ]
                )

            targets.append(
                {
                    "boxes": torch.tensor(boxes_xyxy, dtype=torch.float32)
                    if boxes_xyxy
                    else torch.zeros((0, 4), dtype=torch.float32),
                    "labels": torch.tensor(class_ids, dtype=torch.int64),
                }
            )

        t0 = time.perf_counter()
        batch_detections = detector.detect_batch(pil_images)
        total_time_s += time.perf_counter() - t0
        total_images += len(pil_images)

        preds: list[dict[str, torch.Tensor]] = []
        for detection in batch_detections:
            valid = [d for d in detection if d.label in STAGE1_LABEL2ID]
            preds.append(
                {
                    "boxes": torch.tensor(
                        [list(d.bbox_xyxy) for d in valid], dtype=torch.float32
                    )
                    if valid
                    else torch.zeros((0, 4), dtype=torch.float32),
                    "scores": torch.tensor(
                        [d.score for d in valid], dtype=torch.float32
                    ),
                    "labels": torch.tensor(
                        [STAGE1_LABEL2ID[d.label] for d in valid], dtype=torch.int64
                    ),
                }
            )

        metric.update(preds, targets)

    stats = metric.compute()
    ms_per_img = (total_time_s / max(1, total_images)) * 1000.0

    results: dict[str, float] = {
        "mAP@50": float(stats["map_50"].item()),
        "mAP@50-95": float(stats["map"].item()),
        "latency_ms": ms_per_img,
    }

    per_class = stats.get("map_per_class")
    if per_class is not None and per_class.ndim > 0:
        for idx, val in enumerate(per_class.tolist()):
            cls_name = STAGE1_ID2LABEL.get(idx, str(idx))
            results[f"AP_{cls_name}"] = float(val)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark any registered detector on val/test split."
    )
    parser.add_argument(
        "--backend", default="rtdetr", help="Backend name (e.g. rtdetr, yolo)"
    )
    parser.add_argument(
        "--weights", default="rtdetr_best", help="Weights file/dir inside weights/"
    )
    parser.add_argument("--split", default="val", choices=["val", "test"])
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    settings = load_settings(
        overrides={
            "detection": {
                "backend": args.backend,
                "weights": args.weights,
                "conf": 0.05,
            }
        }
    )
    taxonomy = get_taxonomy()
    weights_path = settings.paths.weights_path(args.weights)
    detector = build_detector(settings.detection, taxonomy, weights_path=weights_path)

    split_path = settings.paths.splits / f"{args.split}.txt"
    report = benchmark_detector(
        detector, split_path, settings.paths.labels, batch_size=args.batch_size
    )

    print(f"\n=== Benchmark [{args.backend} | {args.weights}] on {args.split} ===")
    for k, v in report.items():
        print(f"{k:22s}: {v:.4f}")
