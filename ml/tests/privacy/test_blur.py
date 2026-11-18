import numpy as np
import pytest

from src.privacy.blur import apply_redaction, expand_box

METHODS = ["gaussian", "pixelate", "black"]


# expand_box


def test_expand_box_no_margin():
    assert expand_box((10, 10, 30, 30), 0.0, 100, 100) == (10, 10, 30, 30)


def test_expand_box_margin_is_fraction_of_size():
    # w = h = 20 -> dx = dy = 4
    assert expand_box((10, 10, 30, 30), 0.2, 100, 100) == (6, 6, 34, 34)


def test_expand_box_clamped_to_image():
    assert expand_box((0, 0, 20, 20), 0.5, 25, 25) == (0, 0, 25, 25)


def test_expand_box_fully_outside_gives_empty_box():
    x0, y0, x1, y1 = expand_box((200, 200, 220, 220), 0.0, 100, 100)
    assert x1 - x0 == 0 and y1 - y0 == 0


def test_expand_box_inverted_box_does_not_blow_up():
    x0, y0, x1, y1 = expand_box((30, 30, 10, 10), 0.2, 100, 100)
    assert 0 <= x0 <= 100 and 0 <= y1 <= 100


# apply_redaction


def test_empty_boxes_returns_equal_copy(noise_rgb):
    out = apply_redaction(noise_rgb, [])
    assert np.array_equal(out, noise_rgb)
    assert out is not noise_rgb


@pytest.mark.parametrize("method", METHODS)
def test_input_not_mutated(noise_rgb, method):
    before = noise_rgb.copy()
    apply_redaction(noise_rgb, [(40, 30, 80, 70)], method=method)
    assert np.array_equal(noise_rgb, before)


@pytest.mark.parametrize("method", METHODS)
def test_box_changed_outside_untouched(noise_rgb, method):
    out = apply_redaction(noise_rgb, [(40, 30, 80, 70)], method=method, margin=0.0)
    assert not np.array_equal(out[30:70, 40:80], noise_rgb[30:70, 40:80])
    mask = np.ones(noise_rgb.shape[:2], bool)
    mask[30:70, 40:80] = False
    assert np.array_equal(out[mask], noise_rgb[mask])


@pytest.mark.parametrize("method", METHODS)
def test_shape_and_dtype_preserved(noise_rgb, method):
    out = apply_redaction(noise_rgb, [(40, 30, 80, 70)], method=method)
    assert out.shape == noise_rgb.shape and out.dtype == np.uint8


def test_black_zeros_region(noise_rgb):
    out = apply_redaction(noise_rgb, [(40, 30, 80, 70)], method="black", margin=0.0)
    assert (out[30:70, 40:80] == 0).all()


def test_pixelate_has_few_distinct_blocks(noise_rgb):
    out = apply_redaction(noise_rgb, [(40, 30, 80, 70)], method="pixelate", margin=0.0)
    region = out[30:70, 40:80].reshape(-1, 3)
    assert len(np.unique(region, axis=0)) <= 36  # at most 6x6 blocks


def test_gaussian_removes_high_frequency_detail(noise_rgb):
    out = apply_redaction(noise_rgb, [(40, 30, 80, 70)], method="gaussian", margin=0.0)
    assert out[30:70, 40:80].var() < 0.5 * noise_rgb[30:70, 40:80].var()


def test_margin_enlarges_redacted_area(noise_rgb):
    out = apply_redaction(noise_rgb, [(40, 40, 80, 80)], method="black", margin=0.5)
    assert (out[25:95, 25:95] == 0).all()  # 40 * 0.5 = 20px each side
    assert np.array_equal(out[10, 10], noise_rgb[10, 10])


def test_multiple_boxes(noise_rgb):
    out = apply_redaction(
        noise_rgb, [(5, 5, 25, 25), (100, 60, 140, 100)], method="black", margin=0.0
    )
    assert (out[5:25, 5:25] == 0).all()
    assert (out[60:100, 100:140] == 0).all()


@pytest.mark.parametrize(
    "box", [(10, 10, 11, 40), (10, 10, 40, 11), (500, 500, 520, 520)]
)
def test_degenerate_or_offscreen_boxes_skipped(noise_rgb, box):
    out = apply_redaction(noise_rgb, [box], method="black", margin=0.0)
    assert np.array_equal(out, noise_rgb)


def test_box_touching_edge_does_not_crash(noise_rgb):
    out = apply_redaction(
        noise_rgb, [(-10, -10, 20, 20), (150, 110, 200, 200)], method="gaussian"
    )
    assert out.shape == noise_rgb.shape


def test_tiny_box_gaussian_does_not_crash(noise_rgb):
    apply_redaction(noise_rgb, [(10, 10, 14, 14)], method="gaussian", margin=0.0)


def test_unknown_method_raises(noise_rgb):
    with pytest.raises(ValueError):
        apply_redaction(noise_rgb, [(40, 30, 80, 70)], method="sepia")  # type: ignore[arg-type]
