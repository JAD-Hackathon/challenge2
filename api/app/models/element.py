import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.database.base import Base
from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.observation import Observation


class ElementCategory(enum.StrEnum):
    TRAFFIC_SIGN = "sign"  # sinalização vertical
    STREET_LIGHT = "light"  # iluminação pública
    WASTE_CONTAINER = "waste"  # resíduos


class ElementStatus(enum.StrEnum):
    """Same values as the ML contract."""

    AUTO = "auto"  # as found by ML
    VERIFIED = "verified"  # a technician confirmed it
    CORRECTED = "corrected"  # a technician fixed its type / attributes
    REJECTED = "rejected"  # false positive: hidden, kept so it isn't created again


# Human decisions: ML results never change these elements
LOCKED_STATUSES = frozenset(
    {ElementStatus.VERIFIED, ElementStatus.CORRECTED, ElementStatus.REJECTED}
)


def status_after_verify(status: ElementStatus) -> ElementStatus:
    """A technician confirms the element. 'corrected' already means human-checked: kept.
    A 'rejected' element comes back (undoes a false-positive flag)."""
    return status if status is ElementStatus.CORRECTED else ElementStatus.VERIFIED


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class Element(Base):
    """A piece of street furniture in the catalogue."""

    __tablename__ = "elements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))  # e.g. "Stop", "Candeeiro", "Ecoponto"
    category: Mapped[ElementCategory] = mapped_column(
        pg_enum(ElementCategory, "element_category"), index=True
    )
    # Type inside the category: ML class "sign.speed_limit" -> category "sign", type "speed_limit"
    # traffic sign: stop, yield, speed_limit, other
    # waste container: underground, recycling_island, general
    type: Mapped[str | None] = mapped_column(String(64))
    # Extra key/value facts, e.g. {"limit": 30} for a speed_limit sign (see core/taxonomy.py)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[ElementStatus] = mapped_column(
        pg_enum(ElementStatus, "element_status"),
        default=ElementStatus.AUTO,
        server_default=ElementStatus.AUTO.value,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float)  # detection confidence, 0..1

    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = column_property(func.ST_Y(geom))
    longitude: Mapped[float] = column_property(func.ST_X(geom))

    # ML's pick for the best view of the element; its image + bbox are what the UI shows.
    # No FK on purpose: observations already point here (avoids a circular FK).
    best_observation_id: Mapped[uuid.UUID | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    observations: Mapped[list["Observation"]] = relationship(back_populates="element")
    best_observation: Mapped["Observation | None"] = relationship(
        primaryjoin="foreign(Element.best_observation_id) == Observation.id",
        viewonly=True,
    )
