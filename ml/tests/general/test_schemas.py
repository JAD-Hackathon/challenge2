"""camera_type handling: lenient schema + normalisation/fallback in CameraFrame."""

import logging
from types import SimpleNamespace

import pytest

from src.geometry.base import CameraFrame
from src.service.schemas import CameraMeta


def cfg(default_type="perspective"):
    return SimpleNamespace(
        default_camera_type=default_type,
        default_fov_deg=75.0,
        default_camera_height_m=1.8,
    )


def frame(camera_type=None, default_type="perspective", **kw):
    return CameraFrame.from_meta(
        lat=40.0,
        lon=-8.0,
        heading=10.0,
        image_width=100,
        image_height=50,
        cfg=cfg(default_type),
        camera_type=camera_type,
        **kw,
    )


# schema is lenient (replaces test_camera_type_validated_at_the_boundary)


@pytest.mark.parametrize(
    "value", ["perspective", "equirectangular", "panorama", "fisheye", ""]
)
def test_schema_accepts_any_camera_type_string(value):
    assert (
        CameraMeta(image_id="a", lat=0, lon=0, heading=0, camera_type=value).camera_type
        == value
    )


# normalize_camera_type


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("equirectangular", "equirectangular"),
        ("Panorama", "equirectangular"),
        ("  SPHERICAL ", "equirectangular"),
        ("360", "equirectangular"),
        ("perspective", "perspective"),
        ("Pinhole", "perspective"),
        ("flat", "perspective"),
    ],
)
def test_known_aliases(raw, expected):
    assert CameraFrame.normalize_camera_type(raw) == expected


def test_none_passes_through_silently(caplog):
    with caplog.at_level(logging.WARNING):
        assert CameraFrame.normalize_camera_type(None) is None
    assert caplog.text == ""


@pytest.mark.parametrize("raw", ["fisheye", "", "cylindrical"])
def test_unknown_returns_none_and_warns(raw, caplog):
    with caplog.at_level(logging.WARNING):
        assert CameraFrame.normalize_camera_type(raw) is None
    assert "Unknown camera_type" in caplog.text


# from_meta fallback


def test_alias_resolved_with_matching_default_fov():
    f = frame("panorama")
    assert (f.camera_type, f.fov_deg) == ("equirectangular", 360.0)


def test_unknown_type_falls_back_to_config_default_perspective():
    f = frame("fisheye")
    assert (f.camera_type, f.fov_deg) == ("perspective", 75.0)


def test_unknown_type_falls_back_to_config_default_equirectangular():
    f = frame("fisheye", default_type="equirectangular")
    assert (f.camera_type, f.fov_deg) == ("equirectangular", 360.0)


def test_none_uses_config_default():
    assert frame(None).camera_type == "perspective"


def test_explicit_fov_kept_with_alias():
    assert frame("pinhole", fov=60.0).fov_deg == 60.0


def test_unknown_type_does_not_raise():
    frame("totally-unknown")
