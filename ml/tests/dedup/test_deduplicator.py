import re

import pytest

from ml.src.dedup.deduplicator import AssetDeduplicator
from src.service.schemas import DedupRequest

from .common import bearing_deg, make_cfg, make_el, make_img, make_obs, to_enu


def run(obs=(), images=(), existing=(), taxonomy=None, **cfg):
    return AssetDeduplicator(make_cfg(**cfg), taxonomy).deduplicate(
        DedupRequest(
            observations=list(obs),
            images=list(images),
            existing_elements=list(existing),
        )
    )


@pytest.fixture(autouse=True)
def _tax(taxonomy, monkeypatch):
    import ml.src.dedup.deduplicator as mod

    monkeypatch.setattr(mod, "get_taxonomy", lambda: taxonomy)


def test_empty_request():
    r = run()
    assert (r.elements, r.unassigned_observation_ids, r.removed_element_ids) == (
        [],
        [],
        [],
    )


def test_observation_without_position_is_unassigned():
    r = run([make_obs("a:1", None), make_obs("b:1", (0, 0))])
    assert r.unassigned_observation_ids == ["a:1"]
    assert [e.observation_ids for e in r.elements] == [["b:1"]]


def test_nearby_views_become_one_element():
    r = run([make_obs("a:1", (0, 0), score=0.6), make_obs("b:1", (1, 0), score=0.9)])
    [el] = r.elements
    assert sorted(el.observation_ids) == ["a:1", "b:1"]
    assert (
        el.best_observation_id == "b:1"
        and el.status == "auto"
        and el.type == "sign.stop"
    )
    assert re.fullmatch(r"el_[0-9a-f]{12}", el.element_id)
    assert el.confidence >= 0.9 and el.confidence <= 0.99


def test_far_observations_stay_separate():
    assert len(run([make_obs("a:1", (0, 0)), make_obs("b:1", (50, 0))]).elements) == 2


def test_different_types_never_merge():
    r = run(
        [
            make_obs("a:1", (0, 0), type="sign.stop"),
            make_obs("b:1", (0.5, 0), type="sign.other"),
        ]
    )
    assert sorted(e.type for e in r.elements) == ["sign.other", "sign.stop"]


@pytest.mark.parametrize(
    "type_,dist,expected",
    [
        ("light.street_lamp", 3.5, 1),
        ("sign.stop", 3.5, 2),
        ("waste.general", 4.5, 1),
        ("waste.general", 5.5, 2),
    ],
)
def test_radius_depends_on_category(type_, dist, expected):
    r = run(
        [make_obs("a:1", (0, 0), type=type_), make_obs("b:1", (dist, 0), type=type_)]
    )
    assert len(r.elements) == expected


def test_same_image_detections_not_merged():
    assert (
        len(run([make_obs("img:1", (0, 0)), make_obs("img:2", (1, 0))]).elements) == 2
    )


def test_every_observation_ends_up_somewhere():
    obs = [make_obs(f"i{k}:1", (k * 0.7, 0)) for k in range(6)] + [
        make_obs("n:1", None)
    ]
    r = run(obs)
    placed = [
        o for e in r.elements for o in e.observation_ids
    ] + r.unassigned_observation_ids
    assert sorted(placed) == sorted(o.observation_id for o in obs)


def test_ray_check_enabled_merges_consistent_views():
    t, a, b = (0, 20), (-10, 0), (10, 0)
    imgs = [make_img("A", a), make_img("B", b)]
    obs = [
        make_obs("A:1", (0.3, 20), bearing=bearing_deg(a, t)),
        make_obs("B:1", (-0.3, 20), bearing=bearing_deg(b, t)),
    ]
    [el] = run(obs, imgs, use_ray_check=True).elements
    assert to_enu(el.lat, el.lon) == (
        pytest.approx(0, abs=0.5),
        pytest.approx(20, abs=0.5),
    )


# locked elements


@pytest.mark.parametrize("status", ["verified", "corrected"])
def test_locked_element_not_moved_but_gains_observation(status):
    locked = make_el("L1", (0, 0), status=status)
    r = run([make_obs("a:1", (1, 0))], existing=[locked])
    [el] = r.elements
    assert (el.element_id, el.lat, el.lon, el.status) == (
        "L1",
        locked.lat,
        locked.lon,
        status,
    )
    assert el.observation_ids == ["old", "a:1"]


def test_observation_far_from_locked_makes_new_element_and_keeps_locked():
    locked = make_el("L1", (0, 0), status="verified")
    r = run([make_obs("a:1", (30, 0))], existing=[locked])
    assert {e.element_id for e in r.elements} >= {"L1"} and len(r.elements) == 2
    assert next(e for e in r.elements if e.element_id == "L1").observation_ids == [
        "old"
    ]


def test_locked_of_other_type_not_matched():
    r = run(
        [make_obs("a:1", (0.5, 0), type="sign.other")],
        existing=[make_el("L1", (0, 0), status="verified")],
    )
    assert len(r.elements) == 2


def test_nearest_locked_element_wins():
    r = run(
        [make_obs("a:1", (3.4, 0), type="light.street_lamp")],
        existing=[
            make_el("L1", (0, 0), "light.street_lamp", "verified"),
            make_el("L2", (4, 0), "light.street_lamp", "verified"),
        ],
    )
    by_id = {e.element_id: e for e in r.elements}
    assert by_id["L2"].observation_ids == ["old", "a:1"] and by_id[
        "L1"
    ].observation_ids == ["old"]


def test_locked_input_not_mutated():
    locked = make_el("L1", (0, 0), status="verified")
    run([make_obs("a:1", (1, 0))], existing=[locked])
    assert locked.observation_ids == ["old"]


def test_observation_not_attached_twice():
    locked = make_el("L1", (0, 0), status="verified", obs_ids=("a:1",))
    [el] = run([make_obs("a:1", (0.5, 0))], existing=[locked]).elements
    assert el.observation_ids == ["a:1"]


def test_rejected_elements_are_preserved():
    r = run(
        [make_obs("a:1", (50, 0))], existing=[make_el("R1", (0, 0), status="rejected")]
    )
    assert "R1" in {e.element_id for e in r.elements}


# auto elements


def test_auto_element_id_reused_when_cluster_lands_nearby():
    auto = make_el("el_old", (0, 0))
    r = run([make_obs("a:1", (1, 0))], existing=[auto])
    assert [e.element_id for e in r.elements] == [
        "el_old"
    ] and r.removed_element_ids == []


def test_each_auto_element_reused_at_most_once():
    r = run(
        [make_obs("a:1", (0, 0)), make_obs("b:1", (3.5, 0))],
        existing=[make_el("el_old", (1.7, 0))],
    )
    ids = [e.element_id for e in r.elements]
    assert len(ids) == len(set(ids)) == 2 and "el_old" in ids


def test_unmatched_auto_elements_reported_removed():
    r = run([make_obs("a:1", (0, 0))], existing=[make_el("el_far", (100, 0))])
    assert r.removed_element_ids == ["el_far"] and "el_far" not in {
        e.element_id for e in r.elements
    }


def test_no_new_observations_keeps_everything():
    existing = [make_el("A1", (0, 0)), make_el("V1", (20, 0), status="verified")]
    r = run(existing=existing)
    assert {e.element_id for e in r.elements} == {
        "A1",
        "V1",
    } and r.removed_element_ids == []
