import math


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
