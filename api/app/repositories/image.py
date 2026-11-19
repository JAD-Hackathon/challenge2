from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.models.image import Image


def image_exists(db: Session, image_id: str) -> bool:
    return db.scalar(select(exists().where(Image.id == image_id))) or False


def get_image(db: Session, image_id: str) -> Image | None:
    return db.get(Image, image_id, options=[selectinload(Image.observations)])
