"""Technician corrections: edit (PATCH), verify, flag false positive (mock API)."""

ELEMENTS = "/api/v1/elements"
SPEED_LIMIT_50 = "a0000000-0000-4000-8000-000000000001"  # auto, {"limit": 50}
VERIFIED_LAMP = "a0000000-0000-4000-8000-000000000004"
REJECTED = "a0000000-0000-4000-8000-000000000007"
CORRECTED = "a0000000-0000-4000-8000-000000000011"
UNKNOWN = "00000000-0000-4000-8000-000000000000"


def patch(client, element_id: str, body: dict):
    return client.patch(f"{ELEMENTS}/{element_id}", json=body)


def test_fix_speed_limit_value(client):
    response = patch(client, SPEED_LIMIT_50, {"attributes": {"limit": 30}})
    assert response.status_code == 200
    element = response.json()
    assert (element["type"], element["attributes"], element["status"]) == (
        "speed_limit", {"limit": 30}, "corrected",
    )  # fmt: skip
    assert client.get(f"{ELEMENTS}/{SPEED_LIMIT_50}").json() == element


def test_fix_type(client):
    to_yield = patch(client, SPEED_LIMIT_50, {"type": "yield"}).json()
    assert (to_yield["category"], to_yield["type"], to_yield["name"]) == (
        "sign", "yield", "Cedência de passagem",
    )  # fmt: skip
    assert to_yield["attributes"] == {}  # {"limit": 50} described the old type

    to_waste = patch(
        client, SPEED_LIMIT_50, {"category": "waste", "type": "general"}
    ).json()
    assert (to_waste["category"], to_waste["name"]) == (
        "waste",
        "Contentor indiferenciado",
    )

    wrong = patch(client, VERIFIED_LAMP, {"type": "stop"})  # light.stop doesn't exist
    assert wrong.status_code == 422
    assert wrong.json()["detail"].startswith("Unknown type 'light.stop'")


def test_fix_position(client):
    moved = patch(
        client, SPEED_LIMIT_50, {"latitude": 40.6428, "longitude": -8.6546}
    ).json()
    assert (moved["latitude"], moved["longitude"]) == (40.6428, -8.6546)
    assert moved["type"] == "speed_limit" and moved["attributes"] == {
        "limit": 50
    }  # untouched


def test_patch_validation(client):
    assert patch(client, SPEED_LIMIT_50, {}).status_code == 422  # nothing to change
    assert patch(client, SPEED_LIMIT_50, {"latitude": 40.64}).status_code == 422
    assert (
        patch(client, SPEED_LIMIT_50, {"latitude": 95, "longitude": 0}).status_code
        == 422
    )
    assert patch(client, UNKNOWN, {"type": "stop"}).status_code == 404


def test_verify(client):
    confirmed = client.post(f"{ELEMENTS}/{SPEED_LIMIT_50}/verify").json()
    assert confirmed["status"] == "verified"

    # undoes a false-positive flag: back on the list
    restored = client.post(f"{ELEMENTS}/{REJECTED}/verify").json()
    assert restored["status"] == "verified"
    assert REJECTED in {e["id"] for e in client.get(ELEMENTS).json()}

    # a corrected element is already human-checked
    assert client.post(f"{ELEMENTS}/{CORRECTED}/verify").json()["status"] == "corrected"
    assert client.post(f"{ELEMENTS}/{UNKNOWN}/verify").status_code == 404


def test_flag_then_verify_then_flag(client):
    url = f"{ELEMENTS}/{SPEED_LIMIT_50}"
    assert client.post(f"{url}/false-positive").json()["status"] == "rejected"
    assert client.post(f"{url}/verify").json()["status"] == "verified"
    assert client.post(f"{url}/false-positive").json()["status"] == "rejected"
