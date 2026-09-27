import csv
import json
import math
import os
from pathlib import Path

PREDICTIONS_COLUMNS = (
    "window_id",
    "start_index",
    "end_index",
    "score",
    "output_state",
    "threshold",
    "config_id",
    "run_id",
)

CALIBRATION_COLUMNS = ("window_id", "start_index", "end_index", "score")


def _require_id(value, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if value.strip() == "":
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_index(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _require_finite(value, name: str) -> float:
    if value is None or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    try:
        f = float(value)
    except OverflowError as e:
        raise ValueError(f"{name} must be finite") from e
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite")
    return f


def _validate_trace_rows(rows) -> list[dict]:
    if rows is None or isinstance(rows, (str, bytes, dict)):
        raise TypeError("rows must be a non-empty sequence of dicts")
    try:
        items = list(rows)
    except TypeError:
        raise TypeError("rows must be a non-empty sequence of dicts")
    if not items:
        raise ValueError("rows must not be empty")
    expected = set(PREDICTIONS_COLUMNS)
    seen_ids: set[str] = set()
    prev_end: int | None = None
    config_id: str | None = None
    run_id: str | None = None
    for entry in items:
        if not isinstance(entry, dict):
            raise TypeError("each row must be a dict")
        keys = set(entry.keys())
        missing = expected - keys
        if missing:
            raise ValueError(f"row missing required columns {sorted(missing)}")
        # Strict schema: the required PREDICTIONS_COLUMNS plus the optional
        # 'features' field only. 'features' carries score-derived diagnostics
        # emitted by the pipeline and is the sole permitted extra key; any other
        # unexpected key is rejected. (Score/threshold vs output_state
        # consistency is intentionally NOT enforced here: stateful policies
        # such as k_consecutive/m_of_n/hysteresis legitimately emit an
        # output_state that is not a pure function of score vs threshold.)
        unexpected = keys - expected - {"features"}
        if unexpected:
            raise ValueError(f"row has unexpected columns {sorted(unexpected)}")
        window_id = _require_id(entry["window_id"], "window_id")
        start = _require_index(entry["start_index"], "start_index")
        end = _require_index(entry["end_index"], "end_index")
        if start > end:
            raise ValueError("start_index must be <= end_index")
        score = _require_finite(entry["score"], "score")
        threshold = _require_finite(entry["threshold"], "threshold")
        state = entry["output_state"]
        if state not in ("normal", "alert"):
            raise ValueError("output_state must be 'normal' or 'alert'")
        cid = _require_id(entry["config_id"], "config_id")
        rid = _require_id(entry["run_id"], "run_id")
        if config_id is None:
            config_id = cid
            run_id = rid
        elif cid != config_id or rid != run_id:
            raise ValueError("config_id and run_id must match across rows")
        if window_id in seen_ids:
            raise ValueError("duplicate window_id")
        seen_ids.add(window_id)
        if prev_end is not None and end <= prev_end:
            raise ValueError("end_index must be strictly increasing")
        prev_end = end
    return items


def _validate_calibration_rows(rows) -> list[dict]:
    if rows is None or isinstance(rows, (str, bytes, dict)):
        raise TypeError("calibration_rows must be a non-empty sequence of dicts")
    try:
        items = list(rows)
    except TypeError:
        raise TypeError("calibration_rows must be a non-empty sequence of dicts")
    if not items:
        raise ValueError("calibration_rows must not be empty")
    expected = set(CALIBRATION_COLUMNS)
    seen_ids: set[str] = set()
    prev_end: int | None = None
    for entry in items:
        if not isinstance(entry, dict):
            raise TypeError("each calibration row must be a dict")
        keys = set(entry.keys())
        if keys != expected:
            raise ValueError(f"calibration row must have exactly {CALIBRATION_COLUMNS}")
        window_id = _require_id(entry["window_id"], "window_id")
        start = _require_index(entry["start_index"], "start_index")
        end = _require_index(entry["end_index"], "end_index")
        if start > end:
            raise ValueError("start_index must be <= end_index")
        _require_finite(entry["score"], "score")
        if window_id in seen_ids:
            raise ValueError("duplicate calibration window_id")
        seen_ids.add(window_id)
        if prev_end is not None and end <= prev_end:
            raise ValueError("calibration end_index must be strictly increasing")
        prev_end = end
    return items


def _validate_json_mapping(value, name: str) -> str:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False)


def write_run(output_dir, rows, config: dict, metadata: dict, diagnostics: dict, calibration_rows) -> None:
    trace = _validate_trace_rows(rows)
    calib = _validate_calibration_rows(calibration_rows)
    config_text = _validate_json_mapping(config, "config")
    metadata_text = _validate_json_mapping(metadata, "metadata")
    diagnostics_text = _validate_json_mapping(diagnostics, "diagnostics")
    if output_dir is None or isinstance(output_dir, bool):
        raise TypeError("output_dir must be a path")
    if not isinstance(output_dir, (str, os.PathLike)):
        raise TypeError("output_dir must be a path")
    if isinstance(output_dir, str) and output_dir.strip() == "":
        raise ValueError("output_dir must be non-empty")
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError(f"output directory already exists: {out}")
    out.mkdir(parents=True, exist_ok=False)
    with open(out / "predictions.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        headers = list(PREDICTIONS_COLUMNS)
        if trace and "features" in trace[0]:
            headers.append("features")
            
        writer.writerow(headers)
        for entry in trace:
            row_out = [
                entry["window_id"],
                entry["start_index"],
                entry["end_index"],
                repr(float(entry["score"])),
                entry["output_state"],
                repr(float(entry["threshold"])),
                entry["config_id"],
                entry["run_id"],
            ]
            if "features" in headers:
                row_out.append(json.dumps(entry.get("features", [])))
            writer.writerow(row_out)
    with open(out / "calibration_scores.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(CALIBRATION_COLUMNS))
        for entry in calib:
            writer.writerow(
                [
                    entry["window_id"],
                    entry["start_index"],
                    entry["end_index"],
                    repr(float(entry["score"])),
                ]
            )
    with open(out / "config.json", "w") as fh:
        fh.write(config_text + "\n")
    with open(out / "metadata.json", "w") as fh:
        fh.write(metadata_text + "\n")
    with open(out / "diagnostics.json", "w") as fh:
        fh.write(diagnostics_text + "\n")
