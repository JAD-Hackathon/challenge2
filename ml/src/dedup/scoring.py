from __future__ import annotations

from collections.abc import Sequence

from src.service.schemas import Observation


def select_best_observation(observations: Sequence[Observation]) -> Observation:
    """Pick the highest-score observation, breaking ties by lowest spatial uncertainty."""
    return max(
        observations,
        key=lambda o: (
            o.score,
            -(o.uncertainty_m if o.uncertainty_m is not None else 999.0),
        ),
    )


def fuse_confidence(
    observations: Sequence[Observation], max_confidence: float
) -> float:
    """Aggregate detection scores across views into a calibrated [0, max_confidence] score."""
    if not observations:
        return 0.0

    scores = sorted((obs.score for obs in observations), reverse=True)
    best = scores[0]
    if len(scores) == 1:
        return round(min(best, max_confidence), 4)

    complement = 1.0
    for score in scores:
        complement *= 1.0 - 0.5 * score

    boosted = max(best, 1.0 - complement)
    return round(min(boosted, max_confidence), 4)
