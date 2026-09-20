import dataclasses
import math

from reliable_alerting import loading


def _check_quantile(value) -> float:
    if value is None or isinstance(value, bool):
        raise TypeError("quantile must be a real number")
    if not isinstance(value, (int, float)):
        raise TypeError("quantile must be a real number")
    try:
        q = float(value)
    except OverflowError as e:
        raise ValueError("quantile must be finite") from e
    if not math.isfinite(q):
        raise ValueError("quantile must be finite")
    if not 0 < q <= 1:
        raise ValueError("quantile must satisfy 0 < q <= 1")
    return q


def _check_min_samples(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("min_samples must be an int")
    if value < 1:
        raise ValueError("min_samples must be >= 1")
    return value


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


@dataclasses.dataclass(frozen=True)
class FixedQuantile:
    threshold: float
    quantile: float
    sample_count: int
    method: str = "nearest_rank"

    def __post_init__(self):
        t = _check_threshold(self.threshold)
        q = _check_quantile(self.quantile)
        n = _check_min_samples(self.sample_count)
        if not isinstance(self.method, str) or self.method != "nearest_rank":
            raise ValueError("method must be 'nearest_rank'")
        object.__setattr__(self, "threshold", t)
        object.__setattr__(self, "quantile", q)
        object.__setattr__(self, "sample_count", n)

    @classmethod
    def fit(cls, scores, quantile: float = 0.95, min_samples: int = 2) -> "FixedQuantile":
        q = _check_quantile(quantile)
        m = _check_min_samples(min_samples)
        vals = loading.load_values(scores)
        if len(vals) < m:
            raise ValueError("fewer scores than min_samples")
        ordered = sorted(vals)
        rank = math.ceil(q * len(ordered))
        if rank < 1:
            rank = 1
        if rank > len(ordered):
            rank = len(ordered)
        return cls(
            threshold=float(ordered[rank - 1]),
            quantile=q,
            sample_count=len(ordered),
            method="nearest_rank",
        )
