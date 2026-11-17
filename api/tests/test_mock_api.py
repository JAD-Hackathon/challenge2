"""The mock API, as the web will use it (ML replaced by tests/conftest.py's MLStub)."""

import csv
import io
import json
import uuid

ELEMENTS = "/api/v1/elements"
IMAGES = "/api/v1/images"
SPEED_LIMIT_50 = "a0000000-0000-4000-8000-000000000001"  # auto, {"limit": 50}
SPEED_LIMIT_PHASE_1 = "a0000000-0000-4000-8000-000000000009"  # auto, limit not read yet
REJECTED = "a0000000-0000-4000-8000-000000000007"
META = {"lat": 40.6412, "lon": -8.6538, "heading": 92.5}


def upload(client, files: list[tuple[str, bytes]], metas):
    return client.post(
        IMAGES,
        files=[("images", (name, content, "image/jpeg")) for name, content in files],
        data={"metas": json.dumps(metas)},
    )


# --- health / seed ---


def test_health_reports_mock_mode(client):
    assert client.get("/health").json() == {"status": "ok", "mock": True}
    assert client.get("/health/db").json()["database"] == "mock"


def test_list_hides_rejected_by_default(client):
    elements = client.get(ELEMENTS).json()
    assert len(elements) == 11
    assert all(e["status"] != "rejected" for e in elements)

    rejected = client.get(ELEMENTS, params={"status": "rejected"}).json()
    assert [e["id"] for e in rejected] == [REJECTED]


def test_list_filters_by_category(client):
    signs = client.get(ELEMENTS, params={"category": "sign"}).json()
    assert signs and all(e["category"] == "sign" for e in signs)


def test_speed_limit_attributes(client):
    read = client.get(f"{ELEMENTS}/{SPEED_LIMIT_50}").json()
    assert (read["category"], read["type"], read["attributes"]) == (
        "sign", "speed_limit", {"limit": 50},
    )  # fmt: skip
    phase_1 = client.get(f"{ELEMENTS}/{SPEED_LIMIT_PHASE_1}").json()
    assert phase_1["type"] == "speed_limit" and phase_1["attributes"] == {}


def test_element_image_is_served_from_shared_folder(client, shared_dir):
    element = client.get(f"{ELEMENTS}/{SPEED_LIMIT_50}").json()
    assert element["image_url"] == "/media/images/mock_rossio.jpg"
    assert (shared_dir / "images" / "mock_rossio.jpg").is_file()
    response = client.get(element["image_url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_unknown_element_is_404(client):
    response = client.get(f"{ELEMENTS}/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404


# --- batch upload (goes to ML, like real mode) ---


def test_batch_upload(client, shared_dir, make_jpeg, ml_stub):
    response = upload(
        client,
        [("a.jpg", make_jpeg()), ("b.jpg", make_jpeg(colour="olive"))],
        [
            {**META, "author": "ana", "license": "CC BY-SA 4.0"},
            {**META, "image_id": "web_2"},
        ],
    )
    assert response.status_code == 200
    body = response.json()

    assert [r["status"] for r in body["images"]] == ["processed", "processed"]
    assert [r["filename"] for r in body["images"]] == ["a.jpg", "b.jpg"]
    assert body["images"][1]["image_id"] == "web_2"
    assert body["images"][0]["image_id"].startswith("up_")
    assert [m.image_id for m in ml_stub.inferred] == [
        r["image_id"] for r in body["images"]
    ]
    assert len(ml_stub.dedups) == 1  # one /dedup for the whole batch

    # ML wrote the blurred copies to the shared folder; the API serves them
    for result in body["images"]:
        assert (shared_dir / "images" / f"{result['image_id']}.jpg").is_file()
        assert client.get(result["image_url"]).status_code == 200

    # ML merged the 4 detections into one element per class, with ML's ids
    by_type = {e["type"]: e for e in body["elements"]}
    assert set(by_type) == {"speed_limit", "street_lamp"}
    sign = by_type["speed_limit"]
    assert (sign["attributes"], sign["observation_count"]) == ({"limit": 50}, 2)
    first_obs = ml_stub.dedups[0].observations[0].observation_id
    assert sign["id"] == str(uuid.uuid5(uuid.NAMESPACE_URL, str(first_obs)))

    assert client.get(f"{ELEMENTS}/{sign['id']}").json() == sign
    image = client.get(f"{IMAGES}/{sign['image_id']}").json()
    assert sign["id"] in {o["element_id"] for o in image["observations"]}
    assert str(first_obs) in {
        o["id"] for o in image["observations"]
    }  # ML's observation ids


def test_batch_upload_reports_each_file(client, make_jpeg, ml_stub):
    upload(client, [("first.jpg", make_jpeg())], [{**META, "image_id": "dup"}])
    response = upload(
        client,
        [
            ("ok.jpg", make_jpeg()),
            ("broken.jpg", b"not an image"),
            ("again.jpg", make_jpeg()),
        ],
        [META, META, {**META, "image_id": "dup"}],
    )
    assert response.status_code == 200
    images = response.json()["images"]
    assert [r["status"] for r in images] == ["processed", "failed", "duplicate"]
    assert "unsupported_image" in images[1]["error"]


def test_batch_upload_when_ml_is_down(client, ml_stub):
    response = upload(client, [("a.jpg", b"ML down")], [META])
    assert response.status_code == 502
    assert response.json()["detail"] == "ML service unreachable"


def test_batch_upload_validation(client, make_jpeg, ml_stub):
    one = [("a.jpg", make_jpeg())]
    mismatch = upload(client, one, [META, META])
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"] == "Got 1 images but 2 metas"

    bad_heading = upload(client, one, [{**META, "heading": 400}])
    assert bad_heading.status_code == 422
    assert bad_heading.json()["detail"].startswith("metas[0].heading")

    assert upload(client, one, "nope").status_code == 422
    assert upload(client, one * 2, [{**META, "image_id": "x"}] * 2).status_code == 422
    assert ml_stub.inferred == []  # nothing reached ML


def test_batch_upload_size_limit(client, make_jpeg, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_BATCH_SIZE", 2)
    response = upload(client, [("a.jpg", make_jpeg())] * 3, [META] * 3)
    assert response.status_code == 422


# --- false positive ---


def test_flag_false_positive(client):
    url = f"{ELEMENTS}/{SPEED_LIMIT_50}/false-positive"
    response = client.post(url)
    assert response.status_code == 200
    flagged = response.json()
    assert flagged["status"] == "rejected"
    assert flagged["updated_at"] > flagged["created_at"]

    assert SPEED_LIMIT_50 not in {e["id"] for e in client.get(ELEMENTS).json()}
    rejected = client.get(ELEMENTS, params={"status": "rejected"}).json()
    assert SPEED_LIMIT_50 in {e["id"] for e in rejected}

    again = client.post(url)  # harmless
    assert again.status_code == 200 and again.json() == flagged


def test_flag_unknown_element_is_404(client):
    response = client.post(
        f"{ELEMENTS}/00000000-0000-4000-8000-000000000000/false-positive"
    )
    assert response.status_code == 404


# --- export ---


def test_export_geojson_and_csv(client):
    assert client.get("/api/v1/export/layers").json()[0]["table"] == "elements"

    geojson = client.get("/api/v1/export/elements.geojson").json()
    assert len(geojson["features"]) == 12  # every status, like the real export
    feature = next(
        f for f in geojson["features"] if f["properties"]["id"] == SPEED_LIMIT_50
    )
    assert feature["properties"]["attributes"] == {"limit": 50}
    assert feature["properties"]["best_observation_id"]

    near_university = {"bbox": "-8.66,40.629,-8.65,40.631"}
    box = client.get("/api/v1/export/elements.geojson", params=near_university)
    assert len(box.json()["features"]) == 2

    text = client.get("/api/v1/export/elements.csv").text.lstrip("﻿")
    row = next(
        r for r in csv.DictReader(io.StringIO(text)) if r["id"] == SPEED_LIMIT_50
    )
    assert json.loads(row["attributes"]) == {"limit": 50}  # JSON, not a Python repr
    assert float(row["latitude"]) == 40.64277

    assert client.get("/api/v1/export/nope.geojson").status_code == 404


def test_export_bbox_validation(client):
    url = "/api/v1/export/elements.geojson"
    for bad in [
        "-8.66,40.62,-8.63",  # 3 values
        "a,b,c,d",  # not numbers
        "-8.63,40.62,-8.66,40.65",  # min_lon > max_lon
        "-8.66,40.62,-8.63,95",  # latitude out of range
        "-200,40.62,-8.63,40.65",  # longitude out of range
        "-8.66,nan,-8.63,40.65",
    ]:
        response = client.get(url, params={"bbox": bad})
        assert response.status_code == 422, bad
        assert "longitude first" in response.json()["detail"]
