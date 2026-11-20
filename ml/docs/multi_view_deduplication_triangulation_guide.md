# Multi-View Deduplication & Triangulation (`src/dedup/`)

This document explains how `POST /dedup` (`AssetDeduplicator`) consolidates repeated street-level detections (`Observations`) from multiple images and trajectories into unique, geolocated urban assets (`Elements`) without overwriting human-curated records or merging distinct neighboring objects.

## 1. The Core Problem

When a survey vehicle or pedestrian captures street-level imagery every $\sim 5\text{ m}$ (or from intersecting streets), the same physical asset—such as a STOP sign, street lamp, or waste container—appears in multiple frames.

Directly inserting every `Observation` into the map database would create:

* **Duplicate markers** for the same physical object.

* **Noisy positions**, because single-view distance estimates ($d$) have higher range uncertainty along the camera's line of sight than angular bearing accuracy ($\psi$).

* **Conflicts with manual edits**, if a re-run overwrites assets that a human operator has already verified or corrected.

## 2. Step-by-Step Deduplication Pipeline

### Step 1: Input Validation & Filtering

* Observations missing estimated coordinates (`est_lat is None` or `est_lon is None`) cannot be placed spatially and are immediately routed to `unassigned_observation_ids`.

* For valid observations, the top-level category (`sign`, `light`, or `waste`) is resolved via `Taxonomy.get(obs.type).category` (with prefix fallback) to look up the category-specific clustering radius from `configs/base.yaml`:

  * `sign`: $2.5\text{ m}$

  * `light`: $4.0\text{ m}$

  * `waste`: $5.0\text{ m}$

### Step 2: Protecting Human-Curated Elements (`existing_elements`)

Existing database elements are partitioned by `status` before clustering:

1. **Locked Elements (`verified`, `corrected`, `rejected`):**

   * Their coordinates (`lat`, `lon`), class (`type`), and `status` are strictly immutable.

   * For `verified` and `corrected` elements, any incoming observation of the **exact same `type`** falling within `radius_m` (measured via WGS84 geodesic distance) is attached to that element's `observation_ids` list and excluded from new clustering.

   * `rejected` elements are preserved untouched and never absorb new observations.

2. **Automatic Elements (`auto`):**

   * Re-evaluated cleanly against the remaining unassigned observations. If a newly formed cluster lands within `radius_m` of an existing `auto` element of the same `type`, it reuses that `element_id` for ID stability; otherwise, superseded `auto` IDs are listed in `removed_element_ids`.

### Step 3: Per-Class Complete-Linkage Clustering (`cluster.py`)

1. **Strict Fine-Grained Grouping:** Observations are partitioned by exact `obs.type` (e.g., `sign.stop` is never clustered with `sign.yield`).

2. **Local Metric Projection:** Estimated WGS84 coordinates are projected into a local tangent-plane Cartesian frame (`LocalENU` in metres) anchored at the batch's reference point.

3. **Complete-Linkage Hierarchy:** Using `scipy.cluster.hierarchy.linkage(..., method="complete")` and `fcluster(..., t=radius_m, criterion="distance")`, we enforce that **every pair** of detections inside a cluster is within `radius_m` of each other (preventing chain-merging along long rows of street lamps).

4. **Same-Frame Mutual Exclusion:** Each observation's `image_id` is extracted from its `<image_id>:<suffix>` identifier. Two detections from the **same `image_id`** are never placed in the same cluster—ensuring two bins or two signs visible side-by-side in a single photograph remain separate assets.

### Step 4: Ray-Consistency Check (`geometry_check.py`)

When `dedup.use_ray_check` is enabled, candidate merges are validated against 2D ray geometry before joining a cluster:

* Camera poses $(lat, lon)$ from `request.images` and detection bearings (`bearing_deg`) are converted into `RayObservation` vectors.

* If two cameras observe a target from different angles (parallax $\ge 15^\circ$), their viewing rays must **converge in front of both cameras** (cheirality check) within `max_distance_m` ($50\text{ m}$) and `max_residual_m`.

* If the rays diverge or intersect behind a camera, the merge is rejected—preventing false merges between parallel objects across narrow streets.

### Step 5: Position Estimation via Triangulation or Inverse-Variance Centroid

For each finalized cluster, `(lat, lon)` is computed in `LocalENU`:

1. **Multi-View Weighted Least-Squares Triangulation (`triangulate_rays`):**
   When $\ge 2$ rays exist with sufficient parallax ($\ge 5^\circ$), each ray $i$ with camera origin $\mathbf{p}_i = (x_i, y_i)^T$, compass bearing $\psi_i$, and unit normal $\mathbf{n}_i = (\cos\psi_i, -\sin\psi_i)^T$ contributes to the weighted normal equations ($w_i = 1 / \sigma_i^2$):

   $$
   \left(\sum_i w_i \mathbf{n}_i \mathbf{n}_i^T\right) \mathbf{x} = \sum_i w_i \mathbf{n}_i (\mathbf{n}_i^T \mathbf{p}_i)
   $$

   Solving this $2 \times 2$ system yields the optimal 2D ray intersection, eliminating single-view depth drift.

2. **Inverse-Variance Centroid Fallback:**
   If there is only one observation, or if all views are nearly collinear (e.g., driving straight toward a sign down a narrow street where parallax $< 5^\circ$), the position falls back to the inverse-variance weighted average of single-view estimates:

   $$
   \bar{\mathbf{x}} = \frac{\sum_i w_i \mathbf{x}_i}{\sum_i w_i}, \qquad w_i = \frac{1}{\sigma_i^2}
   $$

### Step 6: Best-View Selection & Confidence Fusion (`scoring.py`)

* **`best_observation_id`:** Picks the observation with the highest detector `score`, breaking ties by lowest spatial `uncertainty_m` so human reviewers see the sharpest image crop.

* **Fused `confidence`:** Combines detector scores $s_1 \ge s_2 \ge \dots \ge s_k$ using damped noisy-OR reinforcement capped at `dedup.max_confidence` ($0.99$):

  $$
  C = \min\left(C_{\max},\ \max\left(s_1,\ 1 - \prod_{i=1}^{k} (1 - 0.5\, s_i)\right)\right)
  $$

  A single sighting preserves its calibrated detector score, while repeated independent sightings smoothly increase confidence without prematurely saturating at $1.0$.

## 3. Module Layout

```
src/dedup/
├── utils/
│   └── helpers.py      # image_id extraction, Taxonomy category lookup, ray builders
├── scoring.py          # best_observation_id ranking & damped noisy-OR confidence fusion
├── geometry_check.py   # ray-consistency check & triangulation / ENU centroid solver
├── cluster.py          # complete-linkage per-class clustering & same-frame separation
└── deduplicator.py     # AssetDeduplicator orchestrating locked elements & Element output

```