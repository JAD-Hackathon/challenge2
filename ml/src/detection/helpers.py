from src.geometry.helpers import BBox


def xyxy_to_yolo(
    bbox: BBox, img_w: int, img_h: int
) -> tuple[float, float, float, float]:
    """Convert [x0, y0, x1, y1] to normalized YOLO [xc, yc, w, h]."""
    if img_w <= 0 or img_h <= 0:
        raise ValueError("Image dimensions must be positive.")

    x0, y0, x1, y1 = bbox
    x0 = max(0, min(img_w, x0))
    y0 = max(0, min(img_h, y0))
    x1 = max(0, min(img_w, x1))
    y1 = max(0, min(img_h, y1))

    if x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid bounding box.")

    w = x1 - x0
    h = y1 - y0
    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2

    return xc / img_w, yc / img_h, w / img_w, h / img_h
