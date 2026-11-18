import types
import pytest
from PIL import Image

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from src.detection.rtdetr import RTDETRDetector  # noqa: E402


class FakeBatch(dict):
    def to(self, device):
        return self


class FakeProcessor:
    """Records what the backend passes in; returns canned post-processing results."""

    def __init__(self, results):
        self.results = results
        self.threshold = None
        self.target_sizes = None

    def __call__(self, images, return_tensors):
        return FakeBatch()

    def post_process_object_detection(self, outputs, threshold, target_sizes):
        self.threshold = threshold
        self.target_sizes = target_sizes
        return self.results


class FakeModel:
    config = types.SimpleNamespace(id2label={0: "traffic_sign", 1: "street_lamp"})

    def __call__(self, **inputs):
        return object()


def _res(scores, labels, boxes):
    return {
        "scores": torch.tensor(scores),
        "labels": torch.tensor(labels),
        "boxes": torch.tensor(boxes),
    }


def _detector(cfg, tax, results, weights_path=None):
    d = RTDETRDetector(cfg, tax, weights_path)
    d._loaded = True  # skip the real model
    d._device = "cpu"
    d._processor = FakeProcessor(results)
    d._model = FakeModel()
    return d


def test_postprocess_maps_ids_to_model_labels(cfg, tax):
    d = _detector(
        cfg, tax, [_res([0.9, 0.4], [0, 1], [[1, 2, 30, 40], [5, 6, 20, 50]])]
    )
    out = d._postprocess(object(), [(100, 200)])[0]
    assert [(x.label, round(x.score, 2)) for x in out] == [
        ("traffic_sign", 0.9),
        ("street_lamp", 0.4),
    ]
    assert out[0].bbox_xyxy == (1.0, 2.0, 30.0, 40.0)


def test_detect_applies_class_map_conf_and_clamp(cfg, tax):
    res = _res(
        [0.9, 0.1, 0.8],
        [0, 1, 1],
        [[-5, -5, 50, 150], [0, 0, 30, 30], [60, 60, 90, 90]],
    )
    d = _detector(cfg, tax, [res])
    out = d.detect(Image.new("RGB", (100, 100)))
    assert [(x.label, x.bbox_xyxy) for x in out] == [
        ("sign.other", (0.0, 0.0, 50.0, 100.0)),
        ("light.street_lamp", (60.0, 60.0, 90.0, 90.0)),  # 0.1 dropped (< conf 0.3)
    ]


def test_target_sizes_are_height_then_width(cfg, tax):
    d = _detector(
        cfg, tax, [_res([], [], torch.zeros((0, 4))), _res([], [], torch.zeros((0, 4)))]
    )
    d.detect_batch([Image.new("RGB", (200, 100)), Image.new("RGB", (50, 80))])
    assert d._processor.target_sizes.tolist() == [[100, 200], [80, 50]]


def test_batch_results_follow_input_order(cfg, tax):
    r1 = _res([0.9], [0], [[1, 1, 20, 20]])
    r2 = _res([0.8], [1], [[2, 2, 30, 30]])
    d = _detector(cfg, tax, [r1, r2])
    out = d.detect_batch([Image.new("RGB", (100, 100)), Image.new("RGB", (100, 100))])
    assert [[x.label for x in img] for img in out] == [
        ["sign.other"],
        ["light.street_lamp"],
    ]


def test_empty_batch_returns_empty(cfg, tax):
    d = _detector(cfg, tax, [])
    assert d.detect_batch([]) == []


def test_threshold_follows_config(cfg, tax):
    # fails on the original `min(self.cfg.conf, 0.05)`: see review notes
    d = _detector(cfg, tax, [_res([], [], torch.zeros((0, 4)))])
    d.detect(Image.new("RGB", (100, 100)))
    assert d._processor.threshold == cfg.conf


def test_source_prefers_local_weights_dir(cfg, tax, tmp_path):
    assert _detector(cfg, tax, [], tmp_path)._resolve_source() == str(tmp_path)
    assert (
        _detector(cfg, tax, [], tmp_path / "missing")._resolve_source() == cfg.model_id
    )
    assert _detector(cfg, tax, [], None)._resolve_source() == cfg.model_id
