from __future__ import annotations

from pathlib import Path

import albumentations as A
import torch
from torch.utils.data import Dataset
from transformers import RTDetrImageProcessor

from src.detection.training.common.dataset import (
    load_split_records,
    read_rgb_array,
)


class RTDETRAveiroDataset(Dataset):
    """Aveiro-Tech-City Hackathon Dataset for RT-DETR."""

    def __init__(
        self,
        split_file: Path,
        labels_dir: Path,
        processor: RTDetrImageProcessor,
        transform: A.Compose,
    ) -> None:
        self.records = load_split_records(split_file, labels_dir)
        self.processor = processor
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        img_path, bboxes, class_ids = self.records[idx]
        image = read_rgb_array(img_path)

        transformed = self.transform(
            image=image,
            bboxes=bboxes,
            class_labels=class_ids,
        )
        aug_img = transformed["image"]
        h, w = aug_img.shape[:2]

        coco_annotations = []
        for (xc, yc, bw, bh), class_id in zip(
            transformed["bboxes"], transformed["class_labels"], strict=True
        ):
            abs_w = bw * w
            abs_h = bh * h
            abs_x = (xc - bw / 2.0) * w
            abs_y = (yc - bh / 2.0) * h
            coco_annotations.append(
                {
                    "bbox": [abs_x, abs_y, abs_w, abs_h],
                    "category_id": int(class_id),
                    "area": abs_w * abs_h,
                    "iscrowd": 0,
                }
            )

        target = {"image_id": idx, "annotations": coco_annotations}
        encoding = self.processor(
            images=aug_img, annotations=target, return_tensors="pt"
        )

        return {
            "pixel_values": encoding["pixel_values"].squeeze(0),
            "labels": encoding["labels"][0],
        }


def collate_fn(batch: list[dict]) -> dict:
    """Combine image tensors and labels into a batch."""
    return {
        "pixel_values": torch.stack([item["pixel_values"] for item in batch]),
        "labels": [item["labels"] for item in batch],
    }
