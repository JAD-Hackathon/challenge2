# Third-Party Licenses & Attribution

This document lists external pretrained models, libraries, and data sources used in the Aveiro Tech City ML pipeline, along with their respective licenses.

---

## 1. Machine Learning Models & Weights

### Object Detection (Inference & Fine-Tuning)
* **RT-DETR (`PekingU/rtdetr_r50vd` / `PekingU/rtdetr_r18vd`)**
  * **Source:** Hugging Face Hub / PaddleDetection (`transformers` implementation)
  * **License:** Apache-2.0
  * **Usage:** Primary production object detector fine-tuned on street-level assets (`sign`, `light`, `waste`).

* **YOLO (YOLOX / YOLOv9-MIT / ONNX Runtime backend)**
  * **Source:** Megvii-BaseDetection (`YOLOX`) / WongKinYiu (`YOLOv9`, Apache-2.0 / GPL-3.0 — using permissive weights/architecture only; excluding `ultralytics` AGPL-3.0 dependencies)
  * **License:** Apache-2.0 / MIT
  * **Usage:** Alternative lightweight object detection backend for benchmarking accuracy vs. latency.

### Dataset Pre-Labelling (Offline Tooling Only)
* **Grounding DINO (`IDEA-Research/grounding-dino-base` / `grounding-dino-tiny`)**
  * **Source:** Hugging Face Hub / IDEA-Research
  * **License:** Apache-2.0
  * **Usage:** Used strictly offline during dataset preparation to generate initial zero-shot bounding box proposals prior to manual human verification in Label Studio. Not bundled or executed in the production inference service.

---

## 2. Street-Level Imagery Data Sources

* **Mapillary**
  * **Source:** Mapillary Graph API (`https://www.mapillary.com/`)
  * **License:** CC BY-SA 4.0
  * **Attribution & Compliance:** Street-level imagery is owned by its respective contributors and licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). Raw images are excluded from version control and anonymized (faces and license plates blurred) before any downstream visual display.

* **KartaView**
  * **Source:** KartaView API (`https://kartaview.org/`)
  * **License:** CC BY-SA 4.0
  * **Attribution & Compliance:** Crowd-sourced street-level imagery licensed under CC BY-SA 4.0. Used for training dataset construction and spatial asset deduplication.

---

## 3. Core Python Dependencies

Core runtime dependencies are managed via `pyproject.toml` and `uv.lock`, relying on permissive open-source licenses:
* **PyTorch & Torchvision:** BSD-3-Clause
* **Hugging Face Transformers:** Apache-2.0
* **FastAPI / Pydantic / Uvicorn:** MIT
* **OpenCV (`opencv-python-headless`):** Apache-2.0
* **NumPy / SciPy / Scikit-learn / Pillow:** BSD-3-Clause / HPND
