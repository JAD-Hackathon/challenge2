from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from src.detection.helpers import clamp_box
from src.geometry.helpers import BBox
from src.config import DetectionConfig
from src.taxonomy import Taxonomy

logger = logging.getLogger(__name__)


class Detection(BaseModel):
    """Detection representation with label, score, and bbox."""

    model_config = ConfigDict(frozen=True)

    label: str
    score: float = Field(ge=0, le=1)
    bbox_xyxy: BBox

    @property
    def width(self) -> float:
        return self.bbox_xyxy[2] - self.bbox_xyxy[0]

    @property
    def height(self) -> float:
        return self.bbox_xyxy[3] - self.bbox_xyxy[1]

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox_xyxy
        return (x1 + x2) / 2, (y1 + y2) / 2


class Detector(ABC):
    """Base class for all detectors."""

    name: ClassVar[str]

    def __init__(
        self, cfg: DetectionConfig, taxonomy: Taxonomy, weights_path: Path | None = None
    ) -> None:
        """
        Initialize the object detector with configuration, class taxonomy, and model weights.
        Args:
            cfg: Detection hyperparameters, thresholds, and model settings.
            taxonomy: Canonical class definitions and label mappings for the target zone.
            weights_path: Optional local path to pretrained or fine-tuned model weights.
        """
        self.cfg = cfg
        self.taxonomy = taxonomy
        self.weights_path = weights_path

        self.class_map: dict[str, str] = {
            **{str(idx): name for idx, name in taxonomy.names_by_id().items()},
            **dict(cfg.class_map),
        }
        self._names = set(taxonomy.names)

        unknown = sorted(set(self.class_map.values()) - self._names)
        if unknown:
            raise ValueError(f"detection.class_map targets not in taxonomy: {unknown}")

        self._loaded = False

    @abstractmethod
    def _load(self) -> None:
        """Load weights onto the device. Called once, lazily."""
        pass

    @abstractmethod
    def _predict(self, image: Image.Image) -> list[Detection]:
        """
        Run the model on one RGB image. Return boxes in pixels of that image, with
        the model's own labels (mapped to the taxonomy by `detect`).
        """
        pass

    def load(self) -> None:
        """Load weights onto the device."""
        if not self._loaded:
            self._load()
            self._loaded = True

    def detect(self, image: Image.Image) -> list[Detection]:
        """Detections for one image, best first. Labels are taxonomy names."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        self.load()
        preds = self._predict(image)
        out = self._finalize(preds, image.size)
        return out

    def detect_batch(self, images: Sequence[Image.Image]) -> list[list[Detection]]:
        """Override in a backend if the model batches natively."""
        return [self.detect(image) for image in images]

    def _finalize(
        self, raw: Sequence[Detection], size: tuple[int, int]
    ) -> list[Detection]:
        """Finalize detector predictions: map labels, filter by score, clamp boxes, etc."""
        width, height = size
        out: list[Detection] = []

        for detection in raw:
            label = self.class_map.get(detection.label, detection.label)
            if label not in self._names:
                logger.debug("dropping unmapped label %r", detection.label)
                continue

            if detection.score < self.cfg.conf:
                continue

            box = clamp_box(detection.bbox_xyxy, width, height)
            if box[2] - box[0] < 1.0 or box[3] - box[1] < 1.0:
                continue

            out.append(Detection(label=label, score=detection.score, bbox_xyxy=box))
        out.sort(key=lambda d: d.score, reverse=True)
        return out


# === registry & factory ====

_REGISTRY: dict[str, type[Detector]] = {}


def register(cls: type[Detector]) -> type[Detector]:
    """Class decorator: make a backend selectable by `detection.backend`."""
    _REGISTRY[cls.name] = cls
    return cls


def build_detector(
    cfg: DetectionConfig, taxonomy: Taxonomy, weights_path: Path | None = None
) -> Detector:
    """Create the backend named in the config."""
    if cfg.backend not in _REGISTRY:
        importlib.import_module(f"src.detection.{cfg.backend}")
    try:
        cls = _REGISTRY[cfg.backend]
    except KeyError:
        raise ValueError(
            f"module src.detection.{cfg.backend} did not register a detector"
        ) from None
    return cls(cfg, taxonomy, weights_path)
