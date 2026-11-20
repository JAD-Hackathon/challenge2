from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import cv2
import httpx
from PIL import Image

from src.config import get_settings
from src.io.common import make_image_id
from src.io.video.parser import parse_gpx
from src.io.video.resampling import resample_track_by_distance
from src.privacy.anonymizer import PrivacyAnonymizer

logger = logging.getLogger(__name__)


def extract_video_frames(
    video_path: Path,
    gpx_path: Path,
    *,
    step_m: float = 5.0,
    sequence_id: str | None = None,
    fov: float | None = None,
    camera_height_m: float | None = None,
    time_offset_s: float = 0.0,
    api_url: str | None = None,
    meta_out: Path | None = None,
) -> list[dict[str, Any]]:
    """Extract frames every ~step_m metres in RAM, redact PII, and write only to shared_dir/images."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video file: {video_path}")

    settings = get_settings()

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_s = total_frames / fps if total_frames > 0 else 0.0

        track_points = parse_gpx(gpx_path)
        waypoints = resample_track_by_distance(
            track_points,
            step_m=step_m,
            video_duration_s=duration_s,
            time_offset_s=time_offset_s,
        )

        seq_id = sequence_id or uuid.uuid4().hex[:12]
        images_dir = settings.paths.images_dir

        anonymizer: PrivacyAnonymizer | None = None
        client: httpx.Client | None = None

        if api_url is not None:
            client = httpx.Client(timeout=60.0)
        else:
            images_dir.mkdir(parents=True, exist_ok=True)
            anonymizer = PrivacyAnonymizer(cfg=settings.privacy, paths=settings.paths)

        metas: list[dict[str, Any]] = []

        try:
            for idx, (video_t, lat, lon, heading) in enumerate(waypoints):
                frame_num = int(round(video_t * fps))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ok, frame_bgr = cap.read()
                if not ok or frame_bgr is None:
                    logger.warning(
                        "Failed to read frame %d at %.2fs", frame_num, video_t
                    )
                    continue

                source_id = f"{seq_id}_{idx:05d}"
                image_id = make_image_id("video", source_id)

                meta: dict[str, Any] = {
                    "image_id": image_id,
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "heading": round(heading, 2),
                    "fov": fov,
                    "camera_type": "perspective",
                    "camera_height_m": camera_height_m,
                    "source": "video",
                    "sequence_id": seq_id,
                    "frame_index": idx,
                }
                metas.append(meta)

                if client is not None and api_url is not None:
                    # /infer
                    ok, buf = cv2.imencode(
                        ".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92]
                    )
                    if not ok:
                        logger.warning("Failed to encode frame %d", frame_num)
                        continue
                    resp = client.post(
                        f"{api_url.rstrip('/')}/infer",
                        files={
                            "image": (f"{image_id}.jpg", buf.tobytes(), "image/jpeg")
                        },
                        data={"meta": json.dumps(meta)},
                    )
                    resp.raise_for_status()
                else:
                    # save blurred image
                    assert anonymizer is not None
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb)
                    redacted = anonymizer.anonymize(pil_img).image
                    out_path = images_dir / f"{image_id}.jpg"
                    redacted.save(out_path, format="JPEG", quality=92)
        finally:
            if client is not None:
                client.close()

        if meta_out is not None:
            meta_out.parent.mkdir(parents=True, exist_ok=True)
            with meta_out.open("w", encoding="utf-8") as f:
                for m in metas:
                    f.write(json.dumps(m) + "\n")

        return metas
    finally:
        cap.release()
