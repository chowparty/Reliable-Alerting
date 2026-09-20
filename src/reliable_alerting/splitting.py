import dataclasses

from reliable_alerting import loading


@dataclasses.dataclass(frozen=True)
class Window:
    window_id: str
    start_index: int
    end_index: int
    values: tuple


def make_windows(values, start: int, stop: int, length: int, stride: int, segment: str) -> list[Window]:
    vals = loading.load_values(values)
    for name, v in (("start", start), ("stop", stop)):
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"{name} must be an int")
    for name, v in (("length", length), ("stride", stride)):
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"{name} must be an int")
        if v < 1:
            raise ValueError(f"{name} must be >= 1")
    if not isinstance(segment, str):
        raise TypeError("segment must be a string")
    if segment == "":
        raise ValueError("segment must be non-empty")
    n = len(vals)
    if not (0 <= start < stop <= n):
        raise ValueError("segment must satisfy 0 <= start < stop <= len(values)")
    if stop - start < length:
        raise ValueError("segment shorter than window length")
    out: list[Window] = []
    s = start
    while s + length <= stop:
        e = s + length - 1
        out.append(
            Window(
                window_id=f"{segment}:{s}:{e}",
                start_index=s,
                end_index=e,
                values=tuple(vals[s : s + length]),
            )
        )
        s += stride
    return out
