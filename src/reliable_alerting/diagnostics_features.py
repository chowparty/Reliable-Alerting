import math

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

class RollingMedianFeature:
    __slots__ = ("_length", "_history")

    def __init__(self, length):
        if not isinstance(length, int) or length < 1:
            raise ValueError("length must be a positive integer")
        self._length = length
        self._history = []

    def update(self, score) -> float:
        f = _check_score(score)
        self._history.append(f)
        if len(self._history) > self._length:
            self._history.pop(0)

        s = sorted(self._history)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        else:
            return (s[n // 2 - 1] + s[n // 2]) / 2.0

class RollingSpreadFeature:
    __slots__ = ("_length", "_history")

    def __init__(self, length):
        if not isinstance(length, int) or length < 1:
            raise ValueError("length must be a positive integer")
        self._length = length
        self._history = []

    def update(self, score) -> float:
        f = _check_score(score)
        self._history.append(f)
        if len(self._history) > self._length:
            self._history.pop(0)

        n = len(self._history)
        if n < 2:
            return 0.0
        
        mean = sum(self._history) / n
        variance = sum((x - mean) ** 2 for x in self._history) / (n - 1)
        return math.sqrt(variance)
