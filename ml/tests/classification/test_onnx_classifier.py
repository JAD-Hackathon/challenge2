import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from src.classification import onnx_classifier as mod
from src.classification.onnx_classifier import ONNXCropClassifier, _softmax

from .conftest import make_det

MEAN = np.array([0.485, 0.456, 0.406])
STD = np.array([0.229, 0.224, 0.225])


class FakeSession:
    def __init__(self, logits=None, shape=(1, 3, 224, 224), meta=None):
        self.logits, self.shape, self.meta = logits, list(shape), meta or {}
        self.fed = self.providers = None

    def get_inputs(self):
        return [SimpleNamespace(name="input", shape=self.shape)]

    def get_modelmeta(self):
        return SimpleNamespace(custom_metadata_map=self.meta)

    def run(self, names, feed):
        self.fed = feed
        return [self.logits]


@pytest.fixture
def make(monkeypatch, tmp_path, taxonomy):
    def _make(session=None, providers=("CPUExecutionProvider",), **kw):
        weights = tmp_path / "m.onnx"
        weights.touch()
        session = session or FakeSession()

        def factory(path, providers=None):
            session.providers = providers
            return session

        monkeypatch.setattr(mod.ort, "InferenceSession", factory)
        monkeypatch.setattr(mod.ort, "get_available_providers", lambda: list(providers))
        return ONNXCropClassifier("sign", weights, taxonomy, **kw), session

    return _make


# softmax


def test_softmax_rows_sum_to_one():
    p = _softmax(np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]]))
    assert np.allclose(p.sum(axis=-1), 1.0)
    assert np.allclose(p[1], 1 / 3)


def test_softmax_stable_for_huge_logits():
    p = _softmax(np.array([[1000.0, 1001.0]]))
    assert np.isfinite(p).all() and p[0, 1] > p[0, 0]


# loading


def test_missing_weights_raise(tmp_path, taxonomy):
    with pytest.raises(FileNotFoundError):
        ONNXCropClassifier("sign", tmp_path / "nope.onnx", taxonomy).load()


@pytest.mark.parametrize(
    "available,expected",
    [
        (
            ["CUDAExecutionProvider", "CPUExecutionProvider"],
            ["CUDAExecutionProvider", "CPUExecutionProvider"],
        ),
        (["CPUExecutionProvider"], ["CPUExecutionProvider"]),
        (["TensorrtExecutionProvider"], ["CPUExecutionProvider"]),
    ],
)
def test_provider_selection(make, available, expected):
    clf, session = make(
        FakeSession(meta={"classes": '["sign.stop"]'}), providers=available
    )
    clf.load()
    assert session.providers == expected


def test_static_input_shape_used(make):
    clf, _ = make(FakeSession(shape=(1, 3, 32, 48), meta={"classes": '["a"]'}))
    clf.load()
    assert clf._input_hw == (32, 48)


def test_dynamic_input_shape_keeps_default(make):
    clf, _ = make(FakeSession(shape=("b", 3, "h", "w"), meta={"classes": '["a"]'}))
    clf.load()
    assert clf._input_hw == (224, 224)


def test_classes_from_metadata_override_fallback(make):
    meta = {"classes": json.dumps(["sign.stop", "sign.yield"])}
    clf, _ = make(FakeSession(meta=meta), fallback_classes=["x"])
    clf.load()
    assert clf._classes == ["sign.stop", "sign.yield"]


def test_fallback_classes_used_without_metadata(make):
    clf, _ = make(fallback_classes=["sign.stop", "sign.yield"])
    clf.load()
    assert clf._classes == ["sign.stop", "sign.yield"]


def test_no_class_mapping_raises(make):
    clf, _ = make()
    with pytest.raises(ValueError):
        clf.load()


# preprocessing / prediction


def test_preprocess_shape_dtype_and_resize(make):
    clf, _ = make(FakeSession(shape=(1, 3, 32, 48), meta={"classes": '["a"]'}))
    clf.load()
    batch = clf._preprocess([Image.new("RGB", (10, 10)), Image.new("RGB", (200, 50))])
    assert batch.shape == (2, 3, 32, 48) and batch.dtype == np.float32


def test_preprocess_imagenet_normalisation_and_channel_order(make):
    clf, _ = make(FakeSession(shape=(1, 3, 8, 8), meta={"classes": '["a"]'}))
    clf.load()
    batch = clf._preprocess([Image.new("RGB", (8, 8), (255, 0, 128))])
    expected = (np.array([1.0, 0.0, 128 / 255]) - MEAN) / STD
    assert np.allclose(batch[0, :, 0, 0], expected, atol=1e-5)


def test_predict_returns_top_label_and_probability(make):
    classes = ["sign.stop", "sign.yield", "sign.other"]
    logits = np.array([[0.0, 5.0, 0.0], [9.0, 0.0, 0.0]], np.float32)
    clf, session = make(FakeSession(logits, meta={"classes": json.dumps(classes)}))
    clf.load()
    crops = [Image.new("RGB", (20, 20))] * 2
    (l0, c0), (l1, c1) = clf._predict_crops(crops)
    assert (l0, l1) == ("sign.yield", "sign.stop")
    assert c0 == pytest.approx(float(_softmax(logits)[0, 1]))
    assert 0.0 < c0 < c1 <= 1.0
    assert session.fed["input"].shape[0] == 2


def test_end_to_end_classify_relabels_detection(make, image):
    classes = ["sign.stop", "sign.yield"]
    logits = np.array([[8.0, 0.0]], np.float32)
    clf, _ = make(FakeSession(logits, meta={"classes": json.dumps(classes)}))
    [out] = clf.classify(image, [make_det("sign.other")])
    assert out.label == "sign.stop"
