from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

BlurMethod = Literal["gaussian", "pixelate", "black"]


def expand_box(
    box_xyxy: tuple[float, float, float, float],
    margin: float,
    img_width: int,
    img_height: int,
) -> tuple[int, int, int, int]:
    """Expand bounding box by `margin` fraction of its size and clamp to image bounds."""
    x0, y0, x1, y1 = box_xyxy
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    dx = w * margin
    dy = h * margin

    ix0 = max(0, min(img_width, int(round(x0 - dx))))
    iy0 = max(0, min(img_height, int(round(y0 - dy))))
    ix1 = max(0, min(img_width, int(round(x1 + dx))))
    iy1 = max(0, min(img_height, int(round(y1 + dy))))
    return ix0, iy0, ix1, iy1


def apply_redaction(
    img_rgb: np.ndarray,
    boxes_xyxy: list[tuple[float, float, float, float]],
    *,
    method: BlurMethod = "gaussian",
    margin: float = 0.2,
) -> np.ndarray:
    """Redact all `boxes_xyxy` in-place on a copy of `img_rgb` (`H, W, 3` uint8)."""
    if not boxes_xyxy:
        return img_rgb.copy()

    out = img_rgb.copy()
    h, w = out.shape[:2]

    for box in boxes_xyxy:
        x0, y0, x1, y1 = expand_box(box, margin=margin, img_width=w, img_height=h)
        roi_w = x1 - x0
        roi_h = y1 - y0
        if roi_w < 2 or roi_h < 2:
            continue

        roi = out[y0:y1, x0:x1]

        if method == "black":
            out[y0:y1, x0:x1] = 0
        elif method == "pixelate":
            small_w = max(1, min(6, roi_w // 4))
            small_h = max(1, min(6, roi_h // 4))
            small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
            out[y0:y1, x0:x1] = cv2.resize(
                small, (roi_w, roi_h), interpolation=cv2.INTER_NEAREST
            )
        elif method == "gaussian":
            kx = max(15, (roi_w // 2) | 1)
            ky = max(15, (roi_h // 2) | 1)
            out[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (kx, ky), sigmaX=0)
        else:
            raise ValueError(f"Unsupported redaction method: {method!r}")

    return out
