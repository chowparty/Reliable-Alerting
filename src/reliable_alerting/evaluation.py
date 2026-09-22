"""Focused offline evaluation core (pure, label-joined-after-save).

Why: episodes form from saved prediction states before labels are
consulted; metrics compare those episodes against clipped label events
on the sample_index basis with half-open intervals.
"""
import copy
import math

from reliable_alerting.writing import PREDICTIONS_COLUMNS

METRIC_DEFINITION_ID = "offline-alert-evaluation-v1"

_VALID_STATES = ("normal", "alert", "defer")
_DURATION_UNIT = "sample_index"


def _exact(d, allowed, where):
    if not isinstance(d, dict):
        raise TypeError(f"{where} must be a dict")
    keys = set(d.keys())
    if keys != set(allowed):
        missing = set(allowed) - keys
        extra = keys - set(allowed)
        raise ValueError(
            f"{where} must have exactly {allowed} (missing={missing} extra={extra})"
        )
    return d


def _require_id(value, name):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if value.strip() == "":
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_index(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _require_finite(value, name):
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


def _require_bounds(pair, name):
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError(f"{name} must be [start, stop]")
    a, b = pair
    if isinstance(a, bool) or not isinstance(a, int):
        raise TypeError(f"{name} bounds must be ints")
    if isinstance(b, bool) or not isinstance(b, int):
        raise TypeError(f"{name} bounds must be ints")
    if a < 0 or b < 0:
        raise ValueError(f"{name} bounds must be >= 0")
    if not a < b:
        raise ValueError(f"{name} must satisfy start < stop")
    return [a, b]


def validate_evaluation_config(config):
    """Validate and resolve the offline evaluation config."""
    _exact(
        config,
        ["schema_version", "time_basis", "horizon",
         "first_decision", "decision_stride", "window_length"],
        "config",
    )
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if not isinstance(config["time_basis"], str) or config["time_basis"] != "sample_index":
        raise ValueError("time_basis must be 'sample_index'")
    horizon = _require_bounds(config["horizon"], "horizon")
    first = config["first_decision"]
    if isinstance(first, bool) or not isinstance(first, int):
        raise TypeError("first_decision must be an int")
    if first < 0:
        raise ValueError("first_decision must be >= 0")
    stride = config["decision_stride"]
    if isinstance(stride, bool) or not isinstance(stride, int):
        raise TypeError("decision_stride must be an int")
    if stride < 1:
        raise ValueError("decision_stride must be >= 1")
    wlen = config["window_length"]
    if isinstance(wlen, bool) or not isinstance(wlen, int):
        raise TypeError("window_length must be an int")
    if wlen < 1:
        raise ValueError("window_length must be >= 1")
    if first != horizon[0] + wlen - 1:
        raise ValueError("first_decision must equal horizon_start + window_length - 1")
    if not first < horizon[1]:
        raise ValueError("first_decision must be < horizon_stop")
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "horizon": [horizon[0], horizon[1]],
        "first_decision": first,
        "decision_stride": stride,
        "window_length": wlen,
    }


def _expected_ends(resolved):
    h0, h1 = resolved["horizon"]
    first = resolved["first_decision"]
    stride = resolved["decision_stride"]
    ends = []
    k = 0
    while first + k * stride < h1:
        ends.append(first + k * stride)
        k += 1
    return ends


def _validate_rows(rows, resolved):
    if rows is None or isinstance(rows, (str, bytes, dict)):
        raise TypeError("rows must be a non-empty sequence of dicts")
    try:
        items = list(rows)
    except TypeError:
        raise TypeError("rows must be a non-empty sequence of dicts")
    if not items:
        raise ValueError("rows must not be empty")
    expected_cols = set(PREDICTIONS_COLUMNS)
    out = []
    seen_ids = set()
    config_id = None
    run_id = None
    for entry in items:
        if not isinstance(entry, dict):
            raise TypeError("each row must be a dict")
        if set(entry.keys()) != expected_cols:
            raise ValueError(f"row must have exactly {tuple(PREDICTIONS_COLUMNS)}")
        window_id = _require_id(entry["window_id"], "window_id")
        start = _require_index(entry["start_index"], "start_index")
        end = _require_index(entry["end_index"], "end_index")
        if start > end:
            raise ValueError("start_index must be <= end_index")
        score = _require_finite(entry["score"], "score")
        threshold = _require_finite(entry["threshold"], "threshold")
        state = entry["output_state"]
        if state not in _VALID_STATES:
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
        out.append({
            "window_id": window_id,
            "start_index": start,
            "end_index": end,
            "score": float(score),
            "output_state": state,
            "threshold": float(threshold),
            "config_id": cid,
            "run_id": rid,
        })
    expected = _expected_ends(resolved)
    if len(out) != len(expected):
        raise ValueError(f"rows must cover exact schedule ({len(expected)} decisions)")
    wlen = resolved["window_length"]
    prev_end = None
    for row, exp_end in zip(out, expected):
        if row["end_index"] != exp_end:
            raise ValueError(f"end_index {row['end_index']} off schedule (expected {exp_end})")
        if row["start_index"] != exp_end - wlen + 1:
            raise ValueError("start_index must equal end_index - window_length + 1")
        if prev_end is not None and not row["end_index"] > prev_end:
            raise ValueError("end_index must be strictly increasing")
        prev_end = row["end_index"]
    return out


def _validate_labels(labels, resolved):
    _exact(labels, ["schema_version", "time_basis", "coverage", "events"], "labels")
    if type(labels["schema_version"]) is not int or labels["schema_version"] != 1:
        raise ValueError("labels schema_version must be 1")
    if not isinstance(labels["time_basis"], str) or labels["time_basis"] != "sample_index":
        raise ValueError("labels time_basis must be 'sample_index'")
    coverage = _require_bounds(labels["coverage"], "coverage")
    h0, h1 = resolved["horizon"]
    if not (coverage[0] <= h0 and coverage[1] >= h1):
        raise ValueError("coverage must encompass full horizon")
    raw_events = labels["events"]
    if not isinstance(raw_events, (list, tuple)):
        raise TypeError("events must be a list")
    events = []
    seen = set()
    prev_start = None
    for entry in raw_events:
        if not isinstance(entry, dict):
            raise TypeError("each event must be a dict")
        if set(entry.keys()) != {"event_id", "start", "stop"}:
            raise ValueError("event must have exactly (event_id, start, stop)")
        eid = _require_id(entry["event_id"], "event_id")
        s = _require_index(entry["start"], "event start")
        e = _require_index(entry["stop"], "event stop")
        if not s < e:
            raise ValueError("event must satisfy start < stop")
        if eid in seen:
            raise ValueError("duplicate event_id")
        seen.add(eid)
        if prev_start is not None and s < prev_start:
            raise ValueError("events must be sorted by start")
        prev_start = s
        events.append({"event_id": eid, "start": s, "stop": e})
    return {"coverage": coverage, "events": events}


def inclusive_events_to_half_open(events):
    """Convert inclusive-stop source events to half-open [start, stop+1)."""
    if events is None or isinstance(events, (str, bytes, dict)):
        raise TypeError("events must be a sequence of dicts")
    try:
        items = list(events)
    except TypeError:
        raise TypeError("events must be a sequence of dicts")
    out = []
    for entry in items:
        if not isinstance(entry, dict):
            raise TypeError("each event must be a dict")
        if set(entry.keys()) != {"event_id", "start", "stop"}:
            raise ValueError("event must have exactly (event_id, start, stop)")
        eid = _require_id(entry["event_id"], "event_id")
        s = _require_index(entry["start"], "event start")
        e = _require_index(entry["stop"], "event stop")
        if not s <= e:
            raise ValueError("inclusive event must satisfy start <= stop")
        out.append({"event_id": eid, "start": s, "stop": e + 1})
    return out


def events_from_point_labels(labels, start_index=0):
    """Convert a binary point-label array to half-open event intervals."""
    if isinstance(start_index, bool) or not isinstance(start_index, int):
        raise TypeError("start_index must be an int")
    if start_index < 0:
        raise ValueError("start_index must be >= 0")
    if labels is None or isinstance(labels, (str, bytes, dict)):
        raise TypeError("labels must be a non-empty sequence of 0/1 ints")
    try:
        items = list(labels)
    except TypeError:
        raise TypeError("labels must be a non-empty sequence of 0/1 ints")
    if not items:
        raise ValueError("labels must not be empty")
    for v in items:
        if type(v) is not int:
            raise TypeError("labels must be strict ints 0/1")
        if v not in (0, 1):
            raise ValueError("labels must be binary 0/1")
    out = []
    run_start = None
    for i, v in enumerate(items):
        if v == 1 and run_start is None:
            run_start = i
        elif v == 0 and run_start is not None:
            out.append({
                "event_id": f"event-{len(out)}",
                "start": start_index + run_start,
                "stop": start_index + i,
            })
            run_start = None
    if run_start is not None:
        out.append({
            "event_id": f"event-{len(out)}",
            "start": start_index + run_start,
            "stop": start_index + len(items),
        })
    return out


def form_episodes(rows, config):
    """Form alert episodes from saved states before consulting labels."""
    resolved = validate_evaluation_config(copy.deepcopy(config))
    valid = _validate_rows(rows, resolved)
    h0, h1 = resolved["horizon"]
    intervals = []
    for i, row in enumerate(valid):
        start = row["end_index"]
        if i + 1 < len(valid):
            stop = valid[i + 1]["end_index"]
        else:
            stop = h1
        if stop > h1:
            stop = h1
        intervals.append((start, stop, row["output_state"]))
    episodes = []
    run_start = None
    run_stop = None
    for start, stop, state in intervals:
        if state == "alert":
            if run_start is None:
                run_start, run_stop = start, stop
            else:
                run_stop = stop
        else:
            if run_start is not None:
                episodes.append({
                    "episode_id": f"episode-{len(episodes)}",
                    "start": run_start,
                    "stop": run_stop,
                })
                run_start = run_stop = None
    if run_start is not None:
        episodes.append({
            "episode_id": f"episode-{len(episodes)}",
            "start": run_start,
            "stop": run_stop,
        })
    return episodes


def _overlaps(a_start, a_stop, b_start, b_stop):
    return a_start < b_stop and b_start < a_stop


def evaluate(rows, labels, config):
    """Join saved predictions with labels and compute offline metrics."""
    resolved = validate_evaluation_config(copy.deepcopy(config))
    valid_rows = _validate_rows(rows, resolved)
    episodes = form_episodes(valid_rows, resolved)
    checked = _validate_labels(copy.deepcopy(labels), resolved)
    h0, h1 = resolved["horizon"]
    horizon_length = h1 - h0
    first = resolved["first_decision"]

    original = [{"event_id": e["event_id"], "start": e["start"], "stop": e["stop"]}
                for e in checked["events"]]
    clipped = []
    excluded_count = 0
    clipped_count = 0
    for e in checked["events"]:
        cs = max(e["start"], h0)
        ce = min(e["stop"], h1)
        if not cs < ce:
            excluded_count += 1
            continue
        if cs != e["start"] or ce != e["stop"]:
            clipped_count += 1
        clipped.append({
            "event_id": e["event_id"],
            "start": cs,
            "stop": ce,
            "original_start": e["start"],
            "original_stop": e["stop"],
        })

    matches = []
    for c in clipped:
        hits = [ep["episode_id"] for ep in episodes
                if _overlaps(ep["start"], ep["stop"], c["start"], c["stop"])]
        recalled = bool(hits)
        if recalled:
            first_start = min(ep["start"] for ep in episodes if ep["episode_id"] in hits)
            delay = max(0, first_start - c["original_start"])
        else:
            delay = None
        matches.append({
            "event_id": c["event_id"],
            "recalled": recalled,
            "delay": delay,
            "matching_episode_ids": hits,
            "original_start": c["original_start"],
            "original_stop": c["original_stop"],
            "clipped_start": c["start"],
            "clipped_stop": c["stop"],
        })

    recalled_delays = [m["delay"] for m in matches if m["recalled"]]
    n_recalled = len(recalled_delays)
    n_missed = len(matches) - n_recalled
    if n_recalled:
        ordered = sorted(recalled_delays)
        mean = float(sum(ordered) / n_recalled)
        n = n_recalled
        if n % 2 == 1:
            median = float(ordered[n // 2])
        else:
            median = float((ordered[n // 2 - 1] + ordered[n // 2]) / 2)
        dmin = int(min(ordered))
        dmax = int(max(ordered))
    else:
        mean = median = dmin = dmax = None

    tp_episodes = sum(1 for ep in episodes
                      if any(_overlaps(ep["start"], ep["stop"], c["start"], c["stop"])
                             for c in clipped))
    n_episodes = len(episodes)
    n_clipped = len(clipped)
    if n_clipped:
        recall_value = float(n_recalled / n_clipped)
    else:
        recall_value = None
    if n_episodes:
        precision_value = float(tp_episodes / n_episodes)
    else:
        precision_value = None

    n = len(valid_rows)
    n_alert = sum(1 for r in valid_rows if r["output_state"] == "alert")
    n_defer = sum(1 for r in valid_rows if r["output_state"] == "defer")
    n_covered = sum(1 for r in valid_rows if r["output_state"] in ("normal", "alert"))

    total_alert = sum(ep["stop"] - ep["start"] for ep in episodes)
    union = [(c["start"], c["stop"]) for c in clipped]
    overlap_len = 0
    if union and episodes:
        ordered_u = sorted(union)
        merged = []
        cs, ce = ordered_u[0]
        for s, e in ordered_u[1:]:
            if s <= ce:
                ce = max(ce, e)
            else:
                merged.append((cs, ce))
                cs, ce = s, e
        merged.append((cs, ce))
        for ep in episodes:
            for s, e in merged:
                lo = max(ep["start"], s)
                hi = min(ep["stop"], e)
                if hi > lo:
                    overlap_len += hi - lo
    non_event_alert = total_alert - overlap_len

    deferred_duration = 0
    for i, r in enumerate(valid_rows):
        if r["output_state"] == "defer":
            stop = valid_rows[i + 1]["end_index"] if i + 1 < n else h1
            deferred_duration += min(stop, h1) - r["end_index"]
    warmup_duration = first - h0

    metrics = {
        "event_recall": {"value": recall_value, "numerator": n_recalled,
                         "denominator": n_clipped},
        "episode_precision": {"value": precision_value, "numerator": tp_episodes,
                              "denominator": n_episodes},
        "alerted_window_fraction": {"value": float(n_alert / n), "numerator": n_alert,
                                    "denominator": n},
        "decision_coverage": {"value": float(n_covered / n), "numerator": n_covered,
                              "denominator": n},
        "deferral_rate": {"value": float(n_defer / n), "numerator": n_defer,
                          "denominator": n},
        "alert_episode_rate": {"value": float(n_episodes / horizon_length),
                               "numerator": n_episodes, "denominator": horizon_length,
                               "unit": "episodes_per_sample_index"},
        "alert_episode_rate_per_1000_decisions": {
            "value": float(n_episodes / n * 1000),
            "numerator": n_episodes, "denominator": n,
            "unit": "episodes_per_1000_decisions"},
        "false_alert_episodes": int(n_episodes - tp_episodes),
        "delay": {"mean": mean, "median": median, "min": dmin, "max": dmax,
                  "recalled_count": n_recalled, "missed_count": n_missed,
                  "unit": _DURATION_UNIT,
                  "per_event": [{"event_id": m["event_id"], "delay": m["delay"],
                                 "matching_episode_ids": list(m["matching_episode_ids"])}
                                for m in matches]},
        "total_alert_duration": {"value": int(total_alert), "unit": _DURATION_UNIT},
        "non_event_alert_duration": {"value": int(non_event_alert), "unit": _DURATION_UNIT},
        "warmup_duration": {"value": int(warmup_duration), "unit": _DURATION_UNIT},
        "deferred_duration": {"value": int(deferred_duration), "unit": _DURATION_UNIT},
        "decision_count": int(n),
        "excluded_event_count": int(excluded_count),
        "clipped_event_count": int(clipped_count),
    }
    diagnostics = {
        "horizon": [h0, h1],
        "horizon_length": int(horizon_length),
        "horizon_length_unit": _DURATION_UNIT,
        "decision_count": int(n),
        "episode_count": int(n_episodes),
        "clipped_event_count": int(n_clipped),
        "excluded_event_count": int(excluded_count),
        "clipped_count": int(clipped_count),
        "warmup_duration": int(warmup_duration),
        "warmup_duration_unit": _DURATION_UNIT,
        "duration_unit": _DURATION_UNIT,
        "invalid_rows": 0,
        "excluded_rows": 0,
        "missing_rows": 0,
        "missing_policy": "reject",
    }
    return {
        "metric_definition_id": METRIC_DEFINITION_ID,
        "config": resolved,
        "episodes": episodes,
        "events": {
            "original": original,
            "clipped": [{"event_id": c["event_id"], "start": c["start"], "stop": c["stop"]}
                        for c in clipped],
            "excluded_count": int(excluded_count),
            "clipped_count": int(clipped_count),
        },
        "matches": matches,
        "metrics": metrics,
        "diagnostics": diagnostics,
    }
