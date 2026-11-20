"""Video -> frames placed on the map, one every `spacing_m` metres of travel.

Port of the ML team's frame picker (ml/src/io/video: parse_gpx, resample_track_by_distance,
extract_video_frames). Each frame comes out as an UploadedImage, so it goes to ML's /infer and
into the catalogue exactly like an uploaded image (source "video", one sequence_id,
frame_index 0, 1, 2...).

Positions come from the GPX track recorded with the video.
"""

import math
import shutil
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import cv2

from app.core.config import settings
from app.core.exceptions import InvalidInputError
from app.schemas.image import ImageMeta, UploadedImage
from app.schemas.video import UploadedVideo, VideoMeta

EARTH_RADIUS_M = 6_371_008.8
STILL_M = 0.3  # a GPS move shorter than this gives no direction of travel
JPEG_QUALITY = 92  # same as ML's extract_video_frames


@dataclass(frozen=True)
class TrackPoint:
    lat: float
    lon: float
    time: datetime | None  # GPX <time>; None if the point has none
    dist_m: float = 0.0  # distance travelled since the first point


@dataclass(frozen=True)
class Placement:
    """Where and when the frame at `video_s` seconds into the video was taken."""

    video_s: float
    lat: float
    lon: float
    heading: float  # camera direction, ° clockwise from north
    captured_at: datetime | None


# --- track ---


def parse_gpx(content: bytes) -> list[TrackPoint]:
    """Track (<trkpt>) or route (<rtept>) points of a GPX file, with their <time> if any."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise InvalidInputError(f"track: not a GPX file ({e})") from None
    points = []
    for elem in root.iter():
        if not elem.tag.endswith(("trkpt", "rtept")):
            continue
        try:
            lat, lon = float(elem.attrib["lat"]), float(elem.attrib["lon"])
        except (KeyError, ValueError):
            raise InvalidInputError("track: a point has no valid lat/lon") from None
        time = next(
            (_gpx_time(c.text) for c in elem if c.tag.endswith("time") and c.text), None
        )
        points.append((lat, lon, time))
    return _measured(points)


def _gpx_time(text: str) -> datetime:
    try:
        return _utc(datetime.fromisoformat(text.strip()))
    except ValueError:
        raise InvalidInputError(f"track: bad <time> {text.strip()!r}") from None


def _measured(points: list[tuple[float, float, datetime | None]]) -> list[TrackPoint]:
    if len(points) < 2:
        raise InvalidInputError(f"track: needs at least 2 points, got {len(points)}")
    if any(not (-90 <= lat <= 90 and -180 <= lon <= 180) for lat, lon, _ in points):
        raise InvalidInputError("track: a point is outside lat -90..90 / lon -180..180")
    track = [TrackPoint(*points[0])]
    for lat, lon, time in points[1:]:
        prev = track[-1]
        step = _distance_m(prev.lat, prev.lon, lat, lon)
        track.append(TrackPoint(lat, lon, time, prev.dist_m + step))
    return track


# --- placing the frames ---


def place_frames(
    track: list[TrackPoint], meta: VideoMeta, duration_s: float
) -> list[Placement]:
    """One frame every meta.spacing_m metres along the track, those that fall inside the video.

    Timed track (a <time> on every GPX point): the frame at video second t was taken at GPS time
    start + t + meta.time_offset_s, where start is meta.start_time or, if not given, the track's
    first point (the recording and the track started together).
    Without times (GPX without <time>): constant speed over the whole video, first
    frame at the start of the track, last one at the end.
    """
    total_m = track[-1].dist_m
    if total_m <= STILL_M:
        raise InvalidInputError("The track doesn't move: all its points are in one place")
    timed = all(p.time is not None for p in track)
    start = _utc(meta.start_time) if meta.start_time else (track[0].time if timed else None)
    headings = _headings(track)

    placements = []
    seg = 0
    for k in range(math.floor(total_m / meta.spacing_m + 1e-9) + 1):
        target_m = k * meta.spacing_m
        # first segment that reaches target_m (skips segments where the GPS didn't move)
        while seg < len(track) - 2 and track[seg + 1].dist_m <= target_m:
            seg += 1
        a, b = track[seg], track[seg + 1]
        length = b.dist_m - a.dist_m
        f = min(max((target_m - a.dist_m) / length, 0.0), 1.0) if length > 0 else 0.0

        if timed:
            taken = _ms(a.time + f * (b.time - a.time))
            video_s = (taken - start).total_seconds() - meta.time_offset_s
        else:
            video_s = target_m / total_m * duration_s
            offset = timedelta(seconds=video_s + meta.time_offset_s)
            taken = _ms(start + offset) if start else None
        if 0 <= video_s <= duration_s:
            placements.append(
                Placement(
                    video_s=video_s,
                    lat=round(a.lat + f * (b.lat - a.lat), 7),
                    lon=round(a.lon + f * (b.lon - a.lon), 7),
                    heading=_camera_heading(headings[seg], meta.heading_offset_deg),
                    captured_at=taken,
                )
            )

    if not placements:  # only possible with times: the clocks don't overlap
        first = start + timedelta(seconds=meta.time_offset_s)
        raise InvalidInputError(
            f"No frame of the video falls on the GPS track: the track runs "
            f"{track[0].time:%H:%M:%S}-{track[-1].time:%H:%M:%S} UTC, the video "
            f"{first:%H:%M:%S} UTC + {duration_s:.0f} s. Line them up with start_time or "
            "time_offset_s"
        )
    return placements


def _headings(track: list[TrackPoint]) -> list[float]:
    """Direction of travel on each segment. Where the GPS didn't move (the camera stopped, it
    didn't turn) take the direction of the closest segment before, else after, that moved."""
    raw = [
        _bearing(a.lat, a.lon, b.lat, b.lon) if b.dist_m - a.dist_m > STILL_M else None
        for a, b in pairwise(track)
    ]
    moved = [h for h in raw if h is not None]
    last = moved[0] if moved else 0.0
    out = []
    for h in raw:
        last = h if h is not None else last
        out.append(last)
    return out


def _camera_heading(travel: float, offset: float) -> float:
    heading = round((travel + offset) % 360, 2)
    return 0.0 if heading >= 360 else heading


# --- reading the frames ---


@dataclass
class VideoFrames:
    """The placed frames of one video. Iterating reads them one at a time (never all in
    memory), as UploadedImages ready for ML /infer. A frame OpenCV can't read is skipped."""

    video: UploadedVideo
    sequence_id: str
    placements: list[Placement]
    _capture: cv2.VideoCapture = field(repr=False)
    _fps: float
    _frame_count: int

    def __iter__(self) -> Iterator[UploadedImage]:
        meta = self.video.meta
        index = 0
        for place in self.placements:
            frame_no = min(round(place.video_s * self._fps), self._frame_count - 1)
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = self._capture.read()
            if ok:
                ok, jpeg = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
            if not ok:
                print(
                    f"[VIDEO] {self.sequence_id}: can't read frame {frame_no} "
                    f"({place.video_s:.1f} s), skipped",
                    flush=True,
                )
                continue
            yield UploadedImage(
                index=index,
                filename=self.video.frame_filename(index),
                content_type="image/jpeg",
                content=jpeg.tobytes(),
                meta=ImageMeta(
                    image_id=f"{self.sequence_id}_{index:04d}",
                    lat=place.lat,
                    lon=place.lon,
                    heading=place.heading,
                    fov=meta.fov,
                    camera_height_m=meta.camera_height_m,
                    source="video",
                    sequence_id=self.sequence_id,
                    frame_index=index,
                    author=meta.author,
                    license=meta.license,
                    captured_at=place.captured_at,
                ),
            )
            index += 1


@contextmanager
def open_video(video: UploadedVideo, sequence_id: str) -> Iterator[VideoFrames]:
    """Place the frames of `video` along its GPS track, then hand them out.

    Everything that can be refused (bad GPX, unreadable video, clocks that don't
    overlap, too many frames) is refused here, before ML sees a single frame. OpenCV reads
    files, not streams, so the video sits in a temporary file until the block ends.
    """
    track = parse_gpx(video.track)
    with tempfile.TemporaryDirectory(prefix="video_") as tmp:
        path = Path(tmp) / f"video{_suffix(video.filename)}"
        with path.open("wb") as out:
            shutil.copyfileobj(video.file, out)
        capture = cv2.VideoCapture(str(path))
        try:  # released before the folder is deleted (Windows locks open files)
            fps = capture.get(cv2.CAP_PROP_FPS)
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if not capture.isOpened() or fps <= 0 or frame_count <= 0:
                raise InvalidInputError("Could not read the video (mp4, mov, avi...)")
            placements = place_frames(track, video.meta, frame_count / fps)
            if len(placements) > settings.MAX_VIDEO_FRAMES:
                raise InvalidInputError(
                    f"The video gives {len(placements)} frames at one every "
                    f"{video.meta.spacing_m:g} m, at most {settings.MAX_VIDEO_FRAMES} per "
                    "upload: raise spacing_m or cut the video"
                )
            print(
                f"[VIDEO] {sequence_id}: {len(placements)} frames placed with the GPS "
                f"track, {frame_count / fps:.1f} s of video at {fps:g} fps",
                flush=True,
            )
            yield VideoFrames(video, sequence_id, placements, capture, fps, frame_count)
        finally:
            capture.release()


def _suffix(filename: str | None) -> str:
    """'.mp4' from 'ride.mp4': helps OpenCV pick the container. Anything odd -> '.mp4'."""
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix[1:].isalnum() and len(suffix) <= 6 else ".mp4"


# --- geodesy (sphere: plenty for metres between GPS points) ---


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compass bearing from point 1 to point 2, 0..360° clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def _utc(dt: datetime) -> datetime:
    """A time without a zone is taken as UTC (GPX times are UTC)."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _ms(dt: datetime) -> datetime:
    """Rounded to the millisecond: interpolation gives 10:15:01.999998 for 10:15:02."""
    return datetime.fromtimestamp(round(dt.timestamp(), 3), UTC)
