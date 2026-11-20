from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from src.geometry.utils.geo import LocalENU


class _TriangulationModel(BaseModel):
    """Frozen, strictly-typed base model for triangulation inputs and outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RayObservation(_TriangulationModel):
    """Single camera ray and optional single-view uncertainty for triangulation."""

    camera_lat: float = Field(ge=-90.0, le=90.0)
    camera_lon: float = Field(ge=-180.0, le=180.0)
    bearing_deg: float = Field(ge=0.0, lt=360.0)
    uncertainty_m: float = Field(default=3.0, gt=0.0)


class TriangulatedPoint(_TriangulationModel):
    """Triangulated WGS84 position and residual error metrics."""

    lat: float
    lon: float
    uncertainty_m: float = Field(gt=0.0)
    mean_residual_m: float = Field(ge=0.0)
    max_ray_angle_deg: float = Field(ge=0.0)


def max_pairwise_angle_deg(bearings_deg: Sequence[float]) -> float:
    """Compute the largest acute/obtuse intersection angle between any pair of rays."""
    max_angle = 0.0
    n = len(bearings_deg)

    for i in range(n):
        for j in range(i + 1, n):
            diff_deg = abs(bearings_deg[i] - bearings_deg[j]) % 360.0
            if diff_deg > 180.0:
                diff_deg = 360.0 - diff_deg

            parallax = min(diff_deg, 180.0 - diff_deg)
            if parallax > max_angle:
                max_angle = parallax

    return max_angle


def triangulate_rays(
    rays: Sequence[RayObservation],
    *,
    min_angle_deg: float = 5.0,
    max_distance_m: float = 50.0,
    max_residual_m: float = 5.0,
) -> TriangulatedPoint | None:
    """
    Find the weighted least-squares intersection of 2+ compass rays.
    Args:
        rays: Two or more observations of the same physical object from different poses.
        min_angle_deg: Minimum required parallax angle between rays.
        max_distance_m: Maximum plausible distance from any observing camera to the solution.
        max_residual_m: Maximum allowed weighted RMS perpendicular distance to rays.
    Returns:
        TriangulatedPoint on WGS84, or None if geometry is degenerate or inconsistent.
    """
    if len(rays) < 2:
        return None

    max_angle = max_pairwise_angle_deg([ray.bearing_deg for ray in rays])
    if max_angle < min_angle_deg:
        return None

    ref_lat = rays[0].camera_lat
    ref_lon = rays[0].camera_lon
    enu = LocalENU(lat0=ref_lat, lon0=ref_lon)

    normals: list[tuple[float, float]] = []
    directions: list[tuple[float, float]] = []
    origins: list[tuple[float, float]] = []
    weights: list[float] = []

    for ray in rays:
        px, py = enu.to_xy(ray.camera_lat, ray.camera_lon)
        az_rad = math.radians(ray.bearing_deg)

        # 0: deg=north, 90: deg=east.
        dx = math.sin(az_rad)
        dy = math.cos(az_rad)

        # norms
        nx = dy
        ny = -dx

        origins.append((px, py))
        directions.append((dx, dy))
        normals.append((nx, ny))
        weights.append(1 / (ray.uncertainty_m**2))

    # x = N^T W b
    A = np.zeros((2, 2), dtype=np.float64)
    b = np.zeros(2, dtype=np.float64)

    for (px, py), (nx, ny), w in zip(origins, normals, weights):
        rhs = nx * px + ny * py
        A[0, 0] += w * nx * nx
        A[0, 1] += w * nx * ny
        A[1, 0] += w * ny * nx
        A[1, 1] += w * ny * ny
        b[0] += w * nx * rhs
        b[1] += w * ny * rhs

    detA = float(np.linalg.det(A))
    if abs(detA) < 1e-12:
        return None

    solution = np.linalg.solve(A, b)
    est_x, est_y = float(solution[0]), float(solution[1])

    # cheirality & range check
    # (target must lie in front of every camera and within range)
    sq_residuals: list[float] = []

    for (px, py), (dx, dy), (nx, ny), w in zip(origins, directions, normals, weights):
        vx = est_x - px
        vy = est_y - py

        dist = vx * dx + vy * dy
        if dist <= 0.0:
            return None
        if math.hypot(vx, vy) > max_distance_m:
            return None

        perp_err = nx * vx + ny * vy
        sq_residuals.append(w * (perp_err**2))

    weighted_sum = sum(weights)
    rms_residual = math.sqrt(sum(sq_residuals) / weighted_sum)
    if rms_residual > max_residual_m:
        return None

    # Cov(x) = (N^T W N)^-1
    cov = np.linalg.inv(A)

    pos_sigma_m = max(2.0, math.sqrt(float(cov.trace())))
    est_lat, est_lon = enu.to_latlon(est_x, est_y)

    return TriangulatedPoint(
        lat=est_lat,
        lon=est_lon,
        uncertainty_m=pos_sigma_m,
        mean_residual_m=rms_residual,
        max_ray_angle_deg=max_angle,
    )
