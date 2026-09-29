"""Reusable evidence utilities: run comparison and saved-trace SVG figure.

Why: day-01 runs must be comparable and plottable from saved artifacts only,
without re-running the pipeline or inventing interpolated alert times.
"""
import argparse
import csv
import json
import math
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from reliable_alerting import pipeline, provenance

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

SUBSTANTIVE_FIELDS = (
    "window_id",
    "start_index",
    "end_index",
    "score",
    "output_state",
    "threshold",
    "config_id",
)

CALIBRATION_COLUMNS = ("window_id", "start_index", "end_index", "score")


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


def _parse_int(raw, name):
    if isinstance(raw, bool):
        raise TypeError(f"{name} must be an int")
    if isinstance(raw, int):
        return _require_index(raw, name)
    if isinstance(raw, str):
        s = raw.strip()
        if s == "":
            raise ValueError(f"{name} must be >= 0")
        try:
            v = int(s)
        except ValueError as e:
            raise ValueError(f"{name} must be an int") from e
        return _require_index(v, name)
    raise TypeError(f"{name} must be an int")


def _parse_finite(raw, name):
    if raw is None or isinstance(raw, bool):
        raise TypeError(f"{name} must be a number")
    if isinstance(raw, (int, float)):
        f = float(raw)
    elif isinstance(raw, str):
        s = raw.strip()
        if s == "":
            raise TypeError(f"{name} must be a number")
        try:
            f = float(s)
        except ValueError as e:
            raise TypeError(f"{name} must be a number") from e
    else:
        raise TypeError(f"{name} must be a number")
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite")
    return f


def load_predictions_csv(path):
    """Load and validate predictions.csv with exact schema (parsed types)."""
    p = Path(path)
    with open(p, newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as e:
            raise ValueError("predictions.csv must not be empty") from e
        # Accept the base 8-column schema, or that schema plus a trailing
        # optional "features" column emitted by the multi-policy pipeline.
        # Only the base columns are used here; "features" carries score-derived
        # diagnostics and is not part of recompute comparison (SUBSTANTIVE_FIELDS).
        base_cols = tuple(PREDICTIONS_COLUMNS)
        if tuple(header) == base_cols:
            n_expected = len(base_cols)
        elif tuple(header) == base_cols + ("features",):
            n_expected = len(base_cols) + 1
        else:
            raise ValueError(
                f"predictions header must be exactly {PREDICTIONS_COLUMNS} "
                f"(optionally followed by 'features')")
        rows = []
        seen = set()
        prev_end = None
        config_id = None
        run_id = None
        for lineno, parts in enumerate(reader, start=2):
            if len(parts) != n_expected:
                raise ValueError(f"row {lineno} must have exactly {n_expected} fields")
            d = dict(zip(base_cols, parts))
            window_id = _require_id(d["window_id"], "window_id")
            start = _parse_int(d["start_index"], "start_index")
            end = _parse_int(d["end_index"], "end_index")
            if start > end:
                raise ValueError("start_index must be <= end_index")
            score = _parse_finite(d["score"], "score")
            threshold = _parse_finite(d["threshold"], "threshold")
            state = d["output_state"]
            if state not in ("normal", "alert", "defer"):
                raise ValueError("output_state must be 'normal', 'alert' or 'defer'")
            # NOTE: no score/threshold -> output_state consistency check here.
            # That invariant holds only for the stateless fixed-threshold policy;
            # stateful policies (k_consecutive, m_of_n, hysteresis) and the
            # adaptive rolling threshold legitimately emit a state that is not a
            # pure function of the current score vs threshold. Recompute
            # verification (SUBSTANTIVE_FIELDS) is what guards trace integrity.
            cid = _require_id(d["config_id"], "config_id")
            rid = _require_id(d["run_id"], "run_id")
            if config_id is None:
                config_id = cid
                run_id = rid
            elif cid != config_id or rid != run_id:
                raise ValueError("config_id and run_id must match across rows")
            if window_id in seen:
                raise ValueError("duplicate window_id")
            seen.add(window_id)
            if prev_end is not None and end <= prev_end:
                raise ValueError("end_index must be strictly increasing")
            prev_end = end
            rows.append({
                "window_id": window_id,
                "start_index": start,
                "end_index": end,
                "score": score,
                "output_state": state,
                "threshold": threshold,
                "config_id": cid,
                "run_id": rid,
            })
    if not rows:
        raise ValueError("predictions.csv must not be empty")
    return rows


def _load_calibration_csv(path):
    p = Path(path)
    with open(p, newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as e:
            raise ValueError("calibration_scores.csv must not be empty") from e
        if tuple(header) != tuple(CALIBRATION_COLUMNS):
            raise ValueError(f"calibration header must be exactly {CALIBRATION_COLUMNS}")
        rows = []
        seen = set()
        prev_end = None
        for lineno, parts in enumerate(reader, start=2):
            if len(parts) != len(CALIBRATION_COLUMNS):
                raise ValueError("calibration row must have exactly 4 fields")
            d = dict(zip(CALIBRATION_COLUMNS, parts))
            window_id = _require_id(d["window_id"], "window_id")
            start = _parse_int(d["start_index"], "start_index")
            end = _parse_int(d["end_index"], "end_index")
            if start > end:
                raise ValueError("start_index must be <= end_index")
            score = _parse_finite(d["score"], "score")
            if window_id in seen:
                raise ValueError("duplicate calibration window_id")
            seen.add(window_id)
            if prev_end is not None and end <= prev_end:
                raise ValueError("calibration end_index must be strictly increasing")
            prev_end = end
            rows.append({
                "window_id": window_id,
                "start_index": start,
                "end_index": end,
                "score": score,
            })
    if not rows:
        raise ValueError("calibration_scores.csv must not be empty")
    return rows


def _load_json(path):
    def _const(x):
        raise ValueError(f"non-finite constant: {x}")

    def _nodup(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate object key: {k!r}")
            out[k] = v
        return out

    with open(path) as fh:
        return json.load(fh, parse_constant=_const,
                         object_pairs_hook=_nodup)


def _read_run(run_dir):
    base = Path(run_dir)
    predictions = load_predictions_csv(base / "predictions.csv")
    calibration = _load_calibration_csv(base / "calibration_scores.csv")
    config_raw = _load_json(base / "config.json")
    resolved = pipeline.validate_config(config_raw)
    recomputed = pipeline.config_id_of(resolved)
    metadata = _load_json(base / "metadata.json")
    diagnostics = _load_json(base / "diagnostics.json")
    if not isinstance(metadata, dict):
        raise TypeError("metadata.json must be a dict")
    if not isinstance(diagnostics, dict):
        raise TypeError("diagnostics.json must be a dict")
    return {
        "predictions": predictions,
        "calibration": calibration,
        "config_raw": config_raw,
        "resolved": resolved,
        "recomputed": recomputed,
        "metadata": metadata,
        "diagnostics": diagnostics,
    }


def _strip(rows):
    return [{k: r[k] for k in SUBSTANTIVE_FIELDS} for r in rows]


EXPECTED_METADATA_KEYS = frozenset((
    "run_id", "config_id", "input_hash", "started_at", "started_at_scope",
    "intended_day1", "command", "environment", "git", "file_hashes",
    "resource_scope", "elapsed_monotonic_seconds", "peak_python_allocation_bytes",
))


def _num_tolerant_equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        try:
            fa, fb = float(a), float(b)
        except (OverflowError, ValueError):
            return False
        return fa == fb
    return a == b


def _raw_matches_resolved(raw, resolved):
    if isinstance(raw, dict) and isinstance(resolved, dict):
        if set(raw.keys()) != set(resolved.keys()):
            return False
        return all(_raw_matches_resolved(raw[k], resolved[k]) for k in raw)
    if isinstance(raw, (list, tuple)) and isinstance(resolved, (list, tuple)):
        if len(raw) != len(resolved):
            return False
        return all(_raw_matches_resolved(x, y) for x, y in zip(raw, resolved))
    return _num_tolerant_equal(raw, resolved)


def _verify_recompute(label, run, diffs):
    """Recompute expected trace from resolved config; record mismatches."""
    try:
        expected = pipeline.compute_trace(run["resolved"])
    except Exception as e:
        diffs.append(f"run {label}: recompute failed: {e}")
        return False
    ok = True
    if not _raw_matches_resolved(run["config_raw"], run["resolved"]):
        diffs.append(f"run {label}: config_raw != resolved config")
        ok = False
    exp_rows = [{k: r[k] for k in SUBSTANTIVE_FIELDS} for r in expected["rows"]]
    if _strip(run["predictions"]) != exp_rows:
        diffs.append(f"run {label}: predictions != recomputed expected rows")
        ok = False
    if run["calibration"] != expected["calibration_rows"]:
        diffs.append(f"run {label}: calibration != recomputed expected")
        ok = False
    if run["diagnostics"] != expected["diagnostics"]:
        diffs.append(f"run {label}: diagnostics != recomputed expected")
        ok = False
    if run["metadata"].get("input_hash") != expected.get("input_hash"):
        diffs.append(f"run {label}: metadata input_hash != recomputed input_hash")
        ok = False
    pred_cid = run["predictions"][0]["config_id"]
    pred_rid = run["predictions"][0]["run_id"]
    meta_cid = run["metadata"].get("config_id")
    meta_rid = run["metadata"].get("run_id")
    diag_cid = run["diagnostics"].get("config_id")
    if pred_cid != run["recomputed"]:
        diffs.append(f"run {label}: predictions config_id != recomputed config_id")
        ok = False
    if meta_cid != run["recomputed"]:
        diffs.append(f"run {label}: metadata config_id != recomputed config_id")
        ok = False
    if diag_cid != run["recomputed"]:
        diffs.append(f"run {label}: diagnostics config_id != recomputed config_id")
        ok = False
    if pred_cid != meta_cid:
        diffs.append(f"run {label}: predictions config_id != metadata config_id")
        ok = False
    if pred_rid != meta_rid:
        diffs.append(f"run {label}: predictions run_id != metadata run_id")
        ok = False
    if run["metadata"].get("input_hash") != run["diagnostics"].get("input_hash"):
        diffs.append(f"run {label}: metadata input_hash != diagnostics input_hash")
        ok = False
    return ok


def compare_runs(run_a, run_b):
    """Compare two run directories; return JSON-serializable report dict."""
    a = _read_run(run_a)
    b = _read_run(run_b)
    diffs = []

    # row counts / fields
    na, nb = len(a["predictions"]), len(b["predictions"])
    if na != nb:
        diffs.append(f"row count differs: {na} vs {nb}")

    # predictions substantive (exclude ONLY run_id)
    sa, sb = _strip(a["predictions"]), _strip(b["predictions"])
    pred_equal = (sa == sb)
    if not pred_equal:
        diffs.append("predictions differ excluding run_id")
        # pinpoint first difference for debugging
        n = min(len(sa), len(sb))
        for i in range(n):
            if sa[i] != sb[i]:
                for k in SUBSTANTIVE_FIELDS:
                    if sa[i][k] != sb[i][k]:
                        diffs.append(f"row {i} field {k}: {sa[i][k]!r} vs {sb[i][k]!r}")
                        break
                break
        if len(sa) != len(sb):
            diffs.append(f"prediction length differs: {len(sa)} vs {len(sb)}")

    # calibration identical
    cal_equal = (a["calibration"] == b["calibration"])
    if not cal_equal:
        diffs.append("calibration_scores differ")

    # diagnostics identical
    diag_equal = (a["diagnostics"] == b["diagnostics"])
    if not diag_equal:
        diffs.append("diagnostics differ")

    # config same + config_id recomputed
    config_equal = (a["resolved"] == b["resolved"])
    if not config_equal:
        diffs.append("config differs")
    ma, mb = a["metadata"], b["metadata"]
    # linkage within each run
    for label, run in (("a", a), ("b", b)):
        pred_cid = run["predictions"][0]["config_id"]
        pred_rid = run["predictions"][0]["run_id"]
        meta_cid = run["metadata"].get("config_id")
        meta_rid = run["metadata"].get("run_id")
        diag_cid = run["diagnostics"].get("config_id")
        if pred_cid != run["recomputed"]:
            diffs.append(f"run {label}: predictions config_id != recomputed config_id")
        if meta_cid != run["recomputed"]:
            diffs.append(f"run {label}: metadata config_id != recomputed config_id")
        if diag_cid != run["recomputed"]:
            diffs.append(f"run {label}: diagnostics config_id != recomputed config_id")
        if pred_cid != meta_cid:
            diffs.append(f"run {label}: predictions config_id != metadata config_id")
        if pred_rid != meta_rid:
            diffs.append(f"run {label}: predictions run_id != metadata run_id")
        meta_hash = run["metadata"].get("input_hash")
        diag_hash = run["diagnostics"].get("input_hash")
        if meta_hash != diag_hash:
            diffs.append(f"run {label}: metadata input_hash != diagnostics input_hash")
    id_match = (
        a["recomputed"] == b["recomputed"]
        and ma.get("config_id") == mb.get("config_id") == a["recomputed"] == b["recomputed"]
    )
    if not id_match:
        diffs.append("config_id mismatch across runs")

    # input_hash / git head / file_hashes / environment consistent
    input_equal = (ma.get("input_hash") == mb.get("input_hash"))
    if not input_equal:
        diffs.append("input_hash differs")
    ga = (ma.get("git") or {}).get("head") if isinstance(ma.get("git"), dict) else None
    gb = (mb.get("git") or {}).get("head") if isinstance(mb.get("git"), dict) else None
    git_equal = (ga == gb)
    if not git_equal:
        diffs.append(f"git head differs: {ga!r} vs {gb!r}")
    fh_equal = (ma.get("file_hashes") == mb.get("file_hashes"))
    if not fh_equal:
        diffs.append("file_hashes differ")
    env_equal = (ma.get("environment") == mb.get("environment"))
    if not env_equal:
        diffs.append("environment differs")

    # required scopes / day marker (previously ignored): must be equal
    rs_equal = (ma.get("resource_scope") == mb.get("resource_scope"))
    if not rs_equal:
        diffs.append("resource_scope differs")
    ss_equal = (ma.get("started_at_scope") == mb.get("started_at_scope"))
    if not ss_equal:
        diffs.append("started_at_scope differs")
    day_equal = (ma.get("intended_day1") == mb.get("intended_day1"))
    if not day_equal:
        diffs.append("intended_day1 differs")

    # expected metadata keys + nonempty provenance
    keys_valid = (set(ma.keys()) == EXPECTED_METADATA_KEYS
                  and set(mb.keys()) == EXPECTED_METADATA_KEYS)
    if not keys_valid:
        diffs.append("metadata keys differ from expected")
    head_valid = (isinstance(ga, str) and ga.strip() != ""
                  and isinstance(gb, str) and gb.strip() != "")
    if not head_valid:
        diffs.append("git head missing or empty")
    fh_valid = (isinstance(ma.get("file_hashes"), dict) and bool(ma.get("file_hashes"))
                and isinstance(mb.get("file_hashes"), dict) and bool(mb.get("file_hashes")))
    if not fh_valid:
        diffs.append("file_hashes missing or empty")
    env_valid = (isinstance(ma.get("environment"), dict) and bool(ma.get("environment"))
                 and isinstance(mb.get("environment"), dict) and bool(mb.get("environment")))
    if not env_valid:
        diffs.append("environment missing or empty")

    # per-run recompute verification (cross-run equality alone is not validity)
    recompute_ok = True
    recompute_ok = _verify_recompute("a", a, diffs) and recompute_ok
    recompute_ok = _verify_recompute("b", b, diffs) and recompute_ok

    # current source hashes must match saved (meaningful only on same code)
    try:
        current_hashes = provenance.file_hashes(provenance.repo_root())
        src_match = (ma.get("file_hashes") == current_hashes
                     and mb.get("file_hashes") == current_hashes)
    except Exception as e:
        current_hashes = None
        src_match = False
        diffs.append(f"source hashes unreadable: {e}")
    if not src_match:
        diffs.append("source_hashes_match_current is false")

    status = (
        pred_equal and cal_equal and diag_equal and config_equal
        and id_match and input_equal and git_equal and fh_equal and env_equal
        and rs_equal and ss_equal and day_equal
        and keys_valid and head_valid and fh_valid and env_valid
        and recompute_ok and src_match
        and na == nb
        and not any(
            d.startswith("run a:") or d.startswith("run b:")
            for d in diffs
        )
    )

    report = {
        "run_a": str(run_a),
        "run_b": str(run_b),
        "status": bool(status),
        "row_counts": {"a": na, "b": nb},
        "fields": list(SUBSTANTIVE_FIELDS),
        "excluded_fields": ["run_id"],
        "run_ids": {"a": ma.get("run_id"), "b": mb.get("run_id")},
        "config_ids": {
            "a_metadata": ma.get("config_id"),
            "b_metadata": mb.get("config_id"),
            "a_recomputed": a["recomputed"],
            "b_recomputed": b["recomputed"],
        },
        "config_equal": bool(config_equal),
        "config_id_match": bool(id_match),
        "calibration_equal": bool(cal_equal),
        "diagnostics_equal": bool(diag_equal),
        "predictions_equal_excluding_run_id": bool(pred_equal),
        "input_hash_equal": bool(input_equal),
        "git_head_equal": bool(git_equal),
        "git_heads": {"a": ga, "b": gb},
        "file_hashes_equal": bool(fh_equal),
        "file_hashes": {"a": ma.get("file_hashes"), "b": mb.get("file_hashes")},
        "environment_equal": bool(env_equal),
        "resource_scope_equal": bool(rs_equal),
        "started_at_scope_equal": bool(ss_equal),
        "intended_day1_equal": bool(day_equal),
        "metadata_keys_valid": bool(keys_valid),
        "recompute_match": bool(recompute_ok),
        "source_hashes_match_current": bool(src_match),
        "differences": diffs,
        "varying_metadata": {
            "started_at": {"a": ma.get("started_at"), "b": mb.get("started_at")},
            "command": {"a": ma.get("command"), "b": mb.get("command")},
            "elapsed_monotonic_seconds": {
                "a": ma.get("elapsed_monotonic_seconds"),
                "b": mb.get("elapsed_monotonic_seconds"),
            },
            "peak_python_allocation_bytes": {
                "a": ma.get("peak_python_allocation_bytes"),
                "b": mb.get("peak_python_allocation_bytes"),
            },
            "git_branch": {
                "a": (ma.get("git") or {}).get("branch") if isinstance(ma.get("git"), dict) else None,
                "b": (mb.get("git") or {}).get("branch") if isinstance(mb.get("git"), dict) else None,
            },
            "git_status": {
                "a": (ma.get("git") or {}).get("status_porcelain") if isinstance(ma.get("git"), dict) else None,
                "b": (mb.get("git") or {}).get("status_porcelain") if isinstance(mb.get("git"), dict) else None,
            },
        },
    }
    return report


def write_comparison(run_a, run_b, output):
    """Serialize comparison report to a new file only (mode 'x')."""
    report = compare_runs(run_a, run_b)
    text = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    # exclusive creation: refuse overwrite, preserve existing output
    with open(output, "x") as fh:
        fh.write(text)
    return report


def render_figure(predictions_csv, output_svg):
    """Plot saved predictions.csv (end_index vs score) to plain SVG stdlib."""
    rows = load_predictions_csv(predictions_csv)
    # fixed-policy utility: varying thresholds would make one line misleading
    if len({r["threshold"] for r in rows}) != 1:
        raise ValueError("varying thresholds not supported for figure")
    xs = [r["end_index"] for r in rows]
    ys = [r["score"] for r in rows]
    thr = rows[0]["threshold"]
    config_id = rows[0]["config_id"]

    width, height = 640, 420
    left, right, top, bottom = 60, 20, 50, 70
    plot_w = width - left - right
    plot_h = height - top - bottom

    x_min, x_max = min(xs), max(xs)
    if x_max == x_min:
        x_min -= 1
        x_max += 1
    y_lo = min(min(ys), thr)
    y_hi = max(max(ys), thr)
    if y_hi == y_lo:
        y_lo -= 1.0
        y_hi += 1.0
    else:
        pad = (y_hi - y_lo) * 0.1 or 1.0
        y_lo -= pad
        y_hi += pad

    def _cx(x):
        return left + (x - x_min) / (x_max - x_min) * plot_w

    def _cy(y):
        return top + plot_h - (y - y_lo) / (y_hi - y_lo) * plot_h

    # ticks: numeric on both axes
    if len(set(xs)) <= 10:
        x_ticks = sorted(set(xs))
    else:
        x_ticks = [x_min + (x_max - x_min) * i / 4 for i in range(5)]
        x_ticks = [int(round(v)) for v in x_ticks]
    y_ticks = [y_lo + (y_hi - y_lo) * i / 4 for i in range(5)]

    thr_y = _cy(thr)
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">'
    )
    title = "Synthetic development smoke \u2014 no quality claim: scores vs end_index"
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{width // 2}" y="24" text-anchor="middle" font-size="14">{escape(title)}</text>'
    )
    # axes
    parts.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="black"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="black"/>'
    )
    parts.append(
        f'<text x="12" y="{top + plot_h // 2}" font-size="11" transform="rotate(-90 12,{top + plot_h // 2})">score</text>'
    )
    parts.append(
        f'<text x="{left + plot_w // 2}" y="{height - 12}" text-anchor="middle" font-size="11">end_index</text>'
    )
    for xt in x_ticks:
        cx = _cx(xt)
        parts.append(
            f'<line x1="{cx:.2f}" y1="{top + plot_h}" x2="{cx:.2f}" y2="{top + plot_h + 5}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{top + plot_h + 18}" text-anchor="middle" font-size="10">{escape(str(xt))}</text>'
        )
    for yt in y_ticks:
        cy = _cy(yt)
        parts.append(
            f'<line x1="{left - 5}" y1="{cy:.2f}" x2="{left}" y2="{cy:.2f}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{cy + 3:.2f}" text-anchor="end" font-size="10">{escape(f"{yt:.3g}")}</text>'
        )
    # threshold dashed line (no backdating: horizontal at decision threshold)
    parts.append(
        f'<line x1="{left}" y1="{thr_y:.2f}" x2="{left + plot_w}" y2="{thr_y:.2f}" '
        f'stroke="black" stroke-dasharray="6,4" stroke-width="1.5"/>'
    )
    parts.append(
        f'<text x="{left + plot_w}" y="{thr_y - 6:.2f}" text-anchor="end" font-size="10">threshold {escape(repr(float(thr)))}</text>'
    )
    # points only: no connecting lines (avoid apparent interpolated predictions)
    for r in rows:
        cx = _cx(r["end_index"])
        cy = _cy(r["score"])
        fill = "red" if r["output_state"] == "alert" else "blue"
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="{fill}">'
            f"<title>{escape(r['window_id'] + ' end=' + str(r['end_index']) + ' ' + r['output_state'])}</title>"
            "</circle>"
        )
    caption_id = f"config_id={config_id}"
    caption_src = f"source={str(predictions_csv)}"
    parts.append(
        f'<text x="{left}" y="{height - 44}" font-size="10">{escape(caption_id)}</text>'
    )
    parts.append(
        f'<text x="{left}" y="{height - 30}" font-size="10">{escape(caption_src)}</text>'
    )
    # visible legend (no connecting lines elsewhere)
    lx = left + plot_w - 130
    ly = top + 10
    parts.append(f'<circle cx="{lx}" cy="{ly}" r="4" fill="blue"/>')
    parts.append(f'<text x="{lx + 8}" y="{ly + 4}" font-size="10">normal</text>')
    parts.append(f'<circle cx="{lx + 65}" cy="{ly}" r="4" fill="red"/>')
    parts.append(f'<text x="{lx + 73}" y="{ly + 4}" font-size="10">alert</text>')
    parts.append("</svg>")
    text = "\n".join(parts) + "\n"
    with open(output_svg, "x", encoding="utf-8") as fh:
        fh.write(text)
    return str(output_svg)


def _load_strict_eval_json(path):
    def _const(x):
        raise ValueError(f"non-finite constant: {x}")

    def _nodup(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate object key: {k!r}")
            out[k] = v
        return out

    with open(path) as fh:
        return json.load(fh, parse_constant=_const,
                         object_pairs_hook=_nodup)


def _eval_file_sha256(path):
    import hashlib as _hl
    h = _hl.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_evaluation(eval_dir):
    from reliable_alerting import evaluation as _evaluation
    from reliable_alerting import evaluation_io as _eio
    base = Path(eval_dir)
    config = _load_strict_eval_json(base / "config.json")
    resolved = _evaluation.validate_evaluation_config(config)
    labels = _load_strict_eval_json(base / "labels.json")
    persisted = _load_strict_eval_json(base / "evaluation.json")
    metadata = _load_strict_eval_json(base / "metadata.json")
    if not isinstance(metadata, dict):
        raise TypeError("metadata.json must be a dict")
    rows = _eio.load_predictions_generic(str(base / "predictions.csv"))
    return {
        "dir": str(base),
        "config": resolved,
        "labels": labels,
        "persisted": persisted,
        "metadata": metadata,
        "rows": rows,
    }


def _validate_eval_provenance(label, ev, diffs):
    """Schema check for eval metadata; equality across evals stays separate."""
    meta = ev["metadata"]
    ok = True

    def _need_str(key):
        nonlocal ok
        v = meta.get(key)
        if not isinstance(v, str) or v.strip() == "":
            diffs.append(f"eval {label}: metadata {key} missing or empty")
            ok = False

    for key in ("eval_id", "evaluator_id", "evaluation_config_id",
                "source_config_id", "created_at", "created_at_scope",
                "resource_scope"):
        _need_str(key)
    for key in ("input_predictions_file_sha256",
                "persisted_predictions_file_sha256",
                "semantic_predictions_sha256", "label_file_sha256",
                "persisted_labels_file_sha256", "semantic_label_sha256"):
        v = meta.get(key)
        if (not isinstance(v, str) or len(v) != 64
                or any(c not in "0123456789abcdef" for c in v.lower())):
            diffs.append(f"eval {label}: metadata {key} missing or not sha256")
            ok = False
    src = meta.get("source_run")
    if not isinstance(src, dict):
        diffs.append(f"eval {label}: metadata source_run must be a dict")
        ok = False
    else:
        for key in ("path", "run_id", "config_id"):
            v = src.get(key)
            if not isinstance(v, str) or v.strip() == "":
                diffs.append(f"eval {label}: metadata source_run.{key} missing")
                ok = False
    cmd = meta.get("command")
    if not isinstance(cmd, dict):
        diffs.append(f"eval {label}: metadata command must be a dict")
        ok = False
    else:
        for key in ("shell", "argv", "orig_argv", "cwd",
                    "rerun_shell", "rerun_executable"):
            if key not in cmd:
                diffs.append(f"eval {label}: metadata command.{key} missing")
                ok = False
        for key in ("shell", "cwd", "rerun_shell", "rerun_executable"):
            v = cmd.get(key)
            if not isinstance(v, str) or v.strip() == "":
                diffs.append(f"eval {label}: metadata command.{key} empty")
                ok = False
    env = meta.get("environment")
    if not isinstance(env, dict) or not env:
        diffs.append(f"eval {label}: metadata environment missing or empty")
        ok = False
    git = meta.get("git")
    if not isinstance(git, dict):
        diffs.append(f"eval {label}: metadata git must be a dict")
        ok = False
    else:
        head = git.get("head")
        if not isinstance(head, str) or head.strip() == "":
            diffs.append(f"eval {label}: metadata git.head missing or empty")
            ok = False
        for key in ("branch", "status_porcelain"):
            if key not in git or not isinstance(git.get(key), str):
                diffs.append(f"eval {label}: metadata git.{key} missing")
                ok = False
    fh = meta.get("file_hashes")
    if not isinstance(fh, dict) or not fh:
        diffs.append(f"eval {label}: metadata file_hashes missing or empty")
        ok = False
    scope = meta.get("resource_scope")
    allowed = (
        "saved_run_validation_recompute_and_evaluation_excluding_output",
        "saved_run_validation_recompute_and_evaluation_excluding_output_inherited_tracing",
    )
    if scope not in allowed:
        diffs.append(f"eval {label}: metadata resource_scope unexpected")
        ok = False
    el = meta.get("elapsed_monotonic_seconds")
    if isinstance(el, bool) or not isinstance(el, (int, float)) or not el >= 0:
        diffs.append(f"eval {label}: metadata elapsed_monotonic_seconds invalid")
        ok = False
    peak = meta.get("peak_python_allocation_bytes")
    if peak is not None and (isinstance(peak, bool) or not isinstance(peak, int)
                             or peak < 0):
        diffs.append(f"eval {label}: metadata peak_python_allocation_bytes invalid")
        ok = False
    n = meta.get("evaluated_decision_count")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        diffs.append(f"eval {label}: metadata evaluated_decision_count invalid")
        ok = False
    return ok


def _verify_evaluation_recompute(label, ev, diffs):
    from reliable_alerting import evaluation as _evaluation
    from reliable_alerting import evaluation_io as _eio
    try:
        recomputed = _evaluation.evaluate(ev["rows"], ev["labels"], ev["config"])
    except Exception as e:
        diffs.append(f"eval {label}: recompute failed: {e}")
        return False
    ok = True
    if recomputed != ev["persisted"]:
        diffs.append(f"eval {label}: persisted evaluation != recomputed evaluation")
        ok = False
    meta = ev["metadata"]
    try:
        sem_pred = _eio.semantic_predictions_hash(ev["rows"])
        if meta.get("semantic_predictions_sha256") != sem_pred:
            diffs.append(f"eval {label}: predictions hash mismatch")
            ok = False
    except Exception as e:
        diffs.append(f"eval {label}: predictions hash unreadable: {e}")
        ok = False
    try:
        sem_label = _eio.semantic_label_hash(ev["labels"])
        if meta.get("semantic_label_sha256") != sem_label:
            diffs.append(f"eval {label}: labels hash mismatch")
            ok = False
    except Exception as e:
        diffs.append(f"eval {label}: labels hash unreadable: {e}")
        ok = False
    try:
        cfg_id = _eio.evaluation_config_id(ev["config"])
        if meta.get("evaluation_config_id") != cfg_id:
            diffs.append(f"eval {label}: config id mismatch")
            ok = False
    except Exception as e:
        diffs.append(f"eval {label}: config id unreadable: {e}")
        ok = False
    if meta.get("evaluator_id") != _evaluation.METRIC_DEFINITION_ID:
        diffs.append(f"eval {label}: evaluator id mismatch")
        ok = False
    try:
        persisted_pred_sha = _eval_file_sha256(str(Path(ev["dir"]) / "predictions.csv"))
        if meta.get("persisted_predictions_file_sha256") != persisted_pred_sha:
            diffs.append(f"eval {label}: persisted predictions file hash mismatch")
            ok = False
    except Exception as e:
        diffs.append(f"eval {label}: persisted predictions hash unreadable: {e}")
        ok = False
    try:
        persisted_labels_sha = _eval_file_sha256(str(Path(ev["dir"]) / "labels.json"))
        if meta.get("persisted_labels_file_sha256") != persisted_labels_sha:
            diffs.append(f"eval {label}: persisted labels file hash mismatch")
            ok = False
    except Exception as e:
        diffs.append(f"eval {label}: persisted labels hash unreadable: {e}")
        ok = False
    try:
        src = meta.get("source_run") or {}
        row_rid = ev["rows"][0]["run_id"] if ev["rows"] else None
        row_cid = ev["rows"][0]["config_id"] if ev["rows"] else None
        if src.get("run_id") != row_rid:
            diffs.append(f"eval {label}: source_run.run_id != copied rows run_id")
            ok = False
        if src.get("config_id") != row_cid:
            diffs.append(f"eval {label}: source_run.config_id != copied rows config_id")
            ok = False
        if meta.get("source_config_id") != row_cid:
            diffs.append(f"eval {label}: source_config_id != copied rows config_id")
            ok = False
    except Exception as e:
        diffs.append(f"eval {label}: source linkage unreadable: {e}")
        ok = False
    return ok


def compare_evaluations(eval_a, eval_b):
    """Compare two saved evaluation directories (scientific vs provenance)."""
    a = _read_evaluation(eval_a)
    b = _read_evaluation(eval_b)
    diffs = []
    config_equal = (a["config"] == b["config"])
    if not config_equal:
        diffs.append("evaluation config differs")
    eval_equal = (a["persisted"] == b["persisted"])
    if not eval_equal:
        diffs.append("persisted evaluation differs")
    from reliable_alerting import evaluation_io as _eio
    sem_pred_equal = (_eio.semantic_predictions_hash(a["rows"])
                      == _eio.semantic_predictions_hash(b["rows"]))
    if not sem_pred_equal:
        diffs.append("semantic predictions differ")
    sem_label_equal = (_eio.semantic_label_hash(a["labels"])
                       == _eio.semantic_label_hash(b["labels"]))
    if not sem_label_equal:
        diffs.append("semantic labels differ")
    recompute_ok = True
    recompute_ok = _verify_evaluation_recompute("a", a, diffs) and recompute_ok
    recompute_ok = _verify_evaluation_recompute("b", b, diffs) and recompute_ok
    provenance_valid = True
    provenance_valid = _validate_eval_provenance("a", a, diffs) and provenance_valid
    provenance_valid = _validate_eval_provenance("b", b, diffs) and provenance_valid
    scientific_equal = bool(config_equal and eval_equal and sem_pred_equal
                            and sem_label_equal and recompute_ok)
    ma, mb = a["metadata"], b["metadata"]
    fh_equal = (ma.get("file_hashes") == mb.get("file_hashes"))
    env_equal = (ma.get("environment") == mb.get("environment"))
    ga = (ma.get("git") or {}).get("head") if isinstance(ma.get("git"), dict) else None
    gb = (mb.get("git") or {}).get("head") if isinstance(mb.get("git"), dict) else None
    git_equal = (ga == gb)
    try:
        current_hashes = provenance.file_hashes(provenance.repo_root())
        src_match = (ma.get("file_hashes") == current_hashes
                     and mb.get("file_hashes") == current_hashes)
    except Exception as e:
        src_match = False
        diffs.append(f"source hashes unreadable: {e}")
    if not src_match:
        diffs.append("source_hashes_match_current is false")
    # Pure status requires scientific equality, input integrity (recompute
    # including raw/linkage checks) and provenance schema validity. Same git
    # head / current file hashes are reported separately, not required.
    status = bool(scientific_equal and recompute_ok and provenance_valid)
    report = {
        "eval_a": str(eval_a),
        "eval_b": str(eval_b),
        "status": status,
        "scientific_equal": bool(scientific_equal),
        "provenance_valid": bool(provenance_valid),
        "config_equal": bool(config_equal),
        "evaluation_equal": bool(eval_equal),
        "semantic_predictions_equal": bool(sem_pred_equal),
        "semantic_labels_equal": bool(sem_label_equal),
        "recompute_match": bool(recompute_ok),
        "file_hashes_equal": bool(fh_equal),
        "environment_equal": bool(env_equal),
        "git_head_equal": bool(git_equal),
        "git_heads": {"a": ga, "b": gb},
        "source_hashes_match_current": bool(src_match),
        "eval_ids": {"a": ma.get("eval_id"), "b": mb.get("eval_id")},
        "evaluator_ids": {"a": ma.get("evaluator_id"), "b": mb.get("evaluator_id")},
        "differences": diffs,
        "varying_metadata": {
            "eval_id": {"a": ma.get("eval_id"), "b": mb.get("eval_id")},
            "created_at": {"a": ma.get("created_at"), "b": mb.get("created_at")},
            "elapsed_monotonic_seconds": {
                "a": ma.get("elapsed_monotonic_seconds"),
                "b": mb.get("elapsed_monotonic_seconds"),
            },
            "peak_python_allocation_bytes": {
                "a": ma.get("peak_python_allocation_bytes"),
                "b": mb.get("peak_python_allocation_bytes"),
            },
            "resource_scope": {
                "a": ma.get("resource_scope"), "b": mb.get("resource_scope"),
            },
            "source_run_path": {
                "a": (ma.get("source_run") or {}).get("path")
                if isinstance(ma.get("source_run"), dict) else None,
                "b": (mb.get("source_run") or {}).get("path")
                if isinstance(mb.get("source_run"), dict) else None,
            },
            "source_run_id": {
                "a": (ma.get("source_run") or {}).get("run_id")
                if isinstance(ma.get("source_run"), dict) else None,
                "b": (mb.get("source_run") or {}).get("run_id")
                if isinstance(mb.get("source_run"), dict) else None,
            },
            "source_config_id": {
                "a": ma.get("source_config_id"), "b": mb.get("source_config_id"),
            },
        },
    }
    return report


def write_comparison_evaluations(eval_a, eval_b, output):
    """Serialize evaluation comparison to a new file only (mode 'x')."""
    report = compare_evaluations(eval_a, eval_b)
    text = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return report


def render_evaluation_figure(eval_dir, output_svg):
    """Plot saved evaluation: half-open events vs forward episodes + horizon."""
    ev = _read_evaluation(eval_dir)
    diffs = []
    if not _verify_evaluation_recompute("eval", ev, diffs):
        raise ValueError(f"persisted evaluation failed validation: {diffs}")
    if not _validate_eval_provenance("eval", ev, diffs):
        raise ValueError(f"persisted evaluation provenance invalid: {diffs}")
    cfg = ev["config"]
    persisted = ev["persisted"]
    h0, h1 = list(cfg["horizon"])
    first = cfg["first_decision"]
    episodes = list(persisted.get("episodes", []))
    clipped = list((persisted.get("events") or {}).get("clipped", []))
    width, height = 640, 420
    left, right, top, bottom = 60, 20, 60, 70
    plot_w = width - left - right
    plot_h = height - top - bottom

    def _cx(x):
        if h1 == h0:
            return left + plot_w / 2
        return left + (x - h0) / (h1 - h0) * plot_w

    y_event = top + plot_h * 0.3
    y_ep = top + plot_h * 0.65
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">'
    )
    title = "Synthetic labels \u2014 no quality claim: half-open events vs forward episodes"
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{width // 2}" y="24" text-anchor="middle" font-size="14">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{width // 2}" y="42" text-anchor="middle" font-size="11">sample_index units; horizon [{h0}, {h1}); warmup [{h0}, {first})</text>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="black"/>'
    )
    parts.append(
        f'<text x="{left + plot_w // 2}" y="{height - 12}" text-anchor="middle" font-size="11">sample_index</text>'
    )
    # horizon + warmup background
    parts.append(
        f'<rect x="{_cx(h0):.2f}" y="{top}" width="{_cx(h1) - _cx(h0):.2f}" height="{plot_h}" fill="none" stroke="black"/>'
    )
    if first > h0:
        parts.append(
            f'<rect x="{_cx(h0):.2f}" y="{top}" width="{_cx(first) - _cx(h0):.2f}" height="{plot_h}" fill="#eeeeee"/>'
        )
        parts.append(
            f'<text x="{(_cx(h0) + _cx(first)) / 2:.2f}" y="{top + plot_h + 34:.2f}" text-anchor="middle" font-size="10">warmup</text>'
        )
    # x ticks
    for xt in (h0, first, h1):
        cx = _cx(xt)
        parts.append(
            f'<line x1="{cx:.2f}" y1="{top + plot_h}" x2="{cx:.2f}" y2="{top + plot_h + 5}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{top + plot_h + 18}" text-anchor="middle" font-size="10">{escape(str(xt))}</text>'
        )
    # events (half-open) blue
    parts.append(f'<text x="{left}" y="{y_event - 10:.2f}" font-size="11">events (half-open)</text>')
    for e in clipped:
        x1, x2 = _cx(e["start"]), _cx(e["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_event:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="blue">'
            f"<title>{escape(str(e.get('event_id', '')) + ' [' + str(e['start']) + ', ' + str(e['stop']) + ')')}</title>"
            "</rect>"
        )
    # episodes (forward) red
    parts.append(f'<text x="{left}" y="{y_ep - 10:.2f}" font-size="11">episodes (forward)</text>')
    for ep in episodes:
        x1, x2 = _cx(ep["start"]), _cx(ep["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_ep:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="red">'
            f"<title>{escape(str(ep.get('episode_id', '')) + ' [' + str(ep['start']) + ', ' + str(ep['stop']) + ')')}</title>"
            "</rect>"
        )
    eval_id = (ev["metadata"] or {}).get("eval_id", "")
    parts.append(
        f'<text x="{left}" y="{height - 44}" font-size="10">{escape(f"eval_id={eval_id}")}</text>'
    )
    parts.append(
        f'<text x="{left}" y="{height - 30}" font-size="10">{escape(f"source={str(eval_dir)}")}</text>'
    )
    parts.append("</svg>")
    text = "\n".join(parts) + "\n"
    with open(output_svg, "x") as fh:
        fh.write(text)
    return str(output_svg)


FAMILY_POLICIES = ("fixed", "hysteresis")

FAMILY_STATE_COLUMNS = (
    "window_id",
    "start_index",
    "end_index",
    "score",
    "availability_end",
    "before_state",
    "after_state",
    "high",
    "low",
    "judging_threshold",
    "comparator",
    "policy_kind",
    "config_id",
    "run_id",
    "replay_version",
)

FAMILY_SOURCE_SCORES_COLUMNS = ("window_id", "start_index", "end_index", "score")
FAMILY_DURATION_UNIT = "sample_index"
FAMILY_FIGURE_WRAP_WIDTH = 78


def _read_family_scores(path):
    base = Path(path)
    with open(base / "source_scores.csv", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as e:
            raise ValueError("source_scores.csv must not be empty") from e
        if tuple(header) != tuple(FAMILY_SOURCE_SCORES_COLUMNS):
            raise ValueError("source_scores header mismatch")
        rows = []
        seen = set()
        prev_end = None
        for lineno, parts in enumerate(reader, start=2):
            if len(parts) != len(FAMILY_SOURCE_SCORES_COLUMNS):
                raise ValueError(f"source_scores row {lineno} width mismatch")
            d = dict(zip(FAMILY_SOURCE_SCORES_COLUMNS, parts))
            window_id = _require_id(d["window_id"], "window_id")
            start = _parse_int(d["start_index"], "start_index")
            end = _parse_int(d["end_index"], "end_index")
            if start > end:
                raise ValueError("start_index must be <= end_index")
            score = _parse_finite(d["score"], "score")
            if window_id in seen:
                raise ValueError("duplicate source window_id")
            seen.add(window_id)
            if prev_end is not None and end <= prev_end:
                raise ValueError("source end_index must increase")
            prev_end = end
            rows.append({"window_id": window_id, "start_index": start,
                         "end_index": end, "score": score})
    if not rows:
        raise ValueError("source_scores.csv must not be empty")
    return rows


def _read_family_state(path):
    doc = _load_json(path)
    if not isinstance(doc, list) or not doc:
        raise ValueError("state.json must be a non-empty list")
    for entry in doc:
        if not isinstance(entry, dict):
            raise TypeError("each state entry must be a dict")
        if set(entry.keys()) != set(FAMILY_STATE_COLUMNS):
            raise ValueError("state entry keys mismatch")
    return doc


def _strip_family_predictions(rows):
    return [{k: r[k] for k in rows[0] if k != "run_id"} for r in rows] if rows else []


def _strip_family_state(state):
    return [{k: e[k] for k in FAMILY_STATE_COLUMNS
             if k not in ("config_id", "run_id")} for e in state]


def _read_family_validated(path):
    """Validate a family dir and return its scientific artifacts.

    Why: table/figure/compare must only render validated saved evidence;
    any tamper raises instead of plotting.
    """
    from reliable_alerting import evaluation as _evaluation
    from reliable_alerting import evaluation_io as _eio
    from reliable_alerting import replay as _replay
    base = Path(path)
    report = _replay.load_family(path)
    if not report.get("status"):
        raise ValueError(
            f"family failed validation: {report.get('differences')}")
    metadata = _load_json(base / "family_metadata.json")
    protocol = _replay.validate_protocol(
        _eio.load_strict_json(str(base / "protocol.json")))
    eval_resolved = _evaluation.validate_evaluation_config(
        _eio.load_strict_json(str(base / "evaluation_config.json")))
    labels = _eio.load_strict_json(str(base / "labels.json"))
    source_resolved = pipeline.validate_config(
        _eio.load_strict_json(str(base / "source_config.json")))
    scores = _read_family_scores(base)
    policies = {}
    for name in FAMILY_POLICIES:
        policy_cfg = _replay.validate_policy_config(
            _eio.load_strict_json(str(base / name / "policy_config.json")))
        rows = _eio.load_predictions_generic(
            str(base / name / "predictions.csv"))
        state = _read_family_state(base / name / "state.json")
        persisted_eval = _eio.load_strict_json(
            str(base / name / "evaluation.json"))
        policies[name] = {
            "policy_config": policy_cfg,
            "rows": rows,
            "state": state,
            "evaluation": persisted_eval,
        }
    return {
        "path": str(base),
        "report": report,
        "metadata": metadata,
        "protocol": protocol,
        "evaluation_config": eval_resolved,
        "labels": labels,
        "source_config": source_resolved,
        "scores": scores,
        "policies": policies,
    }


def _ep_overlaps(a_start, a_stop, b_start, b_stop):
    return a_start < b_stop and b_start < a_stop


def _merge_intervals(intervals):
    ordered = sorted(intervals)
    merged = []
    for s, e in ordered:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _overlap_len(a_start, a_stop, merged):
    total = 0
    for s, e in merged:
        lo = max(a_start, s)
        hi = min(a_stop, e)
        if hi > lo:
            total += hi - lo
    return total


def compare_families(family_a, family_b):
    """Compare two validated families on deterministic scientific equality.

    Excludes run/family IDs, timestamps, paths, timing/allocation, and
    provenance hashes/git (reported separately). Never claims byte identity.
    """
    from reliable_alerting import replay as _replay
    try:
        ra = _replay.load_family(family_a)
    except Exception as e:
        ra = {"status": False, "differences": [f"load failed: {e}"]}
    try:
        rb = _replay.load_family(family_b)
    except Exception as e:
        rb = {"status": False, "differences": [f"load failed: {e}"]}
    diffs = []
    prov_diffs = []
    flags = {}
    va = bool(ra.get("status"))
    vb = bool(rb.get("status"))
    if not va:
        diffs.append(f"family a invalid: {ra.get('differences')}")
    if not vb:
        diffs.append(f"family b invalid: {rb.get('differences')}")
    fa = fb = None
    if va and vb:
        try:
            fa = _read_family_validated(family_a)
        except Exception as e:
            diffs.append(f"family a artifacts unreadable: {e}")
            va = False
        try:
            fb = _read_family_validated(family_b)
        except Exception as e:
            diffs.append(f"family b artifacts unreadable: {e}")
            vb = False
    scientific_equal = bool(va and vb)
    if va and vb:
        if fa["scores"] != fb["scores"]:
            diffs.append("source score rows/boundaries differ")
            flags["source_scores_equal"] = False
        else:
            flags["source_scores_equal"] = True
        if fa["source_config"] != fb["source_config"]:
            diffs.append("source config differs")
            flags["source_config_equal"] = False
        else:
            flags["source_config_equal"] = True
        try:
            ca = _load_calibration_csv(
                str(Path(family_a) / "source_calibration_scores.csv"))
            cb = _load_calibration_csv(
                str(Path(family_b) / "source_calibration_scores.csv"))
            flags["source_calibration_equal"] = bool(ca == cb)
            if not flags["source_calibration_equal"]:
                diffs.append("source calibration rows differ")
        except Exception as e:
            flags["source_calibration_equal"] = False
            diffs.append(f"source calibration unreadable: {e}")
        try:
            da = _load_json(Path(family_a) / "source_diagnostics.json")
            db = _load_json(Path(family_b) / "source_diagnostics.json")
            flags["source_diagnostics_equal"] = bool(da == db)
            if not flags["source_diagnostics_equal"]:
                diffs.append("source diagnostics differ")
        except Exception as e:
            flags["source_diagnostics_equal"] = False
            diffs.append(f"source diagnostics unreadable: {e}")
        if fa["protocol"] != fb["protocol"]:
            diffs.append("protocol differs")
            flags["protocol_equal"] = False
        else:
            flags["protocol_equal"] = True
        if fa["evaluation_config"] != fb["evaluation_config"]:
            diffs.append("evaluation config differs")
            flags["evaluation_config_equal"] = False
        else:
            flags["evaluation_config_equal"] = True
        if fa["labels"] != fb["labels"]:
            diffs.append("labels differ")
            flags["labels_equal"] = False
        else:
            flags["labels_equal"] = True
        policy_flags = {}
        for name in FAMILY_POLICIES:
            pf = {}
            pa, pb = fa["policies"][name], fb["policies"][name]
            pf["config_equal"] = bool(pa["policy_config"] == pb["policy_config"])
            if not pf["config_equal"]:
                diffs.append(f"policy {name}: config differs")
            sa = _strip_family_predictions(pa["rows"])
            sb = _strip_family_predictions(pb["rows"])
            pf["predictions_equal_excluding_run_id"] = bool(sa == sb)
            if not pf["predictions_equal_excluding_run_id"]:
                diffs.append(
                    f"policy {name}: score rows/boundaries/judging "
                    "thresholds differ excluding run_id")
            ta = _strip_family_state(pa["state"])
            tb = _strip_family_state(pb["state"])
            pf["state_equal_excluding_ids"] = bool(ta == tb)
            if not pf["state_equal_excluding_ids"]:
                diffs.append(
                    f"policy {name}: state before/after/comparators differ "
                    "excluding run/config ids")
            pf["evaluation_equal"] = bool(
                pa["evaluation"] == pb["evaluation"])
            if not pf["evaluation_equal"]:
                diffs.append(
                    f"policy {name}: episodes/events/matches/metrics differ")
            for key in ("episodes", "events", "matches", "metrics"):
                eq = (pa["evaluation"].get(key) == pb["evaluation"].get(key))
                pf[f"{key}_equal"] = bool(eq)
                if not eq and pf["evaluation_equal"] is False:
                    pass
            policy_flags[name] = pf
            if not all((pf["config_equal"],
                        pf["predictions_equal_excluding_run_id"],
                        pf["state_equal_excluding_ids"],
                        pf["evaluation_equal"])):
                scientific_equal = False
        flags["policies"] = policy_flags
        if not all(flags.get(k, True) for k in (
                "source_scores_equal", "source_config_equal",
                "source_calibration_equal", "source_diagnostics_equal",
                "protocol_equal", "evaluation_config_equal", "labels_equal")):
            scientific_equal = False
    else:
        scientific_equal = False
    # provenance reported separately, excluded from status
    prov = {}
    try:
        ma = _load_json(Path(family_a) / "family_metadata.json")
        mb = _load_json(Path(family_b) / "family_metadata.json")
    except Exception as e:
        ma = mb = None
        prov_diffs.append(f"family metadata unreadable: {e}")
    if ma is not None and mb is not None:
        prov["file_hashes_equal"] = bool(
            ma.get("file_hashes") == mb.get("file_hashes"))
        if not prov["file_hashes_equal"]:
            prov_diffs.append("provenance file_hashes differ")
        prov["environment_equal"] = bool(
            ma.get("environment") == mb.get("environment"))
        if not prov["environment_equal"]:
            prov_diffs.append("provenance environment differ")
        ga = (ma.get("git") or {}).get("head") if isinstance(
            ma.get("git"), dict) else None
        gb = (mb.get("git") or {}).get("head") if isinstance(
            mb.get("git"), dict) else None
        prov["git_head_equal"] = bool(ga == gb)
        prov["git_heads"] = {"a": ga, "b": gb}
        if not prov["git_head_equal"]:
            prov_diffs.append("provenance git head differ")
        try:
            current = provenance.file_hashes(provenance.repo_root())
            prov["source_hashes_match_current"] = bool(
                ma.get("file_hashes") == current
                and mb.get("file_hashes") == current)
        except Exception as e:
            prov["source_hashes_match_current"] = False
            prov_diffs.append(f"source hashes unreadable: {e}")
        if not prov.get("source_hashes_match_current", False):
            prov_diffs.append("source_hashes_match_current is false")
    else:
        prov = {"file_hashes_equal": False, "environment_equal": False,
                "git_head_equal": False, "source_hashes_match_current": False}
    status = bool(va and vb and scientific_equal)
    report = {
        "family_a": str(family_a),
        "family_b": str(family_b),
        "status": status,
        "scientific_equal": bool(scientific_equal),
        "families_valid": {"a": bool(va), "b": bool(vb)},
        "source_scores_equal": bool(flags.get("source_scores_equal", False)),
        "source_config_equal": bool(flags.get("source_config_equal", False)),
        "source_calibration_equal": bool(
            flags.get("source_calibration_equal", False)),
        "source_diagnostics_equal": bool(
            flags.get("source_diagnostics_equal", False)),
        "protocol_equal": bool(flags.get("protocol_equal", False)),
        "evaluation_config_equal": bool(
            flags.get("evaluation_config_equal", False)),
        "labels_equal": bool(flags.get("labels_equal", False)),
        "policies": flags.get("policies", {}),
        "family_ids": {
            "a": (ra.get("family_id") if isinstance(ra, dict) else None),
            "b": (rb.get("family_id") if isinstance(rb, dict) else None),
        },
        "source_scores_ids": {
            "a": (ra.get("source_scores_id") if isinstance(ra, dict) else None),
            "b": (rb.get("source_scores_id") if isinstance(rb, dict) else None),
        },
        "differences": diffs,
        "provenance_differences": prov_diffs,
        "provenance": prov,
        "varying_metadata": {
            "family_id": {
                "a": (ra.get("family_id") if isinstance(ra, dict) else None),
                "b": (rb.get("family_id") if isinstance(rb, dict) else None),
            },
            "created_at": {
                "a": (ma.get("created_at") if isinstance(ma, dict) else None),
                "b": (mb.get("created_at") if isinstance(mb, dict) else None),
            },
            "elapsed_monotonic_seconds": {
                "a": (ma.get("elapsed_monotonic_seconds")
                      if isinstance(ma, dict) else None),
                "b": (mb.get("elapsed_monotonic_seconds")
                      if isinstance(mb, dict) else None),
            },
            "peak_python_allocation_bytes": {
                "a": (ma.get("peak_python_allocation_bytes")
                      if isinstance(ma, dict) else None),
                "b": (mb.get("peak_python_allocation_bytes")
                      if isinstance(mb, dict) else None),
            },
            "source_run_path": {
                "a": ((ma.get("source_run") or {}).get("path")
                      if isinstance(ma, dict)
                      and isinstance(ma.get("source_run"), dict) else None),
                "b": ((mb.get("source_run") or {}).get("path")
                      if isinstance(mb, dict)
                      and isinstance(mb.get("source_run"), dict) else None),
            },
            "source_run_id": {
                "a": ((ma.get("source_run") or {}).get("run_id")
                      if isinstance(ma, dict)
                      and isinstance(ma.get("source_run"), dict) else None),
                "b": ((mb.get("source_run") or {}).get("run_id")
                      if isinstance(mb, dict)
                      and isinstance(mb.get("source_run"), dict) else None),
            },
            "policy_run_ids": {
                "a": ({k: (v or {}).get("run_id")
                       for k, v in (ma.get("policies") or {}).items()}
                      if isinstance(ma, dict) else None),
                "b": ({k: (v or {}).get("run_id")
                       for k, v in (mb.get("policies") or {}).items()}
                      if isinstance(mb, dict) else None),
            },
        },
    }
    return report


def write_family_comparison(family_a, family_b, output):
    """Serialize a family comparison to a new file only (mode 'x')."""
    report = compare_families(family_a, family_b)
    text = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return report


def _held_forward_intervals(held_window_ids, rows, horizon_stop):
    """Forward availability intervals for held windows from saved rows.

    Each decision takes effect at its availability end (end_index) until
    the next decision's end, or the horizon stop for the last window.
    """
    by_id = {}
    for i, r in enumerate(rows):
        by_id[r["window_id"]] = i
    out = []
    for wid in held_window_ids:
        if wid not in by_id:
            raise ValueError(f"held window {wid!r} not in prediction rows")
        i = by_id[wid]
        start = rows[i]["end_index"]
        if i + 1 < len(rows):
            stop = rows[i + 1]["end_index"]
        else:
            stop = horizon_stop
        out.append({"window_id": wid, "start": start, "stop": stop})
    return out


def _annotate_policy(policy_name, persisted_eval, rows, state, high,
                     horizon_stop):
    matches = list(persisted_eval.get("matches", []))
    episodes = list(persisted_eval.get("episodes", []))
    clipped = list((persisted_eval.get("events") or {}).get("clipped", []))
    # forward availability interval per saved row, in row order
    fwd = []
    for i, r in enumerate(rows):
        start = r["end_index"]
        stop = rows[i + 1]["end_index"] if i + 1 < len(rows) else horizon_stop
        fwd.append({"window_id": r["window_id"], "start": start, "stop": stop,
                    "output_state": r["output_state"]})
    alert_ids = {f["window_id"] for f in fwd if f["output_state"] == "alert"}

    def _episode_alert_windows(ep):
        return sorted(f["window_id"] for f in fwd
                      if f["output_state"] == "alert"
                      and f["start"] >= ep["start"] and f["stop"] <= ep["stop"])

    recalled = [m for m in matches if m.get("recalled")]
    largest = None
    if recalled:
        top = max(m["delay"] for m in recalled)
        cands = sorted((m["event_id"] for m in recalled if m["delay"] == top))
        pick = next(m for m in recalled if m["event_id"] == cands[0])
        windows = sorted({w for eid in pick.get("matching_episode_ids", [])
                          for ep in episodes if ep["episode_id"] == eid
                          for w in _episode_alert_windows(ep)})
        largest = {"event_id": pick["event_id"], "delay": pick["delay"],
                   "matching_episode_ids": list(
                       pick.get("matching_episode_ids", [])),
                   "matching_alert_window_ids": windows,
                   "original_start": pick.get("original_start"),
                   "original_stop": pick.get("original_stop"),
                   "clipped_start": pick.get("clipped_start"),
                   "clipped_stop": pick.get("clipped_stop")}
    missed_ids = sorted(m["event_id"] for m in matches if not m.get("recalled"))
    if missed_ids:
        pick = next(m for m in matches if m["event_id"] == missed_ids[0])
        cs, ce = pick.get("clipped_start"), pick.get("clipped_stop")
        normal = sorted(f["window_id"] for f in fwd
                        if f["output_state"] == "normal"
                        and _ep_overlaps(f["start"], f["stop"], cs, ce))
        first_missed = {"event_id": pick["event_id"],
                        "normal_window_ids": normal,
                        "normal_ends": [
                            next(f["stop"] for f in fwd
                                 if f["window_id"] == w) for w in normal],
                        "original_start": pick.get("original_start"),
                        "original_stop": pick.get("original_stop"),
                        "clipped_start": cs,
                        "clipped_stop": ce}
    else:
        first_missed = None
    merged = _merge_intervals([(c["start"], c["stop"]) for c in clipped])
    ep_stats = []
    for ep in episodes:
        overlap = _overlap_len(ep["start"], ep["stop"], merged)
        non_event = (ep["stop"] - ep["start"]) - overlap
        ep_stats.append({"episode_id": ep["episode_id"],
                         "start": ep["start"], "stop": ep["stop"],
                         "overlap_duration": overlap,
                         "non_event_duration": non_event,
                         "false": overlap == 0})
    false_eps = sorted(e["episode_id"] for e in ep_stats if e["false"])
    if false_eps:
        pick = next(e for e in ep_stats if e["episode_id"] == false_eps[0])
        ep = next(e for e in episodes if e["episode_id"] == pick["episode_id"])
        first_false = {"episode_id": pick["episode_id"],
                       "start": pick["start"], "stop": pick["stop"],
                       "alert_window_ids": _episode_alert_windows(ep)}
    else:
        first_false = None
    if ep_stats:
        top_len = max(e["non_event_duration"] for e in ep_stats)
        cands = sorted(e["episode_id"] for e in ep_stats
                       if e["non_event_duration"] == top_len)
        pick = next(e for e in ep_stats if e["episode_id"] == cands[0])
        ep = next(e for e in episodes if e["episode_id"] == pick["episode_id"])
        longest_non_event = {"episode_id": pick["episode_id"],
                             "start": pick["start"], "stop": pick["stop"],
                             "non_event_duration": pick["non_event_duration"],
                             "total_duration": pick["stop"] - pick["start"],
                             "alert_window_ids": _episode_alert_windows(ep)}
    else:
        longest_non_event = None
    held_ids = [e["window_id"] for e in state
                if e.get("after_state") == "alert"
                and float(e.get("score", float("inf"))) <= float(high)]
    return {
        "largest_delay_recalled_event": largest,
        "first_missed_event": first_missed,
        "first_false_episode": first_false,
        "longest_non_event_alert_episode": longest_non_event,
        "held_on_windows": held_ids,
        "held_on_intervals": _held_forward_intervals(held_ids, rows,
                                                     horizon_stop),
        "note": ("episodes are forward from availability ends; ties break "
                 "first by sorted id; zero false episodes does not imply "
                 "zero non-event alert duration"),
    }


def family_table(path):
    """Build a self-contained operational table from a validated family.

    All attempted policy settings are retained with a feasible flag
    (episode rate <= tolerance and coverage >= floor); infeasible rows are
    reported, not rejected, and nothing here is an operating record.
    """
    fam = _read_family_validated(path)
    base = Path(path)
    metadata = fam["metadata"]
    protocol = fam["protocol"]
    rate_tol = protocol["episode_rate_tolerance_per_1000_decisions"]
    floor = protocol["coverage_floor"]
    high = metadata.get("threshold_high")
    low = metadata.get("threshold_low")
    policies = {}
    for name in FAMILY_POLICIES:
        p = fam["policies"][name]
        rows = p["rows"]
        persisted = p["evaluation"]
        metrics = persisted.get("metrics", {})
        diagnostics = persisted.get("diagnostics", {})
        n = int(metrics.get("decision_count", len(rows)))
        n_alert = sum(1 for r in rows if r["output_state"] == "alert")
        rate = metrics.get("alert_episode_rate_per_1000_decisions", {})
        coverage = metrics.get("decision_coverage", {})
        try:
            feasible = (float(rate.get("value")) <= float(rate_tol)
                        and float(coverage.get("value")) >= float(floor))
        except (TypeError, ValueError):
            feasible = False
        annotations = _annotate_policy(
            name, persisted, rows, p["state"], high,
            fam["evaluation_config"]["horizon"][1])
        policies[name] = {
            "policy": name,
            "policy_config": p["policy_config"],
            "config_id": rows[0]["config_id"] if rows else None,
            "run_id": rows[0]["run_id"] if rows else None,
            "source_paths": {
                "family": str(base),
                "predictions_csv": str(base / name / "predictions.csv"),
                "state_json": str(base / name / "state.json"),
                "evaluation_json": str(base / name / "evaluation.json"),
                "source_scores_csv": str(base / "source_scores.csv"),
            },
            "decision_count": n,
            "alerted_window_count": n_alert,
            "alerted_window_fraction": metrics.get("alerted_window_fraction"),
            "decision_coverage": coverage,
            "deferral_rate": metrics.get("deferral_rate"),
            "episode_count": int(diagnostics.get("episode_count",
                                                len(persisted.get("episodes",
                                                                  [])))),
            "alert_episode_rate": metrics.get("alert_episode_rate"),
            "alert_episode_rate_per_1000_decisions": rate,
            "event_recall": metrics.get("event_recall"),
            "episode_precision": metrics.get("episode_precision"),
            "false_alert_episodes": metrics.get("false_alert_episodes"),
            "delay": metrics.get("delay"),
            "total_alert_duration": metrics.get("total_alert_duration"),
            "non_event_alert_duration": metrics.get(
                "non_event_alert_duration"),
            "warmup_duration": metrics.get("warmup_duration"),
            "deferred_duration": metrics.get("deferred_duration"),
            "excluded_event_count": metrics.get("excluded_event_count"),
            "clipped_event_count": metrics.get("clipped_event_count"),
            "diagnostics": diagnostics,
            "episodes": list(persisted.get("episodes", [])),
            "events": persisted.get("events"),
            "matches": list(persisted.get("matches", [])),
            "resource_scope": metadata.get("resource_scope"),
            "policy_replay_seconds": ((metadata.get("policies") or {}).get(
                name) or {}).get("policy_replay_seconds"),
            "episode_rate_tolerance_per_1000_decisions": rate_tol,
            "coverage_floor": floor,
            "feasible": bool(feasible),
            "annotations": annotations,
        }
    return {
        "family_path": str(base),
        "family_id": metadata.get("family_id"),
        "source_scores_id": metadata.get("source_scores_id"),
        "source_config_id": metadata.get("source_config_id"),
        "evaluation_config_id": metadata.get("evaluation_config_id"),
        "evaluation_config": fam["evaluation_config"],
        "threshold_high": high,
        "threshold_low": low,
        "horizon": list(fam["evaluation_config"]["horizon"]),
        "first_decision": fam["evaluation_config"]["first_decision"],
        "duration_unit": FAMILY_DURATION_UNIT,
        "resource_scope": metadata.get("resource_scope"),
        "policies": policies,
    }


def write_family_table(path, output):
    """Serialize a family operational table to a new file only (mode 'x')."""
    table = family_table(path)
    text = json.dumps(table, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return table


def render_family_figure(path, output):
    """Plot a validated family to plain SVG using only saved evidence.

    Shared scores at availability end, high/low lines, forward episodes for
    fixed and hysteresis, half-open events, warmup/horizon axis, held-on
    intervals where a hysteresis alert scored at or below high, and the same
    deterministic annotations as the table. No rolling values are plotted.
    """
    fam = _read_family_validated(path)
    table = family_table(path)
    base = Path(path)
    metadata = fam["metadata"]
    cfg = fam["evaluation_config"]
    h0, h1 = list(cfg["horizon"])
    first = cfg["first_decision"]
    high = float(metadata["threshold_high"])
    low = float(metadata["threshold_low"])
    scores = fam["scores"]
    xs = [s["end_index"] for s in scores]
    ys = [s["score"] for s in scores]

    width = 680
    left, right, top = 60, 20, 88
    plot_w = width - left - right
    score_top = top
    score_h = 180
    lane_step = 44
    y_event = score_top + score_h + 34
    y_fixed = y_event + lane_step
    y_hyst = y_fixed + lane_step
    held_intervals = (table["policies"]["hysteresis"]["annotations"]
                      ["held_on_intervals"])
    if held_intervals:
        y_held = y_hyst + lane_step
        lanes_bottom = y_held + 16
    else:
        y_held = None
        lanes_bottom = y_hyst + 16

    # footer text first so the canvas height fits every wrapped line
    footer_raw = []
    for name in FAMILY_POLICIES:
        ann = table["policies"][name]["annotations"]
        largest = ann["largest_delay_recalled_event"]
        missed = ann["first_missed_event"]
        false_ep = ann["first_false_episode"]
        longest = ann["longest_non_event_alert_episode"]
        footer_raw.append(
            f"{name} largest-delay: "
            f"{largest['event_id'] + ' delay=' + str(largest['delay']) if largest else 'none'}; "
            f"missed: {missed['event_id'] if missed else 'none'}")
        footer_raw.append(
            f"{name} false: "
            f"{false_ep['episode_id'] if false_ep else 'none'}; "
            f"longest non-event: "
            f"{longest['episode_id'] + ' len=' + str(longest['non_event_duration']) if longest else 'none'}")
    if held_intervals:
        first_held = held_intervals[0]
        footer_raw.append(
            f"held-on: {first_held['window_id']} "
            f"[{first_held['start']}, {first_held['stop']}) "
            "hysteresis alert score<=high")
    else:
        footer_raw.append("held-on intervals: none")
    footer_raw.append(f"family_id={metadata.get('family_id', '')}")
    footer_raw.append(f"source={base / 'source_scores.csv'}")
    footer_lines = []
    for raw in footer_raw:
        footer_lines.extend(
            textwrap.wrap(raw, width=FAMILY_FIGURE_WRAP_WIDTH) or [""])
    axis_y = lanes_bottom + 14
    footer_top = lanes_bottom + 30
    line_h = 14
    height = int(footer_top + len(footer_lines) * line_h + 16)

    y_lo = min(min(ys), low)
    y_hi = max(max(ys), high)
    if y_hi == y_lo:
        y_lo -= 1.0
        y_hi += 1.0
    else:
        pad = (y_hi - y_lo) * 0.1 or 1.0
        y_lo -= pad
        y_hi += pad

    def _cx(x):
        if h1 == h0:
            return left + plot_w / 2
        return left + (x - h0) / (h1 - h0) * plot_w

    def _cy(y):
        return score_top + score_h - (y - y_lo) / (y_hi - y_lo) * score_h

    fixed_eps = list(
        fam["policies"]["fixed"]["evaluation"].get("episodes", []))
    hyst_eps = list(
        fam["policies"]["hysteresis"]["evaluation"].get("episodes", []))
    clipped = list((fam["policies"]["fixed"]["evaluation"].get("events")
                    or {}).get("clipped", []))
    held_on = set(table["policies"]["hysteresis"]["annotations"]
                  ["held_on_windows"])

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">'
    )
    title = ("SYNTHETIC ENGINEERING CHECK \u2014 fixed+hysteresis only; "
             "no quality claim")
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{width // 2}" y="24" text-anchor="middle" font-size="14">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{width // 2}" y="42" text-anchor="middle" font-size="11">sample_index units; horizon [{h0}, {h1}); warmup [{h0}, {first})</text>'
    )
    parts.append(
        f'<text x="{width // 2}" y="58" text-anchor="middle" font-size="11">shared scores at availability end; episodes forward; events half-open</text>'
    )
    # warmup shading + horizon outline span the score band and all lanes
    if first > h0:
        parts.append(
            f'<rect x="{_cx(h0):.2f}" y="{top}" width="{_cx(first) - _cx(h0):.2f}" height="{lanes_bottom - top}" fill="#eeeeee"/>'
        )
    parts.append(
        f'<rect x="{_cx(h0):.2f}" y="{top}" width="{_cx(h1) - _cx(h0):.2f}" height="{lanes_bottom - top}" fill="none" stroke="black"/>'
    )
    # axes for score band
    parts.append(
        f'<line x1="{left}" y1="{score_top}" x2="{left}" y2="{score_top + score_h}" stroke="black"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{score_top + score_h}" x2="{left + plot_w}" y2="{score_top + score_h}" stroke="black"/>'
    )
    parts.append(
        f'<text x="12" y="{score_top + score_h // 2}" font-size="11" transform="rotate(-90 12,{score_top + score_h // 2})">score</text>'
    )
    for xt in (h0, first, h1):
        cx = _cx(xt)
        parts.append(
            f'<line x1="{cx:.2f}" y1="{score_top + score_h}" x2="{cx:.2f}" y2="{score_top + score_h + 5}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{score_top + score_h + 18}" text-anchor="middle" font-size="10">{escape(str(xt))}</text>'
        )
    parts.append(
        f'<text x="{left + plot_w // 2}" y="{axis_y:.0f}" text-anchor="middle" font-size="11">sample_index</text>'
    )
    # high/low lines
    for val, dash, tag in ((high, "6,4", "high"), (low, "2,3", "low")):
        cy = _cy(val)
        parts.append(
            f'<line x1="{left}" y1="{cy:.2f}" x2="{left + plot_w}" y2="{cy:.2f}" '
            f'stroke="black" stroke-dasharray="{dash}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{left + plot_w}" y="{cy - 6:.2f}" text-anchor="end" font-size="10">{tag} {escape(repr(float(val)))}</text>'
        )
    # score points; held-on hysteresis alerts get an orange ring
    for s in scores:
        cx = _cx(s["end_index"])
        cy = _cy(s["score"])
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="blue">'
            f"<title>{escape(s['window_id'] + ' end=' + str(s['end_index']) + ' score=' + repr(float(s['score'])))}</title>"
            "</circle>"
        )
        if s["window_id"] in held_on:
            parts.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="7" fill="none" stroke="orange" stroke-width="2">'
                f"<title>{escape('held-on ' + s['window_id'] + ' hysteresis alert score<=high')}</title>"
                "</circle>"
            )
    # lanes
    parts.append(f'<text x="{left}" y="{y_event - 8:.2f}" font-size="11">events (half-open)</text>')
    for e in clipped:
        x1, x2 = _cx(e["start"]), _cx(e["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_event:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="blue">'
            f"<title>{escape(str(e.get('event_id', '')) + ' [' + str(e['start']) + ', ' + str(e['stop']) + ')')}</title>"
            "</rect>"
        )
    parts.append(f'<text x="{left}" y="{y_fixed - 8:.2f}" font-size="11">fixed episodes (forward)</text>')
    for ep in fixed_eps:
        x1, x2 = _cx(ep["start"]), _cx(ep["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_fixed:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="red">'
            f"<title>{escape(str(ep.get('episode_id', '')) + ' [' + str(ep['start']) + ', ' + str(ep['stop']) + ')')}</title>"
            "</rect>"
        )
    parts.append(f'<text x="{left}" y="{y_hyst - 8:.2f}" font-size="11">hysteresis episodes (forward)</text>')
    for ep in hyst_eps:
        x1, x2 = _cx(ep["start"]), _cx(ep["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_hyst:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="red">'
            f"<title>{escape(str(ep.get('episode_id', '')) + ' [' + str(ep['start']) + ', ' + str(ep['stop']) + ')')}</title>"
            "</rect>"
        )
    if y_held is not None:
        parts.append(f'<text x="{left}" y="{y_held - 8:.2f}" font-size="11">held-on forward intervals (alert score&lt;=high)</text>')
        for iv in held_intervals:
            x1, x2 = _cx(iv["start"]), _cx(iv["stop"])
            parts.append(
                f'<rect x="{x1:.2f}" y="{y_held:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="orange">'
                f"<title>{escape('held-on ' + iv['window_id'] + ' [' + str(iv['start']) + ', ' + str(iv['stop']) + ')')}</title>"
                "</rect>"
            )
    # deterministic annotations matching the table, wrapped to the canvas
    ay = footer_top
    for line in footer_lines:
        parts.append(
            f'<text x="{left}" y="{ay:.2f}" font-size="10">{escape(line)}</text>'
        )
        ay += line_h
    parts.append("</svg>")
    text = "\n".join(parts) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return str(output)


DIAGNOSTIC_ABSENT = "None observed in this evaluated scope"
DIAGNOSTIC_DURATION_UNIT = "sample_index"


def _read_diagnostic_validated(diagnostic_dir):
    """Load and verify a diagnostic dir first; raise on any tamper."""
    from reliable_alerting import diagnostics as _diagnostics
    report = _diagnostics.load_diagnostic(diagnostic_dir)
    if not report.get("status"):
        raise ValueError(
            f"diagnostic failed validation: {report.get('differences')}")
    return report


def _load_diagnostic_linkage(diagnostic_dir, family_dir):
    """Verify exact score/calibration/config linkage via parsed rows.

    Why: raw rows and resolved configs are compared directly; hash
    strings of different constructions are never compared.
    """
    from reliable_alerting import diagnostics as _diagnostics
    diag_report = _read_diagnostic_validated(diagnostic_dir)
    fam = _read_family_validated(family_dir)
    base_d = Path(diagnostic_dir)
    base_f = Path(family_dir)
    diag_scores = _diagnostics._parse_scores_csv(str(base_d / "source_scores.csv"))
    fam_scores = _read_family_scores(base_f)
    scores_equal = (diag_scores == fam_scores)
    try:
        diag_cals = _diagnostics._parse_scores_csv(
            str(base_d / "source_calibration_scores.csv"))
    except Exception:
        diag_cals = None
    try:
        fam_cals = _load_calibration_csv(
            str(base_f / "source_calibration_scores.csv"))
        fam_cals_norm = [{"window_id": r["window_id"],
                          "start_index": r["start_index"],
                          "end_index": r["end_index"],
                          "score": float(r["score"])} for r in fam_cals]
    except Exception:
        fam_cals_norm = None
    calibration_equal = (diag_cals is not None and fam_cals_norm is not None
                         and diag_cals == fam_cals_norm)
    try:
        diag_src_cfg = _load_json(base_d / "source_config.json")
    except Exception:
        diag_src_cfg = None
    try:
        fam_src_cfg = _load_json(base_f / "source_config.json")
    except Exception:
        fam_src_cfg = None
    source_config_equal = (diag_src_cfg is not None and fam_src_cfg is not None
                           and diag_src_cfg == fam_src_cfg)
    if not scores_equal:
        raise ValueError("diagnostic source_scores != family source_scores")
    if not calibration_equal:
        raise ValueError("diagnostic calibration != family calibration")
    if not source_config_equal:
        raise ValueError("diagnostic source_config != family source_config")
    # window alignment across diagnostic rows, family scores, policies
    doc_rows = diag_report["document"]["rows"]
    if [r["window_id"] for r in doc_rows] != [r["window_id"] for r in fam_scores]:
        raise ValueError("diagnostic windows != family score windows")
    for name in FAMILY_POLICIES:
        prows = fam["policies"][name]["rows"]
        if [r["window_id"] for r in prows] != [r["window_id"] for r in fam_scores]:
            raise ValueError(f"policy {name} windows != family scores")
    return {
        "report": diag_report,
        "family": fam,
        "scores_equal": bool(scores_equal),
        "calibration_equal": bool(calibration_equal),
        "source_config_equal": bool(source_config_equal),
    }


def _diagnostic_per_row(diag_rows, policy_rows, policy_state, high):
    """Join diagnostic features with actual policy states per window.

    Why: recent_exceedance_rate uses the frozen family HIGH for the
    current-inclusive trailing trio (same HIGH both policies);
    margin vs current judging is retained separately from
    margin_high vs frozen HIGH.
    """
    state_by_id = {e["window_id"]: e for e in policy_state}
    scores = [float(r["score"]) for r in policy_rows]
    out = []
    for i, prow in enumerate(policy_rows):
        wid = prow["window_id"]
        st = state_by_id[wid]
        judging = float(st["judging_threshold"])
        score = float(prow["score"])
        margin = float(score - judging)
        margin_high = float(score - float(high))
        lo = max(0, i - 2)
        window = scores[lo: i + 1]
        exceed = sum(1 for s in window if s > float(high))
        rate = float(exceed / len(window)) if window else 0.0
        drow = diag_rows[i]
        out.append({
            "window_id": wid,
            "start_index": int(prow["start_index"]),
            "end_index": int(prow["end_index"]),
            "availability_end": int(st["availability_end"]),
            "score": float(score),
            "judging_threshold": float(judging),
            "margin": float(margin),
            "threshold_high": float(high),
            "margin_high": float(margin_high),
            "recent_exceedance_rate": float(rate),
            "output_state": str(prow["output_state"]),
            "before_state": str(st["before_state"]),
            "after_state": str(st["after_state"]),
            "comparator": str(st["comparator"]),
            "feature": (None if drow.get("feature") is None
                        else float(drow["feature"])),
            "trailing_median": (None if drow.get("trailing_median") is None
                                else float(drow["trailing_median"])),
            "reference_median": float(drow.get("reference_median")),
            "warmup": bool(drow.get("warmup")),
        })
    return out


def _diagnostic_misleading(per_row, high):
    """First ready window where feature sign gaps frozen-HIGH exceedance.

    Descriptive example only; not a claim beyond the saved scope.
    Positive feature with current score<=HIGH (no strict_greater
    exceedance), or non-positive feature with current score>HIGH,
    is shown as-is.
    """
    for r in per_row:
        if r.get("warmup") or r.get("feature") is None:
            continue
        feat = float(r["feature"])
        exceeds = float(r["score"]) > float(high)
        if (feat > 0 and not exceeds) or (feat <= 0 and exceeds):
            return {
                "window_id": r["window_id"],
                "end_index": r["end_index"],
                "score": r["score"],
                "judging_threshold": r["judging_threshold"],
                "margin": r["margin"],
                "threshold_high": float(high),
                "margin_high": r["margin_high"],
                "exceeds_high": bool(exceeds),
                "output_state": r["output_state"],
                "feature": feat,
                "note": "descriptive only; shown as saved",
            }
    return None


def diagnostic_table(diagnostic_dir, family_dir):
    """Build a descriptive join of saved diagnostic + family artifacts.

    Features are loaded and verified before the family labels are
    consulted. Exact score/calibration/config linkage is checked on
    parsed rows (no cross-format hash comparison). Per-row entries
    carry raw score, margin vs actual judging plus margin_high vs
    frozen HIGH, recent exceedance rate over the current-inclusive
    trailing 3 vs frozen HIGH, comparator with before/after state,
    and feature.
    """
    linked = _load_diagnostic_linkage(diagnostic_dir, family_dir)
    diag_report = linked["report"]
    fam = linked["family"]
    doc = diag_report["document"]
    diag_rows = doc["rows"]
    metadata = fam["metadata"]
    high_frozen = float(metadata["threshold_high"])
    table = family_table(str(Path(family_dir)))
    warm_ids = [r["window_id"] for r in diag_rows if r.get("warmup")]
    ready_ids = [r["window_id"] for r in diag_rows if not r.get("warmup")]
    policies = {}
    for name in FAMILY_POLICIES:
        p = fam["policies"][name]
        per_row = _diagnostic_per_row(diag_rows, p["rows"], p["state"],
                                      high_frozen)
        ann = table["policies"][name]["annotations"]
        # largest delay with tied ids preserved
        largest = ann.get("largest_delay_recalled_event")
        if isinstance(largest, dict):
            persisted = p["evaluation"]
            recalled = [m for m in persisted.get("matches", []) if m.get("recalled")]
            if recalled:
                top = max(m["delay"] for m in recalled)
                cands = sorted(m["event_id"] for m in recalled if m["delay"] == top)
                largest = dict(largest)
                largest["tied_event_ids"] = list(cands)
        # longest non-event with tied ids preserved
        longest = ann.get("longest_non_event_alert_episode")
        if isinstance(longest, dict):
            persisted = p["evaluation"]
            merged = _merge_intervals(
                [(c["start"], c["stop"]) for c in
                 (persisted.get("events") or {}).get("clipped", [])])
            stats = []
            for ep in persisted.get("episodes", []):
                ov = _overlap_len(ep["start"], ep["stop"], merged)
                stats.append((ep["episode_id"], (ep["stop"] - ep["start"]) - ov))
            if stats:
                top_len = max(v for _, v in stats)
                cands = sorted(eid for eid, v in stats if v == top_len)
                longest = dict(longest)
                longest["tied_episode_ids"] = list(cands)
        first_false = ann.get("first_false_episode")
        first_miss = ann.get("first_missed_event")
        mislead = _diagnostic_misleading(per_row, high_frozen)
        cases = {
            "first_false_episode": (first_false if first_false is not None
                                    else DIAGNOSTIC_ABSENT),
            "largest_delay_recalled_event": (largest if largest is not None
                                             else DIAGNOSTIC_ABSENT),
            "first_missed_event": (first_miss if first_miss is not None
                                   else DIAGNOSTIC_ABSENT),
            "longest_non_event_alert_episode": (longest if longest is not None
                                                else DIAGNOSTIC_ABSENT),
            "misleading_feature_example": (mislead if mislead is not None
                                           else DIAGNOSTIC_ABSENT),
        }
        policies[name] = {
            "policy": name,
            "policy_config": p["policy_config"],
            "config_id": p["rows"][0]["config_id"] if p["rows"] else None,
            "run_id": p["rows"][0]["run_id"] if p["rows"] else None,
            "source_paths": {
                "diagnostic": str(Path(diagnostic_dir) / "diagnostic.json"),
                "family": str(Path(family_dir)),
                "predictions_csv": str(Path(family_dir) / name / "predictions.csv"),
                "state_json": str(Path(family_dir) / name / "state.json"),
                "evaluation_json": str(Path(family_dir) / name / "evaluation.json"),
            },
            "decision_count": len(per_row),
            "per_row": per_row,
            "cases": cases,
            "annotations": ann,
        }
    return {
        "diagnostic_path": str(Path(diagnostic_dir)),
        "family_path": str(Path(family_dir)),
        "diagnostic_id": doc.get("diagnostic_id"),
        "diagnostic_config_id": doc.get("diagnostic_config_id"),
        "score_identity": doc.get("score_identity"),
        "reference_identity": doc.get("reference_identity"),
        "reference_median": float(doc.get("reference", {}).get("median")),
        "family_id": metadata.get("family_id"),
        "source_scores_id": metadata.get("source_scores_id"),
        "evaluation_config_id": metadata.get("evaluation_config_id"),
        "evaluation_config": fam["evaluation_config"],
        "threshold_high": metadata.get("threshold_high"),
        "threshold_low": metadata.get("threshold_low"),
        "horizon": list(fam["evaluation_config"]["horizon"]),
        "first_decision": fam["evaluation_config"]["first_decision"],
        "duration_unit": DIAGNOSTIC_DURATION_UNIT,
        "time_basis": "sample_index",
        "scope_note": ("SYNTHETIC ONLY engineering check; descriptive comparison "
                       "of saved scores, states, and features in sample_index units"),
        "linkage": {
            "scores_equal": bool(linked["scores_equal"]),
            "calibration_equal": bool(linked["calibration_equal"]),
            "source_config_equal": bool(linked["source_config_equal"]),
        },
        "warmup": {
            "warmup_count": len(warm_ids),
            "decision_count": len(diag_rows),
            "ready_count": len(ready_ids),
            "warmup_window_ids": list(warm_ids),
            "ready_window_ids": list(ready_ids),
        },
        "policies": policies,
    }


def write_diagnostic_table(diagnostic_dir, family_dir, output):
    """Serialize a diagnostic table to a new file only (mode 'x')."""
    table = diagnostic_table(diagnostic_dir, family_dir)
    text = json.dumps(table, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return table


def render_diagnostic_plot(diagnostic_dir, family_dir, output):
    """Plot saved diagnostic + family to plain SVG using saved evidence.

    Shared scores at availability end, high/low plus actual per-window
    sidecar judging markers, forward episodes for fixed and hysteresis,
    half-open events, a ready/warmup diagnostic lane, and a separate
    median-gap magnitude panel (feature markers at availability end
    with a zero line; warmup rows have no markers). No rolling
    values are plotted.
    """
    linked = _load_diagnostic_linkage(diagnostic_dir, family_dir)
    diag_report = linked["report"]
    fam = linked["family"]
    table = diagnostic_table(diagnostic_dir, family_dir)
    doc = diag_report["document"]
    base_d = Path(diagnostic_dir)
    base_f = Path(family_dir)
    metadata = fam["metadata"]
    cfg = fam["evaluation_config"]
    h0, h1 = list(cfg["horizon"])
    first = cfg["first_decision"]
    high = float(metadata["threshold_high"])
    low = float(metadata["threshold_low"])
    scores = fam["scores"]
    ys = [s["score"] for s in scores]
    feat_rows = [r for r in doc["rows"] if not r.get("warmup")]
    feat_vals = [float(r["feature"]) for r in feat_rows]

    width = 880
    left, right, top = 60, 20, 88
    plot_w = width - left - right
    score_top = top
    score_h = 170
    lane_step = 40
    y_event = score_top + score_h + 34
    y_fixed = y_event + lane_step
    y_hyst = y_fixed + lane_step
    y_diag = y_hyst + lane_step
    feat_top = y_diag + 40
    feat_h = 120
    lanes_bottom = feat_top + feat_h

    footer_raw = []
    for name in FAMILY_POLICIES:
        cases = table["policies"][name]["cases"]
        largest = cases.get("largest_delay_recalled_event")
        missed = cases.get("first_missed_event")
        false_ep = cases.get("first_false_episode")
        longest = cases.get("longest_non_event_alert_episode")
        mislead = cases.get("misleading_feature_example")
        footer_raw.append(
            f"{name} largest-delay: "
            f"{largest['event_id'] + ' delay=' + str(largest['delay']) if isinstance(largest, dict) else 'none'}; "
            f"missed: {missed['event_id'] if isinstance(missed, dict) else 'none'}")
        footer_raw.append(
            f"{name} false: "
            f"{false_ep['episode_id'] if isinstance(false_ep, dict) else 'none'}; "
            f"longest non-event: "
            f"{longest['episode_id'] + ' len=' + str(longest['non_event_duration']) if isinstance(longest, dict) else 'none'}")
        footer_raw.append(
            f"{name} misleading-feature: "
            f"{mislead['window_id'] + ' feat=' + repr(float(mislead['feature'])) if isinstance(mislead, dict) else 'none'}")
    footer_raw.append("diagnostic_id")
    footer_raw.append(f"diagnostic_id={doc.get('diagnostic_id', '')}")
    footer_raw.append("diagnostic_config_id")
    footer_raw.append(f"diagnostic_config_id={doc.get('diagnostic_config_id', '')}")
    footer_raw.append("family_id")
    footer_raw.append(f"family_id={metadata.get('family_id', '')}")
    footer_raw.append(f"source={base_f / 'source_scores.csv'}")
    footer_raw.append(f"diagnostic={base_d / 'diagnostic.json'}")
    footer_lines = []
    for raw in footer_raw:
        if raw in ("diagnostic_id", "diagnostic_config_id", "family_id"):
            footer_lines.append(raw)
        elif raw.startswith(("diagnostic_config_id=", "family_id=",
                             "diagnostic_id=")):
            # hex IDs stay contiguous on one label-then-id line pair
            footer_lines.append(raw)
        else:
            footer_lines.extend(
                textwrap.wrap(raw, width=FAMILY_FIGURE_WRAP_WIDTH) or [""])
    axis_y = lanes_bottom + 14
    footer_top = lanes_bottom + 30
    line_h = 14
    height = int(footer_top + len(footer_lines) * line_h + 16)

    y_lo = min(min(ys), low)
    y_hi = max(max(ys), high)
    if y_hi == y_lo:
        y_lo -= 1.0
        y_hi += 1.0
    else:
        pad = (y_hi - y_lo) * 0.1 or 1.0
        y_lo -= pad
        y_hi += pad

    def _cx(x):
        if h1 == h0:
            return left + plot_w / 2
        return left + (x - h0) / (h1 - h0) * plot_w

    def _cy(y):
        return score_top + score_h - (y - y_lo) / (y_hi - y_lo) * score_h

    f_lo = min([0.0] + feat_vals)
    f_hi = max([0.0] + feat_vals)
    if f_hi == f_lo:
        f_lo -= 1.0
        f_hi += 1.0
    else:
        f_pad = (f_hi - f_lo) * 0.15 or 1.0
        f_lo -= f_pad
        f_hi += f_pad

    def _fy(f):
        return feat_top + feat_h - (f - f_lo) / (f_hi - f_lo) * feat_h

    fixed_eps = list(fam["policies"]["fixed"]["evaluation"].get("episodes", []))
    hyst_eps = list(fam["policies"]["hysteresis"]["evaluation"].get("episodes", []))
    clipped = list((fam["policies"]["fixed"]["evaluation"].get("events")
                    or {}).get("clipped", []))

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">'
    )
    title = ("SYNTHETIC ONLY diagnostic check \u2014 no quality claim; "
             "scores, episodes, and median-gap features")
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{width // 2}" y="24" text-anchor="middle" font-size="14">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{width // 2}" y="42" text-anchor="middle" font-size="11">sample_index units; horizon [{h0}, {h1}); warmup [{h0}, {first})</text>'
    )
    parts.append(
        f'<text x="{width // 2}" y="58" text-anchor="middle" font-size="11">shared scores at availability end; episodes forward; events half-open; median-gap ready vs warmup</text>'
    )
    if first > h0:
        parts.append(
            f'<rect x="{_cx(h0):.2f}" y="{top}" width="{_cx(first) - _cx(h0):.2f}" height="{lanes_bottom - top}" fill="#eeeeee"/>'
        )
    parts.append(
        f'<rect x="{_cx(h0):.2f}" y="{top}" width="{_cx(h1) - _cx(h0):.2f}" height="{lanes_bottom - top}" fill="none" stroke="black"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{score_top}" x2="{left}" y2="{score_top + score_h}" stroke="black"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{score_top + score_h}" x2="{left + plot_w}" y2="{score_top + score_h}" stroke="black"/>'
    )
    parts.append(
        f'<text x="12" y="{score_top + score_h // 2}" font-size="11" transform="rotate(-90 12,{score_top + score_h // 2})">score</text>'
    )
    for xt in [s["end_index"] for s in scores]:
        cx = _cx(xt)
        parts.append(
            f'<line x1="{cx:.2f}" y1="{score_top + score_h}" x2="{cx:.2f}" y2="{score_top + score_h + 5}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{score_top + score_h + 18}" text-anchor="middle" font-size="9">{escape(str(xt))}</text>'
        )
    parts.append(
        f'<text x="{left + plot_w // 2}" y="{axis_y:.0f}" text-anchor="middle" font-size="11">sample_index</text>'
    )
    for val, dash in ((high, "6,4"), (low, "2,3")):
        cy = _cy(val)
        parts.append(
            f'<line x1="{left}" y1="{cy:.2f}" x2="{left + plot_w}" y2="{cy:.2f}" '
            f'stroke="black" stroke-dasharray="{dash}" stroke-width="1.5"/>'
        )
    # threshold legend on fixed rows with connectors to the dashed lines
    leg_x, leg_w = left + plot_w - 250, 44
    leg_high_y, leg_low_y = score_top + 16, score_top + 32
    for val, dash, tag, ly in ((high, "6,4", "high", leg_high_y),
                               (low, "2,3", "low", leg_low_y)):
        cy = _cy(val)
        parts.append(
            f'<line x1="{leg_x:.2f}" y1="{ly:.2f}" x2="{leg_x + leg_w:.2f}" y2="{ly:.2f}" '
            f'stroke="black" stroke-dasharray="{dash}" stroke-width="1.5">'
            f"<title>{escape(tag + ' threshold legend')}</title>"
            "</line>"
        )
        parts.append(
            f'<text x="{leg_x + leg_w + 6:.2f}" y="{ly + 4:.2f}" font-size="10">{escape(tag + " " + repr(float(val)))}</text>'
        )
        parts.append(
            f'<line x1="{leg_x + leg_w:.2f}" y1="{ly:.2f}" x2="{left + plot_w:.2f}" y2="{cy:.2f}" '
            f'stroke="grey" stroke-dasharray="2,2" stroke-width="1">'
            f"<title>{escape(tag + ' threshold connector to dashed line')}</title>"
            "</line>"
        )
    for s in scores:
        cx = _cx(s["end_index"])
        cy = _cy(s["score"])
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="blue">'
            f"<title>{escape(s['window_id'] + ' end=' + str(s['end_index']) + ' score=' + repr(float(s['score'])))}</title>"
            "</circle>"
        )
    # actual per-window sidecar judging markers at window end
    for name, sym in (("fixed", "square"), ("hysteresis", "diamond")):
        for e in fam["policies"][name]["state"]:
            cx = _cx(e["end_index"])
            cy = _cy(float(e["judging_threshold"]))
            if sym == "square":
                parts.append(
                    f'<rect x="{cx - 3:.2f}" y="{cy - 3:.2f}" width="6" height="6" fill="none" stroke="black">'
                    f"<title>{escape(name + ' judging ' + e['window_id'] + ' end=' + str(e['end_index']) + ' judging=' + repr(float(e['judging_threshold'])) + ' ' + e['comparator'])}</title>"
                    "</rect>"
                )
            else:
                x0, y0 = cx, cy
                pts = f"{x0:.2f},{y0 - 5:.2f} {x0 + 5:.2f},{y0:.2f} {x0:.2f},{y0 + 5:.2f} {x0 - 5:.2f},{y0:.2f}"
                parts.append(
                    f'<polygon points="{pts}" fill="none" stroke="purple" stroke-width="1.5">'
                    f"<title>{escape(name + ' judging ' + e['window_id'] + ' end=' + str(e['end_index']) + ' judging=' + repr(float(e['judging_threshold'])) + ' ' + e['comparator'])}</title>"
                    "</polygon>"
                )
    parts.append(f'<text x="{left}" y="{y_event - 8:.2f}" font-size="11">events (half-open)</text>')
    for e in clipped:
        x1, x2 = _cx(e["start"]), _cx(e["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_event:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="blue">'
            f"<title>{escape(str(e.get('event_id', '')) + ' [' + str(e['start']) + ', ' + str(e['stop']) + ')')}</title>"
            "</rect>"
        )
    parts.append(f'<text x="{left}" y="{y_fixed - 8:.2f}" font-size="11">fixed episodes (forward)</text>')
    for ep in fixed_eps:
        x1, x2 = _cx(ep["start"]), _cx(ep["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_fixed:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="red">'
            f"<title>{escape(str(ep.get('episode_id', '')) + ' [' + str(ep['start']) + ', ' + str(ep['stop']) + ')')}</title>"
            "</rect>"
        )
    parts.append(f'<text x="{left}" y="{y_hyst - 8:.2f}" font-size="11">hysteresis episodes (forward)</text>')
    for ep in hyst_eps:
        x1, x2 = _cx(ep["start"]), _cx(ep["stop"])
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_hyst:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="red">'
            f"<title>{escape(str(ep.get('episode_id', '')) + ' [' + str(ep['start']) + ', ' + str(ep['stop']) + ')')}</title>"
            "</rect>"
        )
    parts.append(f'<text x="{left}" y="{y_diag - 8:.2f}" font-size="11">median-gap ready (green) vs warmup (grey)</text>')
    for i, drow in enumerate(doc["rows"]):
        start = drow["end_index"]
        if i + 1 < len(doc["rows"]):
            stop = doc["rows"][i + 1]["end_index"]
        else:
            stop = h1
        x1, x2 = _cx(start), _cx(stop)
        fill = "#bbbbbb" if drow.get("warmup") else "green"
        feat_txt = "warmup" if drow.get("warmup") else f"feat={repr(float(drow['feature']))}"
        parts.append(
            f'<rect x="{x1:.2f}" y="{y_diag:.2f}" width="{max(1.0, x2 - x1):.2f}" height="16" fill="{fill}">'
            f"<title>{escape(drow['window_id'] + ' [' + str(start) + ', ' + str(stop) + ') ' + feat_txt)}</title>"
            "</rect>"
        )
    # separate median-gap magnitude panel: actual features at availability_end
    parts.append(f'<text x="{left}" y="{feat_top - 8:.2f}" font-size="11">median-gap feature (score units)</text>')
    parts.append(
        f'<text x="{width // 2}" y="{feat_top + 12:.2f}" text-anchor="middle" font-size="10">median(last 3 scores, current-inclusive) - calibration median; score units</text>'
    )
    if first > h0:
        parts.append(
            f'<rect x="{_cx(h0):.2f}" y="{feat_top}" width="{_cx(first) - _cx(h0):.2f}" height="{feat_h}" fill="#eeeeee"/>'
        )
    parts.append(
        f'<rect x="{_cx(h0):.2f}" y="{feat_top}" width="{_cx(h1) - _cx(h0):.2f}" height="{feat_h}" fill="none" stroke="black"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{feat_top}" x2="{left}" y2="{feat_top + feat_h}" stroke="black"/>'
    )
    parts.append(
        f'<text x="12" y="{feat_top + feat_h // 2}" font-size="11" transform="rotate(-90 12,{feat_top + feat_h // 2})">feature</text>'
    )
    zero_y = _fy(0.0)
    parts.append(
        f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_w}" y2="{zero_y:.2f}" '
        f'stroke="grey" stroke-dasharray="4,3" stroke-width="1.5">'
        f"<title>feature=0 zero reference line</title>"
        "</line>"
    )
    parts.append(
        f'<text x="{left - 8}" y="{zero_y + 3:.2f}" text-anchor="end" font-size="9">0</text>'
    )
    for fval in (f_lo, f_hi):
        fy = _fy(fval)
        parts.append(
            f'<line x1="{left - 5}" y1="{fy:.2f}" x2="{left}" y2="{fy:.2f}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{fy + 3:.2f}" text-anchor="end" font-size="9">{escape(f"{fval:.3g}")}</text>'
        )
    for drow in doc["rows"]:
        if drow.get("warmup") or drow.get("feature") is None:
            continue
        cx = _cx(drow["end_index"])
        cy = _fy(float(drow["feature"]))
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="green">'
            f"<title>{escape(drow['window_id'] + ' end=' + str(drow['end_index']) + ' feat=' + repr(float(drow['feature'])))}</title>"
            "</circle>"
        )
    ay = footer_top
    for line in footer_lines:
        parts.append(
            f'<text x="{left}" y="{ay:.2f}" font-size="10">{escape(line)}</text>'
        )
        ay += line_h
    parts.append("</svg>")
    text = "\n".join(parts) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return str(output)


render_diagnostic_figure = render_diagnostic_plot


def compare_diagnostics(diag_a, diag_b):
    """Compare two diagnostic dirs on scientific equality.

    Scientific equality covers the verified document, config, source
    scores, calibration, and source config. Timestamps, paths, timing,
    and provenance docs are reported separately and never decide the
    scientific flag. Never claims byte identity.
    """
    from reliable_alerting import diagnostics as _diagnostics
    try:
        ra = _diagnostics.load_diagnostic(diag_a)
    except Exception as e:
        ra = {"status": False, "differences": [f"load failed: {e}"]}
    try:
        rb = _diagnostics.load_diagnostic(diag_b)
    except Exception as e:
        rb = {"status": False, "differences": [f"load failed: {e}"]}
    diffs = []
    prov_diffs = []
    va = bool(ra.get("status"))
    vb = bool(rb.get("status"))
    if not va:
        diffs.append(f"diagnostic a invalid: {ra.get('differences')}")
    if not vb:
        diffs.append(f"diagnostic b invalid: {rb.get('differences')}")
    flags = {}
    scientific_equal = bool(va and vb)
    if va and vb:
        if ra.get("document") != rb.get("document"):
            diffs.append("diagnostic document differs")
            flags["document_equal"] = False
        else:
            flags["document_equal"] = True
        if ra.get("config") != rb.get("config"):
            diffs.append("diagnostic config differs")
            flags["config_equal"] = False
        else:
            flags["config_equal"] = True
        try:
            sa = _diagnostics._parse_scores_csv(str(Path(diag_a) / "source_scores.csv"))
            sb = _diagnostics._parse_scores_csv(str(Path(diag_b) / "source_scores.csv"))
            flags["scores_equal"] = bool(sa == sb)
            if not flags["scores_equal"]:
                diffs.append("source scores differ")
        except Exception as e:
            flags["scores_equal"] = False
            diffs.append(f"source scores unreadable: {e}")
        try:
            ca = _diagnostics._parse_scores_csv(
                str(Path(diag_a) / "source_calibration_scores.csv"))
            cb = _diagnostics._parse_scores_csv(
                str(Path(diag_b) / "source_calibration_scores.csv"))
            flags["calibration_equal"] = bool(ca == cb)
            if not flags["calibration_equal"]:
                diffs.append("source calibration differs")
        except Exception as e:
            flags["calibration_equal"] = False
            diffs.append(f"source calibration unreadable: {e}")
        try:
            sa_cfg = _load_json(Path(diag_a) / "source_config.json")
            sb_cfg = _load_json(Path(diag_b) / "source_config.json")
            flags["source_config_equal"] = bool(sa_cfg == sb_cfg)
            if not flags["source_config_equal"]:
                diffs.append("source config differs")
        except Exception as e:
            flags["source_config_equal"] = False
            diffs.append(f"source config unreadable: {e}")
        if not all(flags.get(k, False) for k in (
                "document_equal", "config_equal", "scores_equal",
                "calibration_equal", "source_config_equal")):
            scientific_equal = False
    else:
        scientific_equal = False
    prov = {}
    try:
        ma = _load_json(Path(diag_a) / "metadata.json")
        mb = _load_json(Path(diag_b) / "metadata.json")
    except Exception as e:
        ma = mb = None
        prov_diffs.append(f"diagnostic metadata unreadable: {e}")
    if ma is not None and mb is not None:
        prov["file_hashes_equal"] = bool(ma.get("file_hashes") == mb.get("file_hashes"))
        if not prov["file_hashes_equal"]:
            prov_diffs.append("provenance file_hashes differ")
        prov["environment_equal"] = bool(ma.get("environment") == mb.get("environment"))
        if not prov["environment_equal"]:
            prov_diffs.append("provenance environment differ")
        ga = (ma.get("git") or {}).get("head") if isinstance(ma.get("git"), dict) else None
        gb = (mb.get("git") or {}).get("head") if isinstance(mb.get("git"), dict) else None
        prov["git_head_equal"] = bool(ga == gb)
        prov["git_heads"] = {"a": ga, "b": gb}
        if not prov["git_head_equal"]:
            prov_diffs.append("provenance git head differ")
        try:
            current = provenance.file_hashes(provenance.repo_root())
            prov["source_hashes_match_current"] = bool(
                ma.get("file_hashes") == current
                and mb.get("file_hashes") == current)
        except Exception as e:
            prov["source_hashes_match_current"] = False
            prov_diffs.append(f"source hashes unreadable: {e}")
        if not prov.get("source_hashes_match_current", False):
            prov_diffs.append("source_hashes_match_current is false")
    else:
        prov = {"file_hashes_equal": False, "environment_equal": False,
                "git_head_equal": False, "source_hashes_match_current": False}
    status = bool(va and vb and scientific_equal)
    report = {
        "diag_a": str(diag_a),
        "diag_b": str(diag_b),
        "status": status,
        "scientific_equal": bool(scientific_equal),
        "diagnostics_valid": {"a": bool(va), "b": bool(vb)},
        "document_equal": bool(flags.get("document_equal", False)),
        "config_equal": bool(flags.get("config_equal", False)),
        "scores_equal": bool(flags.get("scores_equal", False)),
        "calibration_equal": bool(flags.get("calibration_equal", False)),
        "source_config_equal": bool(flags.get("source_config_equal", False)),
        "diagnostic_ids": {
            "a": ((ra.get("document") or {}).get("diagnostic_config_id")
                  if isinstance(ra.get("document"), dict) else None),
            "b": ((rb.get("document") or {}).get("diagnostic_config_id")
                  if isinstance(rb.get("document"), dict) else None),
        },
        "differences": diffs,
        "provenance_differences": prov_diffs,
        "provenance": prov,
        "varying_metadata": {
            "started_at": {
                "a": (ma.get("started_at") if isinstance(ma, dict) else None),
                "b": (mb.get("started_at") if isinstance(mb, dict) else None),
            },
            "finished_at": {
                "a": (ma.get("finished_at") if isinstance(ma, dict) else None),
                "b": (mb.get("finished_at") if isinstance(mb, dict) else None),
            },
            "elapsed_monotonic_seconds": {
                "a": (ma.get("elapsed_monotonic_seconds")
                      if isinstance(ma, dict) else None),
                "b": (mb.get("elapsed_monotonic_seconds")
                      if isinstance(mb, dict) else None),
            },
            "source_run_path": {
                "a": ((ma.get("source_run") or {}).get("path")
                      if isinstance(ma, dict)
                      and isinstance(ma.get("source_run"), dict) else None),
                "b": ((mb.get("source_run") or {}).get("path")
                      if isinstance(mb, dict)
                      and isinstance(mb.get("source_run"), dict) else None),
            },
            "command": {
                "a": (ma.get("command") if isinstance(ma, dict) else None),
                "b": (mb.get("command") if isinstance(mb, dict) else None),
            },
        },
    }
    return report


def write_diagnostic_comparison(diag_a, diag_b, output):
    """Serialize a diagnostic comparison to a new file only (mode 'x')."""
    report = compare_diagnostics(diag_a, diag_b)
    text = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(output, "x") as fh:
        fh.write(text)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reliable_alerting.evidence")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="compare two run directories")
    c.add_argument("run_a")
    c.add_argument("run_b")
    c.add_argument("--output", required=True)
    f = sub.add_parser("figure", help="plot saved predictions.csv to SVG")
    f.add_argument("predictions_csv")
    f.add_argument("--output", required=True)
    ce = sub.add_parser("compare-evaluations", help="compare two evaluation directories")
    ce.add_argument("eval_a")
    ce.add_argument("eval_b")
    ce.add_argument("--output", required=True)
    ef = sub.add_parser("evaluation-figure", help="plot saved evaluation to SVG")
    ef.add_argument("eval_dir")
    ef.add_argument("--output", required=True)
    cf = sub.add_parser("compare-families", help="compare two family directories")
    cf.add_argument("family_a")
    cf.add_argument("family_b")
    cf.add_argument("--output", required=True)
    ft = sub.add_parser("family-table", help="write a family operational table")
    ft.add_argument("family")
    ft.add_argument("--output", required=True)
    ff = sub.add_parser("family-figure", help="plot a validated family to SVG")
    ff.add_argument("family")
    ff.add_argument("--output", required=True)
    dt = sub.add_parser("diagnostic-table", help="write a diagnostic+family table")
    dt.add_argument("--diagnostic", required=True)
    dt.add_argument("--family", required=True)
    dt.add_argument("--output", required=True)
    dp = sub.add_parser("diagnostic-plot", help="plot saved diagnostic+family to SVG")
    dp.add_argument("--diagnostic", required=True)
    dp.add_argument("--family", required=True)
    dp.add_argument("--output", required=True)
    df = sub.add_parser("diagnostic-figure", help="alias of diagnostic-plot")
    df.add_argument("--diagnostic", required=True)
    df.add_argument("--family", required=True)
    df.add_argument("--output", required=True)
    cd = sub.add_parser("compare-diagnostics", help="compare two diagnostic directories")
    cd.add_argument("diag_a")
    cd.add_argument("diag_b")
    cd.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        report = write_comparison(args.run_a, args.run_b, args.output)
        print(json.dumps({"status": report["status"], "output": args.output}))
        return 0 if report["status"] else 1
    if args.cmd == "figure":
        render_figure(args.predictions_csv, args.output)
        print(args.output)
        return 0
    if args.cmd == "compare-evaluations":
        report = write_comparison_evaluations(args.eval_a, args.eval_b, args.output)
        print(json.dumps({"status": report["status"], "output": args.output}))
        return 0 if report["status"] else 1
    if args.cmd == "evaluation-figure":
        render_evaluation_figure(args.eval_dir, args.output)
        print(args.output)
        return 0
    if args.cmd == "compare-families":
        report = write_family_comparison(args.family_a, args.family_b,
                                         args.output)
        print(json.dumps({"status": report["status"], "output": args.output}))
        return 0 if report["status"] else 1
    if args.cmd == "family-table":
        write_family_table(args.family, args.output)
        print(args.output)
        return 0
    if args.cmd == "family-figure":
        render_family_figure(args.family, args.output)
        print(args.output)
        return 0
    if args.cmd == "diagnostic-table":
        write_diagnostic_table(args.diagnostic, args.family, args.output)
        print(args.output)
        return 0
    if args.cmd in ("diagnostic-plot", "diagnostic-figure"):
        render_diagnostic_plot(args.diagnostic, args.family, args.output)
        print(args.output)
        return 0
    if args.cmd == "compare-diagnostics":
        report = write_diagnostic_comparison(args.diag_a, args.diag_b,
                                             args.output)
        print(json.dumps({"status": report["status"], "output": args.output}))
        return 0 if report["status"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
