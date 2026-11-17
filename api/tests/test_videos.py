"""Video upload: the API passes video + GPX to ML /infer-video and stores the frames it returns."""

import json

import httpx
from app.core.config import settings
from app.services import ml_client

VIDEOS = "/api/v1/videos"
GPX = b'<?xml version="1.0"?><gpx version="1.1"><trk><trkseg/></trk></gpx>'


def post_video(client, content: bytes = b"fake mp4 bytes", meta: dict | None = None):
    data = {"meta": json.dumps(meta)} if meta is not None else {}
    files = [
        ("video", ("ride.mp4", content, "video/mp4")),
        ("track", ("ride.gpx", GPX, "application/gpx+xml")),
    ]
    return client.post(VIDEOS, files=files, data=data)


def test_video_frames_from_ml_are_stored(client, shared_dir, ml_stub):
    meta = {
        "spacing_m": 10,
        "time_offset_s": 2,
        "fov": 70,
        "author": "team",
        "license": "CC0",
    }
    response = post_video(client, meta=meta)
    assert response.status_code == 200
    body = response.json()

    # what ML received: the video and GPX untouched, the settings, a fresh sequence_id
    (video, track, sent) = ml_stub.videos[0]
    assert (video, track) == (b"fake mp4 bytes", GPX)
    assert sent.sequence_id == body["sequence_id"] and sent.sequence_id.startswith(
        "vid_"
    )
    assert (sent.spacing_m, sent.time_offset_s, sent.fov) == (10, 2, 70)
    assert "author" not in sent.model_dump()  # attribution stays in the API

    # every frame ML kept is stored like an uploaded image
    seq = body["sequence_id"]
    assert [r["image_id"] for r in body["images"]] == [
        f"{seq}_{i:04d}" for i in range(3)
    ]
    assert [r["filename"] for r in body["images"]] == [
        f"ride.mp4#{i}" for i in range(3)
    ]
    assert [r["status"] for r in body["images"]] == ["processed"] * 3
    assert {e["type"] for e in body["elements"]} == {"speed_limit", "street_lamp"}
    assert len(ml_stub.dedups) == 1  # one /dedup for the whole video

    frame = client.get(f"/api/v1/images/{seq}_0001").json()
    assert (frame["source"], frame["attribution"]) == ("video", "© team, CC0")
    assert frame["captured_at"] == "2025-06-12T10:15:01Z"
    assert client.get(frame["image_url"]).status_code == 200


def test_video_too_big(client, ml_stub, monkeypatch):
    monkeypatch.setattr(settings, "MAX_VIDEO_MB", 0)
    response = post_video(client)
    assert response.status_code == 413
    assert ml_stub.videos == []


def test_video_refused_by_ml(client, ml_stub):
    response = post_video(client, content=b"not a video")
    assert response.status_code == 422
    assert response.json()["detail"] == "ML unsupported_video: could not read the video"


def test_video_validation(client, ml_stub):
    bad_meta = post_video(client, meta={"spacing_m": 0})
    assert bad_meta.status_code == 422 and bad_meta.json()["detail"].startswith(
        "meta.spacing_m"
    )

    no_track = client.post(VIDEOS, files=[("video", ("ride.mp4", b"x", "video/mp4"))])
    assert no_track.status_code == 422
    assert ml_stub.videos == []


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


def test_video_while_ml_has_no_video_endpoint(client, monkeypatch):
    requests = fake_ml_server(
        monkeypatch, lambda r: httpx.Response(404, json={"detail": "x"})
    )
    response = post_video(client, meta={"spacing_m": 5})

    assert response.status_code == 501
    assert response.json()["detail"] == "ML service has no /infer-video endpoint yet"

    (sent,) = requests  # the multipart request the API sends to ML
    assert sent.url.path == "/infer-video"
    assert sent.extensions["timeout"]["read"] == settings.ML_VIDEO_TIMEOUT_S
    for part in (
        b'name="video"',
        b"fake mp4 bytes",
        b'name="track"',
        GPX,
        b'name="meta"',
    ):
        assert part in sent.content
    assert b'"spacing_m":5.0' in sent.content


def test_video_response_from_ml_is_parsed(client, monkeypatch):
    def respond(request: httpx.Request) -> httpx.Response:
        sequence_id = (
            request.content.split(b'"sequence_id":"')[1].split(b'"')[0].decode()
        )
        frame = {
            "camera": {
                "image_id": f"{sequence_id}_0000", "lat": 40.64, "lon": -8.65, "heading": 90,
                "source": "video", "sequence_id": sequence_id, "frame_index": 0,
            },
            "captured_at": "2025-06-12T10:15:00Z",
            "blurred_image_path": f"images/{sequence_id}_0000.jpg",
            "observations": [],
        }  # fmt: skip
        return httpx.Response(200, json={"sequence_id": sequence_id, "frames": [frame]})

    fake_ml_server(monkeypatch, respond)
    body = post_video(client).json()
    assert [r["status"] for r in body["images"]] == ["processed"]
    assert body["elements"] == []  # no detections: /dedup isn't even called
