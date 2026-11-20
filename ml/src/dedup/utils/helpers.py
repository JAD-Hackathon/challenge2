from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from src.config import Category
from src.geometry.triangulation import RayObservation
from src.service.schemas import CameraMeta, Observation
from src.taxonomy import Taxonomy


def extract_image_id(obs: Observation) -> str | None:
    """Extract embedded image_id from '<image_id>:<suffix>' observation_id, if present."""
    if ":" not in obs.observation_id:
        return None
    prefix = obs.observation_id.split(":", 1)[0].strip()
    return prefix or None


def resolve_category(asset_type: str, taxonomy: Taxonomy) -> Category:
    """Resolve top-level category ('sign', 'light', 'waste') via Taxonomy with prefix fallback."""
    try:
        return taxonomy.get(asset_type).category
    except KeyError:
        prefix = asset_type.split(".", 1)[0]
        if prefix in ("sign", "light", "waste"):
            return cast(Category, prefix)
        raise KeyError(f"Unknown asset class or category: '{asset_type}'") from None


def build_rays(
    observations: Sequence[Observation],
    images_by_id: dict[str, CameraMeta],
) -> list[RayObservation]:
    """Build RayObservation objects for observations that have valid camera poses and bearings."""
    rays: list[RayObservation] = []
    for obs in observations:
        img_id = extract_image_id(obs)
        if img_id is None or img_id not in images_by_id or obs.bearing_deg is None:
            continue
        cam = images_by_id[img_id]
        rays.append(
            RayObservation(
                camera_lat=cam.lat,
                camera_lon=cam.lon,
                bearing_deg=obs.bearing_deg,
                uncertainty_m=obs.uncertainty_m
                if obs.uncertainty_m is not None
                else 3.0,
            )
        )
    return rays
