import numpy as np
import pytest
from PIL import Image

from src.privacy.detectors.face import YuNetFaceDetector


class FakeYuNet:
    def __init__(self, rows):
        self.rows = rows
        self.input_size = None

    def setInputSize(self, size):
        self.input_size = size

    def detect(self, bgr):
        if self.rows is None:
            return 0, None
        return 1, np.array(self.rows, dtype=np.float32)


def row(x, y, w, h, score):
    return [x, y, w, h, *([0.0] * 10), score]  # 4 box + 10 landmarks + score


def make(rows, conf=0.25, tmp_path=None):
    det = YuNetFaceDetector(weights_path=tmp_path or "unused", conf_threshold=conf)
    det._detector = FakeYuNet(rows)  # bypass cv2 model creation
    return det


@pytest.fixture
def img():
    return Image.new("RGB", (160, 120))


def test_missing_weights_raise(tmp_path, img):
    det = YuNetFaceDetector(weights_path=tmp_path / "nope.onnx")
    with pytest.raises(FileNotFoundError):
        det.detect(img)


def test_xywh_converted_to_xyxy(img):
    [b] = make([row(10, 20, 30, 40, 0.9)]).detect(img)
    assert b.kind == "face"
    assert b.bbox_xyxy == pytest.approx((10, 20, 40, 60))
    assert b.score == pytest.approx(0.9)


def test_none_or_empty_detections(img):
    assert make(None).detect(img) == []
    assert make([]).detect(img) == []


def test_low_scores_filtered(img):
    boxes = make([row(0, 0, 10, 10, 0.1), row(20, 20, 10, 10, 0.8)], conf=0.5).detect(
        img
    )
    assert len(boxes) == 1 and boxes[0].score == pytest.approx(0.8)


def test_score_clamped_to_unit_interval(img):
    [b] = make([row(0, 0, 10, 10, 1.7)]).detect(img)
    assert b.score == 1.0


def test_input_size_updated_each_call(img):
    det = make([])
    det.detect(img)
    assert det._detector.input_size == (160, 120)
    det.detect(Image.new("RGB", (64, 48)))
    assert det._detector.input_size == (64, 48)


def test_degenerate_image_returns_empty():
    assert make([row(0, 0, 1, 1, 0.9)]).detect(Image.new("RGB", (1, 1))) == []


def test_accepts_non_rgb_input(img):
    assert make([]).detect(img.convert("L")) == []
