import logging
import pytest
from PIL import Image

from src.config import DetectionConfig
from src.detection.base import Detection, Detector, register


@register
class _Dummy(Detector):
    name = "dummy"
    result: list[Detection] = []

    def _load(self) -> None:
        pass

    def _predict(self, image):
        return list(self.result)


def _det(label, score, box):
    return Detection(label=label, score=score, bbox_xyxy=box)


def test_maps_labels_filters_and_sorts(cfg, tax):
    d = _Dummy(cfg, tax)
    d.result = [
        _det("street_lamp", 0.5, (10, 10, 20, 40)),
        _det("traffic_sign", 0.9, (50, 50, 80, 80)),
        _det("traffic_sign", 0.1, (0, 0, 30, 30)),  # below conf
        _det("banana", 0.9, (0, 0, 30, 30)),  # not in taxonomy
    ]
    out = d.detect(Image.new("RGB", (100, 100)))
    assert [(x.label, x.score) for x in out] == [
        ("sign.other", 0.9),
        ("light.street_lamp", 0.5),
    ]


def test_clamps_and_drops_degenerate_boxes(cfg, tax):
    d = _Dummy(cfg, tax)
    d.result = [
        _det("traffic_sign", 0.9, (-10, -10, 50, 120)),
        _det("traffic_sign", 0.9, (200, 10, 210, 20)),  # fully outside -> zero width
    ]
    out = d.detect(Image.new("L", (100, 100)))  # grayscale is converted to RGB
    assert [x.bbox_xyxy for x in out] == [(0.0, 0.0, 50.0, 100.0)]


def test_class_map_targets_must_exist(tax):
    bad = DetectionConfig(class_map={"x": "sign.stop"}, model_id="test/model")
    with pytest.raises(ValueError):
        _Dummy(bad, tax)


def test_unmapped_label_warns_once(cfg, tax, caplog):
    d = _Dummy(cfg, tax)
    d.result = [
        _det("person", 0.9, (0, 0, 30, 30)),
        _det("person", 0.8, (5, 5, 40, 40)),
    ]
    with caplog.at_level(logging.WARNING, logger="src.detection.base"):
        d.detect(Image.new("RGB", (100, 100)))
        d.detect(Image.new("RGB", (100, 100)))
    assert sum("person" in r.message for r in caplog.records) == 1


def test_detect_batch_default_loops(cfg, tax):
    d = _Dummy(cfg, tax)
    d.result = [_det("traffic_sign", 0.9, (0, 0, 30, 30))]
    out = d.detect_batch([Image.new("RGB", (100, 100))] * 3)
    assert [len(x) for x in out] == [1, 1, 1]
