from __future__ import annotations

import json
from pathlib import Path
from src.config import get_settings
from src.io.common import read_manifest

paths_config = get_settings().paths

OUT_JSON = paths_config.data_dir / "ls_tasks.json"
CLASSES = ["traffic_sign", "street_lamp", "trash_bin"]


def build_tasks() -> None:
    manifest = read_manifest(paths_config.manifest_file)
    tasks = []

    for rec in manifest.values():
        if not rec.save_path:
            continue
        stem = Path(rec.save_path).stem
        label_file = paths_config.labels_dir / f"{stem}.txt"
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
