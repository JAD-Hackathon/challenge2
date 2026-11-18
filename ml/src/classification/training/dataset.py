from __future__ import annotations

from pathlib import Path

import torch
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, transforms


def build_transforms(
    img_size: int, allow_hflip: bool
) -> tuple[transforms.Compose, transforms.Compose]:
    """Create train and validation image transforms for crop classification."""
    train_ops: list[object] = [
        transforms.Resize((img_size, img_size)),
        transforms.ColorJitter(
            brightness=0.25, contrast=0.25, saturation=0.2, hue=0.05
        ),
        transforms.RandomAffine(degrees=10, translate=(0.05, 0.05), scale=(0.9, 1.1)),
    ]
    if allow_hflip:
        train_ops.insert(1, transforms.RandomHorizontalFlip(p=0.5))

    norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    train_tf = transforms.Compose([*train_ops, transforms.ToTensor(), norm])
    val_tf = transforms.Compose(
        [transforms.Resize((img_size, img_size)), transforms.ToTensor(), norm]
    )
    return train_tf, val_tf


def make_balanced_sampler(dataset: datasets.ImageFolder) -> WeightedRandomSampler:
    """Compute inverse-frequency sample weights for imbalanced classes."""
    targets = dataset.targets
    class_counts = torch.bincount(torch.tensor(targets))
    class_weights = 1.0 / class_counts.float().clamp(min=1)
    sample_weights = [class_weights[t].item() for t in targets]
    return WeightedRandomSampler(
        sample_weights, num_samples=len(sample_weights), replacement=True
    )


def create_dataloaders(
    data_dir: Path,
    img_size: int,
    batch_size: int,
    allow_hflip: bool,
    num_workers: int = 2,
) -> tuple[DataLoader, DataLoader, list[str]]:
    """Initialize datasets and dataloaders for training and validation."""
    train_tf, val_tf = build_transforms(img_size, allow_hflip)

    train_ds = datasets.ImageFolder(data_dir / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(data_dir / "val", transform=val_tf)

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        sampler=make_balanced_sampler(train_ds),
        num_workers=num_workers,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )

    return train_loader, val_loader, train_ds.classes
