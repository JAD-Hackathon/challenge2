from __future__ import annotations

import logging

import numpy as np
from PIL import Image

from src.config import PathsConfig, PrivacyConfig
from src.privacy.base import AnonymizationResult, PIIDetector
from src.privacy.blur import apply_redaction
from src.privacy.detectors import YuNetFaceDetector, ONNXPlateDetector

logger = logging.getLogger(__name__)


class PrivacyAnonymizer:
    """High-level GDPR privacy pipeline: detects faces & license plates and redacts them."""

    def __init__(
        self,
        cfg: PrivacyConfig,
        paths: PathsConfig,
        face_detector: PIIDetector | None = None,
        plate_detector: PIIDetector | None = None,
    ) -> None:
        self.cfg = cfg
        self.face_detector: PIIDetector = face_detector or YuNetFaceDetector(
            weights_path=paths.weights_path(cfg.face_weights),
            conf_threshold=cfg.conf,
        )
        self.plate_detector: PIIDetector = plate_detector or ONNXPlateDetector(
            weights_path=paths.weights_path(cfg.plate_weights),
            conf_threshold=cfg.conf,
        )

    def anonymize(self, image: Image.Image) -> AnonymizationResult:
        """Detect and redact PII regions according to `self.cfg`."""
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image
        if not self.cfg.enabled:
            return AnonymizationResult(image=rgb_image.copy())

        faces = self.face_detector.detect(rgb_image) if self.face_detector else []
        plates = self.plate_detector.detect(rgb_image) if self.plate_detector else []
        all_boxes = [*faces, *plates]

        if not all_boxes:
            return AnonymizationResult(image=rgb_image.copy())

        redacted_arr = apply_redaction(
            np.array(rgb_image),
            [b.bbox_xyxy for b in all_boxes],
            method=self.cfg.method,
            margin=self.cfg.margin,
        )
        return AnonymizationResult(
            image=Image.fromarray(redacted_arr),
            faces_blurred=len(faces),
            plates_blurred=len(plates),
            boxes=all_boxes,
        )
