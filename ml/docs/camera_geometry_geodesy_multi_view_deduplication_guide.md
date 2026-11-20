# Camera Geometry, Geodesy & Multi-View Deduplication in Aveiro Tech City

This guide explains the mathematics and physical principles behind our spatial modules (`src/geometry/` and `src/dedup/`): how we convert 2D object bounding boxes (`bbox_xyxy`) into real-world GPS coordinates (`est_lat`, `est_lon`), estimate positional error (`uncertainty_m`), and merge multi-frame sightings into unique physical assets.

---

## Overall Localization Pipeline

To place an object on a map from a single image, we need two quantities:
1. **Direction (Azimuth / Bearing):** the compass angle of the ray passing from the camera through the object's center.
2. **Distance:** how far along that ray the object is located.

Once we know the camera coordinates $(lat_0, lon_0)$, bearing $\psi$, and distance $d$, the problem reduces to a forward geodesic projection on the Earth's ellipsoid.

---

## Part 1. Projective Camera Geometry (`camera.py`)

Our dataset includes two projection types (`camera_type` in config):
* **Standard frames (`perspective`):** photos from smartphones, dashcams, or standard Mapillary/KartaView cameras.
* **360° Panoramas (`equirectangular`):** spherical projections mapped onto a rectangle where image width spans $360^\circ$ and height spans $180^\circ$.

### 1.1. Perspective Camera (Pinhole Camera Model)

In a standard camera, light passes through an optical center onto a flat sensor. The primary intrinsic parameter is the **Horizontal Field of View ($\text{HFOV}$)** (e.g., $90^\circ$).

#### Focal Length in Pixels ($f_{px}$)
The focal length in pixels represents the virtual distance from the optical center to the image plane. From the right triangle formed by half the image width ($W/2$) and half the field of view ($\text{HFOV}/2$):

$$f_{px} = \frac{W / 2}{\tan(\text{HFOV} / 2)}$$

*Example:* If image width $W = 1920\text{ px}$ and $\text{HFOV} = 90^\circ$, then $\tan(45^\circ) = 1$, giving $f_{px} = 960\text{ px}$. (Assuming square pixels, horizontal and vertical focal lengths are equal: $f_x = f_y = f_{px}$.)

#### Horizontal Offset & Compass Bearing (`perspective_bearing`)
Let the bounding box center have horizontal coordinate $c_x$, while the optical axis passes through $W/2$. The pixel offset is $\Delta x = c_x - W/2$, giving a horizontal angle offset of:

$$\Delta \psi = \arctan\left(\frac{c_x - W/2}{f_{px}}\right)$$

* If the object is to the **right** of the frame center ($c_x > W/2$), $\Delta \psi > 0$.
* If to the **left** ($c_x < W/2$), $\Delta \psi < 0$.

Since navigation `heading` is measured **clockwise from True North** ($0^\circ$ = North, $90^\circ$ = East, $180^\circ$ = South, $270^\circ$ = West), the object's absolute bearing is:

$$\psi_{obj} = (\text{heading} + \Delta \psi) \pmod{360^\circ}$$

#### Elevation & Depression Angle (`perspective_elevation_deg`)
Similarly along the vertical axis (noting that in image coordinates $y = 0$ is the **top** edge and $H/2$ is the vertical center):

$$\theta_{elev} = \arctan\left(\frac{H/2 - c_y}{f_{px}}\right)$$

* $\theta_{elev} > 0$: point lies **above** the horizon (looking upward).
* $\theta_{elev} < 0$: point lies **below** the horizon (looking downward at the road). The depression angle is $\theta_{dep} = -\theta_{elev}$.

---

### 1.2. Panoramic Camera (`equirectangular`)

In an equirectangular projection, angles scale linearly with pixel coordinates, eliminating the need for `atan` trigonometry:
* **Bearing (`pano_bearing`):**
  $$\psi_{obj} = \left(\text{heading} + \left(\frac{c_x}{W} - 0.5\right) \cdot \text{HFOV}\right) \pmod{360^\circ}$$
* **Elevation Angle (`pano_elevation_deg`):**
  $$\theta_{elev} = \left(0.5 - \frac{c_y}{H}\right) \cdot 180^\circ$$

---

## Part 2. Single-View Distance Estimation ($d$)

Recovering depth from a single 2D image requires physical priors. Our pipeline uses two complementary geometric estimators:

### 2.1. Physical Size Prior (`size_prior.py`)
From our taxonomy (`taxonomy_pt.yaml`), we know standard physical dimensions—for instance, a STOP sign in Portugal has width $S_{real} = 0.6\text{ m}$, while a street lamp has height $S_{real} = 6.0\text{ m}$.

By similar triangles for a perspective camera:

$$\frac{S_{px}}{f_{px}} = \frac{S_{real}}{d} \implies d = \frac{f_{px} \cdot S_{real}}{S_{px}}$$

For a panorama, the object subtends an angular span $\Delta \alpha = \frac{S_{px}}{H} \cdot \pi$ radians, yielding:

$$d = \frac{S_{real}}{2 \tan(\Delta \alpha / 2)}$$

* **Limitations:** Fails when a class has no fixed physical size (`waste.underground`, where `size: null`) or when the bounding box is truncated at the image border (making apparent $S_{px}$ smaller and artificially inflating $d$).

### 2.2. Ground-Plane Intersection (`ground_plane.py`)
For ground-mounted assets (`ground: true` — street lamps, waste bins), the bottom edge of the bounding box $y_2$ (`cy_base`) marks where the object touches the pavement.

Assuming flat ground and a known camera height $h_{cam}$ (e.g., $1.5\text{ m}$ roof mount), a ray cast downward at depression angle $\theta_{dep}$ intersects the ground at horizontal distance:

$$d = \frac{h_{cam}}{\tan(\theta_{dep})}$$

* **Why `ground_plane_max_distance_m = 15.0`:** Near the horizon, $\theta_{dep} \to 0$ and $1/\tan(\theta_{dep})$ explodes nonlinearly. A tiny $1.5^\circ$ vehicle pitch change (braking or speed bumps) at $30\text{ m}$ introduces tens of metres of error, so this method is capped at $15\text{ m}$.

---

## Part 3. Geodesy: From Metres to GPS Coordinates (`geo.py`)

The Earth is not flat or perfectly spherical, but an oblate ellipsoid (**WGS84**, the GPS standard).

### 3.1. Why Not Simply Add Metres to `lat` and `lon`?
* $1^\circ$ of **latitude** (North–South) is nearly constant everywhere at $\approx 111.32\text{ km}$.
* $1^\circ$ of **longitude** (East–West) converges toward the poles by $\cos(\text{lat})$. At Aveiro's latitude ($40.64^\circ\text{ N}$), $\cos(40.64^\circ) \approx 0.759$, so $1^\circ$ of longitude is only $\approx 84.5\text{ km}$.

### 3.2. Forward Geodesic Problem
Given camera coordinates $(lat_0, lon_0)$, object bearing $\psi_{obj}$, and ground distance $d$ in metres, we compute $(lat_1, lon_1)$ using `pyproj` (`Geod(ellps="WGS84").fwd(...)`), which solves the forward geodesic problem on the WGS84 ellipsoid with sub-millimetre accuracy.

### 3.3. Local Tangent Metric System: ENU (East-North-Up)
For vector operations—such as **multi-view ray triangulation** and **spatial clustering**—operating in degrees is distorted. We pick a local reference anchor $(lat_{ref}, lon_{ref})$ and project coordinates into a local Cartesian **ENU** plane:
* **$E$ (East):** offset East in metres ($X$).
* **$N$ (North):** offset North in metres ($Y$).
* **$U$ (Up):** altitude above the ellipsoid in metres ($Z$).

At city scale (a few kilometres), ENU allows standard Euclidean geometry (Pythagorean distances, line intersections, least squares) before projecting $(E, N)$ back to WGS84 $(lat, lon)$.

---

## Part 4. Sensor Fusion & Error Propagation (`uncertainty_m`)

### 4.1. Inverse-Variance Weighting
When both `size_prior` ($d_1 = 8.2\text{ m}, \sigma_1 = 2.0\text{ m}$) and `ground_plane` ($d_2 = 7.8\text{ m}, \sigma_2 = 1.2\text{ m}$) produce valid estimates for the same object, we fuse them with weights $w_i = 1 / \sigma_i^2$:

$$d_{fused} = \frac{w_1 d_1 + w_2 d_2}{w_1 + w_2}, \qquad \sigma_{fused} = \sqrt{\frac{1}{w_1 + w_2}}$$

More reliable estimates automatically receive higher weight, and the combined distance uncertainty $\sigma_{fused}$ is lower than either individual method.

### 4.2. Total Map Position Uncertainty ($\sigma_{total}$)
The `uncertainty_m` field returned by `/infer` represents the 1-sigma positional radius on the map, combining three independent error sources:
1. **Range error ($\sigma_d$):** distance uncertainty along the ray.
2. **Compass/bearing error ($\sigma_{bearing}$):** camera heading noise (default $2^\circ$) creates a lateral cross-track offset $\sigma_{lat\_offset} = d \cdot \tan(\sigma_{bearing})$.
3. **Camera GPS error ($\sigma_{gps}$):** GPS receiver inaccuracy at capture time (default $3.0\text{ m}$).

Adding variances in quadrature:

$$\sigma_{total} = \sqrt{\sigma_d^2 + \sigma_{gps}^2 + \left(d \cdot \tan(\sigma_{bearing})\right)^2}$$

---

## Part 5. Multi-View Deduplication & Triangulation (`src/dedup/`)

Street-level capture vehicles photograph the same lamp post, sign, or bin across multiple consecutive frames and intersecting streets. The `POST /dedup` module merges repeated detections into unique physical `Elements` without collapsing distinct neighboring objects.

### 5.1. Protecting Human-Curated Elements
Before clustering, existing elements from the database (`existing_elements`) are partitioned by status:
* **Locked (`verified`, `corrected`, `rejected`):** Human-reviewed coordinates, labels, and statuses are **never overwritten or moved**. New detections matching a `verified`/`corrected` element's exact class within `radius_m` are simply appended to its `observation_ids` to prevent duplicate creation.
* **Auto (`auto`):** Recomputed cleanly as new observations arrive, reusing existing `element_id`s whenever a cluster lands within `radius_m` of an earlier `auto` element.

### 5.2. Per-Class Spatial Clustering & Same-Frame Separation
1. **Exact Class Partitioning:** Observations are grouped strictly by fine-grained class (`obs.type`, e.g., `sign.stop` is never merged with `sign.yield`).
2. **Complete-Linkage Hierarchical Clustering:** Coordinates are projected into `LocalENU` metres and clustered with complete-linkage (`scipy.cluster.hierarchy`), guaranteeing that **every pair** of detections inside a cluster lies within the category's radius (`sign: 2.5 m`, `light: 4.0 m`, `waste: 5.0 m`).
3. **Same-Frame Mutual Exclusion:** Two detections originating from the **same `image_id`** are never merged into the same cluster—ensuring two bins sitting side-by-side in one photo remain separate assets.

### 5.3. Ray-Consistency Check & Weighted Least-Squares Triangulation (`triangulation.py`)
Single-view distance estimates suffer from depth ambiguity along the viewing ray, whereas **compass bearings (`bearing_deg`) are highly accurate**. When multiple frames observe an object from different angles:
* **Ray-Consistency Check (`is_ray_consistent`):** Before merging a candidate detection into a cluster, we check whether their viewing rays geometrically intersect in front of both cameras (cheirality check) within `max_distance_m` and `max_residual_m`. If two cameras view a scene from wide parallax ($\ge 15^\circ$) and their rays diverge rather than intersect, the merge is rejected (preventing false merges of parallel street lamps).
* **Multi-View Triangulation (`triangulate_rays`):** In `LocalENU`, each camera pose $(p_x, p_y)$ and compass bearing $\psi$ defines a line with unit normal $\mathbf{n} = (\cos\psi, -\sin\psi)^T$. Weighting each ray by $w_i = 1 / \sigma_i^2$, we solve the weighted linear least-squares intersection:

$$\left(\sum_i w_i \mathbf{n}_i \mathbf{n}_i^T\right) \mathbf{x} = \sum_i w_i \mathbf{n}_i (\mathbf{n}_i^T \mathbf{p}_i)$$

When valid parallax ($\ge 5^\circ$) exists, triangulation overrides noisy single-view depth estimates with true 2D ray-intersection coordinates. When observations are collinear (e.g., approaching straight down a narrow alley), the estimator gracefully falls back to the inverse-variance weighted centroid of single-view estimates.

### 5.4. Confidence Fusion & Best-View Selection
* **`best_observation_id`:** Selects the highest-confidence detector sighting (breaking ties by lowest `uncertainty_m`) so the UI displays the clearest cropped image for human verification.
* **Fused Confidence:** Combines individual detector scores via damped noisy-OR reinforcement ($1 - \prod_i (1 - 0.5 s_i)$), boosting confidence when multiple independent frames confirm the same asset while capping the result at `max_confidence` (`0.99`).