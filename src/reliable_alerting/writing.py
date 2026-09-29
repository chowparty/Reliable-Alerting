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

ACTION_LOG_COLUMNS = ("window_id", "end_index", "action", "threshold")

_ACTION_VALUES = ("hold", "alert", "defer", "recalibrate")


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
        if state not in ("normal", "alert", "defer"):
            raise ValueError("output_state must be 'normal', 'alert' or 'defer'")
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


def _validate_action_rows(rows, trace) -> list[dict]:
    """Validate the label-free per-decision action log against the trace rows.

    One action row per prediction row, in the same order, keyed by window_id
    and end_index. action is one of hold/alert/defer/recalibrate; threshold is
    the finite threshold that judged the window.
    """
    if rows is None or isinstance(rows, (str, bytes, dict)):
        raise TypeError("action_rows must be a sequence of dicts")
    try:
        items = list(rows)
    except TypeError:
        raise TypeError("action_rows must be a sequence of dicts")
    if len(items) != len(trace):
        raise ValueError("action_rows must have one row per prediction row")
    expected = set(ACTION_LOG_COLUMNS)
    out = []
    for entry, prow in zip(items, trace):
        if not isinstance(entry, dict):
            raise TypeError("each action row must be a dict")
        if set(entry.keys()) != expected:
            raise ValueError(f"action row must have exactly {ACTION_LOG_COLUMNS}")
        window_id = _require_id(entry["window_id"], "window_id")
        end = _require_index(entry["end_index"], "end_index")
        action = entry["action"]
        if action not in _ACTION_VALUES:
            raise ValueError(f"action must be one of {_ACTION_VALUES}")
        threshold = _require_finite(entry["threshold"], "threshold")
        if window_id != prow["window_id"] or end != prow["end_index"]:
            raise ValueError("action row must align with the prediction row")
        out.append({"window_id": window_id, "end_index": end,
                    "action": action, "threshold": threshold})
    return out


def _validate_json_mapping(value, name: str) -> str:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False)


def write_run(output_dir, rows, config: dict, metadata: dict, diagnostics: dict, calibration_rows, action_rows=None) -> None:
    trace = _validate_trace_rows(rows)
    calib = _validate_calibration_rows(calibration_rows)
    actions = _validate_action_rows(action_rows, trace) if action_rows is not None else None
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
    if actions is not None:
        with open(out / "policy_actions.csv", "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(list(ACTION_LOG_COLUMNS))
            for entry in actions:
                writer.writerow([
                    entry["window_id"],
                    entry["end_index"],
                    entry["action"],
                    repr(float(entry["threshold"])),
                ])
