import math

import pytest

from src.geometry.utils import camera as cam


def test_focal_length():
    assert cam.focal_length_px(1000, 90) == pytest.approx(500)


@pytest.mark.parametrize(
    "w,fov", [(0, 90), (-5, 90), (1000, 0), (1000, 180), (1000, 200)]
)
def test_focal_length_invalid(w, fov):
    with pytest.raises(ValueError):
        cam.focal_length_px(w, fov)


@pytest.mark.parametrize(
    "heading,cx,expected",
    [
        (90, 500, 90),  # centre column -> heading
        (90, 1000, 135),  # right edge, 90deg FOV -> +45
        (90, 0, 45),  # left edge -> -45
        (350, 1000, 35),  # wraps past north
        (10, 0, 325),  # wraps below north
    ],
)
def test_perspective_bearing(heading, cx, expected):
    assert cam.perspective_bearing(heading, cx, 1000, 90) == pytest.approx(expected)


def test_perspective_elevation_sign_and_value():
    assert cam.perspective_elevation_deg(500, 1000, 1000, 90) == pytest.approx(0)
    assert cam.perspective_elevation_deg(0, 1000, 500, 90) == pytest.approx(
        math.degrees(math.atan(250 / 500))
    )
    assert cam.perspective_elevation_deg(750, 1000, 1000, 90) < 0  # below horizon


def test_perspective_elevation_invalid_height():
    with pytest.raises(ValueError):
        cam.perspective_elevation_deg(10, 1000, 0, 90)


def test_perspective_ground_distance():
    # f=500, base 250px below centre -> tan(dep)=0.5 -> d = 1.5/0.5
    assert cam.perspective_ground_distance(1.5, 750, 1000, 1000, 90) == pytest.approx(
        3.0
    )


@pytest.mark.parametrize("cy", [500, 400, 504])  # horizon, above, <1deg below
def test_perspective_ground_distance_none_near_or_above_horizon(cy):
    assert cam.perspective_ground_distance(1.5, cy, 1000, 1000, 90) is None


@pytest.mark.parametrize("cx,expected", [(1000, 0), (1500, 90), (500, 270), (0, 180)])
def test_pano_bearing(cx, expected):
    assert cam.pano_bearing(0, cx, 2000) == pytest.approx(expected)


def test_pano_bearing_partial_fov():
    assert cam.pano_bearing(100, 3000 / 4, 1000, hfov=180) == pytest.approx(
        145
    )  # +0.25*180


@pytest.mark.parametrize("cy,expected", [(0, 90), (500, 0), (1000, -90), (250, 45)])
def test_pano_elevation(cy, expected):
    assert cam.pano_elevation_deg(cy, 1000) == pytest.approx(expected)


def test_pano_ground_distance():
    assert cam.pano_ground_distance(1.5, 750, 1000) == pytest.approx(
        1.5
    )  # 45deg depression
    assert cam.pano_ground_distance(1.5, 500, 1000) is None
