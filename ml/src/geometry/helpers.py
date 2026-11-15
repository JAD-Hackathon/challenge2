import math

METERS_PER_DEGREE = 111_320
EARTH_RADIUS_M = 6_371_000
# source: https://mapryx.geoforger.com/tools/meter-to-degree-converter

BBox = tuple[float, float, float, float]


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
