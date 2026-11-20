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
  "lat": 40.6412,
  "lon": -8.6538,
  "heading": 92.5,
  "fov": 90.0,
  "camera_type": null,
  "camera_height_m": null,
  "source": "mapillary",
  "sequence_id": null,
  "frame_index": null
}
```

| Field | Needed? |
|-------|---------|
| `image_id`, `lat`, `lon`, `heading` | **Required** (without them we can't compute a position) |
| `fov` | Optional, `null` → default from ML config (less accurate bearing) |
| `camera_type` | Optional, `null` → default from config |
| `camera_height_m` | Optional, `null` → default from config |
| `source` | Optional (`mapillary`, `kartaview`, `video`); lets ML pick default camera settings |
| `sequence_id`, `frame_index` | Only for video frames, otherwise `null` |

**Response:**

```json
{
  "image_id": "6f1c2b0e",
  "blurred_image_path": "images/6f1c2b0e.jpg",
  "observations": [
    {
      "observation_id": "a1b2",
      "type": "sign.speed_limit",
      "score": 0.91,
      "bbox_xyxy": [412, 220, 468, 280],
      "bearing_deg": 94.1,
      "est_lat": 40.64131,
      "est_lon": -8.65349,
      "uncertainty_m": 2.1
    }
  ]
}
```
- `observation_id`: unique per observation and consist of <image_id>:<uuid4.hex[:8]>, used in `/dedup`.
- No detections → `"observations": []` (not an error).
- If the position can't be computed, `est_lat`, `est_lon`, `uncertainty_m` are `null`.
- No crop files: the frontend shows the detection by cropping the blurred image with `bbox_xyxy`.
- Optional extras ML may add later (ignore if not needed): `attributes` (e.g. speed value), `est_distance_m`, `method`, `model_version`.

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
      "lat": 40.64132,
      "lon": -8.65351,
      "confidence": 0.87,
      "observation_ids": ["a1b2", "c3d4", "e5f6"],
      "best_observation_id": "a1b2",
      "status": "auto"
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
/data/images/<image_id>.jpg    blurred full image
```
JSON contains only this relative path. API serves it to the frontend.

---

## 4. Video

No video endpoint in ML: video frames go through `/infer` like any image.

1. The web uploads the video to the API (`POST /videos`) with its GPX track (required).
2. The API picks a frame every ~5 m of travel and sets `lat`, `lon`, `heading` from the track
   (same algorithm as `ml extract-frames video.mp4 track.gpx`, ported to `api/app/services/video_frames.py`).
3. The API sends each frame to `/infer` with `source: "video"`, the same `sequence_id` for the whole
   video and `frame_index` 0, 1, 2… (`image_id` = `<sequence_id>_<frame_index>`), stores the
   results like any other image and runs one `/dedup` for the whole video.

The raw video stays in a temporary file on the API only while its frames are read (not in the
shared folder, DB or UI). `ml extract-frames` stays available to process a video offline.

---

## 5. Errors

```json
{"error": {"code": "invalid_meta", "message": "heading must be 0-360"}}
```
Codes: `invalid_meta` (400), `unsupported_image` (415), `internal` (500), `not_implemented` (501).

---

## 6. Who does what

- **API** sends images to `/infer`, saves observations and elements in PostGIS (plus author/licence/date per image), handles technician edits and export.
- **ML** blurs, detects, locates, and runs dedup.
- `GET /health` returns `{"status": "ok"}`.
- ML provides a **mock mode** (`ML_MOCK=1`) with fake data in this exact format, so the API and frontend can start now.
