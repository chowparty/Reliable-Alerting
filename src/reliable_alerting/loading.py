import math
from collections.abc import Iterable, Sequence


def load_values(values: Iterable) -> tuple[float, ...]:
    if values is None or isinstance(values, (str, bytes)):
        raise TypeError("values must be an iterable of numbers")
    try:
        items = list(values)
    except TypeError:
        raise TypeError("values must be an iterable of numbers")
    if not items:
        raise ValueError("values must not be empty")
    out: list[float] = []
    for v in items:
        if v is None or isinstance(v, bool):
            raise TypeError(f"non-numeric value: {v!r}")
        if not isinstance(v, (int, float)):
            raise TypeError(f"non-numeric value: {v!r}")
        try:
            f = float(v)
        except OverflowError as e:
            raise ValueError(f"non-finite value: {v!r}") from e
        if not math.isfinite(f):
            raise ValueError(f"non-finite value: {v!r}")
        out.append(f)
    return tuple(out)


def load_csv_stream(path: str, value_column: str, time_column: str = "datetime", delimiter: str = ";") -> tuple[float, ...]:
    import csv
    
    out: list[float] = []
    last_val = 0.0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            val_str = row[value_column].strip()
            if not val_str:
                out.append(last_val)  # causal forward-fill for missing values (gaps handling)
            else:
                last_val = float(val_str)
                out.append(last_val)
    
    for v in out:
        if not __import__("math").isfinite(v):
            raise ValueError("non-finite value loaded from csv")
            
    return tuple(out)


def synthetic_values(
    length: int, pattern: Sequence, offsets: Sequence[dict] = ()
) -> tuple[float, ...]:
    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be an int")
    if length <= 0:
        raise ValueError("length must be positive")
    base = load_values(pattern)
    if offsets is None or isinstance(offsets, (str, bytes)):
        raise TypeError("offsets must be a sequence of dicts")
    try:
        items = list(offsets)
    except TypeError:
        raise TypeError("offsets must be a sequence of dicts")
    adds = [0.0] * length
    for entry in items:
        if not isinstance(entry, dict):
            raise TypeError(f"offset entry must be a dict: {entry!r}")
        if set(entry.keys()) != {"start", "stop", "offset"}:
            raise ValueError(f"offset entry must have start/stop/offset: {entry!r}")
        start = entry["start"]
        stop = entry["stop"]
        offset = entry["offset"]
        if isinstance(start, bool) or not isinstance(start, int):
            raise TypeError(f"bad start: {start!r}")
        if isinstance(stop, bool) or not isinstance(stop, int):
            raise TypeError(f"bad stop: {stop!r}")
        if offset is None or isinstance(offset, bool):
            raise TypeError(f"bad offset: {offset!r}")
        if not isinstance(offset, (int, float)):
            raise TypeError(f"bad offset: {offset!r}")
        try:
            off = float(offset)
        except OverflowError as e:
            raise ValueError(f"non-finite offset: {offset!r}") from e
        if not math.isfinite(off):
            raise ValueError(f"non-finite offset: {offset!r}")
        if not (0 <= start <= stop <= length):
            raise ValueError(f"offset range out of bounds: {start}:{stop}")
        for i in range(start, stop):
            adds[i] += off
            if not math.isfinite(adds[i]):
                raise ValueError(f"non-finite offset accumulation at {i}")
    out = tuple(base[i % len(base)] + adds[i] for i in range(length))
    for v in out:
        if not math.isfinite(v):
            raise ValueError("non-finite synthetic value")
    return out
