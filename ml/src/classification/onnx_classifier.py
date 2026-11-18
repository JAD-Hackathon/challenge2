from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from src.classification.base import CropClassifier
from src.config import Category, ClassificationConfig, PathsConfig
from src.detection.base import Detection
from src.taxonomy import Taxonomy

logger = logging.getLogger(__name__)

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _softmax(logits: np.ndarray) -> np.ndarray:
    """Compute numerically stable row-wise softmax probabilities."""
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


class ONNXCropClassifier(CropClassifier):
    """ONNX Runtime crop classifier reading input shape and class map from metadata."""

    def __init__(
        self,
        category: Category,
        weights_path: Path,
        taxonomy: Taxonomy,
        conf_threshold: float = 0.60,
        fallback_classes: Sequence[str] | None = None,
    ) -> None:
        """Initialize ONNX crop classifier with optional fallback class labels."""
        super().__init__(category, weights_path, taxonomy, conf_threshold)
        self._session: ort.InferenceSession | None = None
        self._input_name: str = ""
        self._input_hw: tuple[int, int] = (224, 224)
        self._classes: list[str] = list(fallback_classes or [])

    def _load(self) -> None:
        """Create ONNX Runtime session and extract input dimensions and class labels."""
        if not self.weights_path.is_file():
            raise FileNotFoundError(
                f"Classifier weights not found: {self.weights_path}"
            )

        preferred = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available = set(ort.get_available_providers())
        providers = [p for p in preferred if p in available] or ["CPUExecutionProvider"]

        self._session = ort.InferenceSession(
            str(self.weights_path), providers=providers
        )
        input = self._session.get_inputs()[0]
        self._input_name = input.name

        if (
            len(input.shape) == 4
            and isinstance(input.shape[2], int)
            and isinstance(input.shape[3], int)
        ):
            self._input_hw = (input.shape[2], input.shape[3])

        meta = self._session.get_modelmeta().custom_metadata_map
        if "classes" in meta:
            self._classes = json.loads(meta["classes"])

        if not self._classes:
            raise ValueError(
                f"No class mapping found in ONNX metadata for {self.weights_path}"
            )

    def _preprocess(self, crops: Sequence[Image.Image]) -> np.ndarray:
        """Resize and ImageNet-normalize a batch of RGB crops into NCHW float32 tensor."""
        h, w = self._input_hw
        batch = np.empty((len(crops), 3, h, w), dtype=np.float32)
        for i, crop in enumerate(crops):
            resized = crop.resize((w, h), Image.Resampling.BILINEAR)
            arr = np.asarray(resized, dtype=np.float32) / 255.0
            arr = (arr - _IMAGENET_MEAN) / _IMAGENET_STD
            batch[i] = np.transpose(arr, (2, 0, 1))
        return batch

    def _predict_crops(self, crops: Sequence[Image.Image]) -> list[tuple[str, float]]:
        """Run batched ONNX inference and return top label and probability per crop."""
        assert self._session is not None
        batch = self._preprocess(crops)
        logits = self._session.run(None, {self._input_name: batch})[0]
        probs = _softmax(logits)

        best_ids = np.argmax(probs, axis=-1)
        best_confs = probs[np.arange(len(crops)), best_ids]

        return [
            (self._classes[int(cls_id)], float(conf))
            for cls_id, conf in zip(best_ids, best_confs, strict=True)
        ]


class MultiCategoryClassifier:
    """Orchestrator running enabled per-category crop classifiers on detections."""

    def __init__(
        self, cfg: ClassificationConfig, paths: PathsConfig, taxonomy: Taxonomy
    ) -> None:
        """Instantiate ONNX classifiers for categories whose weight files exist."""
        self.enabled = cfg.enabled
        self._classifiers: list[CropClassifier] = []

        if not self.enabled:
            return

        mapping: list[tuple[Category, str]] = [
            ("sign", cfg.sign_weights),
            ("waste", cfg.waste_weights),
            ("light", cfg.lighting_weights),
        ]
        for category, weight_file in mapping:
            w_path = paths.weights_path(weight_file)
            if w_path.is_file():
                self._classifiers.append(
                    ONNXCropClassifier(
                        category=category,
                        weights_path=w_path,
                        taxonomy=taxonomy,
                    )
                )
            else:
                logger.warning(
                    "Classifier weights %s not found; %s detections will keep coarse labels.",
                    w_path,
                    category,
                )

    def refine(
        self, image: Image.Image, detections: Sequence[Detection]
    ) -> list[Detection]:
        """Sequentially refine detection labels across all active category classifiers."""
        if not self.enabled or not detections or not self._classifiers:
            return list(detections)

        out = list(detections)
        for clf in self._classifiers:
            out = clf.classify(image, out)
        return out
