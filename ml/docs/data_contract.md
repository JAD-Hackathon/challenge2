# API ↔ ML Data Contract (v0.1)

Between the **API** and the **ML service**. Two endpoints. Change anything → tell each other first.

---

## Rules

- Coordinates: WGS84, fields `lat` and `lon`.
- Distances in metres. Angles in degrees, clockwise from north.
- `bbox_xyxy` = `[x1, y1, x2, y2]` in pixels, top-left origin.
- IDs are UUID strings. Unknown values are `null`.
- **Raw images are never saved.** ML blurs them in memory and saves only the blurred version.
- Class names: `category.type`, e.g. `sign.stop`, `sign.yield`, `sign.speed_limit`, `sign.other`, `light.street_lamp`, `waste.underground`, `waste.recycling_island`, `waste.general`.

---

## 1. `POST /infer` (one image)

**Request** (multipart):
- `image`: the image file
- `meta`: JSON string:

```json
{
  "image_id": "6f1c2b0e",
  "source": "mapillary",
  "lat": 40.6412,
  "lon": -8.6538,
  "heading": 92.5,
  "fov": 90.0,
  "camera_height_m": 1.5,
  "captured_at": "2024-05-17",
  "author": "some_user",
  "license": "CC BY-SA 4.0"
}
```
`source` is `mapillary`, `kartaview` or `video`. `heading`, `fov` and `camera_height_m` may be `null`.

**Response:**

```json
{
  "image_id": "6f1c2b0e",
  "blurred_image_path": "images/6f1c2b0e.jpg",
  "observations": [
    {
      "observation_id": "a1b2",
      "class": "sign.speed_limit",
      "attributes": {"speed_kmh": 50},
      "score": 0.91,
      "bbox_xyxy": [412, 220, 468, 280],
      "crop_path": "crops/a1b2.jpg",
      "bearing_deg": 94.1,
      "est_lat": 40.64131,
      "est_lon": -8.65349,
      "est_distance_m": 12.4,
      "uncertainty_m": 2.1,
      "method": "size_prior"
    }
  ],
  "model_version": "v0.1"
}
```
- `method`: `size_prior`, `ground_plane` or `depth`.
- No detections → `"observations": []` (not an error).
- If the position can't be computed, `est_lat`, `est_lon`, `est_distance_m` are `null`.

---

## 2. `POST /dedup` (many observations → elements)

**Request:**

```json
{
  "observations": [ /* observations from /infer */ ],
  "images": [ {"image_id": "6f1c2b0e", "lat": 40.6412, "lon": -8.6538, "heading": 92.5} ],
  "existing_elements": []
}
```
- `images`: camera positions, needed for ray checks.
- `existing_elements`: optional, for adding new images later. Elements with status `verified` or `corrected` are **never changed or deleted** by ML.

**Response:**

```json
{
  "elements": [
    {
      "element_id": "e9f8",
      "type": "sign.speed_limit",
      "attributes": {"speed_kmh": 50},
      "lat": 40.64132,
      "lon": -8.65351,
      "confidence": 0.87,
      "n_observations": 3,
      "observation_ids": ["a1b2", "c3d4", "e5f6"],
      "best_observation_id": "a1b2"
    }
  ],
  "unassigned_observation_ids": [],
  "removed_element_ids": []
}
```

---

## 3. Files

Shared folder, ML writes, API reads:

```
/data/images/<image_id>.jpg         blurred full image
/data/crops/<observation_id>.jpg    blurred crop
```
JSON contains only these relative paths. API serves them to the frontend.

---

## 4. Errors

```json
{"error": {"code": "invalid_meta", "message": "heading must be 0-360"}}
```
Codes: `invalid_meta` (400), `unsupported_image` (415), `internal` (500).

---

## 5. Who does what

- **API** sends images to `/infer`, saves observations and elements in PostGIS, handles technician edits and export.
- **ML** blurs, detects, locates, and runs dedup.
- `GET /health` returns `{"status": "ok"}`.
- ML provides a **mock mode** (`MOCK=1`) with fake data in this exact format, so the API and frontend can start now.

## Still to agree

- [ ] Shared folder path and URL for serving images.
- [ ] Who triggers `/dedup` (button or automatically after a batch).
- [ ] Final class list.