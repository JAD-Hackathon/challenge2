# ML Module: Hackathon Preparation Workplan

Scope: the **ML part only** (detection, classification, privacy, geolocation, dedup). Frontend and API are separate modules, so the ML module must be **independent, pluggable and callable through a clear contract**.

> **Updated** with the revised challenge sheet and the Participants' Guide 2026.
> - Street View is **out**: imagery = **Mapillary, KartaView (CC BY-SA, attribution required) + our own videos**.
> - **No dataset is provided**: we build our own (download, label, record).
> - **Autonomy valued**: simple, local, open-source solutions; **no external APIs at runtime**; pretrained models OK.
> - Judging also rewards **ease of adoption, viability, replicability and documentation** (final: 20/20/20/10 %), so ML must be simple, reproducible and well documented, not just accurate.
> - Deliverables in **Portuguese**. Executive summary (PDF, 2 pages) due **18 Nov 19:00**; PPT + optional repo due **20 Nov 17:30**; both must list the **tools used**.

## Calendar (today is 13 Nov)
| Day | ML focus |
|-----|----------|
| **13–15 Nov (prep, ~3 days)** | Phases 1, 2 (partly), 3 baseline, 4, 5 core (size prior, ground plane, bearing/geo), benchmark script, Docker, Mapillary token + sample download |
| **16 Nov evening** | Clarify questions at Q&A, choose pilot zone, start downloading/recording data |
| **17 Nov** | Fine-tune on local labels, end-to-end run, draft ML part of executive summary (tools + licences) |
| **18 Nov** | Mentor checkpoint (14:00–18:30): demonstrate vertical slice; executive summary due 19:00 |
| **19 Nov** | Dedup, triangulation, depth comparison, evaluation numbers, README |
| **20 Nov** | Freeze, precompute demo, support the pitch (16:00 and, if selected, 18:00) |

**With only ~3 prep days, follow the priority list in section 4 strictly.** Phases are listed by priority, not by day.

Goal of preparation: arrive at the hackathon with a **working template** where every option (size prior, ground plane, depth, triangulation) is already implemented behind one interface, so during the event we only swap data, fine-tune and tune parameters.

---

## 0. Design principles
1. **One interface per stage**, many interchangeable implementations (config-selected).
2. **Config-driven** (YAML): zone, class taxonomy, models, thresholds. No hardcoding, so it generalises to other municipalities.
3. **Pure functions + typed schemas** (pydantic): easy for the API teammate to integrate.
4. **Privacy first**: blur runs before anything is saved.
5. **Everything measurable**: one evaluation script from day one.
6. **Small and fast models by default**, swappable for bigger ones.

---

## 1. Repository layout (template)

```
ml/
├── configs/
│   ├── base.yaml                       # models, thresholds, radii, geometry methods
│   └── taxonomy_pt.yaml                # class taxonomy, ground flags, size priors
├── data/
│   ├── raw/                            # KartaView & KartaView imagery
│   ├── manifest/images.jsonl           # image metadata: IDs, GPS pose, author, licence
│   ├── labels/<image_id>.txt           # YOLO-format Stage-1 bounding box annotations
│   ├── splits/                         # train.txt / val.txt / test.txt
│   └── crops/                          # extracted crops & ImageFolder datasets (sign/light/waste)
├── docs/
│   ├── benchmarks/                     # evaluation reports & metrics
│   ├── contract/                       # API & integration specifications
│   ├── licenses/                       # THIRD_PARTY_LICENSES.md (Apache 2.0 / MIT compliance)
│   ├── data_contract.md
│   └── decisions.md                    # architecture & model selection log
├── weights/                            # model checkpoints & exported ONNX graphs (gitignored)
├── src/
│   ├── service/                        # FastAPI microservice layer
│   │   ├── main.py                     # app factory & /health endpoint
│   │   ├── routes/                     # infer_routes.py (POST /infer), dedup_routes.py (POST /dedup)
│   │   ├── schemas.py                  # Pydantic request/response contracts
│   │   ├── exceptions.py               # domain-specific HTTP exceptions
│   │   └── mock.py                     # ML_MOCK=1 synthetic responses
│   ├── io/                             # data ingestion & manifest utilities
│   │   ├── common.py                   # ImageRecord schema & JSONL manifest I/O
│   │   ├── mapillary.py                # Mapillary API downloader
│   │   └── kartaview.py                # KartaView API downloader
│   ├── privacy/                        # GDPR anonymization stage
│   │   ├── anonymizer.py               # orchestrator for face & plate redaction
│   │   ├── blur.py                     # Gaussian / pixelate / black blur kernels
│   │   └── detectors/                  # face.py (YuNet), plate.py (ONNX)
│   ├── detection/                      # Stage-1 coarse object detection
│   │   ├── base.py                     # Detector ABC, Detection schema, registry
│   │   ├── rtdetr.py                   # HuggingFace RT-DETR backend
│   │   ├── training/                   # common/ (COCO export, metrics), rtdetr/, yolo/
│   │   └── utils/                      # prepare_split.py, export_ls.py, prelabel.py
│   ├── classification/                 # Stage-2 fine-grained subclass refinement
│   │   ├── base.py                     # CropClassifier ABC
│   │   ├── onnx_classifier.py          # ONNXCropClassifier & MultiCategoryClassifier
│   │   ├── training/                   # dataset.py, trainer.py, train.py, export.py, metrics.py
│   │   └── utils/                      # extract_crops.py, prepare_dataset.py (LS + GTSRB)
│   ├── geometry/                       # 3D localization & coordinate transforms
│   │   ├── base.py                     # DistanceEstimator ABC
│   │   ├── localizer.py                # Single-view 3D geolocation orchestrator
│   │   ├── size_prior.py               # distance estimation from known physical dimensions
│   │   ├── ground_plane.py             # ray-ground intersection for grounded objects
│   │   ├── depth.py                    # monocular depth estimator interface & backends
│   │   ├── triangulation.py            # multi-view ray least-squares triangulation
│   │   └── utils/
|   |       ├── helpers.py              # vector math helpers
|   |       ├── geo.py                  # lat/lon ↔ ENU projection, bearing, destination point
|   |       └── camera.py               # intrinsics, FOV, equirect -> perspective, ray bearing
│   ├── dedup/                          # spatial-temporal deduplication & fusion
│   │   └── utils/dedup_images.py       # image-level deduplication utilities
│   ├── config.py                       # Pydantic settings loader & YAML/env overrides
│   ├── taxonomy.py                     # Portuguese urban asset taxonomy & size priors
│   ├── pipeline.py                     # end-to-end inference pipeline orchestrator
│   └── cli.py                          # CLI entrypoints (`ml run`, `ml eval`, `ml export`)
├── tests/                              # pytest suite (classification, detection, privacy, general)
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 2. Contract with the API module (agree this first)

Two integration options. Prefer **A** for the hackathon; keep **B** as fallback.

- **A. Python service with endpoint(s):** `POST /infer` (image + camera metadata → observations), `POST /process-zone` (batch job → elements written to DB).
- **B. Batch CLI writing to PostGIS directly:** `ml run --zone zone.geojson --config default.yaml`.

---

## 3. Phased plan

Phases are ordered by priority, not fixed dates. Adjust to the number of days before the hackathon.

### Phase 1: Foundations (do first)
- [✓] Repo skeleton, `pyproject`, Docker image with GPU/CPU variants, pre-commit, tests.
- [✓] Pydantic schemas and config loader.
- [✓] Agree and freeze the **API contract** with teammates; publish an OpenAPI/JSON example file.
- [✓] Mock endpoint returning fake observations so frontend/API are not blocked.
- [✓] Check compute: local GPU? Colab/Kaggle? Note limits.

### Phase 2: Data and ground truth
- [✓] Pick a **practice zone** in Aveiro (a street with signs, lamps, ecopontos). (--bbox="-8.660,40.636,-8.648,40.645" + --bbox="-8.6585,40.6395,-8.6545,40.6430")
- [✓] Create a free **Mapillary developer token**; download a small sample (images + metadata: position, compass angle, camera type, author, licence) for candidate streets; test KartaView; ~~record a short own video with GPS log~~.
- [✓] Keep **author + licence per image** (CC BY-SA attribution) and start the **tools and licences list** needed for the deliverables.
- [✓] Check Mapillary coverage density per candidate street; this decides the pilot zone.
- [✓] Build a **ground-truth set**: manually mark ~30–50 objects (class + lat/lon) per category in the practice zone.
- [✓] Collect public datasets: MTSD, GTSDB/GTSRB, Mapillary Vistas (check licences), Open Images street-furniture classes.
- [✓] Write the **label mapping** inside the dataset conversion script (public labels, e.g. MTSD → our classes in `taxonomy_pt.yaml`).
- [✓] Set up annotation tool (CVAT or Label Studio); start labelling lamps and waste containers (these have no ready dataset).

### Phase 3: Detection and classification
- [✓] Detector wrapper (base interface) + pretrained baseline for signs.
- [✓] Add a second detector implementation (e.g. RT-DETR vs YOLO) and compare. Watch the licences (Ultralytics is AGPL).
- [✓] Open-vocabulary pre-labelling script (Grounding DINO / OWLv2 / YOLO-World + SAM) for lamps and waste.
- [✓] Training script for fine-tuning (config-driven, logs to a local tracker such as MLflow or W&B).
- [✓] Sign crop classifier (fine-tuned or CLIP-based) with PT class set.
- [✓] Container-type classifier (underground / island / general).
- [✓] Report: precision/recall/mAP per category on a held-out set.

### Phase 4: Privacy
- [✓] Face + plate detector wrapper and blur function (pixelate/Gaussian, with margin).
- [✓] Pipeline guarantee: **blur before saving or returning any image**; raw frames only in memory.
- [✓] Test: sample images → assert no remaining face/plate detections.

### Phase 5: Geometry and geolocation (all options)
Implement each behind a common `DistanceEstimator` interface returning `(distance_m, uncertainty_m)`.
- [✓] `camera.py`: intrinsics from FOV, bbox → bearing, equirectangular panorama → perspective crops with known heading/pitch/FOV.
- [✓] `geo.py`: local ENU projection with `pyproj`; destination point from lat/lon + bearing + distance.
- [✓] **SizePriorEstimator**: table of standard object heights (signs, lamp heights, container sizes) in config.
- [✓] **GroundPlaneEstimator**: camera height + base of bbox; flag when the base is occluded or the bbox is cropped at the image edge. Use only up to `ground_plane_max_distance_m` (~15 m) and add the height/pitch error to `uncertainty_m`.
- [✓] **DepthEstimator**: wrappers for Depth Anything V2, Metric3D/UniDepth; read depth at the bbox (median of a robust region); optional per-model scale calibration against ground truth.
- [✓] **Triangulation**: least-squares intersection of 2+ rays, with outlier rejection (RANSAC) and uncertainty.
- [✓] **Fusion strategy** (config): choose single method, or weighted combination by uncertainty, e.g. size prior + ground plane + depth, then refine with triangulation within clusters.

### Phase 6: Deduplication and confidence
- [ ] Per-class spatial clustering with `dedup.radius_m` (`sign`, `light`, `waste`) + multi-view ray triangulation.
- [ ] Ray-consistency check (`dedup.use_ray_check: true`) before merging observations.
- [ ] Preserve `verified` and `corrected` elements from `existing_elements` untouched.
- [ ] Fused confidence aggregation (detector scores, observation count, geometric consistency, capped at `max_confidence`).

### Phase 7: Integration and robustness
- [ ] Connect `dedup` logic to `POST /dedup` and disable mock mode (`service.mock: false`).
- [ ] Config switch test for another zone/taxonomy file (`configs/taxonomy_pt.yaml`).
- [ ] Performance check: end-to-end `/infer` + `/dedup` latency in Docker on target hardware.

### Phase 8: Hackathon-readiness
- [ ] README with a 5-command quickstart; Docker Compose tested cleanly (`ML_MOCK=false`).
- [ ] All weights (`rtdetr_balanced_best/`, `*_cls.onnx`, `face.onnx`, `plate.onnx`) saved locally for 100% offline run.
- [ ] Offline fallback dataset + precomputed `/infer` and `/dedup` JSON results for the Aveiro demo zone.
- [ ] ML slides/input for the final PPT: architecture, models, datasets, licences (zero-AGPL), and limitations.
- [ ] Dry-run with teammates: full flow from images → `/infer` → `/dedup` → map.

---

## 4. Priorities if time is short
**Must have:** schemas and contract, Mapillary downloader with attribution fields, sign detector baseline, blur, size-prior + ground-plane geolocation, basic clustering dedup + triangulation within clusters, benchmark script, Docker.
**Should have:** fine-tuned lamp and waste detectors, depth estimator, evaluation report.
**Nice to have:** video tracking, appearance embeddings, active learning, OSM snapping.

---

## 5. Open questions for you and your team
1. Integration style: HTTP service (A) or batch writing to PostGIS (B)? Who owns dedup?
2. How many days/hours do you have before the hackathon, and what hardware (GPU)?
3. Which streets have good Mapillary/KartaView coverage, and do we record our own video (permissions, GPS logger)?
4. Do you have a practice zone chosen?
5. Do you want a minimal internal debug UI (e.g. Streamlit/Gradio) to visualise detections and positions, independent of the real frontend?

---

## 6. Risks specific to the ML side
| Risk | Mitigation |
|------|-----------|
| Depth model gives wrong scale | Calibrate on ground truth; prefer metric models; fall back to size prior/ground plane |
| Camera height / pitch unknown (ground plane) | Default height per source, calibrate on ground truth, short range only, large uncertainty; rely on size prior and triangulation |
| No data for lamps/waste | Start labelling early; open-vocab pre-labelling |
| Sign classes mismatch with Portuguese codes | Taxonomy mapping + small fine-tune on local images |
| Sparse or poor-quality crowd-sourced imagery | Choose zone by coverage; own video; handle fisheye/unknown intrinsics per sequence |
| Scoring rewards adoption/replicability/docs | README, Docker, config switch, simple models, honest limitations |
| External API dependence | Download data and weights beforehand; everything runs offline |
| Dedup merges neighbours | Class radii + appearance + ray consistency, tune on ground truth |
| Integration surprises at the event | Frozen contract, mock endpoint, dry run |
