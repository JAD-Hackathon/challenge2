import pytest

from src.geometry.utils.geo import LocalENU, geodesic_distance_m, project_point

from .helpers import LAT0, LON0, offset, to_enu


@pytest.mark.parametrize(
    "bearing,expected_en",
    [
        (0, (0, 100)),
        (90, (100, 0)),
        (180, (0, -100)),
        (270, (-100, 0)),
    ],
)
def test_project_point_cardinal_directions(bearing, expected_en):
    lat, lon = project_point(LAT0, LON0, bearing, 100.0)
    e, n = to_enu(LAT0, LON0, lat, lon)
    assert e == pytest.approx(expected_en[0], abs=0.1)
    assert n == pytest.approx(expected_en[1], abs=0.1)


def test_project_point_zero_distance_returns_origin():
    assert project_point(LAT0, LON0, 45, 0) == (LAT0, LON0)


def test_project_point_returns_floats_in_lat_lon_order():
    lat, lon = project_point(LAT0, LON0, 45, 50)
    assert abs(lat - LAT0) < 0.01 and abs(lon - LON0) < 0.01


def test_geodesic_distance_known_offsets():
    for east, north in [(100, 0), (0, 100), (60, 80)]:
        lat, lon = offset(LAT0, LON0, east, north)
        assert geodesic_distance_m(LAT0, LON0, lat, lon) == pytest.approx(
            (east**2 + north**2) ** 0.5, abs=0.1
        )


def test_geodesic_distance_zero_and_symmetric():
    lat, lon = offset(LAT0, LON0, 30, 40)
    assert geodesic_distance_m(LAT0, LON0, LAT0, LON0) == pytest.approx(0)
    assert geodesic_distance_m(LAT0, LON0, lat, lon) == pytest.approx(
        geodesic_distance_m(lat, lon, LAT0, LON0)
    )


def test_project_then_measure_roundtrip():
    lat, lon = project_point(LAT0, LON0, 123.0, 250.0)
    assert geodesic_distance_m(LAT0, LON0, lat, lon) == pytest.approx(250.0, abs=0.01)


# --- LocalENU -----------------------------------------------------------


def test_enu_origin_maps_to_zero():
    x, y = LocalENU(LAT0, LON0).to_xy(LAT0, LON0)
    assert (x, y) == (pytest.approx(0, abs=1e-3), pytest.approx(0, abs=1e-3))


@pytest.mark.parametrize("east,north", [(100, 0), (0, 100), (-60, 80)])
def test_enu_axes_are_east_north_metres(east, north):
    lat, lon = offset(LAT0, LON0, east, north)
    x, y = LocalENU(LAT0, LON0).to_xy(lat, lon)
    assert x == pytest.approx(east, abs=0.1)
    assert y == pytest.approx(north, abs=0.1)


def test_enu_to_latlon_order_and_origin():
    lat, lon = LocalENU(LAT0, LON0).to_latlon(0, 0)
    assert (lat, lon) == (pytest.approx(LAT0, abs=1e-8), pytest.approx(LON0, abs=1e-8))


def test_enu_roundtrip():
    enu = LocalENU(LAT0, LON0)
    lat, lon = offset(LAT0, LON0, 321.0, -123.0)
    assert enu.to_latlon(*enu.to_xy(lat, lon)) == (
        pytest.approx(lat, abs=1e-8),
        pytest.approx(lon, abs=1e-8),
    )


def test_enu_transformers_cached():
    assert LocalENU(LAT0, LON0).to_local is LocalENU(LAT0, LON0).to_local
