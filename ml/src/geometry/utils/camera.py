from __future__ import annotations
import math


def focal_length_px(width: float, hfov_deg: float) -> float:
    """Compute horizontal focal length in pixels from image width and HFOV."""
    if width <= 0:
        raise ValueError(f"Image width must be > 0, got {width}")
    if not (0 < hfov_deg < 180):
        raise ValueError(f"HFOV must be in (0, 180), got {hfov_deg}")
    return (width / 2.0) / math.tan(math.radians(hfov_deg / 2.0))


# perspective


def perspective_bearing(
    heading: float, cx: float, width: float, hfov_deg: float
) -> float:
    """Compute compass bearing (deg, clockwise from north) for a perspective camera."""
    f_px = focal_length_px(width, hfov_deg)
    offset_deg = math.degrees(math.atan2(cx - width / 2.0, f_px))
    return (heading + offset_deg) % 360.0


def perspective_elevation_deg(
    cy: float, width: float, height: float, hfov_deg: float
) -> float:
    """Compute elevation angle (deg, positive above horizon) for a perspective camera."""
    if height <= 0:
        raise ValueError(f"Image height must be > 0, got {height}")
    f_px = focal_length_px(width, hfov_deg)
    return math.degrees(math.atan2(height / 2.0 - cy, f_px))


def perspective_ground_distance(
    camera_height_m: float,
    cy_base: float,
    width: float,
    height: float,
    hfov_deg: float,
    min_depression_deg: float = 1.0,
) -> float | None:
    """
    Estimate horizontal ground distance from object base row in a perspective image.
    Returns None if the base is at, above, or too close to the horizon.
    """
    depression = -perspective_elevation_deg(cy_base, width, height, hfov_deg)
    if depression < min_depression_deg:
        return None
    return camera_height_m / math.tan(math.radians(depression))


# ponorama


def pano_bearing(heading: float, cx: float, width: float, hfov: float = 360.0) -> float:
    """
    Compass bearing (deg, clockwise from north) of pixel column cx.
    Use hfov < 360 for partial/cylindrical panoramas.
    """
    return (heading + (cx / width - 0.5) * hfov) % 360


def pano_elevation_deg(cy: float, height: float) -> float:
    """Elevation angle of pixel row cy: positive above the horizon."""
    return (0.5 - cy / height) * 180.0


def pano_ground_distance(
    camera_height_m: float,
    cy_base: float,
    height: float,
    min_depression_deg: float = 1.0,
) -> float | None:
    """
    Horizontal distance to an object whose base is at pixel row cy_base.
    None if the base is (almost) at or above the horizon: too uncertain.
    """
    depression = -pano_elevation_deg(cy_base, height)
    if depression < min_depression_deg:
        return None
    return camera_height_m / math.tan(math.radians(depression))
