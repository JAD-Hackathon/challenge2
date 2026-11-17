"""Turn raw Mapillary (API v4) / KartaView (API v2) image records into ImageMeta.

The web downloads the images from those sites and sends them to POST /images with the site's
record as meta ({"mapillary": {...}} or {"kartaview": {...}}). This module works out position,
heading, field of view and attribution (both sites are CC BY-SA 4.0, which requires credit).

Returns None for images the ML service can't use yet (no position/heading, 360° panoramas).
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.schemas.image import ImageMeta

# Fields to request from Mapillary: GET https://graph.mapillary.com/images?fields=...
MAPILLARY_FIELDS = (
    "id,computed_geometry,geometry,computed_compass_angle,compass_angle,"
    "camera_type,camera_parameters,width,height,sequence,captured_at,creator,thumb_2048_url"
)

LICENSE = "CC BY-SA 4.0"  # Mapillary and KartaView imagery
PANORAMA_TYPES = {"spherical", "equirectangular"}


def _float(value: Any) -> float | None:
    """KartaView often sends numbers as strings; Mapillary may send null."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _heading(value: Any) -> float | None:
    heading = _float(value)
    return None if heading is None else heading % 360  # 360.0 -> 0.0, -5 -> 355


def _valid_fov(fov: float | None) -> float | None:
    return fov if fov is not None and 0 < fov < 180 else None


def _mapillary_fov(image: Mapping[str, Any]) -> float | None:
    """camera_parameters = [focal, k1, k2], focal normalised by max(width, height)."""
    params = image.get("camera_parameters") or []
    focal = _float(params[0]) if params else None
    if not focal or focal <= 0:
        return None
    width, height = _float(image.get("width")), _float(image.get("height"))
    # horizontal FOV: half-width in normalised units is width / (2 * max(w, h)); 0.5 if unknown
    half_width = width / (2 * max(width, height)) if width and height else 0.5
    return _valid_fov(math.degrees(2 * math.atan(half_width / focal)))


def _username(value: Any) -> str | None:
    return value.get("username") if isinstance(value, Mapping) else None


def from_mapillary(image: Mapping[str, Any]) -> ImageMeta | None:
    if image.get("camera_type") in PANORAMA_TYPES:
        return None

    geometry = image.get("computed_geometry") or image.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    heading = _heading(image.get("computed_compass_angle"))
    if heading is None:
        heading = _heading(image.get("compass_angle"))
    if len(coords) < 2 or heading is None:
        return None
    lon, lat = coords[0], coords[1]  # GeoJSON order is [lon, lat]

    sequence = image.get("sequence")
    captured_ms = _float(image.get("captured_at"))  # ms since epoch
    return ImageMeta(
        image_id=f"mly_{image['id']}",  # prefix: Mapillary and KartaView ids can collide
        lat=lat,
        lon=lon,
        heading=heading,
        fov=_mapillary_fov(image),
        source="mapillary",
        sequence_id=str(sequence) if sequence else None,
        frame_index=None,  # set by assign_frame_indexes()
        author=_username(image.get("creator")),
        license=LICENSE,
        captured_at=datetime.fromtimestamp(captured_ms / 1000, UTC)
        if captured_ms
        else None,
    )


def from_kartaview(photo: Mapping[str, Any]) -> ImageMeta | None:
    if str(photo.get("projection", "")).upper() == "SPHERE":
        return None

    lat, lon = _float(photo.get("lat")), _float(photo.get("lng"))
    heading = _heading(photo.get("heading"))
    if lat is None or lon is None or heading is None:
        return None

    sequence_id = photo.get("sequenceId")
    index = _float(photo.get("sequenceIndex"))
    return ImageMeta(
        image_id=f"kv_{photo['id']}",
        lat=lat,
        lon=lon,
        heading=heading,
        fov=_valid_fov(_float(photo.get("fieldOfView"))),
        source="kartaview",
        sequence_id=str(sequence_id) if sequence_id is not None else None,
        frame_index=int(index) if index is not None and index >= 0 else None,
        author=photo.get("username") or _username(photo.get("user")),
        license=LICENSE,
        captured_at=_kartaview_date(photo.get("shotDate")),
    )


def _kartaview_date(value: Any) -> datetime | None:
    """e.g. '2019-07-09 09:11:43', read as UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def assign_frame_indexes(metas: Iterable[ImageMeta]) -> None:
    """Mapillary has no frame index: number each sequence's images by capture time.

    Images that already have a frame_index are left alone. Indexes are relative to the images
    of this batch, not to the full sequence.
    """
    by_sequence: dict[str, list[ImageMeta]] = defaultdict(list)
    for meta in metas:
        if meta.sequence_id and meta.frame_index is None and meta.captured_at:
            by_sequence[meta.sequence_id].append(meta)

    for group in by_sequence.values():
        group.sort(key=lambda m: m.captured_at)  # type: ignore[arg-type, return-value]
        for index, meta in enumerate(group):
            meta.frame_index = index
