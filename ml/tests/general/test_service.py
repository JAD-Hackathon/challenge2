import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.config import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_MOCK", "true")
    monkeypatch.setenv("ML_SHARED_DIR", str(tmp_path))
    get_settings.cache_clear()
    from src.service.main import app

    yield TestClient(app)
    get_settings.cache_clear()


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (640, 480), "gray").save(buffer, format="PNG")
    return buffer.getvalue()


def _meta(image_id: str = "img1") -> str:
    return json.dumps(
        {"image_id": image_id, "lat": 40.64, "lon": -8.65, "heading": 90.0}
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "mock": True}


def test_infer_ok(client, tmp_path):
    r = client.post(
        "/infer",
        files={"image": ("a.png", _png_bytes(), "image/png")},
        data={"meta": _meta()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["image_id"] == "img1"
    assert body["blurred_image_path"] == "images/img1.jpg"
    assert (tmp_path / "images" / "img1.jpg").is_file()
    assert 1 <= len(body["observations"]) <= 3
    assert all(len(o["bbox_xyxy"]) == 4 for o in body["observations"])


def test_infer_is_deterministic(client):
    files = {"image": ("a.png", _png_bytes(), "image/png")}
    a = client.post("/infer", files=files, data={"meta": _meta()}).json()
    b = client.post("/infer", files=files, data={"meta": _meta()}).json()
    assert a == b


def test_infer_bad_meta(client):
    r = client.post(
        "/infer",
        files={"image": ("a.png", _png_bytes(), "image/png")},
        data={
            "meta": json.dumps(
                {"image_id": "../x", "lat": 40, "lon": -8, "heading": 90}
            )
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_meta"


def test_infer_bad_image(client):
    r = client.post(
        "/infer",
        files={"image": ("a.png", b"not an image", "image/png")},
        data={"meta": _meta()},
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_image"


def _obs(obs_id, type_, lat, lon, score=0.9):
    return {
        "observation_id": obs_id,
        "type": type_,
        "score": score,
        "bbox_xyxy": [0, 0, 10, 10],
        "est_lat": lat,
        "est_lon": lon,
    }


def test_dedup_merges_close_same_type(client):
    request = {
        "observations": [
            _obs("a", "sign.stop", 40.64000, -8.65000, 0.8),
            _obs("b", "sign.stop", 40.64001, -8.65000, 0.9),  # ~1 m away -> merged
            _obs("c", "sign.stop", 40.64100, -8.65000),  # ~110 m away -> separate
            _obs(
                "d", "light.street_lamp", 40.64000, -8.65000
            ),  # other type -> separate
            {
                "observation_id": "e",
                "type": "sign.stop",
                "score": 0.5,
                "bbox_xyxy": [0, 0, 5, 5],
            },  # no position
        ],
        "images": [],
    }
    body = client.post("/dedup", json=request).json()
    assert len(body["elements"]) == 3
    merged = next(e for e in body["elements"] if len(e["observation_ids"]) == 2)
    assert merged["best_observation_id"] == "b"
    assert body["unassigned_observation_ids"] == ["e"]
