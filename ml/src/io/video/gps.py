from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class TrackPoint:
    """Single GPS point parsed from a GPX track."""

    lat: float
    lon: float
    timestamp_s: float | None
    cum_dist_m: float
