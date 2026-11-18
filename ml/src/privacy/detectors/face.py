from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.privacy.base import PIIDetector, PrivacyBox

logger = logging.getLogger(__name__)


class YuNetFaceDetector(PIIDetector):
    """OpenCV built-in YuNet face detector (MIT license, ONNX)."""

    def __init__(self, weights_path: Path, conf_threshold: float = 0.25) -> None:
        self.weights_path = weights_path
        self.conf_threshold = conf_threshold
        self._detector: cv2.FaceDetectorYN | None = None

    def _load(self, width: int, height: int) -> cv2.FaceDetectorYN:
        """Load the YuNet detector or update its input size."""
        if self._detector is None:
            if not self.weights_path.is_file():
                raise FileNotFoundError(
                    f"Face detector ONNX not found: {self.weights_path}"
                )

            logger.info("Loading YuNet face detector from %s", self.weights_path)

            self._detector = cv2.FaceDetectorYN.create(
                model=str(self.weights_path),
                config="",
                input_size=(width, height),
                score_threshold=self.conf_threshold,
                nms_threshold=0.3,
                top_k=5000,
            )
        else:
            self._detector.setInputSize((width, height))

        return self._detector

    def detect(self, image: Image.Image) -> list[PrivacyBox]:
        """Detect faces in an image and return their bounding boxes."""
        rgb_image = np.array(image.convert("RGB"))
        bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

        h, w = bgr_image.shape[:2]
        if w < 2 or h < 2:
            return []

        detector = self._load(w, h)
        _, detections = detector.detect(bgr_image)
        if detections is None or len(detections) == 0:
            return []

        boxes: list[PrivacyBox] = []

        for det in detections:
            x, y, bw, bh = (float(det[0]), float(det[1]), float(det[2]), float(det[3]))

            score = float(det[-1])
            if score < self.conf_threshold:
                continue

            boxes.append(
                PrivacyBox(
                    kind="face",
                    score=max(0.0, min(1.0, score)),
                    bbox_xyxy=(x, y, x + bw, y + bh),
                )
            )

        return boxes
