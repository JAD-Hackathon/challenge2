import math

import pytest

from src.config import GeometryConfig
from src.geometry.size_prior import SizePriorEstimator

from .helpers import make_frame, make_spec, pano_frame

est = SizePriorEstimator(GeometryConfig())  # min_box 12 px, max distance 40 m
W = make_spec(dim="width", m=0.6, tol=0.15)
H = make_spec("light.street_lamp", ground=True, dim="height", m=6.0, tol=0.4)


def test_perspective_width():
    r = est.estimate((485, 400, 515, 430), W, make_frame())  # 30 px wide, f=500
    assert r.method == "size_prior"
    assert r.distance_m == pytest.approx(500 * 0.6 / 30)  # 10 m
    assert r.uncertainty_m == pytest.approx(10 * 0.15)


def test_perspective_height():
    r = est.estimate((480, 100, 520, 400), H, make_frame())  # 300 px tall
    assert r.distance_m == pytest.approx(500 * 6.0 / 300)
    assert r.uncertainty_m == pytest.approx(10.0 * 0.4)


def test_equirect_width():
    r = est.estimate((990, 400, 1010, 430), W, pano_frame())  # 20px of 2000 @360deg
    ang = math.radians(20 / 2000 * 360)
    assert r.distance_m == pytest.approx(0.6 / (2 * math.tan(ang / 2)))


def test_equirect_height():
    r = est.estimate((990, 300, 1010, 600), H, pano_frame())  # 300px of 1000 @180deg
    ang = math.radians(300 / 1000 * 180)
    assert r.distance_m == pytest.approx(6.0 / (2 * math.tan(ang / 2)))


def test_no_size_prior_returns_none():
    assert (
        est.estimate(
            (485, 400, 515, 430),
            make_spec("waste.underground", ground=True),
            make_frame(),
        )
        is None
    )


def test_width_dim_rejects_horizontal_edge_truncation():
    assert est.estimate((0, 400, 30, 430), W, make_frame()) is None
    assert est.estimate((970, 400, 1000, 430), W, make_frame()) is None


def test_height_dim_rejects_vertical_edge_truncation():
    assert est.estimate((480, 0, 520, 300), H, make_frame()) is None
    assert est.estimate((480, 700, 520, 1000), H, make_frame()) is None


def test_width_dim_ignores_vertical_edges_and_height_dim_ignores_horizontal():
    assert est.estimate((485, 970, 515, 1000), W, make_frame()) is not None
    assert est.estimate((0, 100, 40, 400), H, make_frame()) is not None


@pytest.mark.parametrize(
    "box", [(485, 400, 490, 430), (500, 400, 500, 430), (515, 400, 485, 430)]
)
def test_tiny_or_degenerate_box_rejected(box):
    assert est.estimate(box, W, make_frame()) is None


def test_beyond_max_distance_rejected():
    far = make_spec(dim="width", m=3.0)
    assert (
        est.estimate((494, 400, 506, 430), far, make_frame()) is None
    )  # 500*3/12 = 125 m


def test_uncertainty_floor():
    tiny_tol = make_spec(dim="width", m=0.6, tol=0.001)
    assert est.estimate(
        (485, 400, 515, 430), tiny_tol, make_frame()
    ).uncertainty_m == pytest.approx(0.1)


def test_farther_object_has_smaller_box_and_larger_distance():
    near = est.estimate((480, 400, 520, 430), W, make_frame())
    far = est.estimate((490, 400, 510, 430), W, make_frame())
    assert far.distance_m > near.distance_m
