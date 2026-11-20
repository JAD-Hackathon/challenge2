from __future__ import annotations

from collections.abc import Sequence

from src.dedup.utils.helpers import build_rays
from src.geometry.triangulation import triangulate_rays, max_pairwise_angle_deg
from src.geometry.utils.geo import LocalENU
from src.service.schemas import CameraMeta, Observation


def is_ray_consistent(
    cluster_obs: Sequence[Observation],
    candidate: Observation,
    images_by_id: dict[str, CameraMeta],
    radius_m: float,
) -> bool:
    """Check whether merging `candidate` into `cluster_obs` is geometrically consistent."""
    rays = build_rays([*cluster_obs, candidate], images_by_id)
    if len(rays) < 2:
        return True

    tri = triangulate_rays(
        rays,
        min_angle_deg=8.0,
        max_distance_m=50.0,
        max_residual_m=max(radius_m, 4.0),
    )
    if tri is not None:
        return True

    # If parallax >= 15 deg -> rays diverge
    parallax = max_pairwise_angle_deg([r.bearing_deg for r in rays])
    return parallax < 15.0


def estimate_cluster_position(
    observations: Sequence[Observation],
    images_by_id: dict[str, CameraMeta],
    enu: LocalENU,
) -> tuple[float, float]:
    """Estimate WGS84 (lat, lon) via ray triangulation with inverse-variance ENU fallback."""
    rays = build_rays(observations, images_by_id)
    if len(rays) >= 2:
        tri = triangulate_rays(rays)
        if tri is not None:
            return round(tri.lat, 7), round(tri.lon, 7)

    sum_w = 0.0
    sum_x = 0.0
    sum_y = 0.0

    for obs in observations:
        assert obs.est_lat is not None and obs.est_lon is not None
        sigma = (
            obs.uncertainty_m if (obs.uncertainty_m and obs.uncertainty_m > 0) else 5.0
        )
        w = 1.0 / sigma**2
        x, y = enu.to_xy(obs.est_lat, obs.est_lon)
        sum_w += w
        sum_x += w * x
        sum_y += w * y

    lat, lon = enu.to_latlon(sum_x / sum_w, sum_y / sum_w)
    return round(lat, 7), round(lon, 7)
