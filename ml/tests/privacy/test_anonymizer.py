import numpy as np
import pytest
from PIL import Image

from src.config import PathsConfig, PrivacyConfig
from src.privacy.anonymizer import PrivacyAnonymizer

from .conftest import face_box, plate_box


def make(fake_detector, face=(), plate=(), **cfg):
    cfg = {"method": "black", "margin": 0.0, **cfg}
    return PrivacyAnonymizer(
        PrivacyConfig(**cfg),
        PathsConfig(),
        face_detector=fake_detector(face),
        plate_detector=fake_detector(plate),
    )


def test_disabled_returns_copy_and_skips_detectors(fake_detector, noise_image):
    anon = make(fake_detector, face=[face_box()], enabled=False)
    res = anon.anonymize(noise_image)
    assert np.array_equal(np.array(res.image), np.array(noise_image))
    assert res.image is not noise_image
    assert anon.face_detector.calls == [] and anon.plate_detector.calls == []
    assert (res.faces_blurred, res.plates_blurred, res.boxes) == (0, 0, [])


def test_no_detections_returns_unchanged_copy(fake_detector, noise_image):
    res = make(fake_detector).anonymize(noise_image)
    assert np.array_equal(np.array(res.image), np.array(noise_image))
    assert res.image is not noise_image
    assert res.boxes == []


def test_faces_and_plates_redacted_and_counted(fake_detector, noise_image):
    f, p = face_box((40, 30, 80, 70)), plate_box((100, 80, 140, 100))
    res = make(fake_detector, face=[f], plate=[p]).anonymize(noise_image)
    out, src = np.array(res.image), np.array(noise_image)
    assert (out[30:70, 40:80] == 0).all()
    assert (out[80:100, 100:140] == 0).all()
    assert (res.faces_blurred, res.plates_blurred) == (1, 1)
    assert res.boxes == [f, p]
    mask = np.ones(src.shape[:2], bool)
    mask[30:70, 40:80] = mask[80:100, 100:140] = False
    assert np.array_equal(out[mask], src[mask])


def test_only_plates(fake_detector, noise_image):
    res = make(
        fake_detector, plate=[plate_box(), plate_box((10, 10, 40, 30))]
    ).anonymize(noise_image)
    assert (res.faces_blurred, res.plates_blurred) == (0, 2)


def test_config_margin_is_used(fake_detector, noise_image):
    res = make(fake_detector, face=[face_box((40, 40, 80, 80))], margin=0.5).anonymize(
        noise_image
    )
    assert (np.array(res.image)[25:95, 25:95] == 0).all()


@pytest.mark.parametrize("mode", ["RGBA", "L", "P"])
def test_non_rgb_input_is_converted(fake_detector, noise_image, mode):
    img = noise_image.convert(mode)
    anon = make(fake_detector, face=[face_box()])
    res = anon.anonymize(img)
    assert res.image.mode == "RGB"
    assert all(c.mode == "RGB" for c in anon.face_detector.calls)


def test_input_image_not_mutated(fake_detector, noise_image):
    before = np.array(noise_image).copy()
    make(fake_detector, face=[face_box()]).anonymize(noise_image)
    assert np.array_equal(np.array(noise_image), before)


@pytest.mark.parametrize("which", ["face", "plate"])
def test_detector_failure_propagates_fail_closed(fake_detector, noise_image, which):
    anon = make(fake_detector)
    setattr(anon, f"{which}_detector", fake_detector(error=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        anon.anonymize(noise_image)


def test_missing_weights_raise_instead_of_returning_unblurred(tmp_path, noise_image):
    """Default detectors with no weights on disk must never silently pass the image."""
    anon = PrivacyAnonymizer(
        PrivacyConfig(), PathsConfig(weights_dir=tmp_path)
    )  # lazy: no error yet
    with pytest.raises(FileNotFoundError):
        anon.anonymize(noise_image)


def test_result_is_pil_image(fake_detector, noise_image):
    res = make(fake_detector, face=[face_box()]).anonymize(noise_image)
    assert isinstance(res.image, Image.Image) and res.image.size == noise_image.size
