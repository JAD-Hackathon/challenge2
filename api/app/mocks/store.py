"""In-memory catalogue for mock mode, seeded from fixtures/seed.json. Lost on restart."""

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core import taxonomy
from app.core.exceptions import NotFoundError
from app.mocks import placeholders
from app.models.element import ElementCategory, ElementStatus
from app.schemas.element import ElementRead
from app.schemas.image import ImageRead, ObservationRead, attribution
from app.services import media

SEED_FILE = Path(__file__).parent / "fixtures" / "seed.json"


def now() -> datetime:
    return datetime.now(UTC)


def new_element(
    *,
    element_id: uuid.UUID,
    class_name: str,
    attributes: dict[str, Any],
    confidence: float,
    lat: float,
    lon: float,
    image: ImageRead,
    bbox_xyxy: list[int],
    created_at: datetime,
    status: ElementStatus = ElementStatus.AUTO,
    observation_count: int = 1,
) -> ElementRead:
    """ValueError if class_name isn't a known 'category.type'."""
    category, type_ = taxonomy.split_class(class_name)
    return ElementRead(
        id=element_id,
        name=taxonomy.label(class_name),
        category=category,
        type=type_,
        attributes=attributes,
        status=status,
        confidence=confidence,
        latitude=lat,
        longitude=lon,
        image_id=image.id,
        image_url=image.image_url,
        bbox_xyxy=bbox_xyxy,
        attribution=image.attribution,
        observation_count=observation_count,
        created_at=created_at,
        updated_at=created_at,
    )


class MockStore:
    def __init__(self) -> None:
        self.lock = threading.RLock()  # sync endpoints run in a thread pool
        self._elements: dict[uuid.UUID, ElementRead] = {}
        self._best_observation: dict[
            uuid.UUID, str
        ] = {}  # element id -> observation id
        self._images: dict[str, ImageRead] = {}

    # --- elements ---

    def list_elements(
        self,
        category: ElementCategory | None = None,
        status: ElementStatus | None = None,
    ) -> list[ElementRead]:
        """status=None -> every element except rejected ones (like the real API)."""
        return [
            e
            for e in self.all_elements()
            if (category is None or e.category is category)
            and (
                e.status is status if status else e.status is not ElementStatus.REJECTED
            )
        ]

    def all_elements(self) -> list[ElementRead]:
        with self.lock:
            return sorted(self._elements.values(), key=lambda e: e.created_at)

    def get_element(self, element_id: uuid.UUID) -> ElementRead:
        with self.lock:
            if element_id not in self._elements:
                raise NotFoundError("Element not found")
            return self._elements[element_id]

    def save_element(
        self, element: ElementRead, best_observation_id: str | None = None
    ) -> None:
        """Insert or replace. Elements are treated as immutable: change them with model_copy."""
        with self.lock:
            self._elements[element.id] = element
            if best_observation_id:
                self._best_observation[element.id] = best_observation_id

    def best_observation_id(self, element_id: uuid.UUID) -> str | None:
        with self.lock:
            return self._best_observation.get(element_id)

    # --- images ---

    def has_image(self, image_id: str) -> bool:
        with self.lock:
            return image_id in self._images

    def get_image(self, image_id: str) -> ImageRead:
        with self.lock:
            if image_id not in self._images:
                raise NotFoundError("Image not found")
            return self._images[image_id].model_copy(deep=True)

    def save_image(self, image: ImageRead) -> None:
        with self.lock:
            self._images[image.id] = image

    def add_observation(self, image_id: str, observation: ObservationRead) -> None:
        with self.lock:
            self._images[image_id].observations.append(observation)

    # --- seed ---

    def reset(self) -> None:
        """Back to the seed data, redrawing the seed images in the shared folder."""
        seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        seeded_at = datetime.fromisoformat(seed["seeded_at"])
        with self.lock:
            self._elements.clear()
            self._best_observation.clear()
            self._images.clear()
            for raw in seed["images"]:
                self._seed_image(raw, seeded_at)

    def _seed_image(self, raw: dict[str, Any], seeded_at: datetime) -> None:
        relative = f"{media.IMAGES_SUBDIR}/{raw['id']}.jpg"
        placeholders.draw(media.shared_path(relative), raw["id"], raw["elements"])
        image = ImageRead(
            id=raw["id"],
            source=raw["source"],
            latitude=raw["lat"],
            longitude=raw["lon"],
            heading=raw["heading"],
            fov=raw["fov"],
            image_url=media.media_url(relative),
            filename=None,
            attribution=attribution(raw["author"], raw["license"], raw["source"]),
            captured_at=datetime.fromisoformat(raw["captured_at"]),
            created_at=seeded_at,
            observations=[],
        )
        self.save_image(image)
        for el in raw["elements"]:
            element = new_element(
                element_id=uuid.UUID(el["id"]),
                class_name=el["type"],
                attributes=el["attributes"],
                confidence=el["confidence"],
                lat=el["lat"],
                lon=el["lon"],
                image=image,
                bbox_xyxy=el["bbox_xyxy"],
                status=ElementStatus(el["status"]),
                created_at=seeded_at,
            )
            observation = ObservationRead(
                id=str(uuid.uuid5(element.id, "observation")),  # one view per seed element
                element_id=element.id,
                type=el["type"],
                score=element.confidence,
                bbox_xyxy=el["bbox_xyxy"],
                attributes=el["attributes"],
                latitude=element.latitude,
                longitude=element.longitude,
                uncertainty_m=2.0,
            )
            self.save_element(element, best_observation_id=observation.id)
            self.add_observation(image.id, observation)


store = MockStore()
