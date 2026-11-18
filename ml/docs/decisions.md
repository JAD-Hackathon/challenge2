# Aveiro Tech City — ML Pipeline Decisions

Executive summary of architectural, data, modeling, and compliance decisions across **Data Preparation**, **Object Detection**, and **Privacy Anonymization**.

---

## 1. Zero-AGPL License Compliance & Packaging
* **Decision:** Enforce permissive licenses (**Apache 2.0 / MIT**) across all runtime dependencies and model weights; strictly exclude AGPL-3.0 libraries (`ultralytics`).
* **Implementation:**
  * Adopted **Hugging Face `RT-DETR` (`PekingU/rtdetr_r50vd`, Apache 2.0)** as the primary detector and refactored `YOLODetector` to run on standalone **ONNX Runtime** (`MIT`).
  * Isolated training dependencies (`albumentations`, `torchmetrics`, `pycocotools`, `yolox`) into a `train` group in `pyproject.toml` and excluded them via `.dockerignore` for a lean production image.

---

## 2. Data Pipeline, Taxonomy & Balancing
* **Dataset:** Unified street-level captures from **Mapillary**, **KartaView**, and local Aveiro footage into `data/manifest/images.jsonl` (`train`: 513 imgs / 2,465 boxes; `val`: 156 imgs / 788 boxes; `test`: 37 imgs / 110 boxes).
* **Annotation & Taxonomy:** Accelerated labeling via automated pre-labeling + Label Studio refinement, mapped to `configs/taxonomy_pt.yaml`:
  * `traffic_sign` $\rightarrow$ `sign.other`
  * `street_lamp` $\rightarrow$ `light.street_lamp`
  * `trash_bin` $\rightarrow$ `waste.general`
* **Imbalance Mitigation:** Combined `albumentations` augmentations with class-aware oversampling (`WeightedRandomSampler`) to boost recall on rare street/underground waste bins.

---

## 3. Object Detection Benchmark & Selection
Evaluated on the `val` split (156 images):

| Model Configuration | Input | mAP@50 | mAP@50-95 | `sign.other` | `light.street_lamp` | `waste.general` | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **YOLOX-s (ONNX)** | $640^2$ | 0.5496 | 0.2856 | 0.3587 | 0.3091 | 0.1890 | 148.3 ms |
| **RT-DETR-R50vd** | $640^2$ | 0.7028 | 0.4055 | 0.4794 | 0.4457 | 0.2915 | 86.3 ms |
| **RT-DETR-R50vd** | $960^2$ | 0.7437 | 0.4307 | **0.4956** | 0.4552 | 0.3412 | 96.9 ms |
| **RT-DETR + Balanced Sampler** | $960^2$ | **0.7668** | **0.4392** | 0.4843 | **0.4777** | **0.3557** | **89.0 ms** |

* **Conclusion:** **RT-DETR ($960 \times 960$ + balanced sampling)** outperformed YOLOX-s by **+21.7% mAP@50** while running **1.66x faster** (~89 ms), lifting rare `waste.general` AP by **+6.42%** over baseline.
* **Production Checkpoint:** `weights/rtdetr_balanced_best/` (`conf: 0.30`, `iou: 0.50`, `imgsz: 960`).

---

## 4. GDPR Privacy Anonymization (`src/privacy/`)
* **Decision:** Redact human faces and license plates on-the-fly before storage or downstream serving using lightweight CPU-friendly ONNX models.
* **Implementation:**
  * **Faces:** OpenCV `FaceDetectorYN` with **YuNet** (`face.onnx`, MIT, ~228 KB) running at native image resolution.
  * **License Plates:** Standalone **ONNX Runtime** detector (`plate.onnx`) with automatic input-shape detection.
  * **Redaction:** Expands detected PII boxes by `margin: 0.2` (20%) and applies adaptive **Gaussian blur** (or pixelation/solid mask).

---

## 5. Conclusion & Team Handoff
* **Status:** Detection and GDPR privacy modules are implemented, unit-tested (`pytest`), and license-audited.
* **Weights Setup:** Checkpoints (`weights/rtdetr_balanced_best/`, `weights/face.onnx`, `weights/plate.onnx`) are excluded from Git; place them in `ml/weights/` locally or mount at container runtime.
