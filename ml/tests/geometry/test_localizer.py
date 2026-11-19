import math

import numpy as np
import pytest

from src.config import DepthConfig, GeometryConfig
from src.geometry.base import DistanceEstimation, DistanceEstimator
from src.geometry.depth import DepthEstimator
from src.geometry.localizer import GeoLocalizer

from .helpers import make_frame, to_enu, LAT0, LON0

BOX = (480, 400, 520, 430)  # centre column 500 -> bearing == heading
LAMP = "light.street_lamp"  # size + ground -> both methods usable


class Stub(DistanceEstimator):
    def __init__(self, method, dist=None, sigma=1.0):
        self.method, self.dist, self.sigma, self.calls = method, dist, sigma, 0

    def estimate(self, bbox_xyxy, spec, frame):
        self.calls += 1
        if self.dist is None:
            return None
        return DistanceEstimation(
            distance_m=self.dist, uncertainty_m=self.sigma, method=self.method
        )


def loc(taxonomy, *stubs, **cfg):
    cfg = GeometryConfig(**{"methods": ["size_prior", "ground_plane"], **cfg})
    return GeoLocalizer(cfg, taxonomy, estimators=list(stubs)), cfg


def test_default_estimators_registered(taxonomy):
    g = GeoLocalizer(GeometryConfig(), taxonomy)
    assert set(g._estimators) == {"size_prior", "ground_plane", "depth"}


def test_no_estimates_returns_bearing_only(taxonomy):
    g, _ = loc(taxonomy, Stub("size_prior"), Stub("ground_plane"))
    r = g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame(heading=90))
    assert r.bearing_deg == pytest.approx(90)
    assert (r.est_lat, r.est_lon, r.est_distance_m, r.uncertainty_m, r.method) == (
        None,
    ) * 5


def test_single_estimate_passthrough_and_position(taxonomy):
    g, _ = loc(taxonomy, Stub("size_prior", 20.0, 1.0))
    r = g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame(heading=90))
    assert r.method == "size_prior" and r.est_distance_m == pytest.approx(20.0)
    e, n = to_enu(LAT0, LON0, r.est_lat, r.est_lon)
    assert e == pytest.approx(20.0, abs=0.1) and n == pytest.approx(
        0.0, abs=0.1
    )  # heading 90 = east


def test_position_follows_heading_north(taxonomy):
    g, _ = loc(taxonomy, Stub("size_prior", 30.0))
    r = g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame(heading=0))
    e, n = to_enu(LAT0, LON0, r.est_lat, r.est_lon)
    assert e == pytest.approx(0.0, abs=0.1) and n == pytest.approx(30.0, abs=0.1)


def test_total_uncertainty_formula(taxonomy):
    g, cfg = loc(taxonomy, Stub("size_prior", 20.0, 1.0))
    r = g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame())
    cross = 20.0 * math.tan(math.radians(cfg.bearing_sigma_deg))
    assert r.uncertainty_m == pytest.approx(math.hypot(1.0, cross, cfg.gps_sigma_m))


def test_inverse_variance_fusion(taxonomy):
    g, _ = loc(taxonomy, Stub("size_prior", 10.0, 1.0), Stub("ground_plane", 14.0, 2.0))
    r = g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame())
    assert r.method == "fused"
    assert r.est_distance_m == pytest.approx((10 / 1 + 14 / 4) / 1.25)  # 10.8


def test_fusion_sigma_smaller_than_inputs():
    d, s, m = GeoLocalizer._fuse_estimates(
        [
            DistanceEstimation(distance_m=10, uncertainty_m=1, method="size_prior"),
            DistanceEstimation(distance_m=14, uncertainty_m=2, method="ground_plane"),
        ]
    )
    assert s == pytest.approx(math.sqrt(1 / 1.25)) and s < 1.0 and m == "fused"


def test_first_fusion_stops_at_first_success(taxonomy):
    a, b = Stub("size_prior", 10.0), Stub("ground_plane", 14.0)
    g, _ = loc(taxonomy, a, b, fusion="first")
    r = g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame())
    assert r.method == "size_prior" and (a.calls, b.calls) == (1, 0)


def test_first_fusion_falls_through_failures(taxonomy):
    a, b = Stub("size_prior", None), Stub("ground_plane", 14.0)
    g, _ = loc(taxonomy, a, b, fusion="first")
    assert (
        g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame()).method
        == "ground_plane"
    )


def test_methods_not_applicable_to_class_are_not_called(taxonomy):
    size, ground = Stub("size_prior", 10.0), Stub("ground_plane", 12.0)
    g, _ = loc(taxonomy, size, ground)
    r = g.localize(
        class_name="waste.underground", bbox_xyxy=BOX, frame=make_frame()
    )  # no size prior
    assert size.calls == 0 and ground.calls == 1 and r.method == "ground_plane"
    size.calls = ground.calls = 0
    g.localize(class_name="sign.stop", bbox_xyxy=BOX, frame=make_frame())  # not ground
    assert size.calls == 1 and ground.calls == 0


def test_method_missing_from_registry_is_skipped(taxonomy):
    g, _ = loc(taxonomy, Stub("ground_plane", 12.0))  # no size_prior estimator
    assert (
        g.localize(class_name=LAMP, bbox_xyxy=BOX, frame=make_frame()).method
        == "ground_plane"
    )


def test_unknown_class_raises(taxonomy):
    g, _ = loc(taxonomy, Stub("size_prior", 10.0))
    with pytest.raises(KeyError):
        g.localize(class_name="sign.nope", bbox_xyxy=BOX, frame=make_frame())


def test_end_to_end_with_real_estimators(taxonomy):
    g = GeoLocalizer(GeometryConfig(), taxonomy)
    r = g.localize(
        class_name="sign.stop",
        bbox_xyxy=(485, 400, 515, 430),
        frame=make_frame(heading=90),
    )
    assert r.method == "size_prior" and r.est_distance_m == pytest.approx(10.0)
    e, n = to_enu(LAT0, LON0, r.est_lat, r.est_lon)
    assert e == pytest.approx(10.0, abs=0.1) and n == pytest.approx(0.0, abs=0.1)


# --- prepare_image --------------------------------------------------------


def test_prepare_image_forwards_to_depth_estimator(taxonomy):
    calls = []

    class P:
        def predict_depth_m(self, img):
            calls.append(1)
            return np.ones(img.shape[:2], np.float32)

    cfg = GeometryConfig(depth=DepthConfig(enabled=True))
    g = GeoLocalizer(cfg, taxonomy, estimators=[DepthEstimator(cfg, provider=P())])
    g.prepare_image(np.zeros((10, 10, 3), np.uint8))
    assert calls == [1]


def test_prepare_image_without_depth_estimator_is_noop(taxonomy):
    g, _ = loc(taxonomy, Stub("size_prior", 10.0))
    g.prepare_image(np.zeros((10, 10, 3), np.uint8))
