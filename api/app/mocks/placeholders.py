"""Draws the seed images: a fake street scene with each element as a coloured, labelled box,
so cropping an element's bbox_xyxy in the web shows something recognisable."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

SIZE = (1024, 768)
COLOURS = {"sign": (200, 40, 40), "light": (230, 180, 30), "waste": (40, 140, 70)}


def draw(path: Path, image_id: str, elements: Iterable[Mapping[str, Any]]) -> None:
    """elements: dicts with 'type' (ML class), 'attributes' and 'bbox_xyxy'."""
    width, height = SIZE
    image = Image.new("RGB", SIZE)
    canvas = ImageDraw.Draw(image)
    horizon = int(height * 0.55)
    for y in range(horizon):  # sky
        shade = int(150 + 80 * y / horizon)
        canvas.line([(0, y), (width, y)], fill=(shade - 40, shade - 10, shade + 20))
    canvas.rectangle([0, horizon, width, height], fill=(95, 95, 100))  # road
    canvas.rectangle([0, horizon, width, horizon + 25], fill=(160, 155, 150))  # sidewalk

    font = ImageFont.load_default(size=18)
    for element in elements:
        x1, y1, x2, y2 = element["bbox_xyxy"]
        category = element["type"].split(".")[0]
        canvas.rectangle([x1, y1, x2, y2], fill=COLOURS.get(category, (90, 90, 160)))
        label = element["type"]
        if limit := element.get("attributes", {}).get("limit"):
            label += f" {limit}"
        canvas.text(
            (x1, max(0, y1 - 22)),
            label,
            fill="white",
            font=font,
            stroke_width=2,
            stroke_fill="black",
        )

    canvas.text(
        (12, 10),
        f"MOCK IMAGE  {image_id}",
        fill="white",
        font=font,
        stroke_width=2,
        stroke_fill="black",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=85)
