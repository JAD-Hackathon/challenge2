from __future__ import annotations

import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from src.config import Category, Method, _Cfg, PathsConfig, get_settings

_NAME_RE = re.compile(r"^(sign|light|waste)\.[a-z0-9_]+$")


class Size(_Cfg):
    dim: Literal["height", "width"]
    m: float = Field(gt=0)
    tol: float = Field(0.2, gt=0, le=1)


class ClassSpec(_Cfg):
    name: str
    label: str
    ground: bool = False
    size: Size | None = None

    @model_validator(mode="after")
    def _check(self) -> "ClassSpec":
        if not _NAME_RE.match(self.name):
            raise ValueError(
                f"bad class name '{self.name}' (expected {_NAME_RE.pattern})"
            )
        return self

    @property
    def category(self) -> Category:
        return self.name.split(".", 1)[0]


class Taxonomy(_Cfg):
    classes: list[ClassSpec]

    @model_validator(mode="after")
    def _check(self) -> "Taxonomy":
        names = [c.name for c in self.classes]
        if not names:
            raise ValueError("no classes defined")
        if len(set(names)) != len(names):
            raise ValueError("duplicate class names")
        return self

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.classes]

    def names_by_id(self) -> dict[int, str]:
        """For the YOLO dataset yaml / model class names."""
        return dict(enumerate(self.names))

    def id_of(self, name: str) -> int:
        try:
            return self.names.index(name)
        except ValueError:
            raise KeyError(f"Unknown class '{name}'") from None

    def get(self, name: str) -> ClassSpec:
        return self.classes[self.id_of(name)]

    def by_id(self, class_id: int) -> ClassSpec:
        try:
            return self.classes[class_id]
        except IndexError:
            raise KeyError(f"Unknown class id {class_id}") from None

    def in_category(self, category: Category) -> list[ClassSpec]:
        return [c for c in self.classes if c.category == category]

    def methods_for(self, name: str, order: Sequence[Method]) -> list[Method]:
        """Distance methods usable for this class, in the given priority order."""
        spec = self.get(name)
        usable = {
            "size_prior": spec.size is not None,
            "ground_plane": spec.ground,
            "depth": True,
        }
        return [m for m in order if usable[m]]


def load_taxonomy(path: str | Path | None = None) -> Taxonomy:
    p = PathsConfig._abs(Path(path)) if path else get_settings().paths.taxonomy
    if not p.is_file():
        raise FileNotFoundError(f"Taxonomy file not found: {p}")
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Taxonomy.model_validate(raw)


@lru_cache(maxsize=1)
def get_taxonomy() -> Taxonomy:
    return load_taxonomy()
