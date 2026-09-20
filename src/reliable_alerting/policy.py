import dataclasses
import math


def _check_threshold(value) -> float:
    if value is None or isinstance(value, bool):
        raise TypeError("threshold must be a number")
    if not isinstance(value, (int, float)):
        raise TypeError("threshold must be a number")
    try:
        f = float(value)
    except OverflowError as e:
        raise ValueError("threshold must be finite") from e
    if not math.isfinite(f):
        raise ValueError("threshold must be finite")
    return f


def _check_score(value) -> float:
    if value is None or isinstance(value, bool):
        raise TypeError("score must be a number")
    if not isinstance(value, (int, float)):
        raise TypeError("score must be a number")
    try:
        f = float(value)
    except OverflowError as e:
        raise ValueError("score must be finite") from e
    if not math.isfinite(f):
        raise ValueError("score must be finite")
    return f


@dataclasses.dataclass(frozen=True)
class FixedThresholdPolicy:
    threshold: float

    def __post_init__(self):
        object.__setattr__(self, "threshold", _check_threshold(self.threshold))

    def decide(self, score) -> str:
        f = _check_score(score)
        if f <= self.threshold:
            return "normal"
        return "alert"
