import types

import pytest
from PIL import Image

torch = pytest.importorskip("torch")
pytest.importorskip("ultralytics")

import src.detection.yolo as yolo_module  # noqa: E402
from src.detection.yolo import YOLODetector  # noqa: E402

NAMES = {0: "traffic_sign", 1: "street_lamp"}


class FakeBoxes:
    def __init__(self, xyxy, conf, cls):
        self.xyxy = torch.tensor(xyxy, dtype=torch.float32).reshape(-1, 4)
        self.conf = torch.tensor(conf, dtype=torch.float32)
        self.cls = torch.tensor(cls, dtype=torch.float32)

    def __len__(self):
        return len(self.conf)


def _result(xyxy=(), conf=(), cls=()):
    return types.SimpleNamespace(
        names=NAMES, boxes=FakeBoxes(list(xyxy), list(conf), list(cls))
    )


class FakeYOLO:
    """Stands in for ultralytics.YOLO; records the predict() call."""

    def __init__(self, results):
        self.results = results
        self.kwargs = None

    def predict(self, **kwargs):
        self.kwargs = kwargs
        return self.results


def _detector(cfg, tax, results, weights_path=None):
    d = YOLODetector(cfg, tax, weights_path)
    d._loaded = True  # skip the real model
    d._device = "cpu"
    d._model = FakeYOLO(results)
    return d


def test_to_detections_maps_class_ids_to_names():
    out = YOLODetector._to_detections(
        _result([[1, 2, 30, 40], [5, 6, 20, 50]], [0.9, 0.4], [0, 1])
    )
    assert [(d.label, round(d.score, 2), d.bbox_xyxy) for d in out] == [
        ("traffic_sign", 0.9, (1.0, 2.0, 30.0, 40.0)),
        ("street_lamp", 0.4, (5.0, 6.0, 20.0, 50.0)),
    ]


def test_no_boxes_gives_empty_list():
    assert YOLODetector._to_detections(_result()) == []
    assert (
        YOLODetector._to_detections(types.SimpleNamespace(names=NAMES, boxes=None))
        == []
    )


def test_detect_applies_class_map_conf_and_clamp(cfg, tax):
    res = _result(
        [[-5, -5, 50, 150], [0, 0, 30, 30], [60, 60, 90, 90]],
        [0.9, 0.1, 0.8],
        [0, 1, 1],
    )
    out = _detector(cfg, tax, [res]).detect(Image.new("RGB", (100, 100)))
    assert [(d.label, d.bbox_xyxy) for d in out] == [
        ("sign.other", (0.0, 0.0, 50.0, 100.0)),
        ("light.street_lamp", (60.0, 60.0, 90.0, 90.0)),  # 0.1 dropped (< conf 0.3)
    ]


def test_predict_gets_config_values_and_pil_images(cfg, tax):
    d = _detector(cfg, tax, [_result()])
    img = Image.new("RGB", (100, 100))
    d.detect(img)
    kw = d._model.kwargs
    assert kw["source"] == [img]
    assert (kw["conf"], kw["iou"], kw["imgsz"]) == (cfg.conf, cfg.iou, cfg.imgsz)
    assert kw["device"] == "cpu" and kw["verbose"] is False


def test_batch_follows_input_order_and_converts_to_rgb(cfg, tax):
    r1 = _result([[1, 1, 20, 20]], [0.9], [0])
    r2 = _result([[2, 2, 30, 30]], [0.8], [1])
    d = _detector(cfg, tax, [r1, r2])
    out = d.detect_batch([Image.new("L", (100, 100)), Image.new("RGB", (100, 100))])
    assert [[x.label for x in img] for img in out] == [
        ["sign.other"],
        ["light.street_lamp"],
    ]
    assert all(i.mode == "RGB" for i in d._model.kwargs["source"])


def test_empty_batch_does_not_call_model(cfg, tax):
    d = _detector(cfg, tax, [])
    assert d.detect_batch([]) == []
    assert d._model.kwargs is None


def test_source_prefers_local_weights_file(cfg, tax, tmp_path):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"")
    assert _detector(cfg, tax, [], weights)._resolve_source() == str(weights)
    assert (
        _detector(cfg, tax, [], tmp_path / "missing.pt")._resolve_source()
        == cfg.model_id
    )
    assert _detector(cfg, tax, [], None)._resolve_source() == cfg.model_id


def test_model_is_loaded_once(cfg, tax, monkeypatch):
    loaded = []

    def fake_yolo(source):
        loaded.append(source)
        return FakeYOLO([_result()])

    monkeypatch.setattr(yolo_module, "YOLO", fake_yolo)
    monkeypatch.setattr(yolo_module, "resolve_device", lambda spec: "cpu")
    d = YOLODetector(cfg, tax)
    d.detect(Image.new("RGB", (50, 50)))
    d.detect(Image.new("RGB", (50, 50)))
    assert loaded == [cfg.model_id]
