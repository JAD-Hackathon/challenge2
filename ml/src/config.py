from __future__ import annotations

import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ML_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ML_ROOT / "configs"
DEFAULT_CONFIG = CONFIG_DIR / "base.yaml"

Category = Literal["sign", "light", "waste"]
Method = Literal["size_prior", "ground_plane", "depth"]


class _Cfg(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PathsConfig(_Cfg):
    shared_dir: Path = Path("../data")
    images_subdir: str = "images"
    labels_dir: Path = Path("data/labels")
    splits_dir: Path = Path("data/splits")
    weights_dir: Path = Path("weights")
    taxonomy_file: Path = Path("configs/taxonomy_pt.yaml")

    @property
    def images_dir(self) -> Path:
        return self._abs(self.shared_dir) / self.images_subdir

    @property
    def labels(self) -> Path:
        return self._abs(self.labels_dir)

    @property
    def splits(self) -> Path:
        return self._abs(self.splits_dir)

    @property
    def weights(self) -> Path:
        return self._abs(self.weights_dir)

    @property
    def taxonomy(self) -> Path:
        return self._abs(self.taxonomy_file)

    def weights_path(self, filename: str) -> Path:
        return self.weights / filename

    @staticmethod
    def _abs(p: Path) -> Path:
        return p if p.is_absolute() else (ML_ROOT / p).resolve()


class PrivacyConfig(_Cfg):
    enabled: bool = True
    method: Literal["gaussian", "pixelate", "black"] = "gaussian"
    margin: float = Field(0.2, ge=0, le=1)
    conf: float = Field(0.25, ge=0, le=1)
    face_weights: str = "face.pt"
    plate_weights: str = "plate.pt"


class DetectionConfig(_Cfg):
    weights: str = "detector.pt"
    conf: float = Field(0.30, ge=0, le=1)
    iou: float = Field(0.50, ge=0, le=1)
    imgsz: int = Field(960, gt=0)
    device: str = "auto"


class ClassificationConfig(_Cfg):
    enabled: bool = False
    sign_weights: str = "sign_cls.pt"
    container_weights: str = "container_cls.pt"


class DepthConfig(_Cfg):
    enabled: bool = False
    model: Literal["depth_anything_v2", "metric3d", "unidepth"] = "depth_anything_v2"
    weights: str = "depth.pt"


class GeometryConfig(_Cfg):
    default_fov_deg: float = Field(90.0, gt=0, lt=180)
    default_camera_height_m: float = Field(1.5, gt=0)
    default_camera_type: Literal["perspective", "equirectangular"] = "perspective"
    camera_height_sigma_m: float = Field(0.3, gt=0)
    pitch_sigma_deg: float = Field(1.5, gt=0)
    ground_plane_max_distance_m: float = Field(15.0, gt=0)
    methods: list[Method] = ["size_prior", "ground_plane"]
    fusion: Literal["inverse_variance", "first"] = "inverse_variance"
    max_distance_m: float = Field(40.0, gt=0)
    min_box_px: int = Field(12, ge=1)
    bearing_sigma_deg: float = Field(2.0, gt=0)
    gps_sigma_m: float = Field(3.0, gt=0)
    depth: DepthConfig = DepthConfig()

    @model_validator(mode="after")
    def _methods_not_empty(self) -> "GeometryConfig":
        if not self.methods:
            raise ValueError("geometry.methods must not be empty")
        return self


class DedupConfig(_Cfg):
    radius_m: dict[Category, float] = {"sign": 2.5, "light": 4.0, "waste": 5.0}
    use_ray_check: bool = True
    use_appearance: bool = False
    appearance_min_cos: float = Field(0.7, ge=-1, le=1)
    max_confidence: float = Field(0.99, gt=0, le=1)

    @model_validator(mode="after")
    def _radius_complete(self) -> "DedupConfig":
        missing = set(get_args(Category)) - set(self.radius_m)
        if missing:
            raise ValueError(f"dedup.radius_m missing categories: {sorted(missing)}")
        if any(v <= 0 for v in self.radius_m.values()):
            raise ValueError("dedup.radius_m values must be > 0")
        return self


class ServiceConfig(_Cfg):
    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1, le=65535)
    mock: bool = False


class Settings(_Cfg):
    paths: PathsConfig = PathsConfig()
    privacy: PrivacyConfig = PrivacyConfig()
    detection: DetectionConfig = DetectionConfig()
    classification: ClassificationConfig = ClassificationConfig()
    geometry: GeometryConfig = GeometryConfig()
    dedup: DedupConfig = DedupConfig()
    service: ServiceConfig = ServiceConfig()


# === loading ===


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return data


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _resolve_override_path(p: str | Path) -> Path:
    p = Path(p)
    if p.is_absolute() or p.exists():
        return p
    return CONFIG_DIR / p


_ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "ML_MOCK": ("service", "mock"),
    "ML_SHARED_DIR": ("paths", "shared_dir"),
    "ML_DEVICE": ("detection", "device"),
}


def load_settings(
    path: str | Path | None = None, overrides: dict[str, Any] | None = None
) -> Settings:
    data = _read_yaml(DEFAULT_CONFIG)

    extra_path = path or os.environ.get("ML_CONFIG")
    if extra_path:
        data = _deep_merge(data, _read_yaml(_resolve_override_path(extra_path)))

    env_data: dict[str, Any] = {}
    for var, (section, key) in _ENV_OVERRIDES.items():
        if var in os.environ:
            env_data.setdefault(section, {})[key] = os.environ[var]
    data = _deep_merge(data, env_data)

    if overrides:
        data = _deep_merge(data, overrides)

    return Settings.model_validate(data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings for normal use. Tests should call load_settings()."""
    return load_settings()
