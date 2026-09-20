import dataclasses
import math
import statistics

from reliable_alerting import loading


@dataclasses.dataclass(frozen=True)
class MeanDistanceScorer:
    mean: float
    std: float
    epsilon: float

    def __post_init__(self):
        for name in ("mean", "std", "epsilon"):
            v = getattr(self, name)
            if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a finite number")
            try:
                f = float(v)
            except OverflowError as e:
                raise ValueError(f"{name} must be finite") from e
            if not math.isfinite(f):
                raise ValueError(f"{name} must be finite")
        if float(self.std) < 0:
            raise ValueError("std must be >= 0")
        if float(self.epsilon) <= 0:
            raise ValueError("epsilon must be > 0")
        denom = float(self.std) + float(self.epsilon)
        if not math.isfinite(denom) or denom <= 0:
            raise ValueError("std+epsilon must be finite and > 0")

    @classmethod
    def fit(cls, source_values, epsilon: float = 1e-6) -> "MeanDistanceScorer":
        if epsilon is None or isinstance(epsilon, bool):
            raise TypeError("epsilon must be a positive finite number")
        if not isinstance(epsilon, (int, float)):
            raise TypeError("epsilon must be a positive finite number")
        try:
            eps = float(epsilon)
        except OverflowError as e:
            raise ValueError("epsilon must be finite") from e
        if not math.isfinite(eps) or eps <= 0:
            raise ValueError("epsilon must be finite and > 0")
        vals = loading.load_values(source_values)
        if len(vals) < 2:
            raise ValueError("need at least two source samples")
        try:
            mean = statistics.fmean(vals)
            std = statistics.pstdev(vals)
        except OverflowError as e:
            raise ValueError("non-finite source statistics") from e
        if not math.isfinite(mean) or not math.isfinite(std):
            raise ValueError("non-finite source statistics")
        return cls(mean=float(mean), std=float(std), epsilon=eps)

    def score(self, window_values) -> float:
        vals = loading.load_values(window_values)
        try:
            m = statistics.fmean(vals)
        except OverflowError as e:
            raise ValueError("non-finite score") from e
        result = abs(m - self.mean) / (self.std + self.epsilon)
        if not math.isfinite(m) or not math.isfinite(result):
            raise ValueError("non-finite score")
        return float(result)
