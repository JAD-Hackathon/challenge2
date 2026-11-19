# Aveiro Tech City — ML Pipeline Future Improvements & Roadmap

This document outlines potential enhancements, architectural extensions, and accuracy optimizations that go beyond the current MVP scope (`ml/`) and can be prioritized in subsequent iterations of the project.

---

## 1. Dataset Expansion & Multi-Source Diversity
* **Multi-Source Street Imagery:** Expand the training and validation sets (`data/manifest/images.jsonl`) with additional captures from **Mapillary**, **KartaView**, and locally recorded dashcam/smartphone video sequences across diverse districts of Aveiro (historic center, coastal zones, industrial avenues, and residential streets).
* **Environmental & Lighting Robustness:** Collect footage under varied weather and lighting conditions (overcast skies, harsh low-angle sunlight, dusk/night, wet asphalt reflections) to reduce false negatives on dark metal poles (`light.street_pole`) and weathered bins (`waste.general`).
* **Rare Class Balancing:** Increase real-world sample counts for underrepresented subclasses—especially `light.street_pole` ($N=16$ in current validation) and `waste.underground`—to reduce reliance on synthetic oversampling.

---

## 2. Taxonomy Expansion & Fine-Grained Subclasses
* **Granular Traffic Sign Subclasses (`sign.*`):** Expand `configs/taxonomy_pt.yaml` beyond the current 4 sign classes (`sign.stop`, `sign.yield`, `sign.speed_limit`, `sign.other`) to cover high-value Portuguese road signs (e.g., `sign.crosswalk`, `sign.no_entry`, `sign.parking`, `sign.mandatory_direction`, `sign.roundabout`).
* **OCR / Attribute Extraction:** Add a lightweight attribute extractor for `sign.speed_limit` (e.g., recognizing numeric values `30`, `50`, `70`) to populate the optional `attributes` field in the `POST /infer` schema.
* **Additional Urban Furniture:** Extend the taxonomy to other municipal assets such as traffic lights, fire hydrants, bus stops, or damaged pavement/manholes by adding new entries to `taxonomy_pt.yaml` and training corresponding Stage-2 classifiers.

---

## 3. Geolocation Calibration & Ground-Truth Benchmarking
* **Ground-Truth Coordinate Dataset:** Manually survey and pin 30–50 real-world assets per category (`sign`, `light`, `waste`) in the Aveiro pilot zone using high-resolution satellite imagery / field GPS to build a verified geospatial ground-truth benchmark.
* **Per-Source Camera Calibration (`calibrate.py`):** Run grid-search calibration on the ground-truth set to determine empirical defaults for `camera_height_m` and `pitch_offset_deg` separately for `mapillary`, `kartaview`, and custom `video` sources.
* **Method Selection Benchmark (`benchmark.py`):** Evaluate `size_prior`, `ground_plane`, `depth`, and `inverse_variance` fusion against the ground-truth set (tracking median and P90 error in metres per category) to empirically tune `geometry.methods` and uncertainty weights in `configs/base.yaml`.

---

## 4. OSM Road-Geometry Sanity Check
* **Offline Carriageway Validation (`road_check.py`):** Integrate cached OpenStreetMap (`Overpass`) road centerlines and estimated carriageway half-widths into the localization stage.
* **Snap-to-Curb & Outlier Rejection:** Automatically snap projected asset coordinates that fall inside the drivable carriageway outward to the nearest curb/sidewalk edge (or reject implausible detections), eliminating false placements in the middle of roads.

---

## 5. Monocular Depth & Multi-Object Video Tracking
* **Metric Monocular Depth (`depth.py`):** Export and benchmark a metric depth estimation model (e.g., **Depth Anything V2 Metric** or **UniDepth**, Apache 2.0/MIT) to ONNX Runtime and enable `geometry.depth.enabled: true` as a complementary distance signal alongside `size_prior` and `ground_plane`.
* **Frame-to-Frame Video Tracking:** Add a lightweight multi-object tracker (e.g., **ByteTrack**) for sequential video frames (`source: "video"`, shared `sequence_id`) to stabilize
