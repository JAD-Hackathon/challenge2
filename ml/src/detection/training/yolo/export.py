from __future__ import annotations
from pathlib import Path
import torch


def export_to_onnx(exp, best_pth: Path, onnx_out: Path) -> None:
    """Export the best YOLOX PyTorch checkpoint to standalone ONNX for inference."""
    model = exp.get_model()
    checkpoint = torch.load(best_pth, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    model.head.decode_in_inference = True

    dummy_input = torch.randn(1, 3, exp.test_size[0], exp.test_size[1])
    onnx_out.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_out),
        input_names=["images"],
        output_names=["output"],
        opset_version=13,
        dynamic_axes={"images": {0: "batch"}, "output": {0: "batch"}},
    )
    print(f"Exported ONNX model -> {onnx_out}")
