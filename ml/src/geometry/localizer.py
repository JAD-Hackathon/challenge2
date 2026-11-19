from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from src.config import GeometryConfig, Method
from src.geometry.base import (
    CameraFrame,
    DistanceEstimation,
    DistanceEstimator,
    GeoLocation,
    BBox,
)
from src.geometry.depth import DepthEstimator
from src.geometry.utils.geo import project_point
from src.geometry.ground_plane import GroundPlaneEstimator
from src.geometry.size_prior import SizePriorEstimator
from src.taxonomy import Taxonomy


class GeoLocalizer:
    """Estimate geographic coordinates (lat, lon) and uncertainty for detections."""

    def __init__(
        self,
        cfg: GeometryConfig,
        taxonomy: Taxonomy,
        estimators: Sequence[DistanceEstimator] | None = None,
    ) -> None:
        self.cfg = cfg
        self.taxonomy = taxonomy

        if estimators is None:
            estimators = [
                SizePriorEstimator(cfg),
                GroundPlaneEstimator(cfg),
                DepthEstimator(cfg),
            ]
        self._estimators: dict[Method, DistanceEstimator] = {
            est.method: est for est in estimators
        }

    def prepare_image(self, image_rgb: np.ndarray | None) -> None:
        """Pass current image to estimators that require frame-level precomputation (e.g. depth)."""
        depth_est = self._estimators.get("depth")
        if isinstance(depth_est, DepthEstimator):
            depth_est.set_image(image_rgb)

    def localize(
        self,
        *,
        class_name: str,
        bbox_xyxy: BBox,
        frame: CameraFrame,
    ) -> GeoLocation:
        """Compute bearing, fused distance, WGS84 coordinates, and total uncertainty."""
        bearing_deg = frame.bearing_for_bbox(bbox_xyxy)
        spec = self.taxonomy.get(class_name)

        allowed_methods = self.taxonomy.methods_for(class_name, self.cfg.methods)
        estimates: list[DistanceEstimation] = []

        for method_name in allowed_methods:
            estimator = self._estimators.get(method_name)
            if estimator is None:
                continue

            estimation = estimator.estimate(bbox_xyxy, spec, frame)
            if estimation is not None:
                estimates.append(estimation)
                if self.cfg.fusion == "first":
                    break

        if not estimates:
            return GeoLocation(bearing_deg=bearing_deg)

        fused_dist_m, geom_sigma_m, method_lbl = self._fuse_estimates(estimates)
        est_lat, est_lon = project_point(
            lat=frame.lat,
            lon=frame.lon,
            bearing_deg=bearing_deg,
            distance_m=fused_dist_m,
        )
        total_uncertainty_m = self._total_position_uncertainty(
            distance_m=fused_dist_m,
            geom_sigma_m=geom_sigma_m,
        )
        return GeoLocation(
            bearing_deg=bearing_deg,
            est_lat=est_lat,
            est_lon=est_lon,
            est_distance_m=fused_dist_m,
            uncertainty_m=total_uncertainty_m,
            method=method_lbl,
        )

    @staticmethod
    def _fuse_estimates(
        estimates: Sequence[DistanceEstimation],
    ) -> tuple[float, float, str]:
        """Combine valid distance estimates via inverse-variance weighting."""
        if len(estimates) == 1:
            single = estimates[0]
            return single.distance_m, single.uncertainty_m, single.method

        weights = [1.0 / (est.uncertainty_m**2) for est in estimates]
        weighted_sum = sum(weights)

        fused_dist = (
            sum(w * est.distance_m for w, est in zip(weights, estimates)) / weighted_sum
        )
        fused_sigma = math.sqrt(1.0 / weighted_sum)

        return fused_dist, fused_sigma, "fused"

    def _total_position_uncertainty(
        self,
        *,
        distance_m: float,
        geom_sigma_m: float,
    ) -> float:
        """Combine radial distance error with camera GPS and bearing uncertainties."""
        bearing_sigma_rad = math.radians(self.cfg.bearing_sigma_deg)
        cross_track_sigma_m = distance_m * math.tan(bearing_sigma_rad)
        pos_uncertainty = math.hypot(
            geom_sigma_m, cross_track_sigma_m, self.cfg.gps_sigma_m
        )
        return pos_uncertainty
