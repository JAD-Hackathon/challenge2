"""Independent (module-agnostic) helpers so tests don't rely on the code under test."""

import math

from src.geometry.base import CameraFrame
from src.taxonomy import ClassSpec, Size

LAT0, LON0 = 40.6412, -8.6538  # Aveiro

_A, _E2 = 6378137.0, 0.00669437999014


def _radii(lat):
    s = math.sin(math.radians(lat))
    w = 1 - _E2 * s * s
    return _A * (1 - _E2) / w**1.5, _A / math.sqrt(w)  # meridian, prime-vertical


def offset(lat, lon, east, north):
    """(lat, lon) displaced by (east, north) metres (accurate for small offsets)."""
    m, n = _radii(lat)
    return lat + math.degrees(north / m), lon + math.degrees(
        east / (n * math.cos(math.radians(lat)))
    )


def to_enu(lat0, lon0, lat, lon):
    """(east, north) metres of (lat, lon) relative to (lat0, lon0)."""
    m, n = _radii(lat0)
    return (
        math.radians(lon - lon0) * n * math.cos(math.radians(lat0)),
        math.radians(lat - lat0) * m,
    )


def bearing_deg(frm, to):
    return math.degrees(math.atan2(to[0] - frm[0], to[1] - frm[1])) % 360.0


def make_frame(**kw) -> CameraFrame:
    d = dict(
        lat=LAT0,
        lon=LON0,
        heading=90.0,
        image_width=1000,
        image_height=1000,
        fov_deg=90.0,
        camera_type="perspective",
        camera_height_m=1.5,
    )
    d.update(kw)
    return CameraFrame(**d)


def pano_frame(**kw) -> CameraFrame:
    return make_frame(
        camera_type="equirectangular",
        fov_deg=360.0,
        image_width=2000,
        image_height=1000,
        **kw,
    )


def make_spec(name="sign.stop", ground=False, dim=None, m=0.6, tol=0.15) -> ClassSpec:
    size = Size(dim=dim, m=m, tol=tol) if dim else None
    return ClassSpec(name=name, label=name, ground=ground, size=size)
