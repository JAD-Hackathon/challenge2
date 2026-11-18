from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from src.config import Category
from src.detection.base import Detection
from src.taxonomy import Taxonomy


class CropClassifier(ABC):
    """Base interface for 2nd-stage fine-grained crop classification."""

    def __init__(
        self,
        category: Category,
        weights_path: Path,
        taxonomy: Taxonomy,
        conf_threshold: float = 0.60,
    ) -> None:
        """Initialize classifier parameters for a specific target super-category."""
        self.category = category
        self.weights_path = weights_path
        self.taxonomy = taxonomy
        self.conf_threshold = conf_threshold
        self._loaded = False

    @abstractmethod
    def _load(self) -> None:
        """Load underlying model weights or inference session lazily."""

    @abstractmethod
    def _predict_crops(self, crops: Sequence[Image.Image]) -> list[tuple[str, float]]:
        """Predict (taxonomy_label, confidence) pairs for a batch of RGB crops."""

    def load(self) -> None:
        """Ensure the classifier model is loaded into memory once."""
        if not self._loaded:
            self._load()
            self._loaded = True

    def classify(
        self, image: Image.Image, detections: Sequence[Detection]
    ) -> list[Detection]:
        """Refine labels of detections belonging to the classifier's category."""
        target_indices = [
            i
            for i, det in enumerate(detections)
            if det.label.startswith(f"{self.category}.")
        ]
        if not target_indices:
            return list(detections)

        if image.mode != "RGB":
            image = image.convert("RGB")

        self.load()
        crops = [image.crop(detections[i].bbox_xyxy) for i in target_indices]
        predictions = self._predict_crops(crops)

        updated = list(detections)
        valid_names = set(self.taxonomy.names)

        for idx, (pred_label, pred_conf) in zip(
            target_indices, predictions, strict=True
        ):
            if (
                pred_conf >= self.conf_threshold
                and pred_label.startswith(f"{self.category}.")
                and pred_label in valid_names
            ):
                updated[idx] = updated[idx].model_copy(update={"label": pred_label})
        return updated
