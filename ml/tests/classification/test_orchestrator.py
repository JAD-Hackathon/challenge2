import logging
from types import SimpleNamespace


from src.classification.onnx_classifier import (
    MultiCategoryClassifier,
    ONNXCropClassifier,
)
from src.config import ClassificationConfig, PathsConfig

from .conftest import StubClassifier, make_det


def cfg(enabled=True):
    return SimpleNamespace(
        enabled=enabled,
        sign_weights="sign.onnx",
        container_weights="cont.onnx",
        lighting_weights="light.onnx",
    )


def categories(multi):
    return [c.category for c in multi._classifiers]


def test_disabled_creates_nothing(tmp_path, taxonomy, image):
    multi = MultiCategoryClassifier(
        cfg(False), PathsConfig(weights_dir=tmp_path), taxonomy
    )
    dets = [make_det()]
    assert multi._classifiers == [] and multi.refine(image, dets) == dets


def test_only_existing_weight_files_get_classifiers(tmp_path, taxonomy):
    (tmp_path / "sign.onnx").touch()
    (tmp_path / "cont.onnx").touch()
    multi = MultiCategoryClassifier(cfg(), PathsConfig(weights_dir=tmp_path), taxonomy)
    assert categories(multi) == ["sign", "waste"]
    assert all(isinstance(c, ONNXCropClassifier) for c in multi._classifiers)


def test_missing_weights_logged(tmp_path, taxonomy, caplog):
    with caplog.at_level(logging.WARNING):
        MultiCategoryClassifier(cfg(), PathsConfig(weights_dir=tmp_path), taxonomy)
    assert "not found" in caplog.text


def test_enabled_with_real_config_does_not_crash(tmp_path, taxonomy):
    """ClassificationConfig must expose every weights field the orchestrator reads."""
    MultiCategoryClassifier(
        ClassificationConfig(enabled=True), PathsConfig(weights_dir=tmp_path), taxonomy
    )


def test_refine_no_classifiers_or_detections_returns_copy(tmp_path, taxonomy, image):
    multi = MultiCategoryClassifier(cfg(), PathsConfig(weights_dir=tmp_path), taxonomy)
    dets = [make_det()]
    out = multi.refine(image, dets)
    assert out == dets and out is not dets
    assert multi.refine(image, []) == []


def test_refine_applies_every_classifier(taxonomy, image, tmp_path):
    multi = MultiCategoryClassifier(cfg(), PathsConfig(weights_dir=tmp_path), taxonomy)
    multi._classifiers = [
        StubClassifier([("sign.stop", 0.9)], "sign", taxonomy),
        StubClassifier([("waste.underground", 0.9)], "waste", taxonomy),
    ]
    dets = [
        make_det("sign.other"),
        make_det("waste.general"),
        make_det("light.street_lamp"),
    ]
    out = multi.refine(image, dets)
    assert [d.label for d in out] == [
        "sign.stop",
        "waste.underground",
        "light.street_lamp",
    ]
    assert [d.label for d in dets] == [
        "sign.other",
        "waste.general",
        "light.street_lamp",
    ]
