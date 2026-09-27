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


class RollingThresholdPolicy:
    __slots__ = ("_threshold", "_history", "_history_length", "_quantile", "_admission_rule")

    def __init__(self, initial_threshold, history_length, quantile, admission_rule="normal_only"):
        self._threshold = _check_threshold(initial_threshold)
        if not isinstance(history_length, int) or history_length < 1:
            raise ValueError("history_length must be a positive integer")
        self._history_length = history_length
        f_q = _check_threshold(quantile)
        if not 0 < f_q <= 1:
            raise ValueError("quantile must be between 0 and 1 exclusive/inclusive")
        self._quantile = f_q
        if admission_rule not in ("normal_only", "all"):
            raise ValueError(f"admission_rule unrecognized: {admission_rule}")
        self._admission_rule = admission_rule
        # In a real environment, we would pre-fill history with the calibration scores.
        # But per the exact scope, we just initialize the buffer empty and use initial_threshold until buffer is non-empty.
        self._history = []

    @property
    def threshold(self) -> float:
        return self._threshold

    def decide(self, score) -> str:
        f = _check_score(score)
        state = "normal" if f <= self._threshold else "alert"
        
        admit = False
        if self._admission_rule == "normal_only" and state == "normal":
            admit = True
        elif self._admission_rule == "all":
            admit = True
            
        if admit:
            self._history.append(f)
            if len(self._history) > self._history_length:
                self._history.pop(0)
            
            # Recompute threshold dynamically from recent history
            if len(self._history) > 0:
                s = sorted(self._history)
                idx = int(math.ceil(self._quantile * len(s))) - 1
                idx = max(0, min(len(s) - 1, idx))
                self._threshold = s[idx]
                
        return state

    def reset(self) -> None:
        object.__setattr__(self, "_history", [])


class KConsecutivePolicy:
    __slots__ = ("_threshold", "_k", "_current_run")

    def __init__(self, threshold, k):
        self._threshold = _check_threshold(threshold)
        if not isinstance(k, int) or k < 1:
            raise ValueError("k must be a positive integer")
        self._k = k
        self._current_run = 0

    @property
    def threshold(self) -> float:
        return self._threshold

    def decide(self, score) -> str:
        f = _check_score(score)
        if f > self._threshold:
            self._current_run += 1
        else:
            self._current_run = 0
            
        if self._current_run >= self._k:
            return "alert"
        return "normal"

    def reset(self) -> None:
        self._current_run = 0


class MOfNPolicy:
    __slots__ = ("_threshold", "_m", "_n", "_history")

    def __init__(self, threshold, m, n):
        self._threshold = _check_threshold(threshold)
        if not isinstance(m, int) or not isinstance(n, int):
            raise ValueError("m and n must be integers")
        if m < 1 or n < 1 or m > n:
            raise ValueError("must satisfy 1 <= m <= n")
        self._m = m
        self._n = n
        self._history = []

    @property
    def threshold(self) -> float:
        return self._threshold

    def decide(self, score) -> str:
        f = _check_score(score)
        exceeds = (f > self._threshold)
        self._history.append(exceeds)
        if len(self._history) > self._n:
            self._history.pop(0)
            
        if sum(self._history) >= self._m:
            return "alert"
        return "normal"

    def reset(self) -> None:
        self._history = []
