import math
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.postgis import LatLon
from app.models.element import Element, ElementCategory, ElementStatus
from app.models.observation import Observation

METERS_PER_DEGREE = 111_320

# What ElementRead needs: observation count + best observation with its image
_READ_OPTIONS = (
    selectinload(Element.observations),
    selectinload(Element.best_observation).selectinload(Observation.image),
)


def _for_read(stmt: Select) -> Select:
    return stmt.options(*_READ_OPTIONS)


def list_elements(
    db: Session,
    category: ElementCategory | None = None,
    status: ElementStatus | None = None,
) -> Sequence[Element]:
    """status=None -> every element except rejected ones."""
    stmt = _for_read(select(Element).order_by(Element.created_at))
    if category:
        stmt = stmt.where(Element.category == category)
    if status:
        stmt = stmt.where(Element.status == status)
    else:
        stmt = stmt.where(Element.status != ElementStatus.REJECTED)
    return db.scalars(stmt).all()


def get_element(db: Session, element_id: uuid.UUID) -> Element | None:
    return db.get(Element, element_id, options=_READ_OPTIONS)


def get_elements(db: Session, element_ids: Iterable[uuid.UUID]) -> Sequence[Element]:
    """Fresh copies from the DB (positions and timestamps are computed there)."""
    stmt = (
        _for_read(select(Element).where(Element.id.in_(list(element_ids))))
        .order_by(Element.created_at)
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).all()


def list_near(
    db: Session, points: Sequence[LatLon], margin_m: float
) -> Sequence[Element]:
    """Elements (any status) inside the bbox of the points grown by margin_m, with their
    observations and the images (cameras) those come from, which /dedup needs."""
    if not points:
        return []
    lats, lons = [p.lat for p in points], [p.lon for p in points]
    dlat = margin_m / METERS_PER_DEGREE
    dlon = dlat / max(math.cos(math.radians(max(abs(min(lats)), abs(max(lats))))), 0.01)
    envelope = func.ST_MakeEnvelope(  # xmin, ymin, xmax, ymax: lon first
        min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat, 4326
    )
    stmt = (
        select(Element)
        .where(func.ST_Intersects(Element.geom, envelope))
        .options(selectinload(Element.observations).selectinload(Observation.image))
    )
    return db.scalars(stmt).all()
