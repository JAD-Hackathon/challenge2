# Aveiro Tech City — ML Pipeline Decisions

Executive summary of architectural, data, modeling, and compliance decisions across **Data Preparation**, **Object Detection**, **2-Stage Fine-Grained Classification**, and **Privacy Anonymization**.

---

## 1. Zero-AGPL License Compliance & Packaging
* **Decision:** Enforce permissive licenses (**Apache 2.0 / MIT**) across all runtime dependencies and model weights; strictly exclude AGPL-3.0 libraries (`ultralytics`).
* **Implementation:**
  * Adopted **Hugging Face `RT-DETR` (`PekingU/rtdetr_r50vd`, Apache 2.0)** as the primary Stage-1 detector and refactored `YOLODetector` to run on standalone **ONNX Runtime** (`MIT`).
  * Built Stage-2 fine-grained classifiers using **`timm` (`MobileNetV3-Large`, Apache 2.0)** exported to standalone **ONNX Runtime** graphs (`weights/*_cls.onnx`), isolating training dependencies (`albumentations`, `torchmetrics`, `pycocotools`, `yolox`, `timm`, `onnx`) in the `train` dependency group and excluding them via `.dockerignore`.

---

## 2. Data Pipeline, Taxonomy & Balancing
* **Dataset:** Unified street-level captures from **Mapillary**, **KartaView**, and local Aveiro footage (`data/raw/custom/`, registered via `src/io/custom.py`) into `data/manifest/images.jsonl` (`train`: 513+ imgs / 2,465+ boxes; `val`: 156 imgs / 788 boxes; `test`: 37 imgs / 110 boxes).
* **Annotation & Taxonomy:** Accelerated labeling via automated pre-labeling + Label Studio refinement, mapped to `configs/taxonomy_pt.yaml`:
  * `traffic_sign` $\rightarrow$ `sign.*` (`sign.stop`, `sign.yield`, `sign.speed_limit`, `sign.other`)
  * `street_lamp` $\rightarrow$ `light.*` (`light.street_lamp`, `light.street_pole`)
  * `trash_bin` $\rightarrow$ `waste.*` (`waste.general`, `waste.recycling_island`, `waste.underground`)
* **Imbalance Mitigation:** Combined augmentations with class-aware oversampling (`WeightedRandomSampler`) and external **GTSRB** enrichment for rare traffic sign subclasses.

---

## 3. Stage-1 Object Detection Benchmark & Selection
* **Architecture:** **RT-DETR-R50vd ($960 \times 960$ + balanced sampling)** (`weights/rtdetr_balanced_best/`, `conf: 0.30`, `iou: 0.50`) outperformed the YOLOX-s ONNX baseline (`mAP@50: 0.5496`, `148.3 ms`) in both accuracy and speed.
* **Final Benchmark (`rtdetr_balanced_best`):**
  * **Validation (`val`):** `mAP@50 = 0.7300`, `mAP@50-95 = 0.4470`, latency `92.37 ms` (`AP_sign.other: 0.5031`, `AP_light.street_lamp: 0.5317`, `AP_waste.general: 0.3062`).
  * **Held-out Test (`test`):** `mAP@50 = 0.7645`, `mAP@50-95 = 0.5359`, latency `93.74 ms` (`AP_sign.other: 0.5085`, `AP_light.street_lamp: 0.5733`, `AP_waste.general: 0.5259`).

---

## 4. Stage-2 Fine-Grained Crop Classification (`src/classification/`)
* **Decision:** Decouple coarse localization from subclass classification via lightweight per-category **ONNX Runtime** classifiers (`MultiCategoryClassifier`) with embedded `classes` metadata and automatic fallback to Stage-1 coarse labels when confidence `< 0.60`.
* **Architecture & Validation (`val` split):** `mobilenetv3_large_100` (`128x128` for signs without horizontal flip; `224x224` for lighting and waste):
  * **Signs (`weights/sign_cls.onnx`, $N=529$):** `accuracy = 0.9905`, `macro_f1 = 0.9574`, latency `3.04 ms/crop`.
  * **Lighting (`weights/lighting_cls.onnx`, $N=16$):** `accuracy = 1.0000`, `macro_f1 = 1.0000`, latency `5.80 ms/crop`.
  * **Waste (`weights/waste_cls.onnx`, $N=113$):** `accuracy = 0.8053`, `macro_f1 = 0.7629`, latency `5.33 ms/crop`.

---

## 5. GDPR Privacy Anonymization (`src/privacy/`)
* **Decision:** Redact human faces and license plates on-the-fly before storage or downstream serving using lightweight CPU-friendly ONNX models.
* **Implementation:** OpenCV `FaceDetectorYN` with **YuNet** (`face.onnx`, MIT) + standalone **ONNX Runtime** license plate detector (`plate.onnx`), expanding PII boxes by `margin: 0.2` with adaptive **Gaussian blur**.

---

## 6. 3D Geospatial Localization & Triangulation (`src/geometry/`)
* **Decision:** Estimate real-world WGS84 coordinates (`est_lat`, `est_lon`) and 1-sigma positional uncertainty (`uncertainty_m`) purely offline without external runtime APIs, combining physical priors, projective ground-plane geometry, and multi-view ray triangulation.
* **Implementation:**
  * **Camera Optics & Bearing (`camera.py`, `base.py`):** Unified `CameraFrame` abstraction supporting both `perspective` (pinhole focal length from `hfov_deg`) and `equirectangular` ($360^\circ$ spherical panoramas) projections.
  * **Single-View Distance Estimators (`size_prior.py`, `ground_plane.py`, `depth.py`):**
    * `SizePriorEstimator`: Computes distance from apparent pixel width/height and taxonomy priors (`configs/taxonomy_pt.yaml`), rejecting border-truncated and sub-threshold (`< min_box_px`) detections.
    * `GroundPlaneEstimator`: Intersects bottom-center rays with flat ground for `ground: true` assets (`light.*`, `waste.*`, including size-less `waste.underground`) up to `ground_plane_max_distance_m: 15.0 m`, propagating camera height and pitch uncertainties.
    * `DepthEstimator`: Optional pluggable ONNX monocular depth backend sampling inner-bbox median depth.
  * **Inverse-Variance Fusion & WGS84 Projection (`localizer.py`, `geo.py`):** Combines valid single-view estimates via inverse-variance weighting ($w_i = 1/\sigma_i^2$), projects coordinates onto the WGS84 ellipsoid via `pyproj.Geod`, and propagates radial, bearing, and GPS uncertainties into total `uncertainty_m`.
  * **Multi-View Triangulation (`triangulation.py`):** Refines clustered cross-frame observations in local tangent metric coordinates (`LocalENU`) via weighted least-squares ray intersection with parallax angle (`min_angle_deg`), cheirality, and residual checks.

---

## 7. Conclusion & Team Handoff
* **Status:** Stage-1 detection, Stage-2 fine-grained classification, GDPR privacy, and 3D geospatial localization modules are implemented, unit-tested (`pytest`), and license-audited.
* **Weights Setup:** Place `rtdetr_balanced_best/`, `sign_cls.onnx`, `waste_cls.onnx`, `lighting_cls.onnx`, `face.onnx`, and `plate.onnx` in `ml/weights/` locally or mount at container runtime.
