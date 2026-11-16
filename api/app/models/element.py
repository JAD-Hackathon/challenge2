import enum
import uuid
from datetime import datetime

from app.database.base import Base
from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, String, Text, func
from sqlalchemy.orm import Mapped, column_property, mapped_column


class ElementCategory(enum.StrEnum):
    TRAFFIC_SIGN = "sign"  # sinalização vertical
    STREET_LIGHT = "light"  # iluminação pública
    WASTE_CONTAINER = "waste"  # resíduos


class Element(Base):
    """A piece of street furniture in the catalogue."""

    __tablename__ = "elements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        String(128)
    )  # e.g. "Stop", "Candeeiro", "Ecoponto"
    category: Mapped[ElementCategory] = mapped_column(
        Enum(
            ElementCategory,
            name="element_category",
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
    )
    # traffic sign: stop, yield, speed_limit_50, ...
    # waste container: underground, recycling_island, undifferentiated
    type: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)  # detection confidence, 0..1

    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = column_property(func.ST_Y(geom))
    longitude: Mapped[float] = column_property(func.ST_X(geom))

    image_url: Mapped[str | None] = mapped_column(
        Text
    )  # anonymised image (no faces/plates)
    attribution: Mapped[str | None] = mapped_column(
        Text
    )  # CC BY-SA credit for Mapillary/KartaView

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
