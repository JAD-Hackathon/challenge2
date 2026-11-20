import math

from src.config import DedupConfig
from src.geometry.utils.geo import LocalENU
from src.service.schemas import CameraMeta, Element, Observation

LAT0, LON0 = 40.6412, -8.6538
_A, _E2 = 6378137.0, 0.00669437999014


def _radii(lat):
    s = math.sin(math.radians(lat))
    w = 1 - _E2 * s * s
    return _A * (1 - _E2) / w**1.5, _A / math.sqrt(w)


def offset(east, north, lat=LAT0, lon=LON0):
    m, n = _radii(lat)
    return lat + math.degrees(north / m), lon + math.degrees(
        east / (n * math.cos(math.radians(lat)))
    )


def to_enu(lat, lon, lat0=LAT0, lon0=LON0):
    m, n = _radii(lat0)
    return (
        math.radians(lon - lon0) * n * math.cos(math.radians(lat0)),
        math.radians(lat - lat0) * m,
    )


def bearing_deg(frm, to):
    return math.degrees(math.atan2(to[0] - frm[0], to[1] - frm[1])) % 360.0


ENU = LocalENU(LAT0, LON0)


def make_img(image_id, en=(0, 0), heading=0.0) -> CameraMeta:
    lat, lon = offset(*en)
    return CameraMeta(image_id=image_id, lat=lat, lon=lon, heading=heading)


def make_obs(
    oid, en=None, type="sign.stop", score=0.9, unc=3.0, bearing=None
) -> Observation:
    lat, lon = offset(*en) if en is not None else (None, None)
    return Observation(
        observation_id=oid,
        type=type,
        score=score,
        bbox_xyxy=[0, 0, 10, 10],
        bearing_deg=bearing,
        est_lat=lat,
        est_lon=lon,
        uncertainty_m=unc,
    )


def make_el(eid, en, type="sign.stop", status="auto", obs_ids=("old",)) -> Element:
    lat, lon = offset(*en)
    return Element(
        element_id=eid,
        type=type,
        lat=lat,
        lon=lon,
        confidence=0.9,
        observation_ids=list(obs_ids),
        best_observation_id=obs_ids[0],
        status=status,
    )


def make_cfg(**kw) -> DedupConfig:
    return DedupConfig(
        **{
            "radius_m": {"sign": 2.5, "light": 4.0, "waste": 5.0},
            "use_ray_check": False,
            **kw,
        }
    )
