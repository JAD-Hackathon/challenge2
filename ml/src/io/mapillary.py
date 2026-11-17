from __future__ import annotations

import argparse
import os
from collections.abc import Iterator
from datetime import datetime, timezone

from dotenv import load_dotenv

from ml.src.geometry.utils.helpers import BBox, parse_bbox, tile_bbox
from src.io.common import (
    ImageRecord,
    add_spread_args,
    fetch_images,
    make_image_id,
    request_retry,
    spread_from_args,
)

load_dotenv()

API = "https://graph.mapillary.com/images"
LICENCE = "CC-BY-SA-4.0"
TILE_DEG = 0.002

FIELDS = (
    "id,computed_geometry,geometry,compass_angle,computed_compass_angle,"
    "camera_type,is_pano,captured_at,sequence,creator,width,height,thumb_2048_url"
)


def _headers() -> dict[str, str]:
    return {"Authorization": f"OAuth {os.environ['MAPILLARY_ACCESS_TOKEN']}"}


def search(bbox: BBox, fields: str = FIELDS, limit: int = 500) -> Iterator[dict]:
    """Yield raw image dicts for one bbox, following paging."""
    url: str | None = API
    params: dict | None = {
        "bbox": ",".join(f"{v:.6f}" for v in bbox),
        "fields": fields,
        "limit": limit,
    }
    while url:
        response = request_retry("GET", url, params=params, headers=_headers()).json()
        yield from response.get("data", [])
        url = response.get("paging", {}).get("next")
        params = None


def search_tiled(
    bbox: BBox, fields: str = FIELDS, step_deg: float = TILE_DEG
) -> Iterator[dict]:
    """Search a larger bbox tile by tile, de-duplicating across tile edges."""
    seen: set[str] = set()
    for tile in tile_bbox(bbox, step_deg):
        for d in search(tile, fields):
            if d["id"] not in seen:
                seen.add(d["id"])
                yield d


def is_usable(data: dict, include_panos: bool = False) -> bool:
    """Has a pose and is perspective; panos only if `include_panos`."""
    has_pose = bool(data.get("computed_geometry") or data.get("geometry")) and (
        data.get("computed_compass_angle", data.get("compass_angle")) is not None
    )
    if not has_pose:
        return False
    if data.get("is_pano"):
        return include_panos
    return data.get("camera_type") == "perspective"


def to_record(data: dict) -> ImageRecord | None:
    """Convert a raw dict to ImageRecord if it has a pose."""
    geo = data.get("computed_geometry") or data.get("geometry")
    heading = data.get("computed_compass_angle", data.get("compass_angle"))
    if not geo or heading is None:
        return None

    lon, lat = geo["coordinates"]
    ts = data.get("captured_at")
    captured = (
        datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else None
    )
    sid = str(data["id"])

    return ImageRecord(
        image_id=make_image_id("mapillary", sid),
        source="mapillary",
        source_id=sid,
        lat=lat,
        lon=lon,
        heading=heading % 360,
        camera_type=data.get("camera_type"),
        is_pano=data.get("is_pano"),
        width=data.get("width"),
        height=data.get("height"),
        captured_at=captured,
        sequence_id=data.get("sequence"),
        author=(data.get("creator") or {}).get("username"),
        licence=LICENCE,
        source_url=f"https://www.mapillary.com/app/?pKey={sid}",
    )


def fetch(bbox: BBox, max_images: int, include_panos: bool = False, **spread) -> int:
    """Download usable images in `bbox`. Returns the manifest size.
    `spread`: per_sequence, min_spacing_m (see `fetch_images`)."""
    return fetch_images(
        search_tiled(bbox),
        keep=lambda d: is_usable(d, include_panos),
        to_record=to_record,
        url_of=lambda d: d.get("thumb_2048_url"),
        max_images=max_images,
        **spread,
    )


# main section
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download Mapillary images into the local dir"
    )
    parser.add_argument(
        "--bbox", required=True, type=parse_bbox, help="minLon,minLat,maxLon,maxLat"
    )
    parser.add_argument("--max", type=int, default=300)
    parser.add_argument(
        "--panos", action="store_true", help="also download 360 panoramas"
    )
    add_spread_args(parser)
    args = parser.parse_args()
    spread = spread_from_args(args)
    print(f"manifest now has {fetch(args.bbox, args.max, args.panos, **spread)} images")
