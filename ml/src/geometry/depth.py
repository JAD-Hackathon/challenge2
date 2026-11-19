from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from src.config import GeometryConfig, Method
from src.geometry.base import (
    CameraFrame,
    DistanceEstimation,
    DistanceEstimator,
    BBox,
)
from src.taxonomy import ClassSpec


class DepthMapProvider(Protocol):
    """Protocol for pluggable monocular depth map predictors."""

    def predict_depth_m(self, image_rgb: np.ndarray) -> np.ndarray:
        """Return a 2D float32 depth map in metres matching (H, W) of image_rgb."""
        ...


class ONNXDepthProvider:
    """Standalone ONNX Runtime predictor for metric monocular depth models."""

    def __init__(
        self, weights_path: Path, input_size: tuple[int, int] = (518, 518)
    ) -> None:
        if not weights_path.is_file():
            raise FileNotFoundError(f"Depth weights not found: {weights_path}")
        import onnxruntime as ort

        self.input_size = input_size
        self.session = ort.InferenceSession(
            str(weights_path),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name

    def predict_depth_m(self, image_rgb: np.ndarray) -> np.ndarray:
        """Run inference and resize predicted metric depth map back to (H, W)."""
        import cv2

        orig_h, orig_w = image_rgb.shape[:2]

        # resize + normalize + standardize
        resized = cv2.resize(image_rgb, self.input_size, interpolation=cv2.INTER_LINEAR)
        blob = resized.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        blob = ((blob - mean) / std).transpose(2, 0, 1)[None, ...]

        out = self.session.run(
            output_names=None,
            input_feed={self.input_name: blob},
        )[0]

        depth_small = np.squeeze(out).astype(np.float32)
        depth = cv2.resize(
            depth_small, dsize=(orig_h, orig_w), interpolation=cv2.INTER_LINEAR
        )
        return depth


class DepthEstimator(DistanceEstimator):
    """Estimate object distance from a dense monocular depth map."""

    method: Method = "depth"

    def __init__(
        self,
        cfg: GeometryConfig,
        provider: DepthMapProvider | None = None,
        scale_factor: float = 1.0,
        rel_sigma: float = 0.20,
        core_crop_ratio: float = 0.5,
    ) -> None:
        self.cfg = cfg
        self.provider = provider
        self.scale_factor = scale_factor
        self.rel_sigma = rel_sigma
        self.core_crop_ratio = core_crop_ratio
        self._cached_depth_map: np.ndarray | None = None
        self._cached_image_token: int | None = None

    def set_image(self, image_rgb: np.ndarray | None) -> None:
        """Attach the current RGB frame so depth is computed at most once per image."""
        if image_rgb is None or not self.cfg.depth.enabled or self.provider is None:
            self._cached_depth_map = None
            self._cached_image_token = None
            return

        token = id(image_rgb)
        if token != self._cached_image_token:
            self._cached_depth_map = self.provider.predict_depth_m(image_rgb)
            self._cached_image_token = token

    def set_depth_map(self, depth_map_m: np.ndarray | None) -> None:
        """Directly inject a precomputed metric depth map (useful in tests/offline runs)."""
        self._cached_depth_map = depth_map_m
        self._cached_image_token = None

    def estimate(
        self,
        bbox_xyxy: BBox,
        spec: ClassSpec,
        frame: CameraFrame,
    ) -> DistanceEstimation | None:
        """Sample robust median depth inside the inner region of bbox_xyxy."""
        if not self.cfg.depth.enabled or self._cached_depth_map is None:
            return None

        x0, y0, x1, y1 = bbox_xyxy
        box_w = max(0, x1 - x0)
        box_h = max(0, y1 - y0)
        if box_w < self.cfg.min_box_px or box_h < self.cfg.min_box_px:
            return None

        margin_x = box_w * (1.0 - self.core_crop_ratio) / 2.0
        margin_y = box_h * (1.0 - self.core_crop_ratio) / 2.0

        h, w = self._cached_depth_map.shape[:2]
        ix0 = max(0, int(round(x0 + margin_x)))
        iy0 = max(0, int(round(y0 + margin_y)))
        ix1 = min(w, max(ix0 + 1, int(round(x1 - margin_x))))
        iy1 = min(h, max(iy0 + 1, int(round(y1 - margin_y))))

        patch = self._cached_depth_map[iy0:iy1, ix0:ix1]
        valid_depths = patch[np.isfinite(patch) & (patch > 0.0)]
        if valid_depths.size == 0:
            return None

        distance_m = float(np.median(valid_depths)) * self.scale_factor
        if distance_m <= 0.0 or distance_m > self.cfg.max_distance_m:
            return None

        uncertainty_m = max(0.15, distance_m * self.rel_sigma)

        return DistanceEstimation(
            distance_m=distance_m,
            uncertainty_m=uncertainty_m,
            method=self.method,
        )
