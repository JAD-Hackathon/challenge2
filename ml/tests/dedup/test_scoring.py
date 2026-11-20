import itertools

import pytest

from src.dedup.scoring import fuse_confidence, select_best_observation

from .common import make_obs


def o(score, unc=3.0, oid="x"):
    return make_obs(oid, score=score, unc=unc)


# select_best_observation


def test_best_is_highest_score():
    assert (
        select_best_observation(
            [o(0.5, oid="a"), o(0.9, oid="b"), o(0.7, oid="c")]
        ).observation_id
        == "b"
    )


def test_tie_broken_by_lowest_uncertainty():
    assert (
        select_best_observation([o(0.9, 5.0, "a"), o(0.9, 1.0, "b")]).observation_id
        == "b"
    )


def test_missing_uncertainty_loses_ties():
    assert (
        select_best_observation([o(0.9, None, "a"), o(0.9, 50.0, "b")]).observation_id
        == "b"
    )


def test_best_of_one_and_empty():
    assert select_best_observation([o(0.2, oid="a")]).observation_id == "a"
    with pytest.raises(ValueError):
        select_best_observation([])


# fuse_confidence


def test_empty_is_zero():
    assert fuse_confidence([], 0.99) == 0.0


def test_single_is_score_capped():
    assert fuse_confidence([o(0.7)], 0.99) == 0.7
    assert fuse_confidence([o(1.0)], 0.99) == 0.99


def test_never_below_best_score():
    assert fuse_confidence([o(0.9), o(0.2)], 0.99) >= 0.9


def test_agreeing_weak_views_boost_confidence():
    assert fuse_confidence([o(0.5)] * 4, 0.99) == pytest.approx(0.6836)  # 1 - 0.75**4


def test_capped_by_max_confidence():
    assert fuse_confidence([o(0.99)] * 5, 0.95) == 0.95


def test_monotonic_when_adding_views():
    scores = [0.4, 0.4, 0.4, 0.4]
    vals = [fuse_confidence([o(s) for s in scores[:k]], 0.99) for k in range(1, 5)]
    assert vals == sorted(vals)


def test_order_independent_and_in_range():
    base = [0.3, 0.8, 0.5]
    vals = {
        fuse_confidence([o(s) for s in p], 0.99) for p in itertools.permutations(base)
    }
    assert len(vals) == 1 and 0.0 <= vals.pop() <= 1.0


def test_rounded_to_four_decimals():
    v = fuse_confidence([o(1 / 3), o(1 / 7)], 0.99)
    assert v == round(v, 4)
