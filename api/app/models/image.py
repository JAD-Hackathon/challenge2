from datetime import datetime
from typing import TYPE_CHECKING

from app.database.base import Base
from geoalchemy2 import Geometry
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.observation import Observation


class Image(Base):
    """A street-level photo that went through ML. Only its blurred copy exists (in SHARED_DIR)."""

    __tablename__ = "images"

    # image_id sent to ML, which names the blurred file after it (mly_<id>, kv_<id>, up_<uuid>)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str | None] = mapped_column(String(16))  # mapillary | kartaview | video | null

    # Camera position and direction
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = column_property(func.ST_Y(geom))
    longitude: Mapped[float] = column_property(func.ST_X(geom))
    heading: Mapped[float]
    fov: Mapped[float | None]
    camera_height_m: Mapped[float | None]
    sequence_id: Mapped[str | None] = mapped_column(String(64))
    frame_index: Mapped[int | None]

    blurred_image_path: Mapped[str] = mapped_column(Text)  # relative to SHARED_DIR
    filename: Mapped[str | None] = mapped_column(Text)  # name of the uploaded file

    # Attribution (Mapillary / KartaView images are CC BY-SA)
    author: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observations: Mapped[list["Observation"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )
