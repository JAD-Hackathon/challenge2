from __future__ import annotations

import argparse
from pathlib import Path

import torch

from src.config import get_settings
from src.detection.training.yolo.exp import build_yolox_exp
from src.detection.training.yolo.export import export_to_onnx
from src.detection.training.common.coco_export import export_all
from src.detection.training.common.dataset import validate_stage1_taxonomy
from src.taxonomy import get_taxonomy


def train(
    arch: str = "yolox-s",
    checkpoint_path: str | None = None,
    epochs: int = 30,
    b_size: int = 8,
    imgsz: int = 640,
    out_dir: str = "weights/yolox_runs",
    onnx_out: str = "weights/yolox_best.onnx",
) -> None:
    """Train a YOLOX model on the Stage-1 Aveiro dataset."""
    settings = get_settings()
    taxonomy = get_taxonomy()
    validate_stage1_taxonomy(taxonomy)

    export_all()
    coco_dir = settings.paths.data_dir / "coco"

    run_dir = Path(out_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    exp = build_yolox_exp(arch, coco_dir, imgsz, epochs, run_dir)

    from yolox.core import Trainer

    class Args:
        experiment_name = arch
        name = arch
        dist_backend = "nccl"
        dist_url = None
        batch_size = b_size
        devices = 1 if torch.cuda.is_available() else 0
        checkpoint = checkpoint_path
        resume = False
        start_epoch = None
        num_machines = 1
        machine_rank = 0
        fp16 = torch.cuda.is_available()
        cache = None
        occupy = False
        logger = "tensorboard"
        opts = []

    trainer = Trainer(exp, Args())
    trainer.train()

    best_pth = run_dir / arch / "best_checkpoint.pth"
    if best_pth.exists():
        export_to_onnx(exp, best_pth, Path(onnx_out))
    else:
        print(f"best_checkpoint.pth not found at {best_pth}; skipping ONNX export.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train YOLOX (Apache-2.0) on Stage-1 Aveiro."
    )
    parser.add_argument(
        "--arch",
        default="yolox-s",
        choices=["yolox-nano", "yolox-tiny", "yolox-s", "yolox-m", "yolox-l"],
    )
    parser.add_argument(
        "--checkpoint", default=None, help="Path to pretrained COCO yolox_*.pth weights"
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--out-dir", default="weights/yolox_runs")
    parser.add_argument("--onnx-out", default="weights/yolox_best.onnx")
    args = parser.parse_args()

    train(
        arch=args.arch,
        checkpoint_path=args.checkpoint,
        epochs=args.epochs,
        b_size=args.batch_size,
        imgsz=args.imgsz,
        out_dir=args.out_dir,
        onnx_out=args.onnx_out,
    )
