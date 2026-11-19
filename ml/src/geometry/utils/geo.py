from __future__ import annotations

from functools import lru_cache

from pyproj import Geod, Proj, Transformer

_WGS84_GEOD = Geod(ellps="WGS84")


def project_point(
    lat: float,
    lon: float,
    bearing_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    """
    Project a WGS84 point forward along a compass bearing by `distance_m`.
    Args:
        lat: Origin latitude in decimal degrees.
        lon: Origin longitude in decimal degrees.
        bearing_deg: Forward azimuth in degrees clockwise from true north.
        distance_m: Horizontal geodesic distance in metres.
    Returns:
        Destination (lat, lon) in decimal degrees on WGS84.
    """
    if distance_m == 0:
        return lat, lon
    dets_lat, dets_lon, _ = _WGS84_GEOD.fwd(lat, lon, bearing_deg, distance_m)
    return float(dets_lat), float(dets_lon)


def geodesic_distance_m(lat0: float, lon0: float, lat1: float, lon1: float) -> float:
    """Compute exact ellipsoidal distance in metres between two WGS84 points."""
    _, _, dist_m = _WGS84_GEOD.inv(lat0, lon0, lat1, lon1)
    return float(dist_m)


@lru_cache(maxsize=64)
def _build_enu_transformers(
    lat0: float, lon0: float
) -> tuple[Transformer, Transformer]:
    """Create cached WGS84 <-> local tangent metric (East, North) transformers."""
    wgs84 = Proj(proj="latlong", datum="WGS84")
    local = Proj(
        proj="aeqd",
        lat_0=lat0,
        lon_0=lon0,
        datum="WGS84",
        units="m",
    )
    to_local = Transformer.from_proj(wgs84, local, always_xy=True)
    to_wgs84 = Transformer.from_proj(local, wgs84, always_xy=True)
    return to_local, to_wgs84


class LocalENU:
    """
    Local tangent-plane metric coordinate system (East, North in metres).\n
    Anchored at (lat0, lon0) so multi-view triangulation and spatial
    clustering can operate in Euclidean metres without meridian distortion.
    """

    def __init__(self, lat0: float, lon0: float):
        self.lat0 = lat0
        self.lon0 = lon0
        self.to_local, self.to_wgs84 = _build_enu_transformers(lat0, lon0)

    def to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        """Convert WGS84 (lat, lon) to local metric (east_m, north_m)."""
        east_m, north_m = self.to_local.transform(lat, lon)
        return float(east_m), float(north_m)

    def to_latlon(self, east_m: float, north_m: float) -> tuple[float, float]:
        """Convert local metric (east_m, north_m) back to WGS84 (lat, lon)."""
        lat, lon = self.to_wgs84.transform(east_m, north_m)
        return float(lat), float(lon)
