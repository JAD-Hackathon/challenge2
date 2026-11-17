from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import ClassVar

from PIL import Image
from ultralytics import YOLO

from src.detection.base import Detection, Detector, register
from src.detection.utils.helpers import resolve_device

logger = logging.getLogger(__name__)


@register
class YOLODetector(Detector):
    """YOLO object detector backed by Ultralytics."""

    name: ClassVar[str] = "yolo"

    def _resolve_source(self) -> str:
        """Local fine-tuned .pt file if available, otherwise `cfg.model_id`."""
        if self.weights_path and self.weights_path.is_file():
            return str(self.weights_path)
        return self.cfg.model_id

    def _load(self) -> None:
        """Load weights onto the device. Called once, lazily."""
        source = self._resolve_source()
        self._device = resolve_device(self.cfg.device)
        logger.info("Loading YOLO from %s on %s", source, self._device)
        self._model = YOLO(source)

    def _predict(self, image: Image.Image) -> list[Detection]:
        """Run inference on a single image."""
        return self.detect_batch([image])[0]

    def detect_batch(self, images: Sequence[Image.Image]) -> list[list[Detection]]:
        """Run YOLO inference on a batch of images."""
        if not images:
            return []
        self.load()
        rgb_images = [
            img.convert("RGB") if img.mode != "RGB" else img for img in images
        ]

        results = self._model.predict(
            source=list(rgb_images),
            conf=self.cfg.conf,
            iou=self.cfg.iou,
            imgsz=self.cfg.imgsz,
            device=self._device,
            verbose=False,
        )
        raw_batch = [self._to_detections(res) for res in results]

        return [
            self._finalize(raw, img.size)
            for raw, img in zip(raw_batch, rgb_images, strict=True)
        ]

    @staticmethod
    def _to_detections(result: object) -> list[Detection]:
        """Convert one Ultralytics `Results` into `Detection`s (model labels)."""
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []

        names = result.names
        detection: list[Detection] = []

        for score, label_id, box in zip(
            boxes.conf.cpu().tolist(),
            boxes.cls.cpu().tolist(),
            boxes.xyxy.cpu().tolist(),
        ):
            detection.append(
                Detection(
                    label=str(names.get(int(label_id), label_id)),
                    score=max(0.0, min(1.0, float(score))),
                    bbox_xyxy=(
                        float(box[0]),
                        float(box[1]),
                        float(box[2]),
                        float(box[3]),
                    ),
                )
            )

        return detection
