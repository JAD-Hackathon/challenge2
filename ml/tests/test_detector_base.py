import pytest
from PIL import Image

from src.config import DetectionConfig
from src.detection.base import Detection, Detector, register
from src.taxonomy import Taxonomy

TAX = Taxonomy.model_validate(
    {
        "classes": [
            {"name": "sign.other", "label": "Outro sinal"},
            {"name": "light.street_lamp", "label": "Candeeiro"},
        ]
    }
)
CFG = DetectionConfig(
    conf=0.3,
    class_map={"traffic_sign": "sign.other", "street_lamp": "light.street_lamp"},
)


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


def test_maps_labels_filters_and_sorts():
    d = _Dummy(CFG, TAX)
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


def test_clamps_and_drops_degenerate_boxes():
    d = _Dummy(CFG, TAX)
    d.result = [
        _det("traffic_sign", 0.9, (-10, -10, 50, 120)),
        _det("traffic_sign", 0.9, (200, 10, 210, 20)),  # fully outside -> zero width
    ]
    out = d.detect(Image.new("L", (100, 100)))  # grayscale is converted to RGB
    assert [x.bbox_xyxy for x in out] == [(0.0, 0.0, 50.0, 100.0)]


def test_class_map_targets_must_exist():
    bad = DetectionConfig(class_map={"x": "sign.stop"})
    with pytest.raises(ValueError):
        _Dummy(bad, TAX)
