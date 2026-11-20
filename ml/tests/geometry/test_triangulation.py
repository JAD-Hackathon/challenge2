import math

import pytest
from pydantic import ValidationError

from src.geometry.triangulation import (
    RayObservation,
    max_pairwise_angle_deg,
    triangulate_rays,
)

from .helpers import LAT0, LON0, bearing_deg, offset, to_enu


def ray(cam_en, target_en, unc=3.0, bearing=None):
    lat, lon = offset(LAT0, LON0, *cam_en)
    b = bearing if bearing is not None else bearing_deg(cam_en, target_en)
    return RayObservation(
        camera_lat=lat, camera_lon=lon, bearing_deg=b, uncertainty_m=unc
    )


def solve(pt):
    return to_enu(LAT0, LON0, pt.lat, pt.lon)


A, B, TARGET = (-10, 0), (10, 0), (0, 20)


# --- angle helper ---------------------------------------------------------


@pytest.mark.parametrize(
    "bearings,expected",
    [
        ([0, 90], 90),
        ([0, 180], 0),
        ([350, 10], 20),
        ([0, 0], 0),
        ([10, 100, 40], 90),
        ([0], 0),
    ],
)
def test_max_pairwise_angle(bearings, expected):
    assert max_pairwise_angle_deg(bearings) == pytest.approx(expected)


# --- input models ---------------------------------------------------------


@pytest.mark.parametrize(
    "kw",
    [
        dict(bearing_deg=360),
        dict(bearing_deg=-1),
        dict(uncertainty_m=0),
        dict(camera_lat=95),
    ],
)
def test_ray_validation(kw):
    base = dict(camera_lat=40, camera_lon=-8, bearing_deg=10, uncertainty_m=3)
    with pytest.raises(ValidationError):
        RayObservation(**{**base, **kw})


# --- triangulation --------------------------------------------------------


def test_fewer_than_two_rays():
    assert triangulate_rays([]) is None
    assert triangulate_rays([ray(A, TARGET)]) is None


def test_parallel_rays_rejected():
    assert (
        triangulate_rays([ray(A, TARGET, bearing=0), ray(B, TARGET, bearing=2)]) is None
    )


def test_two_rays_recover_target():
    pt = triangulate_rays([ray(A, TARGET), ray(B, TARGET)])
    assert pt is not None
    e, n = solve(pt)
    assert (e, n) == (pytest.approx(0, abs=0.3), pytest.approx(20, abs=0.3))
    assert pt.mean_residual_m == pytest.approx(0, abs=1e-3)
    assert pt.max_ray_angle_deg == pytest.approx(53.13, abs=0.1)


def test_result_independent_of_ray_order():
    p1 = triangulate_rays([ray(A, TARGET), ray(B, TARGET)])
    p2 = triangulate_rays([ray(B, TARGET), ray(A, TARGET)])
    assert solve(p1) == (
        pytest.approx(solve(p2)[0], abs=0.05),
        pytest.approx(solve(p2)[1], abs=0.05),
    )


def test_target_behind_cameras_rejected():
    rays = [
        ray(A, TARGET, bearing=(bearing_deg(A, TARGET) + 180) % 360),
        ray(B, TARGET, bearing=(bearing_deg(B, TARGET) + 180) % 360),
    ]
    assert triangulate_rays(rays) is None


def test_beyond_max_distance_rejected():
    far = (0, 100)
    assert triangulate_rays([ray(A, far), ray(B, far)], max_distance_m=50) is None
    assert triangulate_rays([ray(A, far), ray(B, far)], max_distance_m=150) is not None


def test_inconsistent_rays_rejected_by_residual():
    rays = [ray(A, TARGET), ray(B, TARGET), ray((0, 0), (3, 20))]
    assert triangulate_rays(rays, max_residual_m=0.05) is None
    assert triangulate_rays(rays, max_residual_m=5.0) is not None


def test_more_certain_ray_pulls_solution_toward_itself():
    def dist_to_c_line(unc_c):
        pt = triangulate_rays(
            [ray(A, TARGET), ray(B, TARGET), ray((0, 0), (3, 20), unc=unc_c)],
            max_residual_m=10,
        )
        e, n = solve(pt)
        b = math.radians(bearing_deg((0, 0), (3, 20)))
        return abs(e * math.cos(b) - n * math.sin(b))

    assert dist_to_c_line(0.1) < dist_to_c_line(10.0)
    assert dist_to_c_line(0.1) < 0.2


def test_uncertainty_has_floor_and_grows_with_ray_noise():
    tight = triangulate_rays([ray(A, TARGET, unc=0.01), ray(B, TARGET, unc=0.01)])
    loose = triangulate_rays(
        [ray(A, TARGET, unc=30), ray(B, TARGET, unc=30)], max_residual_m=50
    )
    assert tight.uncertainty_m == pytest.approx(2.0)
    assert loose.uncertainty_m > tight.uncertainty_m


def test_wraparound_bearings():
    # target due north of both cameras' midpoint, bearings near 0/360
    t = (0, 100)
    pt = triangulate_rays(
        [ray((-5, 0), t), ray((5, 0), t)], min_angle_deg=1, max_distance_m=200
    )
    assert pt is not None
    assert solve(pt)[1] == pytest.approx(100, abs=1.0)
