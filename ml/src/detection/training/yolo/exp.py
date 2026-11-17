from __future__ import annotations
from pathlib import Path
from src.detection.training.common.dataset import STAGE1_ID2LABEL


def build_yolox_exp(
    arch: str,
    coco_dir: Path,
    imgsz: int,
    max_epoch: int,
    out_dir: Path,
):
    """Build a customized YOLOX experiment configuration."""
    from yolox.exp import Exp

    depth_width = {
        "yolox-nano": (0.33, 0.25),
        "yolox-tiny": (0.33, 0.375),
        "yolox-s": (0.33, 0.50),
        "yolox-m": (0.67, 0.75),
        "yolox-l": (1.00, 1.00),
    }
    if arch not in depth_width:
        raise ValueError(
            f"Unsupported YOLOX arch '{arch}'. Choose from {list(depth_width)}"
        )

    depth, width = depth_width[arch]

    class AveiroYOLOXExp(Exp):
        def __init__(self) -> None:
            super().__init__()
            self.depth = depth
            self.width = width
            self.num_classes = len(STAGE1_ID2LABEL)
            self.exp_name = arch

            self.data_dir = str(coco_dir)
            self.train_ann = str(coco_dir / "instances_train.json")
            self.val_ann = str(coco_dir / "instances_val.json")

            self.input_size = (imgsz, imgsz)
            self.test_size = (imgsz, imgsz)
            self.max_epoch = max_epoch
            self.warmup_epochs = 2
            self.no_aug_epochs = max(2, max_epoch // 5)
            self.eval_interval = 1
            self.print_interval = 20
            self.output_dir = str(out_dir)

            # data augmentations
            self.mosaic_prob = 0.8
            self.mixup_prob = 0.2
            self.hsv_prob = 1.0
            self.flip_prob = 0.5
            self.degrees = 5.0
            self.scale = (0.8, 1.2)

        def get_dataset(self, cache: bool = False, cache_type: str = "ram"):
            from yolox.data import COCODataset, TrainTransform

            return COCODataset(
                data_dir="",
                json_file=self.train_ann,
                name="",
                img_size=self.input_size,
                preproc=TrainTransform(
                    max_labels=50,
                    flip_prob=self.flip_prob,
                    hsv_prob=self.hsv_prob,
                ),
                cache=cache,
                cache_type=cache_type,
            )

        def get_eval_dataset(self, **kwargs):
            from yolox.data import COCODataset, ValTransform

            return COCODataset(
                data_dir="",
                json_file=self.val_ann,
                name="",
                img_size=self.test_size,
                preproc=ValTransform(legacy=False),
            )

    return AveiroYOLOXExp()
