"""verification.py - reusable dataset verification checks (Nakul's role).

Label-free structural checks (checksum, timestamp order, cadence, missing
cells) plus label-reading checks used ONLY where the project rules permit:
  - source labels: to verify the source-fit segment is source-normal
    (declared in data/manifest.md), and
  - development labels: offline, after causal decisions have been saved.

Held-out discipline is enforced in code: every label-reading function calls
assert_not_reserved(path) first and refuses any file listed in
RESERVED_HELD_OUT. The reserved list mirrors data/manifest.md; the test suite
checks that the two stay in sync.

Standard library only.
"""
import csv
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path

# Held-out files reserved in data/manifest.md. Label-reading functions refuse
# these. Match is on the trailing path components, so absolute and
# repo-relative spellings of the same file are both refused.
RESERVED_HELD_OUT = ("SKAB/other/21.csv",)


class ReservedHeldOutError(PermissionError):
    """Raised when a label-reading check is pointed at a reserved held-out file."""


def _norm_parts(path):
    return [p.lower() for p in Path(str(path).replace("\\", "/")).parts]


def is_reserved(path):
    parts = _norm_parts(path)
    for reserved in RESERVED_HELD_OUT:
        rparts = _norm_parts(reserved)
        if parts[-len(rparts):] == rparts:
            return True
    return False


def assert_not_reserved(path):
    if is_reserved(path):
        raise ReservedHeldOutError(
            f"{path} is a reserved held-out file (data/manifest.md). "
            "Label-reading checks are not permitted before the frozen evaluation."
        )


def file_sha256(path):
    """SHA-256 of the raw file bytes as they exist on this checkout."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def file_sha256_lf(path):
    """SHA-256 of the file bytes with CRLF line endings normalized to LF.

    Git may check the same file out with CRLF on one machine and LF on
    another, which changes the raw byte checksum without changing any data.
    Normalizing ``\r\n`` to ``\n`` before hashing gives a checkout-independent
    digest, so a checksum check stays meaningful regardless of how the working
    tree was materialized.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        data = fh.read()
    h.update(data.replace(b"\r\n", b"\n"))
    return h.hexdigest()


def read_rows(path, delimiter=";"):
    """Read a delimited file into a list of dicts (header row gives keys)."""
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def timestamp_report(rows, field="datetime", fmt="%Y-%m-%d %H:%M:%S"):
    """Order and cadence of a timestamp column (label-free).

    Returns row count, strict-order violations as (row_index, previous, current),
    a histogram of consecutive deltas in seconds, and first/last timestamps.
    """
    stamps = [datetime.strptime(r[field].strip(), fmt) for r in rows]
    violations = []
    deltas = Counter()
    for i in range(1, len(stamps)):
        d = (stamps[i] - stamps[i - 1]).total_seconds()
        deltas[d] += 1
        if d <= 0:
            violations.append((i, stamps[i - 1].strftime(fmt), stamps[i].strftime(fmt)))
    return {
        "rows": len(stamps),
        "violations": violations,
        "delta_histogram": dict(sorted(deltas.items())),
        "first": stamps[0].strftime(fmt) if stamps else None,
        "last": stamps[-1].strftime(fmt) if stamps else None,
    }


def missing_cells(rows, field):
    """Row indices whose `field` cell is empty or whitespace (label-free)."""
    return [i for i, r in enumerate(rows) if not str(r[field]).strip()]


def _binary(value):
    s = str(value).strip()
    if s in ("0", "0.0"):
        return 0
    if s in ("1", "1.0"):
        return 1
    raise ValueError(f"label value {value!r} is not binary 0/1")


def label_runs(path, field="anomaly", delimiter=";"):
    """Contiguous runs of label==1 as half-open [start, stop) row intervals.

    Refuses reserved held-out files. Accepts '0'/'1'/'0.0'/'1.0' only.
    """
    assert_not_reserved(path)
    labels = [_binary(r[field]) for r in read_rows(path, delimiter)]
    runs, start = [], None
    for i, v in enumerate(labels + [0]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    return runs


def segment_label_counts(runs, segments):
    """Count labelled rows per named [start, stop) segment from half-open runs."""
    out = {}
    for name, (a, b) in segments.items():
        out[name] = sum(max(0, min(b, e) - max(a, s)) for s, e in runs)
    return out