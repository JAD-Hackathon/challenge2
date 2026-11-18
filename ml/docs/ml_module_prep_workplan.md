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
├── data/
│   ├── raw/                    # downloaded images + API pages
│   │   ├── mapillary/
│   │   └── kartaview/
│   ├── manifest/
│   │   └── images.jsonl        # one line per image: ids, pose, author, licence...
│   ├── labels/<image_id>.txt   # YOLO-format labels, same ID as the image (in the shared folder)
│   └── splits/                 # train / val / test lists
├── weights/hf | torch | yolo   # pretrained weights, downloaded once, not in the repo
│
├── configs/
│   ├── base.yaml               # models, thresholds, radii, methods
│   └── taxonomy_pt.yaml        # class list, ground flag, size priors
├── src/
│   ├── service/
│   │   ├── main.py             # FastAPI app, /health
│   │   ├── routes/
│   │   │   ├── routes_infer.py # POST /infer
│   │   │   └── routes_dedup.py # POST /dedup
│   │   ├── schemas.py          # pydantic models = the contract
│   │   ├── exceptions.py       # custom exceptions
│   │   └── mock.py             # ML_MOCK=1 fake responses
│   ├── io/                     # loaders: mapillary, kartaview, video frames
│   ├── privacy/                # face + plate blur
│   ├── detection/              # base.py + yolo.py, rtdetr.py
│   ├── classification/         # sign/container/lighter_classifier.py
│   ├── geometry/
│   │   ├── utils/helpers.py    # helper functions for some calculations
│   │   ├── camera.py           # intrinsics, FOV, equirect→perspective, bearing
│   │   ├── size_prior.py       # distance from known object height
│   │   ├── ground_plane.py     # ray–ground intersection
│   │   ├── depth.py            # base + depth_anything.py, metric3d.py, unidepth.py
│   │   ├── triangulation.py    # multi-ray least squares
│   │   └── geo.py              # lat/lon <-> local metric (pyproj)
│   ├── dedup/                  # clustering, tracking (ByteTrack), fusion, confidence
│   ├── pipeline.py             # orchestrates stages
│   └── cli.py                  # `ml run`, `ml eval`, `ml export`
├── eval/                       # metrics, ground-truth loader, reports
├── notebooks/                  # experiments only
├── tests/
├── Dockerfile / pyproject.toml
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
- [ ] Sign crop classifier (fine-tuned or CLIP-based) with PT class set.
- [ ] Container-type classifier (underground / island / general).
- [ ] Report: precision/recall/mAP per category on a held-out set.

### Phase 4: Privacy
- [✓] Face + plate detector wrapper and blur function (pixelate/Gaussian, with margin).
- [✓] Pipeline guarantee: **blur before saving or returning any image**; raw frames only in memory.
- [✓] Test: sample images → assert no remaining face/plate detections.

### Phase 5: Geometry and geolocation (all options)
Implement each behind a common `DistanceEstimator` interface returning `(distance_m, uncertainty_m)`.
- [ ] `camera.py`: intrinsics from FOV, bbox → bearing, equirectangular panorama → perspective crops with known heading/pitch/FOV.
- [ ] `geo.py`: local ENU projection with `pyproj`; destination point from lat/lon + bearing + distance.
- [ ] **SizePriorEstimator**: table of standard object heights (signs, lamp heights, container sizes) in config.
- [ ] **GroundPlaneEstimator**: camera height + base of bbox; flag when the base is occluded or the bbox is cropped at the image edge. Use only up to `ground_plane_max_distance_m` (~15 m) and add the height/pitch error to `uncertainty_m`.
- [ ] **DepthEstimator**: wrappers for Depth Anything V2, Metric3D/UniDepth; read depth at the bbox (median of a robust region); optional per-model scale calibration against ground truth.
- [ ] **Triangulation**: least-squares intersection of 2+ rays, with outlier rejection (RANSAC) and uncertainty.
- [ ] **Fusion strategy** (config): choose single method, or weighted combination by uncertainty, e.g. size prior + ground plane + depth, then refine with triangulation within clusters.
- [ ] Road-geometry sanity check: pull OSM road lines (Overpass); reject or snap objects that fall in the middle of the carriageway.
- [ ] **Calibrate** default camera height (and a pitch offset) per source on the ground truth (small grid search).
- [ ] **Benchmark script**: run every method on the ground-truth set and output median/90th-percentile error in metres, per category. This decides the default method at the hackathon.

### Phase 6: Deduplication and confidence
- [ ] Per-class clustering (DBSCAN/HDBSCAN) with class-specific radii in config.
- [ ] Appearance embeddings of crops (e.g. CLIP/DINOv2) as a second signal to avoid merging neighbouring identical objects.
- [ ] Ray-consistency check before merging.
- [ ] Video: ByteTrack to merge frame-to-frame detections first.
- [ ] Fused confidence = f(detector score, number of observations, view quality, geometric consistency).
- [ ] Metrics: duplicates per real object, wrong merges.

### Phase 7: Integration and robustness
- [ ] End-to-end `ml run` on the practice zone → elements JSON → import into the API's PostGIS.
- [ ] Export test: GeoJSON/CSV generated from the output.
- [ ] Batch processing with caching (don't recompute images), resumable runs, logs.
- [ ] Config switch for another zone/country (taxonomy file swap).
- [ ] Performance check: images/sec on available hardware; downsize or batch if needed.

### Phase 8: Hackathon-readiness
- [ ] README with a 5-command quickstart; Docker image tested on a clean machine.
- [ ] Cheat sheet: how to add a class, swap a model, change the distance method, retrain.
- [ ] Pre-trained weights saved locally (no dependence on downloads at the event).
- [ ] Offline fallback dataset + precomputed results for the demo zone (venue network may be unreliable).
- [ ] Provide the ML team's input for the Portuguese executive summary and PPT: models used, datasets, licences, limitations, replication steps.
- [ ] Dry-run with teammates: full flow from images to the map.

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
