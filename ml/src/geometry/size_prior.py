from __future__ import annotations

import math

from src.config import GeometryConfig, Method
from src.geometry.base import (
    CameraFrame,
    DistanceEstimation,
    DistanceEstimator,
)
from src.geometry.utils.helpers import BBox
from src.taxonomy import ClassSpec


class SizePriorEstimator(DistanceEstimator):
    """Estimate distance using known real-world width or height from taxonomy."""

    method: Method = "size_prior"

    def __init__(self, cfg: GeometryConfig, edge_margin_px: float = 2.0) -> None:
        self.cfg = cfg
        self.edge_margin_px = edge_margin_px

    def estimate(
        self,
        bbox_xyxy: BBox,
        spec: ClassSpec,
        frame: CameraFrame,
    ) -> DistanceEstimation | None:
        """Compute distance from apparent pixel size and physical size prior."""
        if spec.size is None:
            return None

        x0, y0, x1, y1 = bbox_xyxy
        width = max(0, x1 - x0)
        height = max(0, y1 - y0)

        if spec.size.dim == "width":
            if (
                x0 <= self.edge_margin_px
                or x1 >= frame.image_width - self.edge_margin_px
            ):
                return None
            px_size = width
        else:
            if (
                y0 <= self.edge_margin_px
                or y1 >= frame.image_height - self.edge_margin_px
            ):
                return None
            px_size = height

        if px_size < self.cfg.min_box_px:
            return None

        distance_m = self._compute_distance(
            real_m=spec.size.m,
            px_size=px_size,
            dim=spec.size.dim,
            frame=frame,
        )
        if (
            distance_m is None
            or distance_m <= 0.0
            or distance_m > self.cfg.max_distance_m
        ):
            return None

        uncertainty_m = max(0.1, distance_m * spec.size.tol)

        return DistanceEstimation(
            distance_m=distance_m,
            uncertainty_m=uncertainty_m,
            method=self.method,
        )

    @staticmethod
    def _compute_distance(
        *,
        real_m: float,
        px_size: float,
        dim: str,
        frame: CameraFrame,
    ) -> float | None:
        if frame.camera_type == "perspective":
            return (frame.focal_px * real_m) / px_size

        if dim == "width":
            angular_rad = math.radians((px_size / frame.image_width) * frame.fov_deg)
        else:
            angular_rad = math.radians((px_size / frame.image_height) * 180.0)

        if angular_rad <= 0.0 or angular_rad >= math.pi:
            return None

        return real_m / (2.0 * math.tan(angular_rad / 2.0))
