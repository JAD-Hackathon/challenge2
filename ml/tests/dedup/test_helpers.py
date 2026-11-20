import pytest

from src.dedup.utils.helpers import build_rays, extract_image_id, resolve_category

from .common import make_img, make_obs


@pytest.mark.parametrize(
    "oid,expected",
    [
        ("img1:abc", "img1"),
        ("img1:a:b", "img1"),
        ("abc", None),
        (":abc", None),
        (" :abc", None),
        (" img1 :x", "img1"),
    ],
)
def test_extract_image_id(oid, expected):
    assert extract_image_id(make_obs(oid)) == expected


def test_resolve_category_from_taxonomy(taxonomy):
    assert resolve_category("sign.stop", taxonomy) == "sign"
    assert resolve_category("light.street_lamp", taxonomy) == "light"


def test_resolve_category_prefix_fallback(taxonomy):
    assert resolve_category("waste.something_new", taxonomy) == "waste"


def test_resolve_category_unknown_raises(taxonomy):
    with pytest.raises(KeyError):
        resolve_category("bogus.thing", taxonomy)


IMGS = {"A": make_img("A", (5, 5))}


def test_build_rays_uses_camera_pose_and_bearing():
    [r] = build_rays([make_obs("A:1", bearing=45.0, unc=2.0)], IMGS)
    assert r.bearing_deg == 45.0 and r.uncertainty_m == 2.0
    assert (r.camera_lat, r.camera_lon) == (IMGS["A"].lat, IMGS["A"].lon)


def test_build_rays_default_uncertainty():
    [r] = build_rays([make_obs("A:1", bearing=10.0, unc=None)], IMGS)
    assert r.uncertainty_m == 3.0


@pytest.mark.parametrize(
    "obs",
    [
        make_obs("noprefix", bearing=10.0),  # no image id embedded
        make_obs("Z:1", bearing=10.0),  # unknown image
        make_obs("A:1", bearing=None),  # no bearing
    ],
)
def test_build_rays_skips_unusable(obs):
    assert build_rays([obs], IMGS) == []


def test_bearing_that_rounds_to_360_does_not_crash():
    """The pipeline rounds bearings to 2 dp, so 359.996 arrives as 360.0."""
    [r] = build_rays([make_obs("A:1", bearing=360.0)], IMGS)
    assert r.bearing_deg == pytest.approx(0.0)
