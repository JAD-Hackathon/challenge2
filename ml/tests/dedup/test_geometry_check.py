import pytest

from src.dedup.geometry_check import estimate_cluster_position, is_ray_consistent

from .common import ENU, bearing_deg, make_img, make_obs, to_enu

A_POS, B_POS, TARGET = (-10, 0), (10, 0), (0, 20)
IMGS = {"A": make_img("A", A_POS), "B": make_img("B", B_POS)}


def seen_from(cam_id, cam_pos, target=TARGET, est=None, **kw):
    return make_obs(
        f"{cam_id}:1", en=est or target, bearing=bearing_deg(cam_pos, target), **kw
    )


# is_ray_consistent


def test_consistent_when_rays_meet_in_front():
    assert (
        is_ray_consistent([seen_from("A", A_POS)], seen_from("B", B_POS), IMGS, 2.5)
        is True
    )


def test_inconsistent_when_rays_diverge_with_large_parallax():
    a = make_obs("A:1", en=TARGET, bearing=330.0)
    b = make_obs(
        "B:1", en=TARGET, bearing=30.0
    )  # intersection lies behind both cameras
    assert is_ray_consistent([a], b, IMGS, 2.5) is False


def test_inconsistent_when_intersection_too_far():
    imgs = {"A": make_img("A", (-40, 0)), "B": make_img("B", (40, 0))}
    far = (0, 100)
    a = make_obs("A:1", en=far, bearing=bearing_deg((-40, 0), far))
    b = make_obs("B:1", en=far, bearing=bearing_deg((40, 0), far))
    assert is_ray_consistent([a], b, imgs, 2.5) is False  # > 50 m, parallax ~44 deg


def test_small_parallax_is_not_held_against_merge():
    a = make_obs("A:1", en=TARGET, bearing=0.0)
    b = make_obs("B:1", en=TARGET, bearing=3.0)
    assert is_ray_consistent([a], b, IMGS, 2.5) is True


def test_fewer_than_two_rays_is_consistent():
    assert (
        is_ray_consistent(
            [make_obs("noprefix", en=TARGET)],
            make_obs("alsonone", en=TARGET),
            IMGS,
            2.5,
        )
        is True
    )


# estimate_cluster_position


def test_triangulation_preferred_over_noisy_estimates():
    noisy = (6, 26)
    obs = [seen_from("A", A_POS, est=noisy), seen_from("B", B_POS, est=noisy)]
    lat, lon = estimate_cluster_position(obs, IMGS, ENU)
    assert to_enu(lat, lon) == (pytest.approx(0, abs=0.3), pytest.approx(20, abs=0.3))


def test_fallback_inverse_variance_mean():
    obs = [make_obs("a", en=(0, 0), unc=1.0), make_obs("b", en=(10, 0), unc=2.0)]
    lat, lon = estimate_cluster_position(obs, {}, ENU)
    x, y = to_enu(lat, lon)
    assert x == pytest.approx(2.0, abs=0.05) and y == pytest.approx(
        0.0, abs=0.05
    )  # (0*1 + 10*0.25)/1.25


@pytest.mark.parametrize("unc", [None, 0.0])
def test_fallback_missing_or_zero_uncertainty_defaults_to_5(unc):
    obs = [make_obs("a", en=(0, 0), unc=unc), make_obs("b", en=(10, 0), unc=5.0)]
    x, _ = to_enu(*estimate_cluster_position(obs, {}, ENU))
    assert x == pytest.approx(5.0, abs=0.05)


def test_single_observation_returns_its_position_rounded():
    lat, lon = estimate_cluster_position([make_obs("a", en=(3, 4))], {}, ENU)
    assert lat == round(lat, 7) and lon == round(lon, 7)
    assert to_enu(lat, lon) == (pytest.approx(3, abs=0.05), pytest.approx(4, abs=0.05))


def test_falls_back_when_triangulation_fails():
    a = make_obs("A:1", en=(0, 0), bearing=0.0, unc=1.0)
    b = make_obs(
        "B:1", en=(2, 0), bearing=2.0, unc=1.0
    )  # nearly parallel -> triangulation rejects
    x, _ = to_enu(*estimate_cluster_position([a, b], IMGS, ENU))
    assert x == pytest.approx(1.0, abs=0.05)
