from __future__ import annotations
from pyproj import Geod
from ml.src.io.video.gps import TrackPoint

_GEOD = Geod(ellps="WGS84")


def _forward_azimuth_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute compass bearing (0..360 deg clockwise from north) from p1 to p2."""
    az, _, _ = _GEOD.inv(lon1, lat1, lon2, lat2)
    return float(az) % 360.0


def resample_track_by_distance(
    points: list[TrackPoint],
    step_m: float,
    video_duration_s: float,
    time_offset_s: float = 0.0,
) -> list[tuple[float, float, float, float]]:
    """Sample (video_time_s, lat, lon, heading_deg) every `step_m` metres along the track."""
    has_timestamps = all(p.timestamp_s is not None for p in points)
    t0 = points[0].timestamp_s if has_timestamps else 0.0
    total_dist = points[-1].cum_dist_m

    if total_dist <= 0.0:
        return []

    sampled: list[tuple[float, float, float, float]] = []
    target_dist = 0.0
    seg_idx = 0
    n_pts = len(points)

    while target_dist <= total_dist:
        while seg_idx < n_pts - 2 and points[seg_idx + 1].cum_dist_m < target_dist:
            seg_idx += 1

        p1 = points[seg_idx]
        p2 = points[seg_idx + 1]
        seg_len = p2.cum_dist_m - p1.cum_dist_m
        alpha = (target_dist - p1.cum_dist_m) / seg_len if seg_len > 1e-6 else 0.0
        alpha = max(0.0, min(1.0, alpha))

        lat = p1.lat + alpha * (p2.lat - p1.lat)
        lon = p1.lon + alpha * (p2.lon - p1.lon)
        heading = _forward_azimuth_deg(p1.lat, p1.lon, p2.lat, p2.lon)

        if has_timestamps:
            assert (
                p1.timestamp_s is not None
                and p2.timestamp_s is not None
                and t0 is not None
            )
            gpx_rel_t = (p1.timestamp_s - t0) + alpha * (
                p2.timestamp_s - p1.timestamp_s
            )
            video_t = gpx_rel_t + time_offset_s
        else:
            video_t = (target_dist / total_dist) * video_duration_s

        if 0.0 <= video_t <= video_duration_s:
            sampled.append((video_t, lat, lon, heading))

        target_dist += step_m

    return sampled
