from fastapi import APIRouter

from app.api.deps import SessionDep
from app.api.uploads import ImagesForm, MetasForm, read_batch
from app.schemas.image import BatchResponse, ImageRead
from app.services import image as image_service
from app.services import ingest as ingest_service

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=BatchResponse)
def upload_images(db: SessionDep, images: ImagesForm, metas: MetasForm):
    """Upload a batch of images (1..MAX_BATCH_SIZE) with their camera metadata.

    Each image is blurred and analysed by ML, then the detections of the whole batch are merged
    into elements. Each file gets its own result (`processed`, `duplicate` or `failed`), so one
    bad file doesn't fail the batch. Synchronous: can take a while for big batches.
    """
    return ingest_service.ingest_batch(db, read_batch(images, metas))


@router.get("/{image_id}", response_model=ImageRead)
def get_image(db: SessionDep, image_id: str):
    """Blurred image URL and every detection in it (to draw the boxes)."""
    return image_service.get_image(db, image_id)
