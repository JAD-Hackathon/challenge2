from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import ClassVar

import torch
from PIL import Image
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

from src.detection.base import Detection, Detector, register
from src.detection.utils.helpers import resolve_device

logger = logging.getLogger(__name__)


@register
class RTDETRDetector(Detector):
    """RT-DETR object detector backed by HuggingFace Transformers."""

    name: ClassVar[str] = "rtdetr"

    def _resolve_source(self) -> str:
        """Return local fine-tuned directory path if available, otherwise HF model_id."""
        if self.weights_path and self.weights_path.exists():
            return str(self.weights_path)
        return self.cfg.model_id

    def _load(self) -> None:
        """Load weights onto the device. Called once, lazily."""
        source = self._resolve_source()
        self._device = resolve_device(self.cfg.device)
        logger.info("Loading RT-DETR from %s on %s", source, self._device)

        self._processor = RTDetrImageProcessor.from_pretrained(
            source,
            size={"height": self.cfg.imgsz, "width": self.cfg.imgsz},
        )
        self._model = RTDetrForObjectDetection.from_pretrained(source).to(self._device)
        self._model.eval()

    @torch.inference_mode()
    def _predict(self, image: Image.Image) -> list[Detection]:
        """
        Run the model on one RGB image. Return boxes in pixels of that image, with
        the model's own labels (mapped to the taxonomy by `detect`).
        """
        inputs = self._processor(images=image, return_tensors="pt").to(self._device)
        outputs = self._model(**inputs)
        w, h = image.size
        return self._postprocess(outputs, sizes_hw=[(h, w)])[0]

    @torch.inference_mode()
    def detect_batch(self, images: Sequence[Image.Image]) -> list[list[Detection]]:
        if not images:
            return []
        self.load()
        rgb_images = [
            img.convert("RGB") if img.mode != "RGB" else img for img in images
        ]

        inputs = self._processor(images=rgb_images, return_tensors="pt").to(
            self._device
        )
        outputs = self._model(**inputs)

        sizes_hw = [(img.height, img.width) for img in rgb_images]
        raw_batch = self._postprocess(outputs, sizes_hw)

        return [
            self._finalize(raw, img.size)
            for raw, img in zip(raw_batch, rgb_images, strict=True)
        ]

    def _postprocess(
        self, outputs: object, sizes_hw: list[tuple[int, int]]
    ) -> list[list[Detection]]:
        """Postprocess RT-DETR outputs and map them to `Detection`s."""
        target_sizes = torch.tensor(sizes_hw, device=self._device)

        results = self._processor.post_process_object_detection(
            outputs,
            threshold=self.cfg.conf,
            target_sizes=target_sizes,
        )

        id2label = getattr(self._model.config, "id2label", {})
        batch_detections: list[list[Detection]] = []

        for res in results:
            detections: list[Detection] = []

            for score, label_id, box in zip(
                res["scores"].detach().cpu().tolist(),
                res["labels"].detach().cpu().tolist(),
                res["boxes"].detach().cpu().tolist(),
            ):
                label = id2label.get(int(label_id), str(label_id))
                detections.append(
                    Detection(
                        label=str(label),
                        score=float(score),
                        bbox_xyxy=(
                            float(box[0]),
                            float(box[1]),
                            float(box[2]),
                            float(box[3]),
                        ),
                    )
                )

            batch_detections.append(detections)

        return batch_detections
