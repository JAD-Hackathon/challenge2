from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import get_args

from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, f1_score

from src.classification.onnx_classifier import MultiCategoryClassifier
from src.config import Category, load_settings
from src.detection.base import Detection
from src.taxonomy import Taxonomy, get_taxonomy


def benchmark_classifier(
    classifier: MultiCategoryClassifier,
    dataset_root: Path,
    taxonomy: Taxonomy,
    categories: tuple[Category, ...] = get_args(Category),
    split: str = "val",
    conf_threshold: float = 0.0,
) -> dict[str, dict[str, float]]:
    """Benchmark ONNX crop classifiers on ImageFolder validation or test splits."""
    for clf in classifier._classifiers:
        clf.conf_threshold = conf_threshold

    summary: dict[str, dict[str, float]] = {}

    for category in categories:
        split_dir = dataset_root / category / split
        specs = taxonomy.in_category(category)
        if not split_dir.is_dir() or not specs:
            continue

        coarse_label = specs[0].name
        samples: list[tuple[Path, str]] = [
            (img_path, cls_dir.name)
            for cls_dir in sorted(split_dir.iterdir())
            if cls_dir.is_dir()
            for img_path in sorted(cls_dir.iterdir())
            if img_path.is_file()
        ]
        if not samples:
            continue

        with Image.open(samples[0][0]) as im:
            rgb0 = im.convert("RGB")
            w0, h0 = rgb0.size
            classifier.refine(
                rgb0,
                [
                    Detection(
                        bbox_xyxy=(0.0, 0.0, float(w0), float(h0)),
                        score=1.0,
                        label=coarse_label,
                    )
                ],
            )

        y_true: list[str] = []
        y_pred: list[str] = []
        total_time_s = 0.0

        for img_path, true_label in samples:
            with Image.open(img_path) as im:
                rgb = im.convert("RGB")
            w, h = rgb.size
            det = Detection(
                bbox_xyxy=(0.0, 0.0, float(w), float(h)), score=1.0, label=coarse_label
            )

            t0 = time.perf_counter()
            refined = classifier.refine(rgb, [det])
            total_time_s += time.perf_counter() - t0

            y_true.append(true_label)
            y_pred.append(refined[0].label)

        acc = float(accuracy_score(y_true, y_pred))
        macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
        ms_per_crop = (total_time_s / len(samples)) * 1000.0

        print(
            f"\n=== Classification Report [{category} | {split} | N={len(samples)}] ==="
        )
        print(classification_report(y_true, y_pred, digits=4, zero_division=0))

        summary[category] = {
            "samples": float(len(samples)),
            "accuracy": acc,
            "macro_f1": macro_f1,
            "latency_ms": ms_per_crop,
        }

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark ONNX crop classifiers on val/test dataset splits."
    )
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/crops/dataset"))
    parser.add_argument("--split", default="val", choices=["val", "test"])
    parser.add_argument(
        "--conf", type=float, default=0.0, help="Classifier confidence threshold"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=list(get_args(Category)),
        choices=list(get_args(Category)),
    )
    args = parser.parse_args()

    settings = load_settings(overrides={"classification": {"enabled": True}})
    taxonomy = get_taxonomy()
    classifier = MultiCategoryClassifier(
        cfg=settings.classification,
        paths=settings.paths,
        taxonomy=taxonomy,
    )

    report = benchmark_classifier(
        classifier=classifier,
        dataset_root=args.dataset_dir,
        taxonomy=taxonomy,
        categories=tuple(args.categories),
        split=args.split,
        conf_threshold=args.conf,
    )

    print("\n=== Summary ===")
    for cat, metrics in report.items():
        print(
            f"{cat:8s} | N={int(metrics['samples']):4d} | "
            f"acc={metrics['accuracy']:.4f} | "
            f"macro_f1={metrics['macro_f1']:.4f} | "
            f"latency={metrics['latency_ms']:.2f} ms"
        )
