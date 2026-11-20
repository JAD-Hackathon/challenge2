from src.dedup.cluster import cluster

from .common import ENU, bearing_deg, make_img, make_obs

A_POS, B_POS, TARGET = (-10, 0), (10, 0), (0, 20)
IMGS = {"A": make_img("A", A_POS), "B": make_img("B", B_POS)}


def run(obs, radius=2.5, imgs=None, ray=False):
    return cluster(obs, radius, ENU, imgs or {}, ray)


def sizes(clusters):
    return sorted(len(c) for c in clusters)


def test_empty_and_single():
    assert run([]) == []
    o = make_obs("a", (0, 0))
    assert run([o]) == [[o]]


def test_close_merge_far_split():
    assert sizes(run([make_obs("a", (0, 0)), make_obs("b", (1, 0))])) == [2]
    assert sizes(run([make_obs("a", (0, 0)), make_obs("b", (10, 0))])) == [1, 1]


def test_radius_boundary():
    assert sizes(run([make_obs("a", (0, 0)), make_obs("b", (2.4, 0))])) == [2]
    assert sizes(run([make_obs("a", (0, 0)), make_obs("b", (2.6, 0))])) == [1, 1]


def test_complete_linkage_does_not_chain():
    chain = [make_obs("a", (0, 0)), make_obs("b", (2, 0)), make_obs("c", (4, 0))]
    assert len(run(chain)) == 2


def test_same_image_never_shares_a_cluster():
    assert sizes(run([make_obs("img:a", (0, 0)), make_obs("img:b", (1, 0))])) == [1, 1]


def test_different_images_can_share():
    assert sizes(run([make_obs("i1:a", (0, 0)), make_obs("i2:a", (1, 0))])) == [2]


def test_every_observation_assigned_exactly_once():
    obs = [make_obs(f"i{k}:a", (k * 0.5, 0)) for k in range(10)] + [
        make_obs("far:a", (100, 100))
    ]
    flat = [o.observation_id for c in run(obs) for o in c]
    assert sorted(flat) == sorted(o.observation_id for o in obs)


def test_highest_score_leads_its_cluster():
    clusters = run([make_obs("a", (0, 0), score=0.5), make_obs("b", (1, 0), score=0.9)])
    assert clusters[0][0].score == 0.9


# ray check


def test_ray_check_merges_geometrically_consistent_views():
    a = make_obs("A:1", (0.3, 20), bearing=bearing_deg(A_POS, TARGET))
    b = make_obs("B:1", (-0.3, 20), bearing=bearing_deg(B_POS, TARGET))
    assert sizes(run([a, b], imgs=IMGS, ray=True)) == [2]


def test_ray_check_splits_geometrically_inconsistent_views():
    a = make_obs("A:1", (0.3, 20), bearing=330.0)
    b = make_obs("B:1", (-0.3, 20), bearing=30.0)  # rays diverge
    assert sizes(run([a, b], imgs=IMGS, ray=True)) == [1, 1]


def test_ray_check_without_pose_info_falls_back_to_distance_only():
    assert sizes(run([make_obs("x1", (0, 0)), make_obs("x2", (1, 0))], ray=True)) == [2]
