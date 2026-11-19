import numpy as np
import pytest

from src.config import DepthConfig, GeometryConfig
from src.geometry.depth import DepthEstimator, ONNXDepthProvider

from .helpers import make_frame, make_spec

ON = GeometryConfig(depth=DepthConfig(enabled=True))
SPEC, FRAME = make_spec(), make_frame()
BOX = (400, 400, 600, 600)  # core (50%) = [450:550]


def depth_map(fill=10.0):
    return np.full((1000, 1000), fill, np.float32)


def make(cfg=ON, dm=None, **kw):
    e = DepthEstimator(cfg, **kw)
    if dm is not None:
        e.set_depth_map(dm)
    return e


def test_disabled_or_no_map_returns_none():
    assert make(GeometryConfig(), depth_map()).estimate(BOX, SPEC, FRAME) is None
    assert make().estimate(BOX, SPEC, FRAME) is None


def test_constant_depth():
    r = make(dm=depth_map(10.0)).estimate(BOX, SPEC, FRAME)
    assert r.method == "depth"
    assert r.distance_m == pytest.approx(10.0)
    assert r.uncertainty_m == pytest.approx(2.0)  # 20 %


def test_scale_factor_and_uncertainty_floor():
    r = make(dm=depth_map(1.0), scale_factor=0.5).estimate(BOX, SPEC, FRAME)
    assert r.distance_m == pytest.approx(0.5)
    assert r.uncertainty_m == pytest.approx(0.15)  # floor beats 0.1


def test_median_uses_core_not_background():
    dm = depth_map(30.0)
    dm[420:580, 420:580] = 8.0
    assert make(dm=dm).estimate(BOX, SPEC, FRAME).distance_m == pytest.approx(8.0)


def test_median_robust_to_outliers():
    dm = depth_map(10.0)
    dm[450:460, 450:550] = 500.0  # 10 % outliers in core
    assert make(dm=dm).estimate(BOX, SPEC, FRAME).distance_m == pytest.approx(10.0)


def test_invalid_pixels_ignored():
    dm = depth_map(10.0)
    dm[450:500, 450:550] = np.nan
    dm[500:520, 450:550] = 0.0
    dm[520:530, 450:550] = -3.0
    assert make(dm=dm).estimate(BOX, SPEC, FRAME).distance_m == pytest.approx(10.0)


def test_all_invalid_returns_none():
    assert make(dm=depth_map(np.nan)).estimate(BOX, SPEC, FRAME) is None
    assert make(dm=depth_map(0.0)).estimate(BOX, SPEC, FRAME) is None


def test_beyond_max_distance_returns_none():
    assert (
        make(dm=depth_map(GeometryConfig().max_distance_m + 1)).estimate(
            BOX, SPEC, FRAME
        )
        is None
    )


@pytest.mark.parametrize(
    "box", [(400, 400, 405, 600), (400, 400, 600, 405), (2000, 2000, 2100, 2100)]
)
def test_tiny_or_offscreen_box_returns_none(box):
    assert make(dm=depth_map()).estimate(box, SPEC, FRAME) is None


def test_box_partly_outside_map_still_works():
    assert (
        make(dm=depth_map()).estimate((900, 900, 1100, 1100), SPEC, FRAME) is not None
    )


# --- set_image caching ----------------------------------------------------


class CountingProvider:
    def __init__(self):
        self.calls = 0

    def predict_depth_m(self, img):
        self.calls += 1
        return np.full(img.shape[:2], 10.0, np.float32)


def test_set_image_caches_per_image_object():
    p = CountingProvider()
    e = DepthEstimator(ON, provider=p)
    a, b = np.zeros((1000, 1000, 3), np.uint8), np.zeros((1000, 1000, 3), np.uint8)
    e.set_image(a)
    e.set_image(a)
    assert p.calls == 1
    e.set_image(b)
    assert p.calls == 2
    assert e.estimate(BOX, SPEC, FRAME).distance_m == pytest.approx(10.0)


@pytest.mark.parametrize(
    "cfg,provider,image",
    [
        (ON, CountingProvider(), None),
        (GeometryConfig(), CountingProvider(), np.zeros((10, 10, 3), np.uint8)),
        (ON, None, np.zeros((10, 10, 3), np.uint8)),
    ],
)
def test_set_image_clears_state_when_unusable(cfg, provider, image):
    e = DepthEstimator(cfg, provider=provider)
    e.set_depth_map(depth_map())
    e.set_image(image)
    assert e.estimate(BOX, SPEC, FRAME) is None
    if provider is not None:
        assert provider.calls == 0


# --- ONNX provider --------------------------------------------------------


class FakeSession:
    def __init__(self, depth_value=7.0):
        self.value, self.fed = depth_value, None

    def get_inputs(self):
        return [type("I", (), {"name": "pixel_values"})()]

    def run(self, output_names=None, input_feed=None):
        self.fed = input_feed
        return [np.full((1, 518, 518), self.value, np.float32)]


@pytest.fixture
def provider(monkeypatch, tmp_path):
    ort = pytest.importorskip("onnxruntime")
    session = FakeSession()
    monkeypatch.setattr(ort, "InferenceSession", lambda *a, **k: session)
    w = tmp_path / "depth.onnx"
    w.touch()
    return ONNXDepthProvider(w), session


def test_provider_missing_weights(tmp_path):
    with pytest.raises(FileNotFoundError):
        ONNXDepthProvider(tmp_path / "nope.onnx")


def test_provider_output_matches_image_hw_for_non_square_input(provider):
    prov, session = provider
    img = np.zeros((100, 200, 3), np.uint8)  # H=100, W=200
    out = prov.predict_depth_m(img)
    assert out.shape == (100, 200) and out.dtype == np.float32
    assert np.allclose(out, 7.0)
    blob = session.fed["pixel_values"]
    assert blob.shape == (1, 3, 518, 518) and blob.dtype == np.float32
