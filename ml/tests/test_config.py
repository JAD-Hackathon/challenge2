import pytest
from pydantic import ValidationError

from src.config import load_settings, DedupConfig
from src.taxonomy import load_taxonomy


# === settings ===


def test_defaults_load():
    s = load_settings()
    assert s.geometry.default_fov_deg == 90.0
    assert set(s.dedup.radius_m) == {"sign", "light", "waste"}
    assert s.paths.images_dir.name == "images"


def test_override_file_merges(tmp_path):
    f = tmp_path / "city.yaml"
    f.write_text("dedup:\n  radius_m: {sign: 1.0, light: 4.0, waste: 5.0}\n")
    s = load_settings(path=f)
    assert s.dedup.radius_m["sign"] == 1.0
    assert s.geometry.max_distance_m == 40.0


def test_env_override(monkeypatch):
    monkeypatch.setenv("ML_MOCK", "1")
    monkeypatch.setenv("ML_DEVICE", "cpu")
    s = load_settings()
    assert s.service.mock is True
    assert s.detection.device == "cpu"


def test_unknown_key_rejected():
    with pytest.raises(ValidationError):
        load_settings(overrides={"detection": {"confidence": 0.5}})


def test_incomplete_radius_rejected():
    with pytest.raises(ValidationError):
        DedupConfig(radius_m={"sign": 2.0})


# === taxonomy ===


def test_taxonomy_basic():
    t = load_taxonomy()
    assert t.names[0] == "sign.stop"
    lamp_id = t.id_of("light.street_lamp")
    assert t.names_by_id()[lamp_id] == "light.street_lamp"
    assert t.by_id(t.id_of("waste.general")).name == "waste.general"
    assert t.get("waste.general").category == "waste"
    assert [c.name for c in t.in_category("sign")][-1] == "sign.other"


def test_methods_for():
    t = load_taxonomy()
    order = ["size_prior", "ground_plane"]
    assert t.methods_for("sign.stop", order) == ["size_prior"]
    assert t.methods_for("waste.underground", order) == ["ground_plane"]
    assert t.methods_for("light.street_lamp", order) == ["size_prior", "ground_plane"]


def test_unknown_class():
    with pytest.raises(KeyError):
        load_taxonomy().get("sign.nope")


def test_bad_taxonomy_rejected(tmp_path):
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "classes:\n  - {name: sign.stop, label: a}\n  - {name: sign.stop, label: b}\n"
    )
    with pytest.raises(ValidationError):
        load_taxonomy(dup)

    bad = tmp_path / "bad.yaml"
    bad.write_text("classes:\n  - {name: Stop, label: a}\n")
    with pytest.raises(ValidationError):
        load_taxonomy(bad)
