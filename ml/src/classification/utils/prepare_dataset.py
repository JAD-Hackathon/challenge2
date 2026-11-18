from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from urllib.parse import unquote

GTSRB_TO_CLS: dict[int, str] = {
    14: "sign.stop",
    13: "sign.yield",
    0: "sign.speed_limit",
    1: "sign.speed_limit",
    2: "sign.speed_limit",
    3: "sign.speed_limit",
    4: "sign.speed_limit",
    5: "sign.speed_limit",
    6: "sign.speed_limit",
    7: "sign.speed_limit",
    8: "sign.speed_limit",
}


def extract_ls_choice(task: dict) -> tuple[str | None, bool]:
    """Extract (chosen_label, was_cancelled) from a Label Studio exported task."""
    annotations = task.get("annotations") or []
    cancelled = False
    for ann in annotations:
        if ann.get("was_cancelled"):
            cancelled = True
            continue
        for res in ann.get("result") or []:
            choices = res.get("value", {}).get("choices") or []
            if choices:
                return str(choices[0]), False
    return None, cancelled


def resolve_crop_file(raw_dir: Path, category: str, image_ref: str) -> Path | None:
    """Resolve local crop file path from Label Studio task data image reference."""
    decoded = unquote(image_ref).replace("\\", "/")
    rel_part = decoded.split("?d=")[-1].lstrip("/")
    filename = Path(rel_part).name

    for candidate in (
        raw_dir / rel_part,
        raw_dir / category / filename,
    ):
        if candidate.is_file():
            return candidate

    if "-" in filename:
        stripped = filename.split("-", 1)[1]
        for candidate in (
            raw_dir / Path(rel_part).parent / stripped,
            raw_dir / category / stripped,
        ):
            if candidate.is_file():
                return candidate

    return None


def import_label_studio(
    ls_json: Path, raw_dir: Path, out_dir: Path, category: str
) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Convert Label Studio JSON export into split/class ImageFolder directories."""
    tasks = json.loads(ls_json.read_text(encoding="utf-8"))
    stats: dict[str, dict[str, int]] = {"train": {}, "val": {}}
    skipped: list[str] = []

    cat_out = out_dir / category
    if cat_out.exists():
        shutil.rmtree(cat_out)

    for task in tasks:
        image_ref = task.get("data", {}).get("image", "")
        src_file = resolve_crop_file(raw_dir, category, image_ref)
        label, was_cancelled = extract_ls_choice(task)

        if was_cancelled and src_file is not None:
            skipped.append(src_file.name)
            continue

        if not label or src_file is None:
            continue

        split = "val" if src_file.name.startswith("val_") else "train"
        dst_dir = cat_out / split / label
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_dir / src_file.name)

        stats[split][label] = stats[split].get(label, 0) + 1

    return stats, skipped


def ensure_min_val_samples(
    out_dir: Path, category: str, min_val: int = 8, seed: int = 42
) -> None:
    """Move a small fraction of train crops to val if a rare subclass has too few val examples."""
    rng = random.Random(seed)
    train_root = out_dir / category / "train"
    val_root = out_dir / category / "val"
    if not train_root.is_dir():
        return

    for cls_dir in sorted(train_root.iterdir()):
        if not cls_dir.is_dir():
            continue
        val_cls_dir = val_root / cls_dir.name
        val_cls_dir.mkdir(parents=True, exist_ok=True)

        val_files = list(val_cls_dir.iterdir())
        train_files = sorted(cls_dir.iterdir())
        if len(val_files) >= min_val or len(train_files) <= min_val:
            continue

        needed = min(min_val - len(val_files), max(1, len(train_files) // 5))
        rng.shuffle(train_files)
        for f in train_files[:needed]:
            shutil.move(str(f), str(val_cls_dir / f.name))


def import_gtsrb(
    gtsrb_train_dir: Path, out_dir: Path, max_other: int = 800, seed: int = 42
) -> dict[str, int]:
    """Map GTSRB training folders (00000..00042) into train split of sign taxonomy."""
    rng = random.Random(seed)
    added: dict[str, int] = {}
    other_pool: list[Path] = []

    for cls_dir in sorted(gtsrb_train_dir.iterdir()):
        if not cls_dir.is_dir() or not cls_dir.name.isdigit():
            continue
        cls_id = int(cls_dir.name)
        target_label = GTSRB_TO_CLS.get(cls_id, "sign.other")
        files = [
            p for p in cls_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".ppm"}
        ]

        if target_label == "sign.other":
            other_pool.extend(files)
            continue

        dst_dir = out_dir / "sign" / "train" / target_label
        dst_dir.mkdir(parents=True, exist_ok=True)
        for p in files:
            shutil.copy2(p, dst_dir / f"gtsrb_{cls_id:02d}_{p.name}")
            added[target_label] = added.get(target_label, 0) + 1

    if other_pool:
        rng.shuffle(other_pool)
        selected = other_pool[:max_other]
        dst_dir = out_dir / "sign" / "train" / "sign.other"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for idx, p in enumerate(selected):
            shutil.copy2(p, dst_dir / f"gtsrb_other_{idx:04d}{p.suffix.lower()}")
        added["sign.other"] = len(selected)

    return added


def main() -> None:
    """Build ImageFolder datasets from Label Studio exports and optional public datasets."""
    parser = argparse.ArgumentParser(description="Prepare classification datasets.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/crops/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/crops/dataset"))
    parser.add_argument("--ls-sign", type=Path, default=None)
    parser.add_argument("--ls-waste", type=Path, default=None)
    parser.add_argument("--ls-light", type=Path, default=None)
    parser.add_argument(
        "--gtsrb-dir",
        type=Path,
        default=None,
        help="Path to GTSRB/Final_Training/Images",
    )
    parser.add_argument("--gtsrb-max-other", type=int, default=800)
    args = parser.parse_args()

    skipped_report: dict[str, list[str]] = {}
    for category, ls_path in (
        ("sign", args.ls_sign),
        ("waste", args.ls_waste),
        ("light", args.ls_light),
    ):
        if ls_path and ls_path.is_file():
            stats, skipped = import_label_studio(
                ls_path, args.raw_dir, args.out_dir, category
            )
            ensure_min_val_samples(args.out_dir, category)
            print(f"[LS {category}] -> {json.dumps(stats)}")
            if skipped:
                skipped_report[category] = skipped

    if skipped_report:
        skipped_path = args.out_dir / "skipped_crops.json"
        skipped_path.parent.mkdir(parents=True, exist_ok=True)
        skipped_path.write_text(json.dumps(skipped_report, indent=2), encoding="utf-8")
        print(f"Saved skipped crop filenames to {skipped_path}")

    if args.gtsrb_dir and args.gtsrb_dir.is_dir():
        gtsrb_stats = import_gtsrb(
            args.gtsrb_dir, args.out_dir, max_other=args.gtsrb_max_other
        )
        print(f"[GTSRB -> sign/train] -> {json.dumps(gtsrb_stats)}")


if __name__ == "__main__":
    main()
