from collections.abc import Iterator
import math

METERS_PER_DEGREE = 111_320
EARTH_RADIUS_M = 6_371_000
# source: https://mapryx.geoforger.com/tools/meter-to-degree-converter

BBox = tuple[float, float, float, float]


def bbox_center(bbox: BBox) -> tuple[float, float]:
    """(lat, lon) of the bbox centre."""
    return (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2


def bbox_around(lat: float, lon: float, radius_m: float) -> BBox:
    """Calculate a rectangle around the point (`lat`, `lon`) with a given `radius_m`."""
    dlat = radius_m / METERS_PER_DEGREE
    dlon = radius_m / (METERS_PER_DEGREE * math.cos(math.radians(lat)))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Flat-earth distance, good enough for a few metres."""
    dy = (lat2 - lat1) * METERS_PER_DEGREE
    dx = (lon2 - lon1) * METERS_PER_DEGREE * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def bbox_contains(bbox: BBox, lat: float, lon: float) -> bool:
    """Returns True if BBox contain a point (`lat`, `lon`)."""
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def bbox_size_m(bbox: BBox) -> tuple[float, float]:
    """(width_m, height_m). Equirectangular approximation, fine for sub-km boxes."""
    lat, _ = bbox_center(bbox)
    return (
        (bbox[2] - bbox[0]) * METERS_PER_DEGREE * math.cos(math.radians(lat)),
        (bbox[3] - bbox[1]) * METERS_PER_DEGREE,
    )


def bbox_half_diagonal_m(bbox: BBox) -> float:
    """Radius of the circle that covers the bbox."""
    w, h = bbox_size_m(bbox)
    return math.hypot(w, h) / 2


def tile_bbox(bbox: BBox, step_deg: float) -> Iterator[BBox]:
    """Split a bbox into cells of at most `step_deg`."""
    x0, y0, x1, y1 = bbox
    nx = max(1, math.ceil((x1 - x0) / step_deg))
    ny = max(1, math.ceil((y1 - y0) / step_deg))
    dx, dy = (x1 - x0) / nx, (y1 - y0) / ny
    for i in range(nx):
        for j in range(ny):
            yield (x0 + i * dx, y0 + j * dy, x0 + (i + 1) * dx, y0 + (j + 1) * dy)


def parse_bbox(s: str) -> BBox:
    """'minLon,minLat,maxLon,maxLat' -> BBox (argparse `type=`)."""
    c = [float(v) for v in s.split(",")]
    if len(c) != 4 or c[0] >= c[2] or c[1] >= c[3]:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
    return (c[0], c[1], c[2], c[3])


def pixel_to_bearing(
    center_x: float, image_width: int, heading_deg: float, fov_deg: float
) -> float:
    """Convert a horizontal pixel position to a geographic bearing."""
    focal_px = (image_width / 2) / math.tan(math.radians(fov_deg / 2))
    angle = math.degrees(math.atan((center_x - image_width / 2) / focal_px))
    return (heading_deg + angle) % 360


def destination_point(
    lat: float, lon: float, distance_m: float, bearing_deg: float
) -> tuple[float, float]:
    """Calculate destination coordinates given a point, distance, and bearing."""
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    bearing = math.radians(bearing_deg)
    angular_distance = distance_m / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )

    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )

    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180
