from __future__ import annotations

import argparse
from pathlib import Path

import timm
import torch
import torch.nn as nn
from sklearn.metrics import classification_report

from src.classification.training.dataset import create_dataloaders
from src.classification.training.trainer import train_one_epoch, evaluate
from src.classification.training.export import export_onnx


def main() -> None:
    """Train a 2nd-stage crop classifier and export the best macro-F1 model to ONNX."""
    parser = argparse.ArgumentParser(
        description="Train crop classifier and export to ONNX."
    )
    parser.add_argument(
        "--data-dir", type=Path, required=True, help="Path with train/ and val/ subdirs"
    )
    parser.add_argument(
        "--out-onnx", type=Path, required=True, help="Output .onnx path"
    )
    parser.add_argument("--arch", type=str, default="mobilenetv3_large_100")
    parser.add_argument("--img-size", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument(
        "--no-hflip",
        action="store_true",
        help="Disable horizontal flip (use for signs)",
    )
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # data
    train_loader, val_loader, classes = create_dataloaders(
        args.data_dir, args.img_size, args.batch_size, allow_hflip=not args.no_hflip
    )

    # model / opt
    model = timm.create_model(args.arch, pretrained=True, num_classes=len(classes)).to(
        device
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-2)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # training
    best_f1 = -1.0
    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)
        scheduler.step()

        macro_f1, all_preds, all_targets = evaluate(model, val_loader, device)
        print(
            f"Epoch {epoch:02d}/{args.epochs} | train_loss={train_loss:.4f} | val_macro_f1={macro_f1:.4f}"
        )

        if macro_f1 > best_f1:
            best_f1 = macro_f1
            export_onnx(model, args.out_onnx, args.img_size, classes, device)
            print(f"  -> Saved best ONNX ({best_f1:.4f}) to {args.out_onnx}")
            print(
                classification_report(
                    all_targets, all_preds, target_names=classes, zero_division=0
                )
            )


if __name__ == "__main__":
    main()
