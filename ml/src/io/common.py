from __future__ import annotations

import argparse
import os
import uuid
import time
from collections import defaultdict
from pathlib import Path
from collections.abc import Iterable
from typing import Literal, Any, Callable

import requests
from pydantic import BaseModel, ConfigDict, Field
from ml.src.geometry.utils.helpers import distance_m
from src.config import get_settings

paths_config = get_settings().paths

_NAME_SPACE = uuid.UUID("3f2b8c1e-6d4a-4f7b-9a53-2c1d8e7f0a96")
Source = Literal["mapillary", "kartaview", "video"]
RETRY_STATUS = (429, 500, 502, 503, 504)
FLUSH_EVERY = 50


class ImageRecord(BaseModel):
    """One image = pose + attribution. Source of truth for /infer meta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    image_id: str
    source: Source
    source_id: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    heading: float = Field(ge=0, le=360)
    fov: float | None = None
    camera_type: str | None = None
    is_pano: bool | None = None
    width: int | None = None
    height: int | None = None
    captured_at: str | None = None
    sequence_id: str | None = None
    author: str | None = None
    licence: str | None = None
    source_url: str | None = None
    save_path: str | None = None

    def to_meta(self) -> dict[str, Any]:
        """The `meta` JSON for POST /infer."""
        meta = {
            "image_id": self.image_id,
            "lat": self.lat,
            "lon": self.lon,
            "heading": self.heading,
            "fov": self.fov,
            "camera_height_m": None,
            "source": self.source,
            "sequence_id": None,
            "frame_index": None,
        }
        if self.is_pano:
            meta["camera_type"] = "equirectangular"
        return meta


def make_image_id(source: str, source_id: str) -> str:
    """Deterministic UUID: same source image -> same id on every run."""
    return str(uuid.uuid5(_NAME_SPACE, f"{source}:{source_id}"))


# manifest


def read_manifest(path: Path = paths_config.manifest_file) -> dict[str, ImageRecord]:
    """Read menifest and return dictionary {image_id: ImageRecord}."""
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, ImageRecord] = {}
    with path.open(mode="r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                record = ImageRecord.model_validate_json(line)
                out[record.image_id] = record
    return out


def upsert_manifest(
    records: Iterable[ImageRecord], path: Path = paths_config.manifest_file
) -> int:
    """Merge records by image_id and rewrite atomically. Returns total size."""
    merged = read_manifest(path)
    for record in records:
        merged[record.image_id] = record

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with tmp.open(mode="w", encoding="utf-8") as file:
        for record in merged.values():
            file.write(record.model_dump_json() + "\n")

    os.replace(tmp, path)
    return len(merged)


# http + download


def request_retry(
    method: str, url: str, retries: int = 4, timeout: float = 30, **kwargs: Any
) -> requests.Response:
    """requests.request with exponential backoff on network errors and 429/5xx."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as e:
            last = e
            time.sleep(2**attempt)
            continue
        if r.status_code in RETRY_STATUS:
            time.sleep(2**attempt)
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"{method} {url}: failed after {retries} attempts") from last


def download_image(
    record: ImageRecord, url: str, save_dir: Path = paths_config.raw_dir
) -> ImageRecord:
    """
    Fetch to RAW_DIR/<source>/<source_id>.jpg (skips if present). Returns the record
    with save_path and, if Pillow is installed, width/height.
    """
    rel_path = f"{record.source}/{record.source_id}.jpg"
    out = save_dir / rel_path
    if not out.exists():
        r = request_retry("GET", url, timeout=60)
        if not r.headers.get("content-type", "").startswith("image"):
            raise ValueError(f"not an image: {r.headers.get('content-type')} ({url})")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
    update: dict[str, Any] = {"save_path": rel_path}
    try:
        from PIL import Image

        with Image.open(out) as im:
            update["width"], update["height"] = im.size
    except Exception:
        pass
    return record.model_copy(update=update)


def fetch_images(
    items: Iterable[dict],
    *,
    keep: Callable[[dict], bool],
    to_record: Callable[[dict], ImageRecord | None],
    url_of: Callable[[dict], str | None],
    max_images: int,
    per_sequence: int | None = None,
    min_spacing_m: float = 0.0,
) -> int:
    """
    Generic loader loop: filter -> record -> download -> manifest.
    `per_sequence` caps images per source sequence; `min_spacing_m` skips an image
    closer than that to one already kept from the same sequence (spreads the sample).
    Returns the manifest size.
    """
    pending: list[ImageRecord] = []
    kept: dict[str | None, list[tuple[float, float]]] = defaultdict(list)
    total = ok = failed = 0
    for d in items:
        if ok >= max_images:
            break
        if not keep(d):
            continue
        record, url = to_record(d), url_of(d)
        if record is None or not url:
            continue
        seen = kept[record.sequence_id]
        if per_sequence is not None and len(seen) >= per_sequence:
            continue
        if min_spacing_m and any(
            distance_m(record.lat, record.lon, *p) < min_spacing_m for p in seen
        ):
            continue
        try:
            pending.append(download_image(record, url))
            seen.append((record.lat, record.lon))
            ok += 1
        except (requests.RequestException, RuntimeError, ValueError) as e:
            failed += 1
            print(f"skip {record.source}:{record.source_id}: {e}")
        if len(pending) >= FLUSH_EVERY:
            total = upsert_manifest(pending)
            pending = []
    if pending or not total:
        total = upsert_manifest(pending)
    if failed:
        print(f"{failed} downloads failed")
    return total


# cli


def add_spread_args(parser: argparse.ArgumentParser) -> None:
    """Add the sample-spreading options shared by all loaders."""
    parser.add_argument(
        "--per-sequence", type=int, default=None, help="max images per source sequence"
    )
    parser.add_argument(
        "--min-spacing",
        type=float,
        default=0.0,
        help="min metres between kept images of one sequence",
    )


def spread_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Keyword arguments for `fetch_images` from parsed CLI args."""
    return {"per_sequence": args.per_sequence, "min_spacing_m": args.min_spacing}
