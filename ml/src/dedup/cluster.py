from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist

from src.dedup.utils.helpers import extract_image_id
from src.dedup.geometry_check import is_ray_consistent
from src.geometry.utils.geo import LocalENU
from src.service.schemas import CameraMeta, Observation


def cluster(
    observations: Sequence[Observation],
    radius_m: float,
    enu: LocalENU,
    images_by_id: dict[str, CameraMeta],
    use_ray_check: bool,
) -> list[list[Observation]]:
    """Cluster observations of one fine-grained type within `radius_m`."""
    n = len(observations)
    if n == 0:
        return []
    if n == 1:
        return [list(observations)]

    coords = np.array(
        [enu.to_xy(o.est_lat, o.est_lon) for o in observations], dtype=np.float64
    )
    dists_condensed = pdist(coords, metric="euclidean")
    labels = fcluster(
        linkage(dists_condensed, method="complete", metric="euclidean"),
        t=radius_m,
        criterion="distance",
    )

    spatial_groups: dict[int, list[Observation]] = defaultdict(list)
    for obs, lbl in zip(observations, labels, strict=True):
        spatial_groups[int(lbl)].append(obs)

    clusters: list[list[Observation]] = []

    for group in spatial_groups.values():
        buckets: list[list[Observation]] = []
        bucket_images: list[set[str]] = []

        for obs in sorted(group, key=lambda o: o.score, reverse=True):
            img_id = extract_image_id(obs)

            for b_obs, b_imgs in zip(buckets, bucket_images):
                if img_id is not None and img_id in b_imgs:
                    continue

                if use_ray_check and not is_ray_consistent(
                    cluster_obs=b_obs,
                    candidate=obs,
                    images_by_id=images_by_id,
                    radius_m=radius_m,
                ):
                    continue

                b_obs.append(obs)
                if img_id is not None:
                    b_imgs.add(img_id)

                break
            else:
                buckets.append([obs])
                bucket_images.append({img_id} if img_id is not None else set())

        clusters.extend(buckets)

    return clusters
