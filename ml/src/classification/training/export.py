from __future__ import annotations

import json
from pathlib import Path

import onnx
import torch
import torch.nn as nn


def export_onnx(
    model: nn.Module,
    out_path: Path,
    img_size: int,
    classes: list[str],
    device: torch.device,
) -> None:
    """Export PyTorch classifier to ONNX with dynamic batch size and embedded class names."""
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size, device=device)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=18,
        dynamo=False,
    )

    onnx_model = onnx.load(str(out_path))
    meta = onnx_model.metadata_props.add()
    meta.key = "classes"
    meta.value = json.dumps(classes)
    onnx.save(onnx_model, str(out_path))
