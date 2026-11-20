"""Video upload: the API keeps one frame every spacing_m metres, places it with the GPS track
(or the drawn route) and sends it to ML /infer like an uploaded image.

Test videos are real mp4s (conftest.make_video: 6 s at 10 fps, frame n is grey 4 * n) and the
track goes north at 5 m/s for 6 s (conftest.make_gpx): 30 m, one point per second.
"""

import json
import re
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
from PIL import Image

from app.core.config import settings
from app.services import ml_client

VIDEOS = "/api/v1/videos"
T0 = datetime(2025, 6, 12, 10, 15, tzinfo=UTC)  # start of make_gpx's track
M_PER_DEG_LAT = 111_195
ROUTE = [{"lat": 40.6412, "lon": -8.6538}, {"lat": 40.6425, "lon": -8.6531}]  # ~156 m


def post_video(client, video: bytes, meta: dict | None = None, track: bytes | None = None):
    data = {"meta": json.dumps(meta)} if meta is not None else {}
    files = [("video", ("ride.mp4", video, "video/mp4"))]
    if track is not None:
        files.append(("track", ("ride.gpx", track, "application/gpx+xml")))
    return client.post(VIDEOS, files=files, data=data)


def metres_north(camera) -> float:
    return round((camera.lat - 40.64) * M_PER_DEG_LAT, 1)


def test_video_frames_go_to_infer_and_are_stored(
    client, ml_stub, shared_dir, make_video, make_gpx
):
    meta = {"spacing_m": 10, "fov": 70, "author": "team", "license": "CC0"}
    response = post_video(client, make_video(), meta, track=make_gpx())
    assert response.status_code == 200
    body = response.json()
    seq = body["sequence_id"]
    assert seq.startswith("vid_") and body["location_source"] == "track"

    # one frame every 10 m of the 30 m track, each one an ordinary /infer call
    sent = ml_stub.inferred
    assert [c.image_id for c in sent] == [f"{seq}_{i:04d}" for i in range(4)]
    assert [c.frame_index for c in sent] == [0, 1, 2, 3]
    assert [metres_north(c) for c in sent] == [0, 10, 20, 30]
    assert {(c.source, c.sequence_id, c.fov, c.heading) for c in sent} == {
        ("video", seq, 70, 0.0)  # going north
    }
    # ...and they are the right frames: at 0, 2, 4, 6 s = frames 0, 20, 40, 59 (the last)
    greys = [
        np.asarray(Image.open(shared_dir / "images" / f"{c.image_id}.jpg")).mean()
        for c in sent
    ]
    assert np.allclose(greys, [0, 80, 160, 236], atol=6)

    assert [r["filename"] for r in body["images"]] == [f"ride.mp4#{i}" for i in range(4)]
    assert [r["status"] for r in body["images"]] == ["processed"] * 4
    assert {e["type"] for e in body["elements"]} == {"speed_limit", "street_lamp"}
    assert len(ml_stub.dedups) == 1  # one /dedup for the whole video

    frame = client.get(f"/api/v1/images/{seq}_0001").json()
    assert (frame["source"], frame["attribution"]) == ("video", "© team, CC0")
    assert frame["captured_at"] == "2025-06-12T10:15:02Z"  # GPS time 10 m along the track
    assert client.get(frame["image_url"]).status_code == 200


def test_video_lined_up_with_the_track(client, ml_stub, make_video, make_gpx):
    """The video started 2 s after the track, said either way: its first frame is 10 m along."""
    video, gpx = make_video(), make_gpx()
    for clock in ({"start_time": "2025-06-12T10:15:02Z"}, {"time_offset_s": 2}):
        ml_stub.inferred.clear()
        response = post_video(client, video, {"spacing_m": 10, **clock}, track=gpx)
        assert response.status_code == 200
        assert [metres_north(c) for c in ml_stub.inferred] == [10, 20, 30]


def test_video_placed_with_drawn_route(client, ml_stub, make_video):
    meta = {"route": ROUTE, "spacing_m": 50, "heading_offset_deg": 90}
    response = post_video(client, make_video(), meta)
    assert response.status_code == 200
    assert response.json()["location_source"] == "route"

    sent = ml_stub.inferred  # 0, 50, 100, 150 m, spread over the video at constant speed
    assert len(sent) == 4
    assert (sent[0].lat, sent[0].lon) == (40.6412, -8.6538)
    assert {round(c.heading) for c in sent} == {22 + 90}  # route goes NNE, camera looks right
    frame = client.get(f"/api/v1/images/{sent[1].image_id}").json()
    assert frame["captured_at"] is None  # no clock without a track


def test_video_needs_a_track_or_a_route(client, ml_stub, make_video):
    for track in (None, b""):  # a web form with the file input left empty sends b""
        response = post_video(client, make_video(), track=track)
        assert response.status_code == 422
        assert response.json()["detail"].startswith("No location for the video")
    assert ml_stub.inferred == []


def test_video_refused_before_ml(client, ml_stub, make_video, make_gpx, monkeypatch):
    video, gpx = make_video(), make_gpx()
    an_hour_later = (T0 + timedelta(hours=1)).isoformat()
    cases = [
        (b"not a video", gpx, {}, "Could not read the video"),
        (video, b"<gpx", {}, "track: not a GPX file"),
        (video, make_gpx(seconds=0), {}, "track: needs at least 2 points, got 1"),
        (video, make_gpx(speed_mps=0), {}, "The track doesn't move"),
        (video, gpx, {"start_time": an_hour_later}, "No frame of the video falls on"),
    ]
    for content, track, meta, error in cases:
        response = post_video(client, content, meta, track=track)
        assert response.status_code == 422, error
        assert response.json()["detail"].startswith(error)

    monkeypatch.setattr(settings, "MAX_VIDEO_FRAMES", 2)
    response = post_video(client, video, track=gpx)
    assert response.status_code == 422
    assert response.json()["detail"].startswith("The video gives 7 frames at one every 5 m")
    assert ml_stub.inferred == []


def test_video_too_big(client, ml_stub, monkeypatch, make_video, make_gpx):
    monkeypatch.setattr(settings, "MAX_VIDEO_MB", 0)
    response = post_video(client, make_video(), track=make_gpx())
    assert response.status_code == 413
    assert ml_stub.inferred == []


def test_video_validation(client, ml_stub, make_video, make_gpx):
    video, gpx = make_video(), make_gpx()
    bad_meta = post_video(client, video, {"spacing_m": 0}, track=gpx)
    assert bad_meta.status_code == 422
    assert bad_meta.json()["detail"].startswith("meta.spacing_m")

    one_point = post_video(client, video, {"route": ROUTE[:1]})
    assert one_point.status_code == 422
    assert one_point.json()["detail"].startswith("meta.route")

    bad_point = post_video(client, video, {"route": [{"lat": 91, "lon": 0}] * 2})
    assert bad_point.status_code == 422
    assert bad_point.json()["detail"].startswith("meta.route[0].lat")

    both = post_video(client, video, {"route": ROUTE}, track=gpx)
    assert both.status_code == 422
    assert both.json()["detail"] == "Send either a GPS track or meta.route, not both"

    no_video = client.post(VIDEOS, files=[("track", ("ride.gpx", gpx, "application/gpx+xml"))])
    assert no_video.status_code == 422
    assert ml_stub.inferred == []


# --- the real ML client, against a fake HTTP server ---


def fake_ml_server(monkeypatch, respond) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        requests.append(request)
        return respond(request)

    monkeypatch.setattr(
        ml_client,
        "_client",
        lambda timeout: httpx.Client(
            base_url="http://ml",
            transport=httpx.MockTransport(handler),
            timeout=timeout,
        ),
    )
    return requests


def infer_without_detections(request: httpx.Request) -> httpx.Response:
    image_id = re.search(rb'"image_id":"([^"]+)"', request.content)[1].decode()
    if image_id.endswith("_0001"):
        error = {"code": "unsupported_image", "message": "cannot decode image file"}
        return httpx.Response(415, json={"error": error})
    return httpx.Response(
        200,
        json={
            "image_id": image_id,
            "blurred_image_path": f"images/{image_id}.jpg",
            "observations": [],
        },
    )


def test_frames_reach_ml_infer(client, monkeypatch, make_video, make_gpx):
    """ML has no video endpoint: every frame is a POST /infer, JPEG + the frame's CameraMeta.
    A frame ML refuses only fails that frame, like an image of a batch."""
    requests = fake_ml_server(monkeypatch, infer_without_detections)
    response = post_video(client, make_video(), {"spacing_m": 10}, track=make_gpx())
    assert response.status_code == 200

    assert [r.url.path for r in requests] == ["/infer"] * 4
    first = requests[0].content
    assert b'name="image"' in first and b"Content-Type: image/jpeg" in first
    assert b'"source":"video"' in first and b'"frame_index":0' in first

    body = response.json()
    assert [r["status"] for r in body["images"]] == [
        "processed", "failed", "processed", "processed"
    ]  # fmt: skip
    assert body["images"][1]["error"] == "ML unsupported_image: cannot decode image file"
    assert body["elements"] == []  # no detections: /dedup isn't even called
