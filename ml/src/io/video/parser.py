from __future__ import annotations

from pyproj import Geod
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from ml.src.io.video.gps import TrackPoint

_GEOD = Geod(ellps="WGS84")


def _parse_iso_timestamp(raw: str) -> float:
    """Parse ISO-8601 GPX timestamp into POSIX seconds."""
    cleaned = raw.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned).timestamp()


def parse_gpx(gpx_path: Path) -> list[TrackPoint]:
    """Parse track points (lat, lon, optional time) and cumulative distance from a GPX file."""
    if not gpx_path.is_file():
        raise FileNotFoundError(f"GPX file not found: {gpx_path}")

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    raw_pts: list[tuple[float, float, float | None]] = []
    for elem in root.iter():
        if elem.tag.endswith("trkpt") or elem.tag.endswith("rtept"):
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            ts: float | None = None
            for child in elem:
                if child.tag.endswith("time") and child.text:
                    ts = _parse_iso_timestamp(child.text)
                    break
            raw_pts.append((lat, lon, ts))

    if len(raw_pts) < 2:
        raise ValueError(
            f"GPX track must contain at least 2 points, got {len(raw_pts)}"
        )

    points: list[TrackPoint] = []
    cum_dist = 0.0
    prev_lat, prev_lon, _ = raw_pts[0]

    for i, (lat, lon, ts) in enumerate(raw_pts):
        if i > 0:
            _, _, seg_m = _GEOD.inv(prev_lon, prev_lat, lon, lat)
            cum_dist += float(seg_m)
        points.append(TrackPoint(lat=lat, lon=lon, timestamp_s=ts, cum_dist_m=cum_dist))
        prev_lat, prev_lon = lat, lon

    return points
