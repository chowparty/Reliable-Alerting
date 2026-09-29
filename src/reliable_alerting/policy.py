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


def _check_positive_ratio_or_inf(value, name):
    """Accept a finite positive float OR math.inf (for ablations)."""
    if value is None or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    f = float(value)
    if math.isnan(f):
        raise ValueError(f"{name} must not be NaN")
    if f <= 0:
        raise ValueError(f"{name} must be > 0")
    return f  # may be math.inf


def _nearest_rank_quantile(sorted_vals, q):
    """Nearest-rank quantile: ceil(q * n)-th smallest (1-indexed), clamped."""
    n = len(sorted_vals)
    rank = math.ceil(q * n)
    if rank < 1:
        rank = 1
    if rank > n:
        rank = n
    return sorted_vals[rank - 1]


def _ordinary_median(vals):
    """Ordinary median; mean of the two middle values for even length."""
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2)


class AnchoredRecalibrationPolicy:
    """Admission-separated, anchored recalibration controller (protocol section 4).

    The buffer R holds the last L scores of EVERY window (admission does not
    depend on any decision). At each window end the controller may hold, alert,
    defer, or recalibrate the threshold upward/toward the anchor, under a cap
    (kappa) and a stability guard (rho), with explicit deferral (up to D times).

    Invariants: theta0 <= theta <= kappa*theta0 always; recalibration never
    happens before the buffer is full; at most D consecutive defers before an
    alert-capable decision; no label input; the score input is identical to
    every other arm.
    """

    __slots__ = ("_theta0", "_theta", "_mode", "_c", "_R", "_L", "_q",
                 "_kappa", "_rho", "_D", "_last_action")

    def __init__(self, theta0, block_length=10, quantile=0.95, cap=4.0,
                 stability=2.0, defer_limit=10):
        self._theta0 = _check_threshold(theta0)
        if self._theta0 < 0:
            raise ValueError("theta0 must be >= 0")
        if not isinstance(block_length, int) or isinstance(block_length, bool) \
                or block_length < 1:
            raise ValueError("block_length must be a positive integer")
        self._L = block_length
        q = _check_threshold(quantile)
        if not 0 < q <= 1:
            raise ValueError("quantile must satisfy 0 < q <= 1")
        self._q = q
        self._kappa = _check_positive_ratio_or_inf(cap, "cap")
        self._rho = _check_positive_ratio_or_inf(stability, "stability")
        if not isinstance(defer_limit, int) or isinstance(defer_limit, bool) \
                or defer_limit < 0:
            raise ValueError("defer_limit must be a non-negative integer")
        self._D = defer_limit
        self._theta = self._theta0
        self._mode = "normal"
        self._c = 0
        self._R = []
        self._last_action = "hold"

    @property
    def threshold(self) -> float:
        return self._theta

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def last_action(self) -> str:
        return self._last_action

    def decide(self, score) -> str:
        s = _check_score(score)
        # append s to R (drop oldest beyond L). Admission is unconditional.
        self._R.append(s)
        if len(self._R) > self._L:
            self._R.pop(0)
        full = len(self._R) == self._L
        median = _ordinary_median(self._R) if self._R else 0.0
        elevated = full and median > self._theta

        if self._mode == "escalated":
            if elevated:
                # stay escalated, no recalibration
                if s > self._theta:
                    self._last_action = "alert"
                    return "alert"
                self._last_action = "hold"
                return "normal"
            # elevation over; leave escalation and fall through
            self._mode = "normal"

        if elevated:
            sorted_R = sorted(self._R)
            cand = _nearest_rank_quantile(sorted_R, self._q)
            stable = max(self._R) <= self._rho * median
            if stable and cand <= self._kappa * self._theta0:
                self._theta = max(self._theta0, cand)
                self._mode = "normal"
                self._c = 0
                self._last_action = "recalibrate"
                return "alert" if s > self._theta else "normal"
            if self._c < self._D:
                self._c += 1
                self._mode = "suspect"
                self._last_action = "defer"
                return "defer"
            self._mode = "escalated"
            self._c = 0
            if s > self._theta:
                self._last_action = "alert"
                return "alert"
            self._last_action = "hold"
            return "normal"

        # not elevated
        if self._mode == "suspect":
            self._mode = "normal"
            self._c = 0
        if full and self._theta > self._theta0:
            sorted_R = sorted(self._R)
            cand = _nearest_rank_quantile(sorted_R, self._q)
            if cand < self._theta:
                self._theta = max(self._theta0, cand)
                self._last_action = "recalibrate"
                return "alert" if s > self._theta else "normal"
        if s > self._theta:
            self._last_action = "alert"
            return "alert"
        self._last_action = "hold"
        return "normal"

    def reset(self) -> None:
        self._theta = self._theta0
        self._mode = "normal"
        self._c = 0
        self._R = []
        self._last_action = "hold"


class SunConfidenceSequencePolicy:
    """Re-implementation of Sun et al. (ICML 2024) Algorithm 1 with eq. (1);
    not the authors' code.

    This is the closest-literature abstention baseline (frozen protocol
    section 5). It maintains a running history of scores (the calibration
    scores plus every replay score seen so far -- admit-all, the
    single-offline-dataset matched branch of the paper's Algorithm 4) and, at
    each window, builds a confidence set for the p-quantile:

        u_n(alpha) = 0.85 * sqrt((log log(e*n) + 0.8*log(1612/alpha)) / n)
        Qhat(p; y_1..n) = (y_(floor(p*n)) + y_(ceil(p*n))) / 2   (1-indexed
                          order statistics, with y_(0) := y_(1))
        C = [ Qhat(max(p - 2*u_n, 0)), Qhat(min(p + 2*u_n, 1)) ]

    Decision on the current score S:
        S > max(C) -> alert ; S in C -> defer ; else normal.

    The paper's change-point Algorithms 2-3 and its match test are NOT
    implemented here; only Algorithm 1 with the eq. (1) confidence set. p and
    alpha default to the frozen values (p=0.95, alpha=0.05).
    """

    __slots__ = ("_p", "_alpha", "_history")

    def __init__(self, calibration_scores=(), p=0.95, alpha=0.05):
        p_f = _check_threshold(p)
        if not 0 < p_f < 1:
            raise ValueError("p must satisfy 0 < p < 1")
        a_f = _check_threshold(alpha)
        if not 0 < a_f < 1:
            raise ValueError("alpha must satisfy 0 < alpha < 1")
        self._p = p_f
        self._alpha = a_f
        hist = []
        for v in calibration_scores:
            hist.append(_check_score(v))
        self._history = hist

    @property
    def history(self):
        return list(self._history)

    def u_n(self, n) -> float:
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError("n must be a positive integer")
        return 0.85 * math.sqrt(
            (math.log(math.log(math.e * n)) + 0.8 * math.log(1612.0 / self._alpha)) / n)

    def q_hat(self, values, p) -> float:
        """Interpolated quantile Qhat(p; values) with y_(0) := y_(1)."""
        s = sorted(_check_score(v) for v in values)
        n = len(s)
        if n == 0:
            raise ValueError("q_hat needs at least one value")

        def order(k):
            if k <= 0:
                k = 1
            if k > n:
                k = n
            return s[k - 1]

        lo = math.floor(p * n)
        hi = math.ceil(p * n)
        return (order(lo) + order(hi)) / 2.0

    def decide(self, score) -> str:
        s = _check_score(score)
        # history = calibration scores UNION replay scores so far, including s.
        self._history.append(s)
        n = len(self._history)
        u = self.u_n(n)
        lo_p = max(self._p - 2.0 * u, 0.0)
        hi_p = min(self._p + 2.0 * u, 1.0)
        c_lo = self.q_hat(self._history, lo_p)
        c_hi = self.q_hat(self._history, hi_p)
        if s > c_hi:
            return "alert"
        if s >= c_lo:
            return "defer"
        return "normal"

    def reset(self, calibration_scores=()) -> None:
        self._history = [_check_score(v) for v in calibration_scores]
