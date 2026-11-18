import numpy as np
import pytest
from PIL import Image

from src.privacy.detectors import plate as plate_mod
from src.privacy.detectors.plate import ONNXPlateDetector, _nms_xyxy


# NMS


def test_nms_empty():
    assert _nms_xyxy(np.zeros((0, 4)), np.zeros(0)) == []


def test_nms_suppresses_overlap_keeps_best():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], float)
    assert _nms_xyxy(boxes, np.array([0.6, 0.9, 0.7]), 0.45) == [1, 2]


def test_nms_keeps_disjoint():
    boxes = np.array([[0, 0, 10, 10], [20, 20, 30, 30]], float)
    assert sorted(_nms_xyxy(boxes, np.array([0.5, 0.5]))) == [0, 1]


def test_nms_single():
    assert _nms_xyxy(np.array([[0, 0, 5, 5]], float), np.array([0.3])) == [0]


# fakes


class FakeInput:
    def __init__(self, shape):
        self.name, self.shape = "images", list(shape)


class FakeSession:
    def __init__(self, out, shape=(1, 3, 640, 640)):
        self.out, self.shape, self.fed = out, shape, None

    def get_inputs(self):
        return [FakeInput(self.shape)]

    def run(self, output_names=None, input_feed=None):
        self.fed = input_feed
        return [self.out[None, ...]]


def v8_output(dets, n=20):
    """YOLOv8 layout [4+C, N]; dets = (cx, cy, w, h, score) in model space."""
    out = np.zeros((5, n), np.float32)
    for i, d in enumerate(dets):
        out[:, i] = d
    return out


def yolox_output(dets, n=20):
    """YOLOX layout [N, 5+C]; dets = (cx, cy, w, h, obj, cls)."""
    out = np.zeros((n, 6), np.float32)
    for i, d in enumerate(dets):
        out[i] = d
    return out


def model_box(box, ratio):
    x0, y0, x1, y1 = box
    return (
        (x0 + x1) / 2 * ratio,
        (y0 + y1) / 2 * ratio,
        (x1 - x0) * ratio,
        (y1 - y0) * ratio,
    )


def make(monkeypatch, tmp_path, out, shape=(1, 3, 640, 640), **kw):
    weights = tmp_path / "plate.onnx"
    weights.touch()
    session = FakeSession(out, shape)
    monkeypatch.setattr(plate_mod.ort, "InferenceSession", lambda **_: session)
    return ONNXPlateDetector(weights, **kw), session


# loading


def test_missing_weights_raise(tmp_path):
    with pytest.raises(FileNotFoundError):
        ONNXPlateDetector(tmp_path / "nope.onnx").detect(Image.new("RGB", (64, 64)))


def test_static_input_shape_overrides_input_size(monkeypatch, tmp_path):
    det, _ = make(monkeypatch, tmp_path, v8_output([]), shape=(1, 3, 320, 480))
    det._load()
    assert det.input_size == (320, 480)


def test_dynamic_input_shape_keeps_default(monkeypatch, tmp_path):
    det, _ = make(monkeypatch, tmp_path, v8_output([]), shape=("b", 3, "h", "w"))
    det._load()
    assert det.input_size == (640, 640)


# detection


@pytest.mark.parametrize(
    "size,box",
    [
        ((200, 100), (90, 45, 110, 55)),  # landscape (w, h)
        ((100, 200), (40, 90, 60, 110)),  # portrait
        ((640, 640), (300, 300, 340, 320)),
    ],  # exact model size
)
@pytest.mark.parametrize("layout", ["v8", "yolox"])
def test_boxes_mapped_back_to_original_pixels(monkeypatch, tmp_path, size, box, layout):
    w, h = size
    ratio = min(640 / h, 640 / w)
    cx, cy, bw, bh = model_box(box, ratio)
    out = (
        v8_output([(cx, cy, bw, bh, 0.9)])
        if layout == "v8"
        else yolox_output([(cx, cy, bw, bh, 0.9, 1.0)])
    )
    det, session = make(monkeypatch, tmp_path, out)

    [b] = det.detect(Image.new("RGB", size))

    assert b.kind == "plate"
    assert b.bbox_xyxy == pytest.approx(box, abs=1.0)
    assert b.score == pytest.approx(0.9, abs=1e-3)
    blob = session.fed["images"]
    assert blob.shape == (1, 3, 640, 640) and blob.dtype == np.float32
    assert 0.0 <= blob.min() and blob.max() <= 1.0


def test_low_confidence_filtered(monkeypatch, tmp_path):
    out = v8_output([(320, 320, 64, 32, 0.9), (100, 100, 40, 20, 0.05)])
    det, _ = make(monkeypatch, tmp_path, out, conf_threshold=0.25)
    boxes = det.detect(Image.new("RGB", (640, 640)))
    assert len(boxes) == 1 and boxes[0].score == pytest.approx(0.9, abs=1e-3)


def test_nothing_above_threshold_returns_empty(monkeypatch, tmp_path):
    det, _ = make(monkeypatch, tmp_path, v8_output([]), conf_threshold=0.25)
    assert det.detect(Image.new("RGB", (640, 480))) == []


def test_duplicate_detections_merged_by_nms(monkeypatch, tmp_path):
    out = v8_output([(320, 320, 64, 32, 0.9), (322, 321, 64, 32, 0.8)])
    det, _ = make(monkeypatch, tmp_path, out)
    assert len(det.detect(Image.new("RGB", (640, 640)))) == 1


def test_boxes_clipped_to_image(monkeypatch, tmp_path):
    out = v8_output([(5, 5, 100, 100, 0.9)])
    [b] = make(monkeypatch, tmp_path, out)[0].detect(Image.new("RGB", (640, 640)))
    x0, y0, x1, y1 = b.bbox_xyxy
    assert x0 >= 0 and y0 >= 0 and x1 <= 640 and y1 <= 640


def test_accepts_non_rgb_input(monkeypatch, tmp_path):
    det, _ = make(monkeypatch, tmp_path, v8_output([]))
    assert det.detect(Image.new("RGBA", (320, 240))) == []
