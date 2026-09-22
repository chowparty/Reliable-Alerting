"""Reusable evidence utilities: run comparison and saved-trace SVG figure.

Why: day-01 runs must be comparable and plottable from saved artifacts only,
without re-running the pipeline or inventing interpolated alert times.
"""
import argparse
import csv
import json
import math
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
        if tuple(header) != tuple(PREDICTIONS_COLUMNS):
            raise ValueError(f"predictions header must be exactly {PREDICTIONS_COLUMNS}")
        rows = []
        seen = set()
        prev_end = None
        config_id = None
        run_id = None
        for lineno, parts in enumerate(reader, start=2):
            if len(parts) != len(PREDICTIONS_COLUMNS):
                raise ValueError(f"row {lineno} must have exactly {len(PREDICTIONS_COLUMNS)} fields")
            d = dict(zip(PREDICTIONS_COLUMNS, parts))
            window_id = _require_id(d["window_id"], "window_id")
            start = _parse_int(d["start_index"], "start_index")
            end = _parse_int(d["end_index"], "end_index")
            if start > end:
                raise ValueError("start_index must be <= end_index")
            score = _parse_finite(d["score"], "score")
            threshold = _parse_finite(d["threshold"], "threshold")
            state = d["output_state"]
            if state not in ("normal", "alert"):
                raise ValueError("output_state must be 'normal' or 'alert'")
            expected = "normal" if score <= threshold else "alert"
            if state != expected:
                raise ValueError("output_state inconsistent with score and threshold")
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
    with open(output_svg, "x") as fh:
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
