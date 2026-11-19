from __future__ import annotations

import logging
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from src.classification.onnx_classifier import MultiCategoryClassifier
from src.config import Settings, get_settings
from src.detection.base import Detector, build_detector
from src.geometry.base import CameraFrame
from src.geometry.localizer import GeoLocalizer
from src.privacy.anonymizer import PrivacyAnonymizer
from src.service.schemas import CameraMeta, InferResponse, Observation
from src.taxonomy import Taxonomy, get_taxonomy

logger = logging.getLogger(__name__)


class InferencePipeline:
    """Orchestrate GDPR redaction, 2-stage asset detection, and WGS84 localization."""

    def __init__(
        self,
        settings: Settings | None = None,
        taxonomy: Taxonomy | None = None,
        *,
        anonymizer: PrivacyAnonymizer | None = None,
        detector: Detector | None = None,
        classifier: MultiCategoryClassifier | None = None,
        localizer: GeoLocalizer | None = None,
        detector_weights: Path | None = None,
    ) -> None:
        """Initialize all pipeline stages from Settings and Taxonomy."""
        self.settings = settings or get_settings()
        self.taxonomy = taxonomy or get_taxonomy()

        self.anonymizer = anonymizer or PrivacyAnonymizer(
            cfg=self.settings.privacy,
            paths=self.settings.paths,
        )
        self.detector = detector or self._build_default_detector(detector_weights)
        self.classifier = classifier or MultiCategoryClassifier(
            cfg=self.settings.classification,
            paths=self.settings.paths,
            taxonomy=self.taxonomy,
        )
        self.localizer = localizer or GeoLocalizer(
            cfg=self.settings.geometry,
            taxonomy=self.taxonomy,
        )

    def _build_default_detector(self, detector_weights: Path | None) -> Detector:
        """Resolve detector weights path for RT-DETR or ONNX YOLO and build detector."""
        det_cfg = self.settings.detection
        paths = self.settings.paths

        if detector_weights is not None:
            resolved_weights: Path | None = detector_weights
        elif det_cfg.backend == "rtdetr":
            candidate = paths.weights_path(det_cfg.weights)
            resolved_weights = candidate if candidate.exists() else None
        else:
            resolved_weights = paths.weights_path(det_cfg.weights)

        return build_detector(det_cfg, self.taxonomy, weights_path=resolved_weights)

    def warmup(self) -> None:
        """Eagerly load detector weights into memory before serving requests."""
        self.detector.load()

    def run(
        self,
        image: Image.Image,
        meta: CameraMeta,
        *,
        save_blurred: bool = True,
    ) -> InferResponse:
        """
        Execute full single-image inference and return contract-compliant `InferResponse`.
        Steps:
            1. Anonymize faces and license plates in memory (raw image is never persisted).
            2. Optionally write the redacted image to `<shared_dir>/<images_subdir>/<image_id>.jpg`.
            3. Run Stage-1 object detection on the redacted image.
            4. Refine subclasses with Stage-2 per-category ONNX classifiers.
            5. Estimate bearing, distance, and WGS84 coordinates for each detection.
        """
        # anonymize
        anon_result = self.anonymizer.anonymize(image)
        blurred_image = anon_result.image

        rel_blurred_path = f"{self.settings.paths.images_subdir}/{meta.image_id}.jpg"
        if save_blurred:
            self._save_blurred_image(blurred_image, meta.image_id)

        # detect
        detections = self.detector.detect(blurred_image)
        if not detections:
            return InferResponse(
                image_id=meta.image_id,
                blurred_image_path=rel_blurred_path,
                observations=[],
            )

        # classify
        refined = self.classifier.refine(blurred_image, detections)

        # localize
        width, height = blurred_image.size
        frame = CameraFrame.from_meta(
            lat=meta.lat,
            lon=meta.lon,
            heading=meta.heading,
            image_width=width,
            image_height=height,
            cfg=self.settings.geometry,
            fov=meta.fov,
            camera_type=meta.camera_type,
            camera_height_m=meta.camera_height_m,
        )

        if self.settings.geometry.depth.enabled:
            self.localizer.prepare_image(np.asarray(blurred_image))

        observations: list[Observation] = []

        for detection in refined:
            geo = self.localizer.localize(
                class_name=detection.label,
                bbox_xyxy=detection.bbox_xyxy,
                frame=frame,
            )
            observations.append(
                Observation(
                    observation_id=uuid.uuid4().hex[:12],
                    type=detection.label,
                    score=round(detection.score, 4),
                    bbox_xyxy=[int(coord) for coord in detection.bbox_xyxy],
                    bearing_deg=round(geo.bearing_deg, 2),
                    est_lat=round(geo.est_lat, 7) if geo.est_lat is not None else None,
                    est_lon=round(geo.est_lon, 7) if geo.est_lon is not None else None,
                    uncertainty_m=(
                        round(geo.uncertainty_m, 2)
                        if geo.uncertainty_m is not None
                        else None
                    ),
                )
            )

        return InferResponse(
            image_id=meta.image_id,
            blurred_image_path=rel_blurred_path,
            observations=observations,
        )

    def _save_blurred_image(self, image: Image.Image, image_id: str) -> Path:
        """Persist only the GDPR-redacted JPEG to the shared images directory."""
        out_dir = self.settings.paths.images_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{image_id}.jpg"
        image.save(out_path, format="JPEG", quality=92)
        return out_path
