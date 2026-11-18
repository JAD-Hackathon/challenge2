import pytest

from .conftest import make_det


def labels(dets):
    return [d.label for d in dets]


def test_no_matching_category_returns_copy_without_loading(stub, image):
    clf = stub([], category="sign")
    dets = [make_det("waste.general"), make_det("light.street_lamp")]
    out = clf.classify(image, dets)
    assert out == dets and out is not dets
    assert clf.loads == 0 and clf.seen == []


def test_empty_detections(stub, image):
    assert stub([]).classify(image, []) == []


def test_only_target_category_relabelled_order_preserved(stub, image):
    clf = stub([("sign.stop", 0.9), ("sign.yield", 0.8)])
    dets = [make_det("sign.other"), make_det("waste.general"), make_det("sign.other")]
    assert labels(clf.classify(image, dets)) == [
        "sign.stop",
        "waste.general",
        "sign.yield",
    ]


def test_inputs_not_mutated(stub, image):
    dets = [make_det("sign.other")]
    stub([("sign.stop", 0.9)]).classify(image, dets)
    assert labels(dets) == ["sign.other"]


def test_other_fields_preserved(stub, image):
    [out] = stub([("sign.stop", 0.9)]).classify(
        image, [make_det("sign.other", (1, 2, 30, 40), 0.77)]
    )
    assert out.bbox_xyxy == (1, 2, 30, 40) and out.score == 0.77


def test_below_threshold_keeps_label(stub, image):
    [out] = stub([("sign.stop", 0.59)], conf_threshold=0.6).classify(
        image, [make_det("sign.other")]
    )
    assert out.label == "sign.other"


def test_threshold_is_inclusive(stub, image):
    [out] = stub([("sign.stop", 0.6)], conf_threshold=0.6).classify(
        image, [make_det("sign.other")]
    )
    assert out.label == "sign.stop"


def test_unknown_label_ignored(stub, image):
    [out] = stub([("sign.banana", 0.99)]).classify(image, [make_det("sign.other")])
    assert out.label == "sign.other"


def test_prediction_from_other_category_ignored(stub, image):
    """A sign classifier must never turn a sign into a waste container."""
    [out] = stub([("waste.general", 0.99)], category="sign").classify(
        image, [make_det("sign.other")]
    )
    assert out.label == "sign.other"


def test_prefix_match_is_exact_category(stub, image):
    # "signal.x" must not be treated as category "sign"
    clf = stub([], category="sign")
    clf.classify(image, [make_det("light.street_lamp")])
    assert clf.seen == []


@pytest.mark.parametrize("mode", ["RGBA", "L", "P"])
def test_non_rgb_image_converted_before_crop(stub, image, mode):
    clf = stub([("sign.stop", 0.9)])
    clf.classify(image.convert(mode), [make_det("sign.other")])
    assert all(c.mode == "RGB" for c in clf.seen[0])


def test_crops_match_bboxes(stub, image):
    clf = stub([("sign.stop", 0.9), ("sign.stop", 0.9)])
    clf.classify(
        image,
        [
            make_det("sign.other", (10, 10, 50, 40)),
            make_det("sign.other", (0, 0, 20, 20)),
        ],
    )
    assert [c.size for c in clf.seen[0]] == [(40, 30), (20, 20)]


def test_float_bbox_accepted(stub, image):
    clf = stub([("sign.stop", 0.9)])
    clf.classify(image, [make_det("sign.other", (10.4, 10.6, 50.2, 40.9))])
    assert len(clf.seen[0]) == 1


def test_model_loaded_once_across_calls(stub, image):
    clf = stub([("sign.stop", 0.9)])
    for _ in range(3):
        clf.classify(image, [make_det("sign.other")])
    assert clf.loads == 1


def test_prediction_count_mismatch_raises(stub, image):
    clf = stub([("sign.stop", 0.9)])
    clf.preds = []  # returns fewer predictions than crops
    with pytest.raises(ValueError):
        clf.classify(image, [make_det("sign.other")])
