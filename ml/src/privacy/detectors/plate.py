from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

from src.privacy.base import PIIDetector, PrivacyBox

logger = logging.getLogger(__name__)


def _nms_xyxy(
    boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45
) -> list[int]:
    """Apply Non-Maximum Suppression (NMS) to bounding boxes in XYXY format."""
    if len(boxes) == 0:
        return []

    x0, y0, x1, y1 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x1 - x0) * (y1 - y0)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = int(order[0])
        keep.append(i)

        if order.size == 1:
            break

        xx0 = np.maximum(x0[i], x0[order[1:]])
        yy0 = np.maximum(y0[i], y0[order[1:]])
        xx1 = np.minimum(x1[i], x1[order[1:]])
        yy1 = np.minimum(y1[i], y1[order[1:]])

        inter = np.maximum(0.0, xx1 - xx0) * np.maximum(0.0, yy1 - yy0)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_thresh]

    return keep


class ONNXPlateDetector(PIIDetector):
    """Lightweight ONNX Runtime license-plate detector (supports YOLOX & YOLOv8/v11 ONNX)."""

    def __init__(
        self,
        weights_path: Path,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        input_size: tuple[int, int] = (640, 640),
    ) -> None:
        self.weights_path = weights_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = input_size
        self._session: ort.InferenceSession | None = None
        self._input_name: str = "images"

    def _load(self) -> ort.InferenceSession:
        """Load the ONNX plate detector and initialize its input metadata."""
        if self._session is None:
            if not self.weights_path.is_file():
                raise FileNotFoundError(
                    f"Plate detector ONNX not found: {self.weights_path}"
                )

            logger.info("Loading ONNX plate detector from %s", self.weights_path)

            self._session = ort.InferenceSession(
                path_or_bytes=str(self.weights_path),
                providers=["CPUExecutionProvider"],
            )
            input = self._session.get_inputs()[0]
            self._input_name = input.name
            if isinstance(input.shape[2], int) and isinstance(input.shape[3], int):
                self.input_size = (input.shape[2], input.shape[3])

        return self._session

    def detect(self, image: Image.Image) -> list[PrivacyBox]:
        """Detect faces in an image and return their bounding boxes."""
        session = self._load()
        rgb_image = np.array(image.convert("RGB"))

        # sync sizes (resize + pad)
        orig_h, orig_w = rgb_image.shape[:2]
        target_h, target_w = self.input_size

        ratio = min(target_h / orig_h, target_w / orig_w)
        resized = cv2.resize(
            rgb_image,
            dsize=(int(orig_w * ratio), int(orig_h * ratio)),
            interpolation=cv2.INTER_LINEAR,
        )
        padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        padded[: resized.shape[0], : resized.shape[1]] = resized

        # normalize and transform to NCHW float32
        blob = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32) / 255.0

        out = session.run(
            output_names=None, input_feed={self._input_name: blob[None, ...]}
        )[0][0]

        # handle different layouts
        if out.ndim == 2 and out.shape[0] < out.shape[1]:
            # YOLOv8: [4 + C, N]
            pred = out.T
            boxes_cxcywh = pred[:, :4]
            scores = np.max(pred[:, 4:], axis=1)
        else:
            # YOLOX: [N, 5 + C]
            boxes_cxcywh = out[:, :4]
            obj_conf = out[:, 4]
            cls_conf = np.max(out[:, 5:], axis=1) if out.shape[1] > 5 else 1.0
            scores = obj_conf * cls_conf

        # filter
        mask = scores >= self.conf_threshold
        if not np.any(mask):
            return []

        boxes_cxcywh = boxes_cxcywh[mask]
        scores = scores[mask]

        # clip
        cx, cy, bw, bh = (
            boxes_cxcywh[:, 0],
            boxes_cxcywh[:, 1],
            boxes_cxcywh[:, 2],
            boxes_cxcywh[:, 3],
        )
        x0 = np.clip((cx - bw / 2.0) / ratio, 0.0, orig_w)
        y0 = np.clip((cy - bh / 2.0) / ratio, 0.0, orig_h)
        x1 = np.clip((cx + bw / 2.0) / ratio, 0.0, orig_w)
        y1 = np.clip((cy + bh / 2.0) / ratio, 0.0, orig_h)
        boxes_xyxy = np.stack([x0, y0, x1, y1], axis=1)

        # nms
        detections = _nms_xyxy(boxes_xyxy, scores, iou_thresh=self.iou_threshold)

        return [
            PrivacyBox(
                kind="plate",
                score=max(0.0, min(1.0, float(scores[det]))),
                bbox_xyxy=(
                    float(boxes_xyxy[det, 0]),
                    float(boxes_xyxy[det, 1]),
                    float(boxes_xyxy[det, 2]),
                    float(boxes_xyxy[det, 3]),
                ),
            )
            for det in detections
        ]
