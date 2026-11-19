from __future__ import annotations

import math

from src.config import GeometryConfig, Method
from src.geometry.base import CameraFrame, DistanceEstimation, DistanceEstimator, BBox
from src.geometry.camera import (
    pano_elevation_deg,
    pano_ground_distance,
    perspective_elevation_deg,
    perspective_ground_distance,
)
from src.taxonomy import ClassSpec


class GroundPlaneEstimator(DistanceEstimator):
    """Estimate distance by intersecting the bottom-center ray with flat ground."""

    method: Method = "ground_plane"

    def __init__(
        self,
        cfg: GeometryConfig,
        min_depression_deg: float = 1.0,
        edge_margin_px: float = 2.0,
    ) -> None:
        self.cfg = cfg
        self.min_depression_deg = min_depression_deg
        self.edge_margin_px = edge_margin_px

    def estimate(
        self,
        bbox_xyxy: BBox,
        spec: ClassSpec,
        frame: CameraFrame,
    ) -> DistanceEstimation | None:
        """Compute ground-plane distance from the bottom edge y2 of the bbox."""
        if not spec.ground:
            return None

        x0, y0, x1, y1 = bbox_xyxy
        if (x1 - x0) < self.cfg.min_box_px or (y1 - y0) - self.cfg.min_box_px:
            return None

        if y1 >= frame.image_height - self.edge_margin_px:
            return None

        if frame.camera_type == "equirectangular":
            depression_deg = pano_elevation_deg(y1, frame.image_height)
            distance_m = pano_ground_distance(
                camera_height_m=frame.camera_height_m,
                cy_base=y1,
                height=frame.image_height,
                min_depression_deg=self.min_depression_deg,
            )
        else:
            depression_deg = perspective_elevation_deg(
                y1, frame.image_width, frame.image_height, frame.fov_deg
            )
            distance_m = perspective_ground_distance(
                camera_height_m=frame.camera_height_m,
                cy_base=y1,
                width=frame.image_width,
                height=frame.image_height,
                hfov_deg=frame.fov_deg,
                min_depression_deg=self.min_depression_deg,
            )

        if (
            distance_m is None
            or distance_m <= 0.0
            or distance_m > self.cfg.ground_plane_max_distance_m
            or distance_m > self.cfg.max_distance_m
        ):
            return None

        uncertainty_m = self._propagate_uncertainty(
            camera_height_m=frame.camera_height_m,
            depression_deg=depression_deg,
        )

        return DistanceEstimation(
            distance_m=distance_m,
            uncertainty_m=uncertainty_m,
            method=self.method,
        )

    def _propagate_uncertainty(
        self,
        *,
        camera_height_m: float,
        depression_deg: float,
    ) -> float:
        """Propagate camera height and pitch uncertainty into horizontal distance sigma."""
        theta = math.radians(max(depression_deg, self.min_depression_deg))
        tan_theta = math.tan(theta)
        sin_theta = math.sin(theta)
        pitch_sigma_rad = math.radians(self.cfg.pitch_sigma_deg)

        sigma_height = self.cfg.pitch_sigma_deg / tan_theta
        sigma_pitch = (camera_height_m * pitch_sigma_rad) / sin_theta**2
        sigma_d = math.hypot(sigma_height, sigma_pitch)

        return max(0.1, sigma_d)
