import math

import pytest

from src.config import GeometryConfig
from src.geometry.ground_plane import GroundPlaneEstimator

from .helpers import make_frame, make_spec, pano_frame

CFG = GeometryConfig()
est = GroundPlaneEstimator(CFG)
GROUND = make_spec("light.street_lamp", ground=True, dim="height", m=6.0)


def expected_sigma(cam_h, depression_deg):
    th = math.radians(depression_deg)
    return max(
        0.1,
        math.hypot(
            CFG.camera_height_sigma_m / math.tan(th),
            cam_h * math.radians(CFG.pitch_sigma_deg) / math.sin(th) ** 2,
        ),
    )


def test_normal_box_gets_an_estimate():
    r = est.estimate((480, 500, 520, 750), GROUND, make_frame())
    assert r is not None and r.method == "ground_plane"
    assert r.distance_m == pytest.approx(3.0)  # 1.5 / tan(atan(250/500))


def test_uncertainty_follows_error_propagation():
    r = est.estimate((480, 500, 520, 750), GROUND, make_frame())
    assert r.uncertainty_m == pytest.approx(
        expected_sigma(1.5, math.degrees(math.atan(0.5))), rel=1e-6
    )


def test_uncertainty_grows_with_distance():
    near = est.estimate((480, 500, 520, 750), GROUND, make_frame())  # 3.0 m
    far = est.estimate((480, 400, 520, 600), GROUND, make_frame())  # 7.5 m
    assert far.distance_m > near.distance_m
    assert far.uncertainty_m > near.uncertainty_m


def test_uncertainty_depends_on_camera_height_sigma():
    big = GroundPlaneEstimator(GeometryConfig(camera_height_sigma_m=1.0))
    small = GroundPlaneEstimator(GeometryConfig(camera_height_sigma_m=0.1))
    box = (480, 500, 520, 750)
    assert (
        big.estimate(box, GROUND, make_frame()).uncertainty_m
        > small.estimate(box, GROUND, make_frame()).uncertainty_m
    )


def test_non_ground_class_returns_none():
    assert (
        est.estimate((480, 500, 520, 750), make_spec(dim="width"), make_frame()) is None
    )


def test_base_touching_bottom_edge_rejected():
    assert est.estimate((480, 800, 520, 999), GROUND, make_frame()) is None


@pytest.mark.parametrize("y1", [500, 450, 503])  # horizon, above, <1deg below
def test_base_at_or_above_horizon_rejected(y1):
    assert est.estimate((480, 100, 520, y1), GROUND, make_frame()) is None


def test_beyond_ground_plane_range_rejected():
    # base ~2.3deg below horizon -> ~37 m > 15 m limit
    assert est.estimate((480, 300, 520, 520), GROUND, make_frame()) is None


@pytest.mark.parametrize(
    "box", [(480, 740, 520, 750), (495, 500, 505, 750)]
)  # too short / too narrow
def test_tiny_box_rejected(box):
    assert est.estimate(box, GROUND, make_frame()) is None


def test_camera_height_scales_distance():
    r = est.estimate((480, 500, 520, 750), GROUND, make_frame(camera_height_m=3.0))
    assert r.distance_m == pytest.approx(6.0)


def test_equirectangular():
    r = est.estimate((990, 500, 1010, 750), GROUND, pano_frame())  # 45deg depression
    assert r.distance_m == pytest.approx(1.5)
    assert r.uncertainty_m == pytest.approx(expected_sigma(1.5, 45.0), rel=1e-6)
