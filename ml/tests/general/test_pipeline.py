import re
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from src import pipeline as pipeline_mod
from src.classification.onnx_classifier import MultiCategoryClassifier
from src.config import DepthConfig, GeometryConfig, PathsConfig, Settings
from src.geometry.base import GeoLocation
from src.geometry.localizer import GeoLocalizer
from src.pipeline import InferencePipeline
from src.privacy.anonymizer import PrivacyAnonymizer
from src.service.schemas import InferResponse

from .conftest import FakeAnonymizer, FakeClassifier, FakeDetector, FakeLocalizer, det


# construction


def test_injected_stages_are_used(build):
    pipe, s = build()
    assert (pipe.anonymizer, pipe.detector, pipe.classifier, pipe.localizer) == (
        s.anonymizer,
        s.detector,
        s.classifier,
        s.localizer,
    )


def test_default_stages_built_from_settings(settings, taxonomy):
    pipe = InferencePipeline(settings, taxonomy, detector=FakeDetector())
    assert isinstance(pipe.anonymizer, PrivacyAnonymizer)
    assert isinstance(pipe.classifier, MultiCategoryClassifier)
    assert isinstance(pipe.localizer, GeoLocalizer)


def test_warmup_loads_detector(build):
    pipe, s = build()
    pipe.warmup()
    assert s.detector.loaded == 1


# _build_default_detector-


@pytest.fixture
def detector_factory(monkeypatch, build, tmp_path):
    captured = {}
    monkeypatch.setattr(
        pipeline_mod,
        "build_detector",
        lambda cfg, tax, weights_path=None: captured.update(path=weights_path) or "DET",
    )
    pipe, _ = build()

    def configure(backend="yolo", weights="detector.onnx"):
        pipe.settings = SimpleNamespace(
            detection=SimpleNamespace(backend=backend, weights=weights),
            paths=SimpleNamespace(weights_path=lambda name: tmp_path / name),
        )
        return pipe

    return configure, captured


def test_explicit_weights_win(detector_factory, tmp_path):
    configure, cap = detector_factory
    assert configure("rtdetr")._build_default_detector(tmp_path / "custom.pt") == "DET"
    assert cap["path"] == tmp_path / "custom.pt"


def test_onnx_backend_uses_configured_weights_file(detector_factory, tmp_path):
    configure, cap = detector_factory
    configure("yolo", "detector.onnx")._build_default_detector(None)
    assert cap["path"] == tmp_path / "detector.onnx"


def test_rtdetr_uses_candidate_only_if_it_exists(detector_factory, tmp_path):
    configure, cap = detector_factory
    pipeline = configure("rtdetr")
    pipeline._build_default_detector(None)
    assert cap["path"] is None

    candidate = tmp_path / pipeline.settings.detection.weights
    candidate.touch()
    configure("rtdetr")._build_default_detector(None)
    assert cap["path"] == candidate


# response contract


def test_response_shape_and_path(build, image, meta):
    pipe, _ = build([det()])
    r = pipe.run(image, meta)
    assert isinstance(r, InferResponse)
    assert r.image_id == "img_1" and r.blurred_image_path == "images/img_1.jpg"
    assert len(r.observations) == 1 and r.observations[0].type == "sign.other"


def test_rounding_and_int_bbox(build, image, meta):
    geo = GeoLocation(
        bearing_deg=94.123456,
        est_lat=40.123456789,
        est_lon=-8.987654321,
        est_distance_m=10.0,
        uncertainty_m=2.3456,
        method="size_prior",
    )
    pipe, _ = build(
        [det(score=0.912345, box=(10.2, 20.7, 50.9, 60.4))],
        localizer=FakeLocalizer(geo),
    )
    [o] = pipe.run(image, meta).observations
    assert o.score == 0.9123 and o.bearing_deg == 94.12
    assert (o.est_lat, o.est_lon, o.uncertainty_m) == (40.1234568, -8.9876543, 2.35)
    assert all(isinstance(v, int) for v in o.bbox_xyxy)
    assert all(abs(a - b) <= 1 for a, b in zip(o.bbox_xyxy, (10.2, 20.7, 50.9, 60.4)))


def test_unlocalised_detection_keeps_bearing_with_null_position(build, image, meta):
    pipe, _ = build([det()], localizer=FakeLocalizer(GeoLocation(bearing_deg=45.0)))
    [o] = pipe.run(image, meta).observations
    assert o.bearing_deg == 45.0
    assert (o.est_lat, o.est_lon, o.uncertainty_m) == (None, None, None)


def test_observation_ids_unique_short_hex_and_order_kept(build, image, meta):
    pipe, s = build([det("sign.stop"), det("sign.other"), det("light.street_lamp")])
    obs = pipe.run(image, meta).observations
    ids = [o.observation_id for o in obs]
    assert len(set(ids)) == 3 and all(
        re.fullmatch(rf"{re.escape(meta.image_id)}:[0-9a-f]{{8}}", i) for i in ids
    )
    assert [o.type for o in obs] == ["sign.stop", "sign.other", "light.street_lamp"]
    assert [c.class_name for c in s.localizer.calls] == [o.type for o in obs]


# no detections


def test_no_detections_returns_empty_and_skips_later_stages(
    build, image, meta, settings
):
    pipe, s = build([])
    r = pipe.run(image, meta)
    assert r.observations == []
    assert s.classifier.seen == [] and s.localizer.calls == []
    assert (settings.paths.images_dir / "img_1.jpg").is_file()  # blurred still saved


# privacy guarantees


def test_every_stage_sees_blurred_image_not_raw(build, image, meta):
    pipe, s = build([det()])
    pipe.run(image, meta)
    assert s.anonymizer.seen == [image]
    for seen in (s.detector.seen[0], s.classifier.seen[0][0]):
        assert seen is not image
        assert (
            np.asarray(seen)[:50, :50].max() == 0
            and np.asarray(image)[:50, :50].min() >= 100
        )


def test_only_blurred_pixels_are_persisted(build, image, meta, settings):
    pipe, _ = build([det()])
    pipe.run(image, meta)
    files = [p for p in settings.paths.shared_dir.rglob("*") if p.is_file()]
    assert files == [settings.paths.images_dir / "img_1.jpg"]
    saved = np.asarray(Image.open(files[0]))
    assert saved[:50, :50].mean() < 15  # redacted corner, not raw noise (>=100)


def test_anonymizer_failure_blocks_everything(build, image, meta, settings):
    pipe, s = build([det()], anonymizer=FakeAnonymizer(error=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        pipe.run(image, meta)
    assert s.detector.seen == []
    assert not settings.paths.images_dir.exists() or not any(
        settings.paths.images_dir.iterdir()
    )


def test_missing_privacy_weights_fail_closed(settings, taxonomy, image, meta):
    pipe = InferencePipeline(
        settings,
        taxonomy,
        detector=FakeDetector([det()]),
        classifier=FakeClassifier(),
        localizer=FakeLocalizer(),
    )
    with pytest.raises(FileNotFoundError):
        pipe.run(image, meta)
    assert not settings.paths.images_dir.exists()


# saving


def test_saved_jpeg_is_valid_and_same_size(build, image, meta, settings):
    pipe, _ = build()
    pipe.run(image, meta)
    with Image.open(settings.paths.images_dir / "img_1.jpg") as im:
        assert im.format == "JPEG" and im.size == image.size


def test_save_blurred_false_writes_nothing(build, image, meta, settings):
    pipe, _ = build([det()])
    r = pipe.run(image, meta, save_blurred=False)
    assert not settings.paths.images_dir.exists()
    assert r.blurred_image_path == "images/img_1.jpg"


def test_existing_file_overwritten(build, image, meta, settings):
    settings.paths.images_dir.mkdir(parents=True)
    target = settings.paths.images_dir / "img_1.jpg"
    target.write_bytes(b"old")
    build()[0].run(image, meta)
    assert target.read_bytes() != b"old"


# classification + localisation wiring


def test_refined_label_flows_to_localizer_and_response(build, image, meta):
    pipe, s = build(
        [det("sign.other", box=(10, 10, 50, 40))],
        classifier=FakeClassifier({"sign.other": "sign.stop"}),
    )
    [o] = pipe.run(image, meta).observations
    assert o.type == "sign.stop"
    assert s.localizer.calls[0].class_name == "sign.stop"
    assert s.localizer.calls[0].bbox == (10, 10, 50, 40)


def test_frame_built_from_blurred_size_meta_and_defaults(build, image, meta):
    pipe, s = build([det()])
    pipe.run(image, meta)
    f = s.localizer.calls[0].frame
    assert (f.image_width, f.image_height) == (200, 100)
    assert (f.lat, f.lon, f.heading) == (meta.lat, meta.lon, meta.heading)
    assert f.fov_deg == pipe.settings.geometry.default_fov_deg
    assert f.camera_height_m == pipe.settings.geometry.default_camera_height_m


def test_frame_uses_meta_overrides(build, image, meta):
    pipe, s = build([det()])
    pipe.run(image, meta.model_copy(update={"fov": 70.0, "camera_height_m": 2.0}))
    f = s.localizer.calls[0].frame
    assert (f.fov_deg, f.camera_height_m) == (70.0, 2.0)


# depth


def test_depth_prepared_with_blurred_pixels_when_enabled(build, image, meta, tmp_path):
    cfg = Settings(
        paths=PathsConfig(shared_dir=tmp_path),
        geometry=GeometryConfig(depth=DepthConfig(enabled=True)),
    )
    pipe, s = build([det()], settings_=cfg)
    pipe.run(image, meta)
    [arr] = s.localizer.prepared
    assert arr.shape == (100, 200, 3) and arr[:50, :50].max() == 0


def test_depth_not_prepared_when_disabled(build, image, meta):
    pipe, s = build([det()])
    pipe.run(image, meta)
    assert s.localizer.prepared == []
