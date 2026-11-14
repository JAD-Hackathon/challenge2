import io
import math
import random
import uuid

from fastapi import status
from PIL import Image, ImageFilter, UnidentifiedImageError

from src.config import get_settings
from src.service.exceptions import APIError
from src.service.schemas import (
    CameraMeta,
    DedupRequest,
    DedupResponse,
    Element,
    InferResponse,
    Observation,
)
from src.taxonomy import get_taxonomy

METERS_PER_DEGREE = 111_320


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Flat-earth distance, good enough for a few metres."""
    dy = (lat2 - lat1) * METERS_PER_DEGREE
    dx = (lon2 - lon1) * METERS_PER_DEGREE * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def _open_image(image_bytes: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise APIError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_image",
            "could not read the image",
        ) from None


def _save_blurred(image: Image.Image, image_id: str) -> str:
    """Saves into <shared>/images and returns the relative path for the JSON."""
    settings = get_settings()
    settings.paths.images_dir.mkdir(parents=True, exist_ok=True)
    blurred = image.filter(ImageFilter.GaussianBlur(radius=8))
    blurred.save(settings.paths.images_dir / f"{image_id}.jpg", quality=85)
    return f"{settings.paths.images_subdir}/{image_id}.jpg"


def _fake_observation(
    rng: random.Random, camera: CameraMeta, width: int, height: int, index: int
) -> Observation:
    settings = get_settings()

    box_w = rng.randint(30, 80)
    box_h = rng.randint(30, 80)
    x1 = rng.randint(0, max(0, width - box_w))
    y1 = rng.randint(0, max(0, height - box_h))

    # bearing from the horizontal position of the box centre
    fov = camera.fov or settings.geometry.default_fov_deg
    focal_px = (width / 2) / math.tan(math.radians(fov / 2))
    center_x = x1 + box_w / 2
    angle = math.degrees(math.atan((center_x - width / 2) / focal_px))
    bearing = (camera.heading + angle) % 360

    # position: move 5-20 m from the camera along the bearing
    distance = rng.uniform(5, 20)
    lat = camera.lat + distance * math.cos(math.radians(bearing)) / METERS_PER_DEGREE
    lon = camera.lon + distance * math.sin(math.radians(bearing)) / (
        METERS_PER_DEGREE * math.cos(math.radians(camera.lat))
    )

    return Observation(
        observation_id=str(uuid.UUID(int=rng.getrandbits(128))),
        type=rng.choice(get_taxonomy().names),
        score=round(rng.uniform(0.5, 0.98), 2),
        bbox_xyxy=[x1, y1, x1 + box_w, y1 + box_h],
        bearing_deg=round(bearing, 1),
        est_lat=round(lat, 6),
        est_lon=round(lon, 6),
        uncertainty_m=round(1 + 0.15 * distance, 1),
    )


def mock_infer(image_bytes: bytes, camera: CameraMeta) -> InferResponse:
    image = _open_image(image_bytes)
    width, height = image.size
    path = _save_blurred(image, camera.image_id)

    rng = random.Random(camera.image_id)
    observations = [
        _fake_observation(rng, camera, width, height, i)
        for i in range(rng.randint(1, 3))
    ]
    return InferResponse(
        image_id=camera.image_id,
        blurred_image_path=path,
        observations=observations,
    )


def mock_dedup(request: DedupRequest) -> DedupResponse:
    """Greedy distance clustering per type. Ignores existing_elements."""
    radius_by_category = get_settings().dedup.radius_m
    groups: list[list[Observation]] = []
    unassigned: list[str] = []

    for obs in request.observations:
        if obs.est_lat is None or obs.est_lon is None:
            unassigned.append(obs.observation_id)
            continue

        radius = radius_by_category.get(obs.type.split(".")[0], 3.0)
        for group in groups:
            first = group[0]
            if (
                first.type == obs.type
                and _distance_m(first.est_lat, first.est_lon, obs.est_lat, obs.est_lon)
                <= radius
            ):
                group.append(obs)
                break
        else:
            groups.append([obs])

    elements = []
    for group in groups:
        best = max(group, key=lambda o: o.score)
        elements.append(
            Element(
                element_id=str(uuid.uuid5(uuid.NAMESPACE_URL, group[0].observation_id)),
                type=group[0].type,
                lat=sum(o.est_lat for o in group) / len(group),
                lon=sum(o.est_lon for o in group) / len(group),
                confidence=best.score,
                observation_ids=[o.observation_id for o in group],
                best_observation_id=best.observation_id,
            )
        )

    return DedupResponse(elements=elements, unassigned_observation_ids=unassigned)
