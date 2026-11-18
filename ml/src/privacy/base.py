from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


@dataclass(frozen=True, slots=True)
class PrivacyBox:
    """Detected PII region (face or license plate)."""

    kind: str  # "face" | "plate"
    score: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class AnonymizationResult:
    """Output of running privacy redaction on a single image."""

    image: Image.Image
    faces_blurred: int = 0
    plates_blurred: int = 0
    boxes: list[PrivacyBox] = field(default_factory=list)


class PIIDetector(ABC):
    """Abstract interface for a face or license-plate detector."""

    @abstractmethod
    def detect(self, image: Image.Image) -> list[PrivacyBox]:
        """Detect PII regions in `image`."""
