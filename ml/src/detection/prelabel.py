from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
import torch
from PIL import Image
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
from src.detection.helpers import xyxy_to_yolo
from src.io.common import read_manifest
from src.config import get_settings

load_dotenv()
TOKEN = os.getenv("HF_TOKEN")

paths_config = get_settings().paths

DEFAULT_MODEL_ID = "IDEA-Research/grounding-dino-base"


DEFAULT_CLASS_PROMPTS = {
    0: ["traffic sign", "road sign", "street sign"],
    1: ["street lamp", "street light", "lamp post"],
    2: ["trash bin", "garbage container", "recycling bin", "waste container"],
}


def build_prompt_mapping(
    class_prompts: dict[int, list[str]],
) -> tuple[str, dict[str, int]]:
    """Build a single dot-separated prompt string and reverse lookup map."""
    phrase_to_id: dict[str, int] = {}
    phrases: list[str] = []

    for class_id, prompts in class_prompts.items():
        for prompt in prompts:
            clean = prompt.strip().lower()
            phrase_to_id[clean] = class_id
            phrases.append(clean)

    prompt = ". ".join(phrases) + "."
    return prompt, phrase_to_id


def map_label_to_class_id(label: str, phrase_to_id: dict[str, int]) -> int | None:
    """Match model output text span back to a canonical class ID."""
    clean = label.strip().lower()
    if clean in phrase_to_id:
        return phrase_to_id[clean]
    for phrase, class_id in phrase_to_id.items():
        if phrase in clean or clean in phrase:
            return class_id
    return None


def run_prelabel(
    model_id: str = DEFAULT_MODEL_ID,
    box_threshold: float = 0.30,
    text_threshold: float = 0.25,
    overwrite: bool = False,
    limit: int | None = None,
) -> None:
    """Run zero-shot object detection on manifest images and write YOLO .txt labels."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {model_id} on {device}...")

    processor = AutoProcessor.from_pretrained(model_id, token=TOKEN)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(device)
    model.eval()

    prompt, phrase_to_id = build_prompt_mapping(DEFAULT_CLASS_PROMPTS)
    paths_config.labels_dir.mkdir(parents=True, exist_ok=True)

    classes_file = paths_config.labels_dir / "classes.txt"
    with classes_file.open("w", encoding="utf-8") as file:
        for class_id in sorted(DEFAULT_CLASS_PROMPTS):
            file.write(f"{DEFAULT_CLASS_PROMPTS[class_id][0].replace(' ', '_')}\n")

    manifest = read_manifest(paths_config.manifest_file)
    records = list(manifest.values())
    if limit is not None:
        records = records[:limit]

    processed = 0
    total_boxes = 0

    for rec in records:
        if not rec.save_path:
            continue
        img_path = paths_config.raw_dir / rec.save_path
        if not img_path.exists():
            continue

        stem = Path(img_path).stem
        label_path = paths_config.labels_dir / f"{stem}.txt"

        if label_path.exists() and not overwrite:
            continue

        with Image.open(img_path) as img:
            image = img.convert("RGB")
            img_w, img_h = image.size

        inputs = processor(
            images=image,
            text=prompt,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)

        results = processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=box_threshold,
            text_threshold=text_threshold,
            target_sizes=[(img_h, img_w)],
        )[0]

        yolo_lines = []
        for box, score, label in zip(
            results["boxes"], results["scores"], results["labels"]
        ):
            class_id = map_label_to_class_id(label, phrase_to_id)
            if class_id is None:
                continue
            xc, yc, w, h = xyxy_to_yolo(tuple(box.tolist()), img_w, img_h)
            if w <= 0.0 or h <= 0.0:
                continue
            yolo_lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

        label_path.write_text(
            "\n".join(yolo_lines) + ("\n" if yolo_lines else ""), encoding="utf-8"
        )
        processed += 1
        total_boxes += len(yolo_lines)

        if processed % 25 == 0:
            print(
                f"Processed {processed}/{len(records)} images ({total_boxes} boxes)..."
            )

    print(f"Done. Pre-labelled {processed} images with {total_boxes} total detections.")


# main section
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Zero-shot pre-labelling with Grounding DINO"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL_ID, help="HuggingFace model ID or local path"
    )
    parser.add_argument(
        "--box-thresh",
        type=float,
        default=0.30,
        help="Bounding box confidence threshold",
    )
    parser.add_argument(
        "--text-thresh", type=float, default=0.25, help="Text matching threshold"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing .txt label files"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max number of images to process"
    )
    args = parser.parse_args()

    run_prelabel(
        model_id=args.model,
        box_threshold=args.box_thresh,
        text_threshold=args.text_thresh,
        overwrite=args.overwrite,
        limit=args.limit,
    )
