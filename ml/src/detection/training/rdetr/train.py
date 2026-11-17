from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader, WeightedRandomSampler
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

from src.detection.training.rdetr.dataset import RTDETRAveiroDataset, collate_fn
from src.detection.training.rdetr.evaluate import evaluate
from src.config import get_settings
from src.detection.utils.helpers import resolve_device
from src.detection.training.common.dataset import (
    STAGE1_ID2LABEL,
    STAGE1_LABEL2ID,
    build_transforms,
    compute_sample_weights,
    validate_stage1_taxonomy,
)
from src.taxonomy import get_taxonomy


def train(
    model_id: str = "PekingU/rtdetr_r50vd",
    epochs: int = 20,
    batch_size: int = 4,
    lr: float = 1e-4,
    imgsz: int = 640,
    out_dir: str = "weights/rtdetr_best",
    balanced_sampler: bool = False,
) -> None:
    """Fine-tune an RT-DETR model on the Stage-1 dataset."""
    settings = get_settings()
    taxonomy = get_taxonomy()
    validate_stage1_taxonomy(taxonomy)
    device = resolve_device(settings.detection.device)

    processor = RTDetrImageProcessor.from_pretrained(
        model_id,
        size={"height": imgsz, "width": imgsz},
    )
    model = RTDetrForObjectDetection.from_pretrained(
        model_id,
        id2label=STAGE1_ID2LABEL,
        label2id=STAGE1_LABEL2ID,
        ignore_mismatched_sizes=True,
    ).to(device)

    train_ds = RTDETRAveiroDataset(
        settings.paths.splits / "train.txt",
        settings.paths.labels,
        processor,
        build_transforms(train=True),
    )
    val_ds = RTDETRAveiroDataset(
        settings.paths.splits / "val.txt",
        settings.paths.labels,
        processor,
        build_transforms(train=False),
    )

    sampler = None
    if balanced_sampler:
        sampler = WeightedRandomSampler(
            weights=compute_sample_weights(train_ds.records),
            num_samples=len(train_ds),
            replacement=True,
        )

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        sampler=sampler,
        shuffle=sampler is None,
        collate_fn=collate_fn,
        num_workers=2,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=2,
    )

    backbone_params = [p for n, p in model.named_parameters() if "backbone" in n]
    head_params = [p for n, p in model.named_parameters() if "backbone" not in n]
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_params, "lr": lr * 0.1},
            {"params": head_params, "lr": lr},
        ],
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=1e-6
    )
    scaler = torch.amp.GradScaler("cuda", enabled=torch.cuda.is_available())

    save_path = Path(out_dir)
    best_map50 = -1.0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            pixel_values = batch["pixel_values"].to(device)
            labels = [
                {k: v.to(device) for k, v in lbl.items()} for lbl in batch["labels"]
            ]

            with torch.amp.autocast("cuda", enabled=torch.cuda.is_available()):
                outputs = model(pixel_values=pixel_values, labels=labels)
                loss = outputs.loss

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.1)
            scaler.step(optimizer)
            scaler.update()

            total_loss += loss.item()

        scheduler.step()
        avg_loss = total_loss / max(1, len(train_loader))
        metrics = evaluate(model, processor, val_loader, device)
        mAP50 = metrics["map_50"]
        mAP = metrics["map"]
        print(
            f"Epoch {epoch}/{epochs} | loss={avg_loss:.4f} | val_mAP50={mAP50:.4f} | val_mAP={mAP:.4f}"
        )

        if metrics["map_50"] > best_map50:
            best_map50 = metrics["map_50"]
            save_path.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(save_path)
            processor.save_pretrained(save_path)
            print(
                f"Saved new best RT-DETR checkpoint (mAP@50={best_map50:.4f}) -> {save_path}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fine-tune RT-DETR on Stage-1 street assets."
    )
    parser.add_argument("--model-id", default="PekingU/rtdetr_r50vd")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--out-dir", default="weights/rtdetr_best")
    parser.add_argument(
        "--balanced-sampler",
        action="store_true",
        help="Use WeightedRandomSampler to oversample rare classes",
    )
    args = parser.parse_args()

    train(
        model_id=args.model_id,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        imgsz=args.imgsz,
        out_dir=args.out_dir,
    )
