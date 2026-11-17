from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from collections.abc import Iterator
from datetime import datetime, timezone

from ml.src.geometry.utils.helpers import (
    BBox,
    bbox_center,
    bbox_contains,
    bbox_half_diagonal_m,
    parse_bbox,
    tile_bbox,
)
from src.io.common import (
    ImageRecord,
    add_spread_args,
    fetch_images,
    make_image_id,
    request_retry,
    spread_from_args,
)

API_URL = "https://api.kartaview.org/1.0/list/nearby-photos/"
STORAGE_DOMAIN = "openstreetcam.org"
LICENCE = "CC-BY-SA-4.0"
TILE_DEG = 0.001
ITEMS_PER_PAGE = 200
MAX_PAGES = 20
PAUSE_S = 0.2
SIZE_FIELDS = ("name", "lth_name", "th_name")
PANO_PROJECTIONS = {"SPHERE", "SPHERICAL", "CYLINDER", "EQUIRECTANGULAR", "WRAPPED"}


def _post(params: dict) -> dict:
    j = request_retry("POST", API_URL, data=params).json()
    status = j.get("status") or {}
    if status.get("apiCode") is not None and str(status["apiCode"]) != "600":
        raise RuntimeError(f"KartaView API error: {status}")
    return j


def search_circle(lat: float, lon: float, radius_m: int) -> Iterator[dict]:
    """Yield photos in one circle. Page until a page brings nothing new."""
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        j = _post(
            {
                "lat": lat,
                "lng": lon,
                "radius": radius_m,
                "ipp": ITEMS_PER_PAGE,
                "page": page,
            }
        )
        new = [
            d for d in (j.get("currentPageItems") or []) if str(d.get("id")) not in seen
        ]
        if not new:
            break
        for d in new:
            seen.add(str(d["id"]))
            yield d
        time.sleep(PAUSE_S)


def search_bbox(bbox: BBox) -> Iterator[dict]:
    """Cover the bbox with circles; de-duplicate and keep only photos inside it."""
    seen: set[str] = set()
    for tile in tile_bbox(bbox, TILE_DEG):
        lat, lon = bbox_center(tile)
        radius = math.ceil(bbox_half_diagonal_m(tile)) + 5
        for d in search_circle(lat, lon, radius):
            sid = str(d["id"])
            if sid not in seen and _inside(d, bbox):
                seen.add(sid)
                yield d


def _position(d: dict) -> tuple[float, float] | None:
    """(lat, lon) or None. Range checks are left to ImageRecord."""
    try:
        return float(d["lat"]), float(d["lng"])
    except (KeyError, TypeError, ValueError):
        return None


def _inside(d: dict, bbox: BBox) -> bool:
    """Returns True if BBox contain a position."""
    pos = _position(d)
    return pos is not None and bbox_contains(bbox, *pos)


def _heading(d: dict) -> float | None:
    """Return heading angle (0-360)."""
    try:
        return float(d["heading"]) % 360
    except (KeyError, TypeError, ValueError):
        return None


def _is_pano(d: dict) -> bool:
    """Returns True if projection is in `PANO_PROJECTIONS` or wrapper is True."""
    proj = str(d.get("projection") or "").upper()
    wrapped = str(d.get("isWrapped") or d.get("is_wrapped") or "0").lower()
    return proj in PANO_PROJECTIONS or wrapped in ("1", "true")


def is_usable(d: dict, include_panos: bool = False) -> bool:
    """Has a position and a heading; panos only if `include_panos`."""
    return (
        _position(d) is not None
        and _heading(d) is not None
        and (include_panos or not _is_pano(d))
    )


def _iso(s: str | None) -> str | None:
    """Convert str to iso format."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace(" ", "T").rstrip("Z"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


def to_record(d: dict) -> ImageRecord | None:
    """Convert a raw dict to ImageRecord if it has a pose."""
    pos, heading = _position(d), _heading(d)
    if pos is None or heading is None:
        return None

    sid = str(d["id"])
    seq, idx = d.get("sequence_id"), d.get("sequence_index")

    return ImageRecord(
        image_id=make_image_id("kartaview", sid),
        source="kartaview",
        source_id=sid,
        lat=pos[0],
        lon=pos[1],
        heading=heading,
        camera_type="spherical" if _is_pano(d) else "perspective",
        is_pano=_is_pano(d),
        captured_at=_iso(d.get("shot_date")),
        sequence_id=str(seq) if seq is not None else None,
        author=d.get("username"),
        licence=LICENCE,
        source_url=(
            f"https://kartaview.org/details/{seq}/{idx}/track-info"
            if seq is not None and idx is not None
            else None
        ),
    )


def _file_url(p: str) -> str:
    """Convert a relative storage path into an absolute HTTPS URL."""
    if p.startswith("http"):
        return p
    host, _, rest = p.lstrip("/").partition("/")
    return f"https://{host}.{STORAGE_DOMAIN}/{rest}"


def image_url(d: dict, size: str = "name") -> str | None:
    """Pick the requested size, falling back to smaller ones."""
    for field in [size, *(f for f in SIZE_FIELDS if f != size)]:
        if p := d.get(field):
            return _file_url(str(p))
    return None


def fetch(
    bbox: BBox,
    max_images: int,
    size: str = "name",
    include_panos: bool = False,
    **spread,
) -> int:
    """Download usable images in `bbox`. Returns the manifest size.
    `spread`: per_sequence, min_spacing_m (see `fetch_images`)."""
    return fetch_images(
        search_bbox(bbox),
        keep=lambda d: is_usable(d, include_panos),
        to_record=to_record,
        url_of=lambda d: image_url(d, size),
        max_images=max_images,
        **spread,
    )


def summarize(bbox: BBox) -> dict:
    """Coverage numbers without downloading images."""
    total = usable = 0
    seqs, authors, years = set(), set(), Counter()
    for d in search_bbox(bbox):
        total += 1
        if not is_usable(d):
            continue
        usable += 1
        seqs.add(d.get("sequence_id"))
        authors.add(d.get("username"))
        if iso := _iso(d.get("shot_date")):
            years[int(iso[:4])] += 1
    return {
        "total": total,
        "usable": usable,
        "sequences": len(seqs),
        "authors": len(authors),
        "by_year": dict(sorted(years.items())),
    }


# main section
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download KartaView images into the local dir"
    )
    parser.add_argument(
        "--bbox", required=True, type=parse_bbox, help="minLon,minLat,maxLon,maxLat"
    )
    parser.add_argument("--max", type=int, default=300)
    parser.add_argument("--size", choices=SIZE_FIELDS, default="name")
    parser.add_argument(
        "--panos", action="store_true", help="also download 360 panoramas"
    )
    add_spread_args(parser)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--probe", action="store_true", help="print the first raw item and exit"
    )
    mode.add_argument(
        "--count-only", action="store_true", help="coverage numbers, no downloads"
    )
    args = parser.parse_args()

    if args.probe:
        first = next(search_bbox(args.bbox), None)
        print(
            json.dumps(first, indent=2, ensure_ascii=False)
            if first
            else "no photos found"
        )
    elif args.count_only:
        print(json.dumps(summarize(args.bbox), indent=2))
    else:
        spread = spread_from_args(args)
        print(
            f"manifest now has {fetch(args.bbox, args.max, args.size, args.panos, **spread)} images"
        )
