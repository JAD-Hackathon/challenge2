import numpy as np
import pytest
from PIL import Image

from src.classification.base import CropClassifier
from src.detection.base import Detection
from src.taxonomy import Taxonomy

CLASSES = [
    "sign.stop",
    "sign.yield",
    "sign.speed_limit",
    "sign.other",
    "light.street_lamp",
    "light.street_pole",
    "waste.underground",
    "waste.recycling_island",
    "waste.general",
]


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.model_validate(
        {"classes": [{"name": n, "label": n} for n in CLASSES]}
    )


@pytest.fixture
def image() -> Image.Image:
    rng = np.random.default_rng(0)
    return Image.fromarray(rng.integers(0, 256, (80, 100, 3), dtype=np.uint8))


def make_det(label="sign.other", box=(10, 10, 50, 40), score=0.9) -> Detection:
    return Detection(label=label, score=score, bbox_xyxy=box)


class StubClassifier(CropClassifier):
    """Scripted classifier: returns `preds` in order, records crops and loads."""

    def __init__(self, preds, category="sign", taxonomy=None, conf_threshold=0.6):
        super().__init__(category, "unused", taxonomy, conf_threshold)
        self.preds, self.loads, self.seen = preds, 0, []

    def _load(self):
        self.loads += 1

    def _predict_crops(self, crops):
        self.seen.append(list(crops))
        return self.preds[: len(crops)]


@pytest.fixture
def stub(taxonomy):
    def _make(preds, **kw):
        return StubClassifier(preds, taxonomy=taxonomy, **kw)

    return _make
