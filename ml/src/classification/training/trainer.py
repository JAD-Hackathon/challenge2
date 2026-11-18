from __future__ import annotations

import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> float:
    """Run one training epoch and return the average loss."""
    model.train()
    running_loss = 0.0

    for x, y in loader:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        loss = criterion(model(x), y)
        loss.backward()
        optimizer.step()
        running_loss += loss.item() * x.size(0)

    return running_loss / len(loader.dataset)


def evaluate(
    model: nn.Module, loader: DataLoader, device: torch.device
) -> tuple[float, list[int], list[int]]:
    """Run validation and return macro-F1 score along with predictions and targets."""
    model.eval()
    all_preds: list[int] = []
    all_targets: list[int] = []

    with torch.no_grad():
        for x, y in loader:
            preds = model(x.to(device)).argmax(dim=-1).cpu().tolist()
            all_preds.extend(preds)
            all_targets.extend(y.tolist())

    macro_f1 = f1_score(all_targets, all_preds, average="macro", zero_division=0)
    return macro_f1, all_preds, all_targets
