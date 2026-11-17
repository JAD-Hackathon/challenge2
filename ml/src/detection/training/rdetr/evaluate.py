from __future__ import annotations

import torch
from torch.utils.data import DataLoader
from torchmetrics.detection.mean_ap import MeanAveragePrecision
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor


@torch.inference_mode()
def evaluate(
    model: RTDetrForObjectDetection,
    processor: RTDetrImageProcessor,
    val_loader: DataLoader,
    device: torch.device,
) -> dict[str, float]:
    """Evaluate the object detection model on the validation dataset."""
    model.eval()
    metric = MeanAveragePrecision(box_format="xyxy", iou_type="bbox")

    for batch in val_loader:
        pixel_values = batch["pixel_values"].to(device)
        labels = batch["labels"]

        outputs = model(pixel_values=pixel_values)
        orig_sizes = torch.stack([lbl["orig_size"] for lbl in labels]).to(device)
        results = processor.post_process_object_detection(
            outputs, threshold=0.05, target_sizes=orig_sizes
        )

        preds = [
            {
                "boxes": res["boxes"].cpu(),
                "scores": res["scores"].cpu(),
                "labels": res["labels"].cpu(),
            }
            for res in results
        ]

        targets = []
        for label in labels:
            h, w = label["orig_size"].tolist()
            boxes_cxcywh = label["boxes"].cpu()
            if boxes_cxcywh.numel() > 0:
                cx, cy, bw, bh = boxes_cxcywh.unbind(-1)
                x1 = (cx - bw / 2.0) * w
                y1 = (cy - bh / 2.0) * h
                x2 = (cx + bw / 2.0) * w
                y2 = (cy + bh / 2.0) * h
                boxes_xyxy = torch.stack([x1, y1, x2, y2], dim=-1)
            else:
                boxes_xyxy = torch.zeros((0, 4), dtype=torch.float32)

            targets.append(
                {
                    "boxes": boxes_xyxy,
                    "labels": label["class_labels"].cpu(),
                }
            )

        metric.update(preds, targets)

    stats = metric.compute()
    return {
        "map_50": float(stats["map_50"].item()),
        "map": float(stats["map"].item()),
    }
