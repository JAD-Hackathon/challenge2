from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from src.config import PathsConfig, Settings
from src.detection.base import Detection
from src.geometry.base import GeoLocation
from src.privacy.base import AnonymizationResult
from src.service.schemas import CameraMeta
from src.taxonomy import Taxonomy

W, H = 200, 100


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.model_validate(
        {
            "classes": [
                {
                    "name": "sign.stop",
                    "label": "Stop",
                    "size": {"dim": "width", "m": 0.6},
                },
                {
                    "name": "sign.other",
                    "label": "Outro",
                    "size": {"dim": "width", "m": 0.6},
                },
                {"name": "light.street_lamp", "label": "Candeeiro", "ground": True},
            ]
        }
    )


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        paths=PathsConfig(shared_dir=tmp_path, weights_dir=tmp_path / "weights")
    )


@pytest.fixture
def image() -> Image.Image:
    rng = np.random.default_rng(0)
    return Image.fromarray(
        rng.integers(100, 256, (H, W, 3), dtype=np.uint8)
    )  # bright noise


@pytest.fixture
def meta() -> CameraMeta:
    return CameraMeta(image_id="img_1", lat=40.6412, lon=-8.6538, heading=92.5)


def det(label="sign.other", score=0.9, box=(10, 10, 50, 40)) -> Detection:
    return Detection(
        label=label, score=score, bbox_xyxy=box
    )  # adjust if Detection differs


# duck-typed stages


class FakeAnonymizer:
    """Blacks out the top-left 50x50 so raw vs blurred is distinguishable."""

    def __init__(self, error=None):
        self.error, self.seen = error, []

    def anonymize(self, image):
        self.seen.append(image)
        if self.error:
            raise self.error
        out = image.copy()
        out.paste((0, 0, 0), (0, 0, 50, 50))
        return AnonymizationResult(image=out)


class FakeDetector:
    def __init__(self, detections=()):
        self.detections, self.seen, self.loaded = list(detections), [], 0

    def detect(self, image):
        self.seen.append(image)
        return list(self.detections)

    def load(self):
        self.loaded += 1


class FakeClassifier:
    def __init__(self, relabel=None):
        self.relabel, self.seen = relabel or {}, []

    def refine(self, image, detections):
        self.seen.append((image, list(detections)))
        return [
            d.model_copy(update={"label": self.relabel.get(d.label, d.label)})
            for d in detections
        ]


class FakeLocalizer:
    def __init__(self, geo=None):
        self.geo = geo or GeoLocation(
            bearing_deg=90.0,
            est_lat=40.1,
            est_lon=-8.1,
            est_distance_m=10.0,
            uncertainty_m=3.0,
            method="size_prior",
        )
        self.calls, self.prepared = [], []

    def localize(self, *, class_name, bbox_xyxy, frame):
        self.calls.append(
            SimpleNamespace(class_name=class_name, bbox=bbox_xyxy, frame=frame)
        )
        return self.geo

    def prepare_image(self, arr):
        self.prepared.append(arr)


@pytest.fixture
def build(settings, taxonomy):
    from src.pipeline import InferencePipeline

    def _build(
        detections=(),
        *,
        anonymizer=None,
        classifier=None,
        localizer=None,
        settings_=None,
    ):
        stages = dict(
            anonymizer=anonymizer or FakeAnonymizer(),
            detector=FakeDetector(detections),
            classifier=classifier or FakeClassifier(),
            localizer=localizer or FakeLocalizer(),
        )
        pipe = InferencePipeline(settings_ or settings, taxonomy, **stages)
        return pipe, SimpleNamespace(**stages)

    return _build
