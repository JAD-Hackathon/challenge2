from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from src.config import load_settings
from src.io.common import ImageRecord, read_manifest

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _clean_invalid_custom_lines(manifest_path: Path) -> None:
    """Remove previously appended lines with source='custom' from manifest."""
    if not manifest_path.is_file():
        return
    valid_lines: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if data.get("source") == "custom":
                continue
        except json.JSONDecodeError:
            continue
        valid_lines.append(line)
    manifest_path.write_text(
        "\n".join(valid_lines) + ("\n" if valid_lines else ""), encoding="utf-8"
    )


def register_custom_images(
    default_lat: float = 40.6412,
    default_lon: float = -8.6538,
    default_heading: float = 0.0,
) -> int:
    """Append unmanifested images from data/raw/custom/ with labels to images.jsonl."""
    settings = load_settings()
    raw_dir = settings.paths._abs(settings.paths.raw_dir)
    custom_dir = raw_dir / "custom"
    labels_dir = settings.paths.labels
    manifest_path = settings.paths._abs(settings.paths.manifest_file)

    if not custom_dir.is_dir():
        print(f"Custom directory not found: {custom_dir}")
        return 0

    _clean_invalid_custom_lines(manifest_path)
    existing = read_manifest(manifest_path)
    existing_paths = {
        rec.save_path.replace("\\", "/") for rec in existing.values() if rec.save_path
    }

    added = 0
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("a", encoding="utf-8") as mf:
        for img_path in sorted(custom_dir.iterdir()):
            if not img_path.is_file() or img_path.suffix.lower() not in _IMAGE_EXTS:
                continue

            rel_save_path = f"custom/{img_path.name}"
            if rel_save_path in existing_paths or img_path.stem in existing:
                continue

            label_file = labels_dir / f"{img_path.stem}.txt"
            if not label_file.is_file():
                continue

            with Image.open(img_path) as img:
                width, height = img.size

            record = ImageRecord(
                image_id=img_path.stem,
                source="video",
                source_id=img_path.stem,
                save_path=rel_save_path,
                lat=default_lat,
                lon=default_lon,
                heading=default_heading,
                width=width,
                height=height,
                sequence_id=None,
                author="local_team",
                licence="CC BY-SA 4.0",
            )
            mf.write(record.model_dump_json() + "\n")
            added += 1

    print(f"Registered {added} custom images into {manifest_path}")
    return added


if __name__ == "__main__":
    register_custom_images()
