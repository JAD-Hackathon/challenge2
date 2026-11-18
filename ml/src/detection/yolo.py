from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

import cv2
import numpy as np
import onnxruntime as ort
import torch
from PIL import Image
from torchvision.ops import batched_nms

from src.detection.base import Detection, Detector, register
from src.detection.utils.helpers import resolve_device

logger = logging.getLogger(__name__)

_YOLOX_ID_TO_NAME: dict[int, str] = {
    0: "traffic_sign",
    1: "street_lamp",
    2: "trash_bin",
}


@register
class YOLODetector(Detector):
    """YOLOX object detector backed by ONNX Runtime (Apache-2.0 / MIT)."""

    name: ClassVar[str] = "yolo"

    def _resolve_source(self) -> Path:
        """Resolve local fine-tuned `.onnx` weights path."""
        if self.weights_path and self.weights_path.is_file():
            return self.weights_path
        raise FileNotFoundError(
            f"YOLOX ONNX weights not found at '{self.weights_path}'. "
            "Export the trained checkpoint to .onnx before running inference."
        )

    def _load(self) -> None:
        """Load ONNX session onto the configured device. Called once, lazily."""
        source = self._resolve_source()
        self._device = resolve_device(self.cfg.device)
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "cuda" in str(self._device).lower()
            else ["CPUExecutionProvider"]
        )
        logger.info("Loading YOLOX ONNX from %s on %s", source, providers[0])
        self._session = ort.InferenceSession(str(source), providers=providers)

        inp = self._session.get_inputs()[0]
        self._input_name: str = inp.name
        if isinstance(inp.shape[2], int) and isinstance(inp.shape[3], int):
            self._input_size: tuple[int, int] = (inp.shape[2], inp.shape[3])
        else:
            self._input_size = (self.cfg.imgsz, self.cfg.imgsz)

    def _predict(self, image: Image.Image) -> list[Detection]:
        """Run inference on a single image."""
        return self.detect_batch([image])[0]

    def detect_batch(self, images: Sequence[Image.Image]) -> list[list[Detection]]:
        """Run YOLOX ONNX inference on a batch of images."""
        if not images:
            return []
        self.load()

        rgb_images = [
            img.convert("RGB") if img.mode != "RGB" else img for img in images
        ]

        blobs: list[np.ndarray] = []
        ratios: list[float] = []
        orig_sizes: list[tuple[int, int]] = []

        for img in rgb_images:
            bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            orig_h, orig_w = bgr.shape[:2]
            orig_sizes.append((orig_w, orig_h))
            blob, ratio = self._letterbox(bgr, self._input_size)
            blobs.append(blob)
            ratios.append(ratio)

        batch_tensor = np.stack(blobs, axis=0)
        raw_outputs = self._session.run(None, {self._input_name: batch_tensor})[0]

        results: list[list[Detection]] = []
        for pred, ratio, orig_size, img in zip(
            raw_outputs, ratios, orig_sizes, rgb_images, strict=True
        ):
            raw_dets = self._to_detections(pred, ratio=ratio, orig_size=orig_size)
            results.append(self._finalize(raw_dets, img.size))

        return results

    @staticmethod
    def _letterbox(
        img_bgr: np.ndarray, input_size: tuple[int, int]
    ) -> tuple[np.ndarray, float]:
        """Resize and pad BGR image with 114 border (YOLOX preprocessing)."""
        h, w = img_bgr.shape[:2]
        target_h, target_w = input_size
        ratio = min(target_h / h, target_w / w)

        resized = cv2.resize(
            img_bgr,
            (int(w * ratio), int(h * ratio)),
            interpolation=cv2.INTER_LINEAR,
        )
        padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        padded[: resized.shape[0], : resized.shape[1]] = resized

        blob = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)
        return blob, ratio

    def _to_detections(
        self,
        pred: np.ndarray,
        *,
        ratio: float,
        orig_size: tuple[int, int],
    ) -> list[Detection]:
        """Decode raw YOLOX output `[N, 5 + C]` into filtered `Detection`s."""
        if pred.size == 0:
            return []

        obj_conf = pred[:, 4]
        cls_scores = pred[:, 5:]
        cls_ids = np.argmax(cls_scores, axis=1)
        scores = obj_conf * cls_scores[np.arange(len(pred)), cls_ids]

        mask = scores >= self.cfg.conf
        if not np.any(mask):
            return []

        pred = pred[mask]
        scores_t = torch.from_numpy(scores[mask]).float()
        cls_ids_t = torch.from_numpy(cls_ids[mask]).long()

        orig_w, orig_h = orig_size
        cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
        x1 = np.clip((cx - bw / 2.0) / ratio, 0.0, orig_w)
        y1 = np.clip((cy - bh / 2.0) / ratio, 0.0, orig_h)
        x2 = np.clip((cx + bw / 2.0) / ratio, 0.0, orig_w)
        y2 = np.clip((cy + bh / 2.0) / ratio, 0.0, orig_h)
        boxes_t = torch.from_numpy(np.stack([x1, y1, x2, y2], axis=1)).float()

        keep = batched_nms(boxes_t, scores_t, cls_ids_t, iou_threshold=self.cfg.iou)
        if keep.numel() == 0:
            return []

        detections: list[Detection] = []
        for idx in keep.tolist():
            label_id = int(cls_ids_t[idx].item())
            box = boxes_t[idx].tolist()
            detections.append(
                Detection(
                    label=_YOLOX_ID_TO_NAME.get(label_id, str(label_id)),
                    score=max(0.0, min(1.0, float(scores_t[idx].item()))),
                    bbox_xyxy=(
                        float(box[0]),
                        float(box[1]),
                        float(box[2]),
                        float(box[3]),
                    ),
                )
            )

        return detections
