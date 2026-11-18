from __future__ import annotations

import types

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch")
ort = pytest.importorskip("onnxruntime")

import src.detection.yolo as yolo_module  # noqa: E402
from src.detection.yolo import YOLODetector  # noqa: E402


def _raw_preds(
    boxes_xyxy: list[list[float]] = (),
    scores: list[float] = (),
    cls_ids: list[int] = (),
    num_classes: int = 3,
) -> np.ndarray:
    """Build synthetic YOLOX `[N, 5 + C]` output array from xyxy boxes."""
    if not boxes_xyxy:
        return np.zeros((0, 5 + num_classes), dtype=np.float32)

    rows: list[list[float]] = []
    for (x1, y1, x2, y2), score, cid in zip(boxes_xyxy, scores, cls_ids, strict=True):
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        bw = x2 - x1
        bh = y2 - y1
        cls_probs = [0.0] * num_classes
        cls_probs[cid] = 1.0
        rows.append([cx, cy, bw, bh, float(score), *cls_probs])

    return np.asarray(rows, dtype=np.float32)


class FakeORTSession:
    """Stands in for onnxruntime.InferenceSession; records run() calls."""

    def __init__(
        self, batch_outputs: list[np.ndarray], input_size: tuple[int, int] = (640, 640)
    ):
        self.batch_outputs = batch_outputs
        self.input_size = input_size
        self.calls: list[tuple[str, np.ndarray]] = []

    def get_inputs(self):
        return [
            types.SimpleNamespace(
                name="images",
                shape=["batch", 3, self.input_size[0], self.input_size[1]],
            )
        ]

    def run(self, output_names, input_feed):
        assert output_names is None
        ((inp_name, tensor),) = input_feed.items()
        self.calls.append((inp_name, tensor))
        return [np.stack(self.batch_outputs, axis=0)]


def _detector(cfg, tax, batch_outputs, weights_path=None, input_size=(640, 640)):
    d = YOLODetector(cfg, tax, weights_path)
    d._loaded = True
    d._device = "cpu"
    d._input_name = "images"
    d._input_size = input_size
    d._session = FakeORTSession(batch_outputs, input_size=input_size)
    return d


def test_to_detections_decodes_yolox_predictions(cfg, tax):
    d = _detector(cfg, tax, [])
    raw = _raw_preds([[1, 2, 30, 40], [50, 60, 120, 150]], [0.9, 0.45], [0, 1])
    out = d._to_detections(raw, ratio=1.0, orig_size=(200, 200))
    assert [(det.label, round(det.score, 2), det.bbox_xyxy) for det in out] == [
        ("traffic_sign", 0.9, (1.0, 2.0, 30.0, 40.0)),
        ("street_lamp", 0.45, (50.0, 60.0, 120.0, 150.0)),
    ]


def test_no_boxes_gives_empty_list(cfg, tax):
    d = _detector(cfg, tax, [])
    assert d._to_detections(_raw_preds(), ratio=1.0, orig_size=(100, 100)) == []


def test_detect_applies_class_map_conf_and_clamp(cfg, tax):
    # Note: 100x100 image into 640x640 letterbox -> ratio = 6.4
    ratio = 6.4
    raw = _raw_preds(
        [
            [-5 * ratio, -5 * ratio, 50 * ratio, 150 * ratio],
            [0, 0, 30 * ratio, 30 * ratio],
            [60 * ratio, 60 * ratio, 90 * ratio, 90 * ratio],
        ],
        [0.9, 0.1, 0.8],
        [0, 1, 1],
    )
    out = _detector(cfg, tax, [raw]).detect(Image.new("RGB", (100, 100)))
    assert [(det.label, det.bbox_xyxy) for det in out] == [
        ("sign.other", (0.0, 0.0, 50.0, 100.0)),
        ("light.street_lamp", (60.0, 60.0, 90.0, 90.0)),  # 0.1 dropped (< conf)
    ]


def test_predict_passes_preprocessed_batch_tensor(cfg, tax):
    d = _detector(cfg, tax, [_raw_preds()])
    img = Image.new("RGB", (100, 100))
    d.detect(img)
    assert len(d._session.calls) == 1
    inp_name, tensor = d._session.calls[0]
    assert inp_name == "images"
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32


def test_batch_follows_input_order_and_converts_grayscale_to_rgb(cfg, tax):
    r1 = _raw_preds([[10, 10, 100, 100]], [0.9], [0])
    r2 = _raw_preds([[20, 20, 150, 150]], [0.8], [1])
    d = _detector(cfg, tax, [r1, r2])
    out = d.detect_batch([Image.new("L", (100, 100)), Image.new("RGB", (100, 100))])
    assert [[x.label for x in img] for img in out] == [
        ["sign.other"],
        ["light.street_lamp"],
    ]
    _, tensor = d._session.calls[0]
    assert tensor.shape == (2, 3, 640, 640)


def test_empty_batch_does_not_call_session(cfg, tax):
    d = _detector(cfg, tax, [])
    assert d.detect_batch([]) == []
    assert d._session.calls == []


def test_source_prefers_local_onnx_file_and_raises_if_missing(cfg, tax, tmp_path):
    weights = tmp_path / "yolox_best.onnx"
    weights.write_bytes(b"fake-onnx")
    assert _detector(cfg, tax, [], weights)._resolve_source() == weights

    with pytest.raises(FileNotFoundError):
        _detector(cfg, tax, [], tmp_path / "missing.onnx")._resolve_source()

    with pytest.raises(FileNotFoundError):
        _detector(cfg, tax, [], None)._resolve_source()


def test_session_is_loaded_once(cfg, tax, tmp_path, monkeypatch):
    weights = tmp_path / "yolox_best.onnx"
    weights.write_bytes(b"fake-onnx")
    loaded: list[tuple[str, list[str]]] = []

    def fake_inference_session(model_path, providers=None):
        loaded.append((model_path, providers))
        return FakeORTSession([_raw_preds()])

    monkeypatch.setattr(ort, "InferenceSession", fake_inference_session)
    monkeypatch.setattr(yolo_module, "resolve_device", lambda spec: "cpu")

    d = YOLODetector(cfg, tax, weights)
    d.detect(Image.new("RGB", (50, 50)))
    d.detect(Image.new("RGB", (50, 50)))
    assert loaded == [(str(weights), ["CPUExecutionProvider"])]
