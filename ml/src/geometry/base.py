from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import GeometryConfig, Method
from src.geometry.utils.camera import (
    focal_length_px,
    pano_bearing,
    perspective_bearing,
)
from src.taxonomy import ClassSpec

BBox = tuple[float, float, float, float]


class _GeometryModel(BaseModel):
    """Frozen, strictly-typed base model for geometry data structures."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# input


class CameraFrame(_GeometryModel):
    """Normalized camera pose and optical parameters for a single image."""

    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    heading: float = Field(ge=0.0, le=360.0)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    fov_deg: float = Field(gt=0.0, le=360.0)
    camera_type: Literal["perspective", "equirectangular"]
    camera_height_m: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _validate_perspective_fov(self) -> "CameraFrame":
        if self.camera_type == "perspective" and self.fov_deg >= 180.0:
            raise ValueError(
                f"Perspective camera requires fov_deg < 180, got {self.fov_deg}"
            )
        return self

    @classmethod
    def from_meta(
        cls,
        *,
        lat: float,
        lon: float,
        heading: float,
        image_width: int,
        image_height: int,
        cfg: GeometryConfig,
        fov: float | None = None,
        camera_type: Literal["perspective", "equirectangular"] | None = None,
        camera_height_m: float | None = None,
    ) -> "CameraFrame":
        """Build a CameraFrame by falling back to GeometryConfig defaults for None values."""
        resolved_type = (
            camera_type if camera_type is not None else cfg.default_camera_type
        )
        if fov is not None:
            resolved_fov = fov
        elif resolved_type == "equirectangular":
            resolved_fov = 360.0
        else:
            resolved_fov = cfg.default_fov_deg

        resolved_height = (
            camera_height_m
            if camera_height_m is not None
            else cfg.default_camera_height_m
        )

        return cls(
            lat=lat,
            lon=lon,
            heading=heading % 360.0,
            image_width=image_width,
            image_height=image_height,
            fov_deg=resolved_fov,
            camera_type=resolved_type,
            camera_height_m=resolved_height,
        )

    @property
    def focal_px(self) -> float:
        """Horizontal focal length in pixels (for perspective cameras)."""
        if self.camera_type != "perspective":
            raise ValueError(
                "focal_px is only defined for perspective cameras, "
                f"got '{self.camera_type}'"
            )
        return focal_length_px(self.image_width, self.fov_deg)

    def bearing_for_x(self, cx: float) -> float:
        """Compute compass bearing (deg, clockwise from north) for pixel column cx."""
        if self.camera_type == "equirectangular":
            return pano_bearing(self.heading, cx, self.image_width, self.fov_deg)
        return perspective_bearing(self.heading, cx, self.image_width, self.fov_deg)

    def bearing_for_bbox(self, bbox_xyxy: BBox) -> float:
        """Compute compass bearing for the horizontal center of a bounding box."""
        cx = (bbox_xyxy[0] + bbox_xyxy[2]) / 2.0
        return self.bearing_for_x(cx)


# output


class DistanceEstimation(_GeometryModel):
    """Single-method distance prediction and its 1-sigma uncertainty in metres."""

    distance_m: float = Field(gt=0.0)
    uncertainty_m: float = Field(gt=0.0)
    method: Method


class GeoLocation(_GeometryModel):
    """Final 3D localization output attached to a single observation."""

    bearing_deg: float = Field(ge=0.0, lt=360.0)
    est_lat: float | None = None
    est_lon: float | None = None
    est_distance_m: float | None = None
    uncertainty_m: float | None = None
    method: str | None = None


class DistanceEstimator(ABC):
    """Common interface implemented by all single-view distance estimators."""

    method: Method

    @abstractmethod
    def estimate(
        self,
        bbox_xyxy: BBox,
        spec: ClassSpec,
        frame: CameraFrame,
    ) -> DistanceEstimation | None:
        """
        Estimate horizontal distance (m) and uncertainty (m) to an object.\n
        Returns None when the method is inapplicable or the observation is unreliable
        (e.g. occluded base, truncated bbox, or beyond max reliable range).
        """
        pass
