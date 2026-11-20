# api

FastAPI + PostGIS. Receives images and videos from the web, sends them to the ML service
(see `ml/docs/data_contract.md`), stores the street furniture it finds and serves it back.

Visual guide with diagrams (upload flow, dedup, statuses, every function): open
[`docs/api-guide.html`](docs/api-guide.html) in a browser.

## Run

```bash
docker compose up        # from the repo root: PostGIS + ML (in mock mode) + API
```

The ML service has its own mock (`ML_MOCK=true`, on by default): it blurs the images and
invents detections in the contract's format. So the full flow already works with fake ML
results, and the web can use it right away.

### API mock mode: no database

Set `API_MOCK=true` in `api/.env`. The API then keeps the catalogue in memory instead of
PostGIS. It starts with 12 sample elements around Aveiro (every category and status), with
their images drawn into the shared folder, and resets on restart. Same routes, parameters and
JSON as the real API. Docs: http://localhost:8000/docs

Uploads still go to the ML service (its mock), exactly like real mode: the API never fakes ML.
API and ML must share the same folder for images, so run both with `docker compose up`, or both
locally (both then use `challenge2/data`):

```bash
cd ml  && uv run uvicorn src.service.main:app --port 8001   # ML mock, where the API expects it
cd api && uv run fastapi dev
```

Everything mock-only is in [`app/mocks/`](app/mocks/__init__.py). It mirrors the real layout
(`endpoints/`, `services/`) and `tests/test_mock_parity.py` fails if the two drift apart.

## Endpoints (`/api/v1`)

| Method | Path | What |
|---|---|---|
| GET  | `/elements?category=&status=` | Catalogue. Default: everything except `rejected` |
| GET  | `/elements/{id}` | One element |
| PATCH | `/elements/{id}` | Technician correction: type, attributes, position |
| POST | `/elements/{id}/verify` | Technician confirms it (also undoes a false-positive flag) |
| POST | `/elements/{id}/false-positive` | Technician flags it as a false positive |
| POST | `/images` | Upload a **batch** of images (multipart) |
| POST | `/videos` | Upload a video with its GPS track (GPX) (multipart) |
| GET  | `/images/{image_id}` | Image + all its detections (boxes) |
| GET  | `/export/layers`, `/export/{table}.geojson`, `/export/{table}.csv` | Export, `?bbox=min_lon,min_lat,max_lon,max_lat` filter (**longitude first**, like GeoJSON and Leaflet's `getBounds().toBBoxString()`) |
| GET  | `/media/images/{image_id}.jpg` | Blurred image (from the shared folder) |

### Element

```json
{
  "id": "a0000000-0000-4000-8000-000000000001",
  "name": "Limite de velocidade",
  "category": "sign",
  "type": "speed_limit",
  "attributes": {"limit": 50},
  "status": "auto",
  "confidence": 0.91,
  "latitude": 40.64277, "longitude": -8.65452,
  "image_id": "mock_rossio",
  "image_url": "/media/images/mock_rossio.jpg",
  "bbox_xyxy": [610, 250, 680, 320],
  "attribution": "© mock_user (Mapillary), CC BY-SA 4.0",
  "observation_count": 1,
  "created_at": "...", "updated_at": "..."
}
```

- `attributes`: key/value facts that depend on the type. Speed limit signs:
  phase 1 only finds the sign (`{}`), phase 2 also reads the number (`{"limit": 50}`).
  Treat every key as optional.
- `status`: `auto` (found by ML), `verified` (confirmed by a technician), `corrected` (fixed by
  a technician) or `rejected` (flagged as false positive). ML never changes an element that
  isn't `auto`.
- `attribution`: credit for the photo (Mapillary / KartaView are CC BY-SA: show it with the image).
- To show the element, crop `image_url` with `bbox_xyxy` (pixels, `[x1, y1, x2, y2]`).
- `image_url` is relative. Prefix it with the API's address, or set `MEDIA_URL` to an absolute URL.

### Batch upload: `POST /images`

Multipart form:
- `images`: one file per image (repeat the field; JPEG/PNG; up to `MAX_BATCH_SIZE`, default 20)
- `metas`: JSON array, one item per file **in the same order**. Each item is either:
  - the image's position: required `lat`, `lon`, `heading` (° clockwise from north);
    optional `image_id`, `fov`, `source`, `author`, `license`, `captured_at`, ...
  - or, for an image from Mapillary / KartaView, the site's record as is (see below).

```bash
curl -F images=@a.jpg -F images=@b.jpg \
     -F 'metas=[{"lat":40.6412,"lon":-8.6538,"heading":92.5},{"lat":40.6415,"lon":-8.6531,"heading":90}]' \
     http://localhost:8000/api/v1/images
```

```php
$request = Http::timeout(300);
foreach ($files as $file) {
    $request = $request->attach('images', file_get_contents($file->getRealPath()), $file->getClientOriginalName());
}
$response = $request->post("$api/api/v1/images", ['metas' => json_encode($metas)]);
```

The response has one result per file: `processed`, `duplicate` (that `image_id` was already
sent) or `failed` (with `error`). It also lists the `elements` created or updated, and the
`removed_element_ids` (merged into others). A bad file doesn't fail the batch, but a bad
request does (422: count mismatch, invalid meta, too many files). If ML is down the whole batch
fails (502). The request is synchronous, so use a long timeout for big batches.

#### Images from Mapillary / KartaView

The web gets the images from the site, downloads each file and sends it with the record the
site returned. The API works out position, heading, field of view, capture time and the
CC BY-SA credit from it, so the web doesn't need to:

```json
[
  {"mapillary": {"id": "1234", "computed_geometry": {...}, "computed_compass_angle": 92.5, ...}},
  {"kartaview": {"id": 77, "lat": "40.64", "lng": "-8.65", "heading": "180", ...}, "author": "kv_user"}
]
```

- **Mapillary** (API v4): request the images with
  `fields=id,computed_geometry,geometry,computed_compass_angle,compass_angle,camera_type,camera_parameters,width,height,sequence,captured_at,creator,thumb_2048_url`
  (`MAPILLARY_FIELDS` in `app/services/street_view.py`) and upload the file at `thumb_2048_url`.
- **KartaView** (API v2): send the photo record (`id`, `lat`, `lng`, `heading`, `projection`,
  `fieldOfView`, `sequenceId`, `sequenceIndex`, `shotDate`, and `username` if you have it).
- Any other key next to the record overrides what the API worked out, e.g. `"author"` when the
  KartaView record has no username.
- Image ids are `mly_<id>` / `kv_<id>`, so the same photo sent again comes back as `duplicate`.
- 360° panoramas and records without position or heading can't be used yet: that file comes
  back `failed` with the reason, the rest of the batch goes on.

### Video upload: `POST /videos`

Multipart form:
- `video`: the video file (mp4, mov, ...), up to `MAX_VIDEO_MB` (default 1024 = 1 GB)
- `track`: the GPS track recorded at the same time, as GPX (any GPS logger app exports it),
  with a `<time>` on every point. **Required**: it is the only source of the frame positions.
- `meta` (optional): JSON with any of
  - `spacing_m` (default 5): keep one frame every N metres
  - `start_time`: UTC time (GPS clock) of the video's first frame. Default: the time of the
    track's first point, i.e. the video and the track were started together
  - `time_offset_s`: seconds added to every frame time, if the video and GPS clocks don't match
  - `heading_offset_deg`: camera direction vs travel (0 = front, 90 = right)
  - `fov`, `camera_height_m`, `author`, `license`

Without a GPX the API refuses the video (422). GPS stored inside the video file (GoPro, DJI,
dashcams) isn't read: export it to GPX first (e.g. `exiftool -ee -p gpx.fmt video.mp4`).

```bash
curl -F video=@ride.mp4 -F track=@ride.gpx -F 'meta={"spacing_m": 5}' http://localhost:8000/api/v1/videos
```

```php
$response = Http::timeout(900)
    ->attach('video', fopen($video->getRealPath(), 'r'), $video->getClientOriginalName())
    ->attach('track', file_get_contents($gpx->getRealPath()), $gpx->getClientOriginalName())
    ->post("$api/api/v1/videos", ['meta' => json_encode(['spacing_m' => 5])]);
```

**How it works** (`app/services/video_frames.py`, a port of ML's `extract-frames`, which the
ML team also runs as a CLI):

1. The track is measured: distance travelled at every point.
2. A spot every `spacing_m` metres along it gets a frame: its position is interpolated
   between the two GPS points around it, its heading is the direction of travel there
   (+ `heading_offset_deg`). Where the GPS stood still, the heading of the closest move is kept.
3. Which frame: with GPS times, the one filmed when the GPS was at that spot (video second =
   GPS time - `start_time` - `time_offset_s`); spots outside the video are dropped. A GPX
   without times is taken at constant speed: the spot halfway along is the frame halfway
   through the video.
4. Each frame (JPEG) is sent to ML `POST /infer` like an uploaded image, with
   `source: "video"`, the video's `sequence_id` and `frame_index` 0, 1, 2...: ML blurs it and
   detects elements, the API stores it, then one `/dedup` runs for the whole video.

The response is the same as for images, plus `sequence_id`, and
`captured_at` of each frame is its GPS time. The video is only kept in a temporary file while
its frames are read, never in the shared folder or the database. A video gives at most
`MAX_VIDEO_FRAMES` frames (default 300, i.e. 1.5 km at 5 m): it's synchronous, one `/infer`
per frame, so give the request a long timeout.

Errors: 413 video too big; 422 bad `meta`, no GPX (or an empty one), a GPX that can't be read,
a video that can't be read, clocks that don't overlap (`No frame of the video falls on the GPS
track...`), too many frames; 502 ML down. A frame ML refuses only fails that frame.

### Technician corrections

A technician checks each element against its image (`image_url` cropped to `bbox_xyxy`) and:

- **Confirms it**: `POST /elements/{id}/verify`, no body → `verified`. On a `rejected` element
  it undoes the false-positive flag. A `corrected` element stays `corrected`.
- **Fixes it**: `PATCH /elements/{id}` with only what changes → `corrected`:
  ```json
  {"attributes": {"limit": 30}}                       // wrong speed limit
  {"type": "yield"}                                   // wrong type, same category
  {"category": "waste", "type": "general"}            // wrong category
  {"latitude": 40.64281, "longitude": -8.65463}       // wrong position (both together)
  ```
  The type must exist (`sign`: stop, yield, speed_limit, other; `light`: street_lamp,
  street_pole; `waste`: underground, recycling_island, general), otherwise 422. When the type
  changes and `attributes` isn't sent, the old attributes are cleared.
- **Flags a false positive**: `POST /elements/{id}/false-positive`, no body → `rejected`: hidden
  from `GET /elements` (list them with `?status=rejected`) and never created again from new
  images.

All three return the element, 404 if it doesn't exist, and can be repeated safely. ML never
changes `verified`, `corrected` or `rejected` elements; new images of them are only linked.

## IDs

- `image_id` is chosen by the API (ML only uses it as the file name): `up_<hex>` for uploaded
  images, `<sequence_id>_<frame_index>` for video frames (`vid_<hex>_0000`), `mly_<id>` /
  `kv_<id>` for Mapillary / KartaView. The web may send its own `image_id` for images.
- Observation and element ids are created by ML and stored as they are, so they match ML's
  logs. Observation ids are plain strings (ML sends short hex ids); element ids must be UUIDs,
  and if ML ever sends an element id that isn't one, the request fails with 502.
- ML's mock derives observation ids from the `image_id`, so an `image_id` must reach ML only
  once. The API makes sure of that: an id that was already processed is skipped (`duplicate`).

## Shared folder

ML writes blurred images to `<SHARED_DIR>/images/<image_id>.jpg` (`/data` in Docker, `../data`
locally). The API serves that folder at `/media/images/`. API mock mode also draws its sample
images there (`mock_*.jpg`), so URLs work the same in both modes. Raw images and videos are
never saved.

## Tests

```bash
uv run pytest
```

Run in API mock mode with a temporary shared folder and a stand-in for the ML service
(`tests/conftest.py`), so neither the database nor ML is needed.

## Changing models

`create_all` only creates missing tables. After a model change (like this one: new `images`
and `observations` tables, plus `attributes` and `status` on `elements`), drop the old tables or
`docker compose down -v` (this also deletes the DB data and the shared images).
