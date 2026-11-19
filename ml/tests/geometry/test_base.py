import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.config import GeometryConfig
from src.geometry.base import CameraFrame, DistanceEstimation, GeoLocation

from .helpers import make_frame, pano_frame


def test_geometry_config_exposes_default_camera_type():
    """CameraFrame.from_meta reads cfg.default_camera_type."""
    assert hasattr(GeometryConfig(), "default_camera_type")


@pytest.mark.parametrize(
    "kw",
    [
        dict(heading=361),
        dict(heading=-1),
        dict(lat=91),
        dict(lon=181),
        dict(image_width=0),
        dict(camera_height_m=0),
        dict(fov_deg=0),
        dict(fov_deg=180),  # perspective needs < 180
        dict(camera_type="fisheye"),
    ],
)
def test_invalid_frames_rejected(kw):
    with pytest.raises(ValidationError):
        make_frame(**kw)


def test_equirectangular_allows_360_fov():
    assert pano_frame().fov_deg == 360.0


def test_frame_is_frozen_and_forbids_extras():
    f = make_frame()
    with pytest.raises(ValidationError):
        f.heading = 10  # type: ignore[misc]
    with pytest.raises(ValidationError):
        CameraFrame(**{**f.model_dump(), "extra": 1})


def test_focal_px_perspective_only():
    assert make_frame().focal_px == pytest.approx(500)
    with pytest.raises(ValueError):
        pano_frame().focal_px


def test_bearing_perspective_and_pano():
    f = make_frame(heading=90)
    assert f.bearing_for_x(500) == pytest.approx(90)
    assert f.bearing_for_bbox((900, 0, 1000, 10)) == pytest.approx(
        90 + math.degrees(math.atan(450 / 500))
    )  # cx=950
    p = pano_frame(heading=0)
    assert p.bearing_for_x(1500) == pytest.approx(90)


# --- from_meta (uses a stub cfg so it doesn't depend on config fields) ---

CFG = SimpleNamespace(
    default_camera_type="perspective", default_fov_deg=75.0, default_camera_height_m=1.8
)


def meta(**kw):
    base = dict(
        lat=40.0, lon=-8.0, heading=10.0, image_width=100, image_height=50, cfg=CFG
    )
    return CameraFrame.from_meta(**{**base, **kw})


def test_from_meta_defaults():
    f = meta()
    assert (f.fov_deg, f.camera_height_m, f.camera_type) == (75.0, 1.8, "perspective")


def test_from_meta_explicit_values_win():
    f = meta(fov=100.0, camera_height_m=2.5)
    assert (f.fov_deg, f.camera_height_m) == (100.0, 2.5)


def test_from_meta_equirectangular_defaults_to_360():
    assert meta(camera_type="equirectangular").fov_deg == 360.0


def test_from_meta_normalises_heading():
    assert meta(heading=370.0).heading == pytest.approx(10.0)
    assert meta(heading=360.0).heading == 0.0


# --- output models --------------------------------------------------------


def test_distance_estimation_validation():
    DistanceEstimation(distance_m=1, uncertainty_m=0.1, method="size_prior")
    for kw in (dict(distance_m=0), dict(uncertainty_m=0), dict(method="lidar")):
        with pytest.raises(ValidationError):
            DistanceEstimation(
                **{**dict(distance_m=1, uncertainty_m=0.1, method="depth"), **kw}
            )


def test_geolocation_defaults_and_bearing_range():
    g = GeoLocation(bearing_deg=10)
    assert g.est_lat is None and g.uncertainty_m is None
    with pytest.raises(ValidationError):
        GeoLocation(bearing_deg=360)
