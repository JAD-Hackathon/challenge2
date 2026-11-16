"""Images from Mapillary / KartaView: the web sends the file + the site's record as meta."""

import json
import math
from datetime import UTC, datetime

import pytest
from app.services import street_view

IMAGES = "/api/v1/images"

MAPILLARY = {  # GET graph.mapillary.com/images?fields=MAPILLARY_FIELDS
    "id": "1234",
    "computed_geometry": {"type": "Point", "coordinates": [-8.6538, 40.6412]},
    "computed_compass_angle": 92.5,
    "camera_type": "perspective",
    "camera_parameters": [0.8, 0, 0],
    "width": 2048,
    "height": 1536,
    "sequence": "seqA",
    "captured_at": 1749723300000,  # ms
    "creator": {"username": "jsmith", "id": "99"},
}
KARTAVIEW = {  # KartaView API v2 photo
    "id": 77,
    "lat": "40.6405",
    "lng": "-8.6536",
    "heading": "180",
    "projection": "PLANE",
    "fieldOfView": "70",
    "sequenceId": 5,
    "sequenceIndex": "3",
    "shotDate": "2019-07-09 09:11:43",
}


def upload(client, metas: list[dict], make_jpeg):
    files = [("images", (f"{i}.jpg", make_jpeg(), "image/jpeg")) for i in range(len(metas))]
    return client.post(IMAGES, files=files, data={"metas": json.dumps(metas)})


def test_mapillary_and_kartaview_records(client, make_jpeg, ml_stub):
    response = upload(
        client, [{"mapillary": MAPILLARY}, {"kartaview": KARTAVIEW, "author": "kv_user"}], make_jpeg
    )
    assert response.status_code == 200
    body = response.json()
    assert [r["image_id"] for r in body["images"]] == ["mly_1234", "kv_77"]
    assert [r["status"] for r in body["images"]] == ["processed", "processed"]

    mly, kv = ml_stub.inferred  # what ML got, worked out from the records
    assert (mly.lat, mly.lon, mly.heading, mly.source) == (40.6412, -8.6538, 92.5, "mapillary")
    assert mly.fov == pytest.approx(math.degrees(2 * math.atan(0.5 / 0.8)))
    assert (mly.sequence_id, mly.frame_index) == ("seqA", 0)
    assert (kv.lat, kv.heading, kv.fov, kv.sequence_id, kv.frame_index) == (
        40.6405, 180, 70, "5", 3,
    )  # fmt: skip

    image = client.get(f"{IMAGES}/mly_1234").json()
    assert image["attribution"] == "© jsmith (Mapillary), CC BY-SA 4.0"
    assert image["captured_at"] == "2025-06-12T10:15:00Z"
    kv_image = client.get(f"{IMAGES}/kv_77").json()
    assert kv_image["attribution"] == "© kv_user (KartaView), CC BY-SA 4.0"  # override

    element = next(e for e in body["elements"] if e["image_id"] == "mly_1234")
    assert element["attribution"] == "© jsmith (Mapillary), CC BY-SA 4.0"


def test_unusable_records_fail_alone(client, make_jpeg, ml_stub):
    panorama = {**MAPILLARY, "id": "1", "camera_type": "spherical"}
    no_heading = {**KARTAVIEW, "id": 2, "heading": None}
    no_id = {k: v for k, v in MAPILLARY.items() if k != "id"}
    response = upload(
        client,
        [
            {"mapillary": panorama},
            {"kartaview": no_heading},
            {"mapillary": no_id},
            {"mapillary": MAPILLARY},
        ],
        make_jpeg,
    )
    assert response.status_code == 200
    results = response.json()["images"]
    assert [r["status"] for r in results] == ["failed", "failed", "failed", "processed"]
    assert "360° panorama" in results[0]["error"]
    assert results[1]["error"].startswith("kartaview image without position")
    assert results[2]["error"] == "mapillary record: missing 'id'"
    assert [m.image_id for m in ml_stub.inferred] == ["mly_1234"]  # only the good one reached ML


def test_same_mapillary_image_twice(client, make_jpeg, ml_stub):
    assert upload(client, [{"mapillary": MAPILLARY}] * 2, make_jpeg).status_code == 422
    upload(client, [{"mapillary": MAPILLARY}], make_jpeg)
    again = upload(client, [{"mapillary": MAPILLARY}], make_jpeg).json()["images"][0]
    assert again["status"] == "duplicate"


def test_frame_indexes_follow_capture_time(client, make_jpeg, ml_stub):
    later = {**MAPILLARY, "id": "2", "captured_at": MAPILLARY["captured_at"] + 2000}
    other_sequence = {**MAPILLARY, "id": "3", "sequence": "seqB"}
    upload(
        client,
        [{"mapillary": later}, {"mapillary": MAPILLARY}, {"mapillary": other_sequence}],
        make_jpeg,
    )
    frames = {m.image_id: m.frame_index for m in ml_stub.inferred}
    assert frames == {"mly_2": 1, "mly_1234": 0, "mly_3": 0}


# --- converters ---


def test_mapillary_fallbacks():
    meta = street_view.from_mapillary(
        {"id": "5", "geometry": {"coordinates": [-8.65, 40.64]}, "compass_angle": 360.0}
    )
    assert meta is not None
    assert (meta.heading, meta.fov, meta.author, meta.captured_at) == (0.0, None, None, None)
    assert street_view.from_mapillary({"id": "6", "compass_angle": 10}) is None  # no position


def test_kartaview_fallbacks():
    assert street_view.from_kartaview({**KARTAVIEW, "projection": "SPHERE"}) is None
    meta = street_view.from_kartaview({**KARTAVIEW, "user": {"username": "u"}, "shotDate": None})
    assert meta is not None and (meta.author, meta.captured_at) == ("u", None)
    dated = street_view.from_kartaview(KARTAVIEW)
    assert dated is not None and dated.captured_at == datetime(2019, 7, 9, 9, 11, 43, tzinfo=UTC)
