import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.element import Element
    from app.models.image import Image


class Observation(Base):
    """One detection in one image (ML /infer). /dedup groups observations into elements."""

    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    image_id: Mapped[str] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    element_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("elements.id", ondelete="SET NULL"), index=True
    )

    type: Mapped[str] = mapped_column(String(64))  # ML class, e.g. "sign.speed_limit"
    score: Mapped[float]
    bbox_xyxy: Mapped[list[int]] = mapped_column(
        ARRAY(Integer)
    )  # px in the blurred image
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    # Estimated position of the object (null when ML couldn't compute it)
    bearing_deg: Mapped[float | None]
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    latitude: Mapped[float | None] = column_property(func.ST_Y(geom))
    longitude: Mapped[float | None] = column_property(func.ST_X(geom))
    uncertainty_m: Mapped[float | None]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    image: Mapped["Image"] = relationship(back_populates="observations")
    element: Mapped["Element | None"] = relationship(back_populates="observations")
