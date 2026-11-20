from __future__ import annotations

import uuid
from collections import defaultdict

from src.config import DedupConfig
from src.dedup.cluster import cluster
from src.dedup.geometry_check import estimate_cluster_position
from src.dedup.scoring import fuse_confidence, select_best_observation
from src.dedup.utils.helpers import resolve_category
from src.geometry.utils.geo import LocalENU, geodesic_distance_m
from src.service.schemas import (
    CameraMeta,
    DedupRequest,
    DedupResponse,
    Element,
    Observation,
)
from src.taxonomy import Taxonomy, get_taxonomy


class AssetDeduplicator:
    """Merge multi-view street observations into deduplicated physical Elements."""

    def __init__(
        self,
        cfg: DedupConfig,
        taxonomy: Taxonomy | None = None,
    ) -> None:
        self.cfg = cfg
        self.taxonomy = taxonomy or get_taxonomy()

    def deduplicate(self, request: DedupRequest) -> DedupResponse:
        """Execute deduplication while preserving human-verified/corrected Elements."""
        images_by_id: dict[str, CameraMeta] = {
            img.image_id: img for img in request.images
        }

        unassigned_ids: list[str] = []
        valid_obs: list[Observation] = []

        for obs in request.observations:
            if obs.est_lat is None or obs.est_lon is None:
                unassigned_ids.append(obs.observation_id)
            else:
                valid_obs.append(obs)

        locked_elements: list[Element] = [
            el
            for el in request.existing_elements
            if el.status in ("verified", "corrected", "rejected")
        ]
        auto_elements: list[Element] = [
            el for el in request.existing_elements if el.status in ("auto")
        ]

        updated_locked, remaining_obs = self._attach_to_locked(
            valid_obs, locked_elements
        )

        if not remaining_obs:
            return DedupResponse(
                elements=[*updated_locked, *auto_elements],
                unassigned_observation_ids=unassigned_ids,
                removed_element_ids=[],
            )

        lat0, lon0 = remaining_obs[0].est_lat, remaining_obs[0].est_lon
        assert lat0 is not None and lon0 is not None
        enu = LocalENU(lat0, lon0)

        by_type: dict[str, list[Observation]] = defaultdict(list)
        for obs in remaining_obs:
            by_type[obs.type].append(obs)

        new_elements: list[Element] = []
        reused_auto_ids: set[str] = set()

        for asset_type, observations in by_type.items():
            category = resolve_category(asset_type, self.taxonomy)
            radius_m = self.cfg.radius_m[category]
            clusters = cluster(
                observations=observations,
                radius_m=radius_m,
                enu=enu,
                images_by_id=images_by_id,
                use_ray_check=self.cfg.use_ray_check,
            )

            for cluster_obs in clusters:
                lat, lon = estimate_cluster_position(
                    observations=cluster_obs,
                    images_by_id=images_by_id,
                    enu=enu,
                )
                best_obs = select_best_observation(cluster_obs)
                conf = fuse_confidence(
                    observations=cluster_obs, max_confidence=self.cfg.max_confidence
                )

                obs_ids = [obs.observation_id for obs in cluster_obs]
                matched_id = self._match_auto_element(
                    asset_type=asset_type,
                    lat=lat,
                    lon=lon,
                    radius_m=radius_m,
                    auto_elements=auto_elements,
                    reused_ids=reused_auto_ids,
                )

                new_elements.append(
                    Element(
                        element_id=matched_id or f"el_{uuid.uuid4().hex[:12]}",
                        type=asset_type,
                        lat=lat,
                        lon=lon,
                        confidence=conf,
                        observation_ids=obs_ids,
                        best_observation_id=best_obs.observation_id,
                        status="auto",
                    )
                )

        removed_element_ids = [
            el.element_id
            for el in auto_elements
            if el.element_id not in reused_auto_ids
        ]

        return DedupResponse(
            elements=[*new_elements, *updated_locked],
            unassigned_observation_ids=unassigned_ids,
            removed_element_ids=removed_element_ids,
        )

    def _attach_to_locked(
        self,
        observations: list[Observation],
        locked_elements: list[Element],
    ) -> tuple[list[Element], list[Observation]]:
        """Attach nearby observations to existing verified/corrected elements without moving them."""
        buckets: dict[str, list[str]] = {
            el.element_id: el.observation_ids.copy() for el in locked_elements
        }
        remaining: list[Observation] = []

        for obs in observations:
            assert obs.est_lat is not None and obs.est_lon is not None
            category = resolve_category(obs.type, self.taxonomy)
            best_dist = self.cfg.radius_m[category]
            matched: Element | None = None

            for el in locked_elements:
                if el.status == "rejected" or el.type != obs.type:
                    continue
                dist = geodesic_distance_m(obs.est_lat, obs.est_lon, el.lat, el.lon)

                if dist <= best_dist:
                    best_dist = dist
                    matched = el

            if matched is not None:
                if obs.observation_id not in buckets[matched.element_id]:
                    buckets[matched.element_id].append(obs.observation_id)
            else:
                remaining.append(obs)

        updated = [
            el.model_copy(update={"observation_ids": buckets[el.element_id]})
            for el in locked_elements
        ]

        return updated, remaining

    @staticmethod
    def _match_auto_element(
        asset_type: str,
        lat: float,
        lon: float,
        radius_m: float,
        auto_elements: list[Element],
        reused_ids: set[str],
    ) -> str | None:
        """Reuse an existing 'auto' element_id if a recomputed cluster lands within `radius_m`."""
        for el in auto_elements:
            if el.element_id in reused_ids or el.type != asset_type:
                continue
            if geodesic_distance_m(lat, lon, el.lat, el.lon) <= radius_m:
                reused_ids.add(el.element_id)
                return el.element_id
        return None
