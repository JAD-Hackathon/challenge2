from app.core.exceptions import NotFoundError
from app.models.image import Image
from app.models.observation import Observation
from app.repositories import image as image_repo
from app.schemas.image import ImageRead, ObservationRead, attribution
from app.services import media
from sqlalchemy.orm import Session


def get_image(db: Session, image_id: str) -> ImageRead:
    image = image_repo.get_image(db, image_id)
    if image is None:
        raise NotFoundError("Image not found")
    return to_image_read(image)


def to_image_read(image: Image) -> ImageRead:
    return ImageRead(
        id=image.id,
        source=image.source,
        latitude=image.latitude,
        longitude=image.longitude,
        heading=image.heading,
        fov=image.fov,
        image_url=media.media_url(image.blurred_image_path),
        filename=image.filename,
        attribution=attribution(image.author, image.license, image.source),
        captured_at=image.captured_at,
        created_at=image.created_at,
        observations=[
            _observation_read(o) for o in sorted(image.observations, key=lambda o: -o.score)
        ],
    )


def _observation_read(obs: Observation) -> ObservationRead:
    return ObservationRead(
        id=obs.id,
        element_id=obs.element_id,
        type=obs.type,
        score=obs.score,
        bbox_xyxy=obs.bbox_xyxy,
        attributes=obs.attributes or {},
        latitude=obs.latitude,
        longitude=obs.longitude,
        uncertainty_m=obs.uncertainty_m,
    )
