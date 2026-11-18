import numpy as np
import pytest
from PIL import Image

from src.privacy.base import PIIDetector, PrivacyBox


@pytest.fixture
def noise_rgb() -> np.ndarray:
    """Deterministic noise: any blur/redaction visibly changes it."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (120, 160, 3), dtype=np.uint8)


@pytest.fixture
def noise_image(noise_rgb) -> Image.Image:
    return Image.fromarray(noise_rgb)


class FakeDetector(PIIDetector):
    def __init__(self, boxes=(), error: Exception | None = None):
        self.boxes = list(boxes)
        self.error = error
        self.calls: list[Image.Image] = []

    def detect(self, image):
        self.calls.append(image)
        if self.error:
            raise self.error
        return list(self.boxes)


@pytest.fixture
def fake_detector():
    return FakeDetector


def face_box(xyxy=(40, 30, 80, 70), score=0.9) -> PrivacyBox:
    return PrivacyBox(kind="face", score=score, bbox_xyxy=xyxy)


def plate_box(xyxy=(100, 80, 140, 100), score=0.8) -> PrivacyBox:
    return PrivacyBox(kind="plate", score=score, bbox_xyxy=xyxy)
