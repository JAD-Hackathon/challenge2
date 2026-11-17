from __future__ import annotations

import json
from pathlib import Path
from src.io.common import DATA_DIR, MANIFEST_PATH, read_manifest

LABELS_DIR = DATA_DIR / "labels"
OUT_JSON = DATA_DIR / "ls_tasks.json"
CLASSES = ["traffic_sign", "street_lamp", "trash_bin"]


def build_tasks() -> None:
    manifest = read_manifest(MANIFEST_PATH)
    tasks = []

    for rec in manifest.values():
        if not rec.save_path:
            continue
        stem = Path(rec.save_path).stem
        label_file = LABELS_DIR / f"{stem}.txt"
        if not label_file.exists():
            continue

        predictions = []
        for line in label_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cid_s, xc_s, yc_s, w_s, h_s = line.split()
            cid = int(cid_s)
            if cid >= len(CLASSES):
                continue
            xc, yc, w, h = float(xc_s), float(yc_s), float(w_s), float(h_s)
            predictions.append(
                {
                    "from_name": "label",
                    "to_name": "image",
                    "type": "rectanglelabels",
                    "value": {
                        "x": (xc - w / 2.0) * 100.0,
                        "y": (yc - h / 2.0) * 100.0,
                        "width": w * 100.0,
                        "height": h * 100.0,
                        "rectanglelabels": [CLASSES[cid]],
                    },
                }
            )

        rel_url_path = rec.save_path.replace("\\", "/")
        tasks.append(
            {
                "data": {"image": f"/data/local-files/?d=raw/{rel_url_path}"},
                "predictions": [{"result": predictions}] if predictions else [],
            }
        )

    OUT_JSON.write_text(json.dumps(tasks, indent=2), encoding="utf-8")
    print(f"Exported {len(tasks)} tasks to {OUT_JSON}")


if __name__ == "__main__":
    build_tasks()
