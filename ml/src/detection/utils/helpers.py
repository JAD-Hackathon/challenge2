from src.geometry.utils.helpers import BBox


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


def clamp_box(box: BBox, width: int, height: int) -> BBox:
    """Clamp bounding box to correct size."""
    x1, y1, x2, y2 = box
    return (
        min(max(x1, 0.0), width),
        min(max(y1, 0.0), height),
        min(max(x2, 0.0), width),
        min(max(y2, 0.0), height),
    )


def resolve_device(spec: str) -> str:
    """'auto' -> 'cuda:0' if available else 'cpu'."""
    if spec != "auto":
        return spec
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda:0" if torch.cuda.is_available() else "cpu"
