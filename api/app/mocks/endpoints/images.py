from app.api.uploads import ImagesForm, MetasForm, read_batch
from app.api.v1.endpoints import images as real
from app.mocks.endpoints import mirrors
from app.mocks.services import images as service
from app.schemas.image import BatchResponse, ImageRead
from fastapi import APIRouter

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=BatchResponse)
@mirrors(real.upload_images)
def upload_images(images: ImagesForm, metas: MetasForm):
    return service.ingest_batch(read_batch(images, metas))


@router.get("/{image_id}", response_model=ImageRead)
@mirrors(real.get_image)
def get_image(image_id: str):
    return service.get_image(image_id)
