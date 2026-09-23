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


class HysteresisPolicy:
    __slots__ = ("_low", "_high", "_state")

    def __init__(self, low, high) -> None:
        low_f = _check_threshold(low)
        high_f = _check_threshold(high)
        if not low_f < high_f:
            raise ValueError("low must be below high")
        object.__setattr__(self, "_low", low_f)
        object.__setattr__(self, "_high", high_f)
        object.__setattr__(self, "_state", "normal")

    @property
    def low(self) -> float:
        return self._low

    @property
    def high(self) -> float:
        return self._high

    @property
    def state(self) -> str:
        return self._state

    def decide(self, score) -> str:
        f = _check_score(score)
        if self._state == "normal":
            if f > self._high:
                object.__setattr__(self, "_state", "alert")
        else:
            if f < self._low:
                object.__setattr__(self, "_state", "normal")
        return self._state

    def reset(self) -> None:
        object.__setattr__(self, "_state", "normal")
