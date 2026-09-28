"""Day-05 provisional diagnostic: trailing median gap (Pratyush support only).

Why: decision-time diagnostic aid only, not a detection claim. For each
replay window, current-inclusive median of the last 3 scores minus the
frozen calibration-score median (score units, no divide, one setting).
First 2 rows are null warmup with an explicit readiness_reason; each
independent call resets (document reset="independent_call", inclusion=
"current_inclusive"); no state carries across segments. Calibration must
strictly precede scores (no overlap/follow). Reference records fit
bounds/window_length. No labels are read or accepted. Timed region is
validation recompute + config check + build + verification only; provenance
capture and file writes are excluded. PROVISIONAL Pratyush support; not an
Aman deliverable.
"""
import argparse
import csv
import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

DIAGNOSTIC_ID = "trailing-median-gap-v1"
DIAGNOSTIC_VERSION = "diagnostics-v1"
RESOURCE_SCOPE = "saved_run_validation_recompute_diagnostic_verification_excluding_output"
RESOURCE_DESCRIPTION = (
    "source run validation recompute + diagnostic config check + "
    "label-free feature build + independent verification; excludes "
    "provenance capture (command/environment/git/file hashes) and "
    "file creation/writes/completion writes"
)
ALLOWED_ARTIFACTS = frozenset((
    "config.json",
    "diagnostic.json",
    "source_scores.csv",
    "source_calibration_scores.csv",
    "source_config.json",
    "verification.json",
    "metadata.json",
))
# Frozen snapshot of the provenance whitelist for the NEW diagnostic format.
# Keys must match exactly; digest VALUES may differ from current files
# (historical drift allowed, never rewritten).
EXPECTED_FILE_HASH_KEYS = frozenset((
    "src/reliable_alerting/__init__.py",
    "src/reliable_alerting/loading.py",
    "src/reliable_alerting/scoring.py",
    "src/reliable_alerting/splitting.py",
    "src/reliable_alerting/calibration.py",
    "src/reliable_alerting/policy.py",
    "src/reliable_alerting/writing.py",
    "src/reliable_alerting/pipeline.py",
    "src/reliable_alerting/provenance.py",
    "src/reliable_alerting/evidence.py",
    "src/reliable_alerting/evaluation.py",
    "src/reliable_alerting/evaluation_io.py",
    "src/reliable_alerting/replay.py",
    "src/reliable_alerting/diagnostics.py",
    "configs/day01-synthetic.json",
    "configs/day02-evaluation.json",
    "configs/day04-synthetic-family.json",
    "configs/day05-diagnostic.json",
    "tests/test_pipeline.py",
    "tests/test_source.py",
    "tests/test_decisions.py",
    "tests/test_evidence.py",
    "tests/test_evaluation.py",
    "tests/test_evaluation_io.py",
    "tests/test_hysteresis.py",
    "tests/test_replay.py",
    "tests/test_family_evidence.py",
    "tests/test_diagnostics.py",
    "tests/test_diagnostic_evidence.py",
    "tests/fixtures/day02-synthetic-labels.json",
    "report/outline.md",
    "README.md",
    "pyproject.toml",
))
SCORE_COLUMNS = ("window_id", "start_index", "end_index", "score")
DOCUMENT_KEYS = (
    "diagnostic_id", "diagnostic_version", "diagnostic_config_id",
    "score_identity", "reference_identity", "reference", "time_basis",
    "unit", "trailing_window", "warmup_count", "inclusion", "reset",
    "score_bounds", "decision_count", "source_identities", "rows",
)
REFERENCE_KEYS = (
    "segment", "statistic", "fit_scope", "count", "median",
    "bounds", "window_length",
)
ROW_KEYS = (
    "window_id", "start_index", "end_index", "availability_end",
    "score", "trailing_median", "reference_median", "feature",
    "contributing_count", "contributing_window_ids",
    "contributing_start_index", "contributing_end_index", "warmup",
    "readiness_reason",
)
INCLUSION = "current_inclusive"
RESET = "independent_call"


def _readiness_reason(i):
    if i < 2:
        return (f"warmup: have {i + 1}/3 current-inclusive scores; "
                "need 3 for trailing median")
    return "ready: current-inclusive median of 3"


def _is_int(v):
    return type(v) is int


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a number")
    try:
        f = float(v)
    except OverflowError as e:
        raise ValueError(f"{name} must be finite") from e
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite")
    return f


def _require_id(value, name):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if value.strip() == "":
        raise ValueError(f"{name} must be non-empty")
    return value


def _exact(d, allowed, where):
    if not isinstance(d, dict):
        raise TypeError(f"{where} must be a dict")
    keys = set(d.keys())
    if keys != set(allowed):
        missing = set(allowed) - keys
        extra = keys - set(allowed)
        raise ValueError(f"{where} must have exactly {allowed} (missing={missing} extra={extra})")
    return d


def validate_config(config):
    """Validate the one-setting diagnostic config (strict, label-free)."""
    _exact(config,
           ["schema_version", "diagnostic_id", "trailing_window",
            "warmup_count", "reference", "score_unit", "normalize",
            "time_basis", "provisional", "provisional_owner", "notes"],
           "diagnostic config")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if config["diagnostic_id"] != DIAGNOSTIC_ID:
        raise ValueError(f"diagnostic_id must be {DIAGNOSTIC_ID!r}")
    if type(config["trailing_window"]) is not int or config["trailing_window"] != 3:
        raise ValueError("trailing_window must be 3 (one setting)")
    if type(config["warmup_count"]) is not int or config["warmup_count"] != 2:
        raise ValueError("warmup_count must be 2")
    ref = config["reference"]
    _exact(ref, ["segment", "statistic", "fit_scope"], "reference")
    if ref["segment"] != "calibration":
        raise ValueError("reference.segment must be 'calibration'")
    if ref["statistic"] != "median":
        raise ValueError("reference.statistic must be 'median'")
    if ref["fit_scope"] != "calibration_scores":
        raise ValueError("reference.fit_scope must be 'calibration_scores'")
    if config["score_unit"] != "score":
        raise ValueError("score_unit must be 'score'")
    if type(config["normalize"]) is not bool or config["normalize"] is not False:
        raise ValueError("normalize must be false (score units, no divide)")
    if config["time_basis"] != "sample_index":
        raise ValueError("time_basis must be 'sample_index'")
    if type(config["provisional"]) is not bool or config["provisional"] is not True:
        raise ValueError("provisional must be true")
    _require_id(config["provisional_owner"], "provisional_owner")
    _require_id(config["notes"], "notes")
    return {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "trailing_window": 3,
        "warmup_count": 2,
        "reference": {"segment": "calibration", "statistic": "median",
                      "fit_scope": "calibration_scores"},
        "score_unit": "score",
        "normalize": False,
        "time_basis": "sample_index",
        "provisional": True,
        "provisional_owner": config["provisional_owner"],
        "notes": config["notes"],
    }


def diagnostic_config_id(resolved):
    text = json.dumps(resolved, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _canonical_rows(rows):
    return [{k: r[k] for k in SCORE_COLUMNS} for r in rows]


def score_identity_of(rows):
    text = json.dumps(_canonical_rows(rows), sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _validate_row_list(items, label):
    if items is None or isinstance(items, (str, bytes, dict)):
        raise TypeError(f"{label} must be a non-empty sequence of dicts")
    try:
        rows = list(items)
    except TypeError:
        raise TypeError(f"{label} must be a non-empty sequence of dicts")
    if not rows:
        raise ValueError(f"{label} must not be empty")
    out = []
    seen = set()
    prev_end = None
    prev_start = None
    length = None
    for entry in rows:
        if not isinstance(entry, dict):
            raise TypeError(f"each {label} row must be a dict")
        _exact(entry, list(SCORE_COLUMNS), f"{label} row")
        wid = _require_id(entry["window_id"], "window_id")
        start = entry["start_index"]
        end = entry["end_index"]
        if type(start) is not int or start < 0:
            raise TypeError("start_index must be an int >= 0")
        if type(end) is not int or end < 0:
            raise TypeError("end_index must be an int >= 0")
        if start > end:
            raise ValueError("start_index must be <= end_index")
        score = _num(entry["score"], "score")
        if wid in seen:
            raise ValueError("duplicate window_id")
        seen.add(wid)
        if prev_end is not None and end <= prev_end:
            raise ValueError("end_index must be strictly increasing")
        cur_len = end - start + 1
        if length is None:
            length = cur_len
        elif cur_len != length:
            raise ValueError("windows must share one length (misalignment)")
        if prev_end is not None:
            if start != prev_end + 1:
                raise ValueError("windows must be adjacent nonoverlapping (gap/overlap)")
            if start - prev_start != length:
                raise ValueError("windows must use one regular stride (misalignment)")
        prev_end = end
        prev_start = start
        out.append({"window_id": wid, "start_index": start,
                    "end_index": end, "score": score})
    return out, length


def _median_of(values):
    ordered = sorted(values)
    n = len(ordered)
    if n % 2 == 1:
        return float(ordered[n // 2])
    return float((ordered[n // 2 - 1] + ordered[n // 2]) / 2)


def compute_features(score_rows, calibration_rows, config):
    """Build the trailing-median-gap document (fresh state per call)."""
    resolved = validate_config(config)
    scores, score_len = _validate_row_list(score_rows, "score_rows")
    cals, cal_len = _validate_row_list(calibration_rows, "calibration_rows")
    if score_len != cal_len:
        raise ValueError("score and calibration window lengths must match")
    _check_chronology(scores, cals)
    ref_median = _median_of([r["score"] for r in cals])
    if not math.isfinite(ref_median):
        raise ValueError("reference median must be finite")
    cfg_id = diagnostic_config_id(resolved)
    s_id = score_identity_of(scores)
    r_id = score_identity_of(cals)
    rows = []
    for i, s in enumerate(scores):
        if i < 2:
            trailing = None
            feat = None
            warm = True
            count = i + 1
            contrib = [r["window_id"] for r in scores[: i + 1]]
            c_start = scores[0]["start_index"]
        else:
            window3 = [scores[i - 2]["score"], scores[i - 1]["score"], s["score"]]
            ordered3 = sorted(window3)
            trailing = float(ordered3[1])
            feat = float(trailing - ref_median)
            if not math.isfinite(trailing) or not math.isfinite(feat):
                raise ValueError("trailing_median/feature must be finite")
            warm = False
            count = 3
            contrib = [scores[i - 2]["window_id"], scores[i - 1]["window_id"],
                       s["window_id"]]
            c_start = scores[i - 2]["start_index"]
        rows.append({
            "window_id": s["window_id"],
            "start_index": s["start_index"],
            "end_index": s["end_index"],
            "availability_end": s["end_index"],
            "score": float(s["score"]),
            "trailing_median": trailing,
            "reference_median": float(ref_median),
            "feature": feat,
            "contributing_count": count,
            "contributing_window_ids": list(contrib),
            "contributing_start_index": int(c_start),
            "contributing_end_index": int(s["end_index"]),
            "warmup": bool(warm),
            "readiness_reason": _readiness_reason(i),
        })
    return {
        "diagnostic_id": DIAGNOSTIC_ID,
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "diagnostic_config_id": cfg_id,
        "score_identity": s_id,
        "reference_identity": r_id,
        "reference": {"segment": "calibration", "statistic": "median",
                      "fit_scope": "calibration_scores",
                      "count": len(cals), "median": float(ref_median),
                      "bounds": [cals[0]["start_index"], cals[-1]["end_index"]],
                      "window_length": int(cal_len)},
        "time_basis": "sample_index",
        "unit": "score",
        "trailing_window": 3,
        "warmup_count": 2,
        "inclusion": INCLUSION,
        "reset": RESET,
        "score_bounds": [scores[0]["start_index"], scores[-1]["end_index"]],
        "decision_count": len(scores),
        "source_identities": {"score_identity": s_id,
                              "reference_identity": r_id,
                              "diagnostic_config_id": cfg_id},
        "rows": rows,
    }


def _is_strict_int(v):
    return type(v) is int


def _float_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    if type(a) not in (int, float) or type(b) not in (int, float):
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError, OverflowError):
        return False
    if not (math.isfinite(fa) and math.isfinite(fb)):
        return False
    if fa == fb:
        return True
    return math.isclose(fa, fb, rel_tol=1e-12, abs_tol=1e-12)


def _check_chronology(scores, cals):
    if cals[-1]["end_index"] >= scores[0]["start_index"]:
        raise ValueError(
            "calibration must strictly precede scores "
            "(calibration end must be < score start; no overlap/follow)")


def verify_features(document, score_rows, calibration_rows, config):
    """Independently verify a feature document via fresh sorting arithmetic."""
    diffs = []
    try:
        resolved = validate_config(config)
    except Exception as e:
        return {"status": False, "differences": [f"config invalid: {e}"],
                "diagnostic_id": DIAGNOSTIC_ID, "checked_rows": 0}
    try:
        scores, score_len = _validate_row_list(score_rows, "score_rows")
    except Exception as e:
        return {"status": False, "differences": [f"score_rows invalid: {e}"],
                "diagnostic_id": DIAGNOSTIC_ID, "checked_rows": 0}
    try:
        cals, cal_len = _validate_row_list(calibration_rows, "calibration_rows")
    except Exception as e:
        return {"status": False, "differences": [f"calibration_rows invalid: {e}"],
                "diagnostic_id": DIAGNOSTIC_ID, "checked_rows": 0}
    if score_len != cal_len:
        diffs.append("score and calibration window lengths differ")
    try:
        _check_chronology(scores, cals)
    except ValueError as e:
        diffs.append(f"chronology: {e}")
    if not isinstance(document, dict):
        return {"status": False, "differences": ["document must be a dict"],
                "diagnostic_id": DIAGNOSTIC_ID, "checked_rows": 0}
    if set(document.keys()) != set(DOCUMENT_KEYS):
        diffs.append(f"document keys must be exactly {DOCUMENT_KEYS}")
    # independent reference median from sorted calibration scores
    cal_vals = sorted([float(r["score"]) for r in cals])
    n = len(cal_vals)
    if n % 2 == 1:
        expect_ref = float(cal_vals[n // 2])
    else:
        expect_ref = float((cal_vals[n // 2 - 1] + cal_vals[n // 2]) / 2)
    expect_cfg = diagnostic_config_id(resolved)
    expect_sid = score_identity_of(scores)
    expect_rid = score_identity_of(cals)
    if document.get("diagnostic_id") != DIAGNOSTIC_ID:
        diffs.append("diagnostic_id mismatch")
    if document.get("diagnostic_version") != DIAGNOSTIC_VERSION:
        diffs.append("diagnostic_version mismatch")
    if document.get("diagnostic_config_id") != expect_cfg:
        diffs.append("diagnostic_config_id mismatch")
    if document.get("score_identity") != expect_sid:
        diffs.append("score_identity mismatch")
    if document.get("reference_identity") != expect_rid:
        diffs.append("reference_identity mismatch")
    src_ids = document.get("source_identities")
    if not isinstance(src_ids, dict) or set(src_ids.keys()) != {
            "score_identity", "reference_identity", "diagnostic_config_id"}:
        diffs.append("source_identities must have exactly "
                     "{score_identity, reference_identity, diagnostic_config_id}")
    elif src_ids.get("score_identity") != expect_sid \
            or src_ids.get("reference_identity") != expect_rid \
            or src_ids.get("diagnostic_config_id") != expect_cfg:
        diffs.append("source_identities mismatch")
    ref = document.get("reference")
    if not isinstance(ref, dict):
        diffs.append("reference must be a dict")
    else:
        if set(ref.keys()) != set(REFERENCE_KEYS):
            diffs.append(f"reference keys must be exactly {REFERENCE_KEYS}")
        if ref.get("segment") != "calibration" or ref.get("statistic") != "median" \
                or ref.get("fit_scope") != "calibration_scores":
            diffs.append("reference stats/fit scope mismatch")
        if not _is_strict_int(ref.get("count")) or ref.get("count") != len(cals):
            diffs.append("reference count mismatch")
        if not _float_equal(ref.get("median"), expect_ref):
            diffs.append(f"reference median {ref.get('median')!r} != recomputed {expect_ref!r}")
        rb = ref.get("bounds")
        if not isinstance(rb, list) or len(rb) != 2 \
                or not _is_strict_int(rb[0]) or not _is_strict_int(rb[1]) \
                or rb != [cals[0]["start_index"], cals[-1]["end_index"]]:
            diffs.append("reference bounds mismatch")
        if not _is_strict_int(ref.get("window_length")) \
                or ref.get("window_length") != cal_len:
            diffs.append("reference window_length mismatch")
    if not _is_strict_int(document.get("trailing_window")) \
            or document.get("trailing_window") != 3 \
            or not _is_strict_int(document.get("warmup_count")) \
            or document.get("warmup_count") != 2:
        diffs.append("trailing_window/warmup_count mismatch")
    if document.get("time_basis") != "sample_index" or document.get("unit") != "score":
        diffs.append("time_basis/unit mismatch")
    if document.get("inclusion") != INCLUSION:
        diffs.append("inclusion mismatch")
    if document.get("reset") != RESET:
        diffs.append("reset mismatch")
    if not _is_strict_int(document.get("decision_count")) \
            or document.get("decision_count") != len(scores):
        diffs.append("decision_count mismatch")
    bounds = document.get("score_bounds")
    if not isinstance(bounds, list) or len(bounds) != 2 \
            or not _is_strict_int(bounds[0]) or not _is_strict_int(bounds[1]) \
            or bounds != [scores[0]["start_index"], scores[-1]["end_index"]]:
        diffs.append("score_bounds mismatch")
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != len(scores):
        diffs.append("row count mismatch")
        rows = [] if not isinstance(rows, list) else rows
    m = min(len(rows), len(scores))
    for i in range(m):
        got = rows[i]
        want_s = scores[i]
        if not isinstance(got, dict):
            diffs.append(f"row {i}: must be a dict")
            continue
        if set(got.keys()) != set(ROW_KEYS):
            diffs.append(f"row {i}: keys must be exactly {ROW_KEYS}")
            continue
        for k in ("window_id",):
            if got.get(k) != want_s[k]:
                diffs.append(f"row {i}: {k} mismatch")
        for k in ("start_index", "end_index"):
            if not _is_strict_int(got.get(k)) or got.get(k) != want_s[k]:
                diffs.append(f"row {i}: {k} mismatch")
        if not _is_strict_int(got.get("availability_end")) \
                or got.get("availability_end") != want_s["end_index"]:
            if f"row {i}: availability_end must equal end_index" not in diffs:
                diffs.append(f"row {i}: availability_end must equal end_index")
        if not _float_equal(got.get("score"), float(want_s["score"])):
            diffs.append(f"row {i}: score mismatch")
        if not _float_equal(got.get("reference_median"), expect_ref):
            diffs.append(f"row {i}: reference_median mismatch")
        if i < 2:
            if got.get("warmup") is not True:
                diffs.append(f"row {i}: warmup must be true")
            if got.get("trailing_median") is not None or got.get("feature") is not None:
                diffs.append(f"row {i}: warmup trailing_median/feature must be null")
            if not _is_strict_int(got.get("contributing_count")) \
                    or got.get("contributing_count") != i + 1:
                diffs.append(f"row {i}: contributing_count mismatch")
            if list(got.get("contributing_window_ids") or []) != \
                    [r["window_id"] for r in scores[: i + 1]]:
                diffs.append(f"row {i}: contributing_window_ids mismatch")
            if not _is_strict_int(got.get("contributing_start_index")) \
                    or got.get("contributing_start_index") != scores[0]["start_index"]:
                diffs.append(f"row {i}: contributing_start_index mismatch")
        else:
            trio = sorted([float(scores[i - 2]["score"]),
                           float(scores[i - 1]["score"]),
                           float(want_s["score"])])
            expect_trail = float(trio[1])
            expect_feat = float(expect_trail - expect_ref)
            if got.get("warmup") is not False:
                diffs.append(f"row {i}: warmup must be false")
            if not _float_equal(got.get("trailing_median"), expect_trail):
                diffs.append(f"row {i}: trailing_median mismatch")
            if not _float_equal(got.get("feature"), expect_feat):
                diffs.append(f"row {i}: feature mismatch")
            if not _is_strict_int(got.get("contributing_count")) \
                    or got.get("contributing_count") != 3:
                diffs.append(f"row {i}: contributing_count mismatch")
            if list(got.get("contributing_window_ids") or []) != \
                    [scores[i - 2]["window_id"], scores[i - 1]["window_id"],
                     want_s["window_id"]]:
                diffs.append(f"row {i}: contributing_window_ids mismatch")
            if not _is_strict_int(got.get("contributing_start_index")) \
                    or got.get("contributing_start_index") != scores[i - 2]["start_index"]:
                diffs.append(f"row {i}: contributing_start_index mismatch")
        if not _is_strict_int(got.get("contributing_end_index")) \
                or got.get("contributing_end_index") != want_s["end_index"]:
            diffs.append(f"row {i}: contributing_end_index mismatch")
        if got.get("readiness_reason") != _readiness_reason(i):
            diffs.append(f"row {i}: readiness_reason mismatch")
    status = not diffs
    return {"status": bool(status), "differences": diffs,
            "diagnostic_id": DIAGNOSTIC_ID,
            "diagnostic_config_id": expect_cfg,
            "row_count": len(scores), "checked_rows": m}


def load_strict_json(path):
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


def write_strict_json(path, obj):
    text = json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(path, "x") as fh:
        fh.write(text)
    return str(path)


def write_diagnostic(path, document):
    if not isinstance(document, dict):
        raise TypeError("document must be a dict")
    if set(document.keys()) != set(DOCUMENT_KEYS):
        raise ValueError(f"document keys must be exactly {DOCUMENT_KEYS}")
    return write_strict_json(path, document)


def read_diagnostic(path):
    doc = load_strict_json(path)
    if not isinstance(doc, dict):
        raise TypeError("diagnostic must be a dict")
    if set(doc.keys()) != set(DOCUMENT_KEYS):
        raise ValueError(f"diagnostic keys must be exactly {DOCUMENT_KEYS}")
    return doc


def _scores_csv_text(rows):
    import io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(list(SCORE_COLUMNS))
    for r in rows:
        writer.writerow([r["window_id"], r["start_index"], r["end_index"],
                         repr(float(r["score"]))])
    return out.getvalue()


def _parse_scores_csv(path):
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as e:
            raise ValueError("scores csv must not be empty") from e
        if tuple(header) != tuple(SCORE_COLUMNS):
            raise ValueError(f"scores header must be exactly {SCORE_COLUMNS}")
        rows = []
        for lineno, parts in enumerate(reader, start=2):
            if len(parts) != len(SCORE_COLUMNS):
                raise ValueError(f"row {lineno} width mismatch")
            d = dict(zip(SCORE_COLUMNS, parts))
            wid = d["window_id"]
            if not isinstance(wid, str) or wid.strip() == "":
                raise ValueError("window_id must be non-empty")
            for k in ("start_index", "end_index"):
                raw = d[k]
                s = str(raw).strip()
                try:
                    v = int(s)
                except ValueError as e:
                    raise ValueError(f"{k} must be an int") from e
                if not s.lstrip("-").isdigit():
                    raise ValueError(f"{k} must be an int")
                if v < 0:
                    raise ValueError(f"{k} must be >= 0")
                d[k] = v
            try:
                f = float(str(d["score"]).strip())
            except ValueError as e:
                raise TypeError("score must be a number") from e
            if not math.isfinite(f):
                raise ValueError("score must be finite")
            d["score"] = f
            rows.append({"window_id": wid, "start_index": d["start_index"],
                         "end_index": d["end_index"], "score": d["score"]})
    if not rows:
        raise ValueError("scores csv must not be empty")
    return rows


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _refuse_symlink(path, label):
    p = Path(path)
    if p.is_symlink():
        raise ValueError(f"{label}: symlink refused: {p}")
    return p


def _refuse_symlink_chain(path, label):
    """Refuse symlinks on path and every parent up to the repo root.

    Why: a symlinked parent directory bypasses leaf-only checks, so the
    loader must not read anything until the full chain is clean. Mirrors
    replay._refuse_symlink_chain without importing replay.
    """
    from reliable_alerting import provenance as _provenance
    p = Path(path)
    try:
        repo = _provenance.repo_root()
    except Exception:
        repo = None
    for cur in [p, *p.parents]:
        if cur.is_symlink():
            raise ValueError(f"{label}: symlink refused: {cur}")
        if repo is not None and cur == repo:
            break
        if cur == cur.parent:
            break
    return p


SOURCE_RUN_ARTIFACTS = (
    "predictions.csv",
    "calibration_scores.csv",
    "config.json",
    "metadata.json",
    "diagnostics.json",
)


def _is_sha256_hex(v):
    return (isinstance(v, str) and len(v) == 64
            and all(c in "0123456789abcdef" for c in v.lower()))


def _parse_aware_iso(v):
    try:
        dt = datetime.fromisoformat(v)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid iso timestamp: {v!r}") from e
    if dt.tzinfo is None:
        raise ValueError(f"timestamp missing timezone: {v!r}")
    return dt


def run_diagnostic(source_run, config_path, output_dir):
    """Build one exclusive diagnostic dir from a verified source run."""
    out = Path(output_dir)
    _refuse_symlink_chain(output_dir, "output")
    if out.exists():
        raise FileExistsError(f"output directory already exists: {out}")
    _refuse_symlink_chain(source_run, "source_run")
    _refuse_symlink_chain(config_path, "config")
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    from reliable_alerting import evidence as _evidence
    from reliable_alerting import provenance as _provenance
    # 1. Verify saved source trace before any feature work (no labels).
    # Refuse symlinked source artifacts before evidence reads them.
    for rel in SOURCE_RUN_ARTIFACTS:
        _refuse_symlink_chain(Path(source_run) / rel,
                              f"source {rel!r}")
    run = _evidence._read_run(source_run)
    diffs = []
    if not _evidence._verify_recompute("source", run, diffs):
        raise ValueError(f"source run failed recompute verification: {diffs}")
    # 2. Strict diagnostic config.
    raw_config = load_strict_json(config_path)
    resolved = validate_config(raw_config)
    # 3. Raw saved predictions stripped + calibration (score units only).
    scores = [{"window_id": r["window_id"], "start_index": r["start_index"],
               "end_index": r["end_index"], "score": float(r["score"])}
              for r in run["predictions"]]
    cals = [{"window_id": r["window_id"], "start_index": r["start_index"],
             "end_index": r["end_index"], "score": float(r["score"])}
            for r in run["calibration"]]
    document = compute_features(scores, cals, resolved)
    verification = verify_features(document, scores, cals, resolved)
    if not verification.get("status"):
        raise ValueError(f"diagnostic self-verification failed: {verification.get('differences')}")
    elapsed = time.monotonic() - t0
    finished_at = datetime.now(timezone.utc).isoformat()
    repo = _provenance.repo_root()
    metadata = {
        "diagnostic_id": DIAGNOSTIC_ID,
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "diagnostic_config_id": document["diagnostic_config_id"],
        "score_identity": document["score_identity"],
        "reference_identity": document["reference_identity"],
        "source_run": {"path": str(source_run),
                       "run_id": run["metadata"].get("run_id"),
                       "config_id": run["metadata"].get("config_id")},
        "source_config_id": run["recomputed"],
        "decision_count": len(scores),
        "started_at": started_at,
        "started_at_scope": "diagnostics_entry",
        "finished_at": finished_at,
        "finished_at_scope": "diagnostic_verified_pre_provenance",
        "command": _provenance.command_record(),
        "environment": _provenance.environment_record(),
        "git": _provenance.git_record(str(repo)),
        "file_hashes": _provenance.file_hashes(repo),
        "resource_scope": RESOURCE_SCOPE,
        "resource_description": RESOURCE_DESCRIPTION,
        "allocation_note": "peak_python_allocation_bytes unmeasured",
        "elapsed_monotonic_seconds": elapsed,
        "peak_python_allocation_bytes": None,
    }
    files = {
        "config.json": _canonical(resolved).encode(),
        "diagnostic.json": _canonical(document).encode(),
        "source_scores.csv": _scores_csv_text(scores).encode(),
        "source_calibration_scores.csv": _scores_csv_text(cals).encode(),
        "source_config.json": _canonical(run["resolved"]).encode(),
        "verification.json": _canonical(verification).encode(),
        "metadata.json": _canonical(metadata).encode(),
    }
    out.mkdir(parents=True, exist_ok=False)
    try:
        for rel in sorted(files):
            with open(out / rel, "xb") as fh:
                fh.write(files[rel])
    except Exception:
        # Leave partial dir for inspection; caller uses fresh dir per run.
        raise
    return {"output": str(out),
            "diagnostic_id": DIAGNOSTIC_ID,
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "diagnostic_config_id": document["diagnostic_config_id"],
            "score_identity": document["score_identity"],
            "reference_identity": document["reference_identity"],
            "decision_count": len(scores),
            "verification": verification,
            "metadata": metadata,
            "files": {k: str(out / k) for k in sorted(files)}}


def load_diagnostic(path, source_run=None):
    """Strictly verify a persisted diagnostic dir with fresh recomputation.

    Both a directory path and a direct diagnostic.json file path resolve to
    the same containing root, and both run the exact artifact entry plus
    symlink-chain checks before any persisted file is read.
    """
    base = Path(path)
    try:
        _refuse_symlink_chain(base, "diagnostic path")
    except ValueError as e:
        return {"path": str(base), "status": False,
                "differences": [str(e)]}
    if base.is_dir():
        root = base
    else:
        root = base.parent
        try:
            _refuse_symlink_chain(root, "diagnostic root")
        except ValueError as e:
            return {"path": str(base), "status": False,
                    "differences": [str(e)]}
    diag_path = root / "diagnostic.json"
    diffs = []
    try:
        names = sorted(p.name for p in root.iterdir())
    except OSError as e:
        return {"path": str(base), "status": False,
                "differences": [f"directory unreadable: {e}"]}
    if set(names) != set(ALLOWED_ARTIFACTS):
        diffs.append(f"directory files must be exactly {sorted(ALLOWED_ARTIFACTS)} "
                     f"(found={names})")
    symlink_diffs = []
    for rel in sorted(set(names) & set(ALLOWED_ARTIFACTS)):
        try:
            _refuse_symlink_chain(root / rel, f"artifact {rel!r}")
        except ValueError as e:
            symlink_diffs.append(str(e))
    if symlink_diffs:
        diffs.extend(symlink_diffs)
        return {"path": str(base), "status": False,
                "differences": diffs, "document": None,
                "metadata": None, "config": None,
                "verification": {"status": False,
                                 "differences": symlink_diffs,
                                 "diagnostic_id": DIAGNOSTIC_ID,
                                 "checked_rows": 0}}
    if diffs:
        # Exact entries violated: refuse before reading persisted files.
        return {"path": str(base), "status": False,
                "differences": diffs, "document": None,
                "metadata": None, "config": None,
                "verification": {"status": False,
                                 "differences": diffs,
                                 "diagnostic_id": DIAGNOSTIC_ID,
                                 "checked_rows": 0}}
    try:
        document = read_diagnostic(str(diag_path))
    except Exception as e:
        return {"path": str(base), "status": False,
                "differences": [f"diagnostic unreadable: {e}"]}
    try:
        resolved = validate_config(load_strict_json(str(root / "config.json")))
    except Exception as e:
        return {"path": str(base), "status": False,
                "differences": [f"config invalid: {e}"]}
    try:
        scores = _parse_scores_csv(str(root / "source_scores.csv"))
    except Exception as e:
        return {"path": str(base), "status": False,
                "differences": [f"source_scores unreadable: {e}"]}
    try:
        cals = _parse_scores_csv(str(root / "source_calibration_scores.csv"))
    except Exception as e:
        return {"path": str(base), "status": False,
                "differences": [f"source_calibration unreadable: {e}"]}
    verification = verify_features(document, scores, cals, resolved)
    diffs.extend(verification.get("differences", []))
    try:
        metadata = load_strict_json(str(root / "metadata.json"))
    except Exception as e:
        diffs.append(f"metadata unreadable: {e}")
        metadata = None
    if isinstance(metadata, dict):
        for k in ("diagnostic_id", "diagnostic_version",
                  "diagnostic_config_id", "score_identity",
                  "reference_identity", "source_run", "source_config_id",
                  "decision_count", "command", "environment", "git",
                  "file_hashes", "resource_scope", "resource_description",
                  "started_at", "started_at_scope", "finished_at",
                  "finished_at_scope", "elapsed_monotonic_seconds",
                  "peak_python_allocation_bytes", "allocation_note"):
            if k not in metadata:
                diffs.append(f"metadata.{k} missing")
        if metadata.get("diagnostic_id") != DIAGNOSTIC_ID:
            diffs.append("metadata diagnostic_id mismatch")
        if metadata.get("diagnostic_version") != DIAGNOSTIC_VERSION:
            diffs.append("metadata diagnostic_version mismatch")
        if metadata.get("diagnostic_config_id") != document.get("diagnostic_config_id"):
            diffs.append("metadata diagnostic_config_id != document")
        if metadata.get("score_identity") != document.get("score_identity"):
            diffs.append("metadata score_identity != document")
        if metadata.get("reference_identity") != document.get("reference_identity"):
            diffs.append("metadata reference_identity != document")
        if not _is_strict_int(metadata.get("decision_count")) \
                or metadata.get("decision_count") < 1 \
                or metadata.get("decision_count") != len(scores) \
                or metadata.get("decision_count") != document.get("decision_count"):
            diffs.append("metadata decision_count mismatch")
        if metadata.get("resource_scope") != RESOURCE_SCOPE:
            diffs.append("metadata resource_scope mismatch")
        if metadata.get("resource_description") != RESOURCE_DESCRIPTION:
            diffs.append("metadata resource_description mismatch")
        if metadata.get("started_at_scope") != "diagnostics_entry":
            diffs.append("metadata started_at_scope mismatch")
        if metadata.get("finished_at_scope") != "diagnostic_verified_pre_provenance":
            diffs.append("metadata finished_at_scope mismatch")
        for k in ("started_at", "finished_at"):
            v = metadata.get(k)
            if not isinstance(v, str) or not v.strip():
                diffs.append(f"metadata.{k} missing or empty")
            else:
                try:
                    _parse_aware_iso(v)
                except ValueError:
                    diffs.append(f"metadata.{k} invalid iso timestamp")
        try:
            if isinstance(metadata.get("started_at"), str) \
                    and isinstance(metadata.get("finished_at"), str):
                s_dt = _parse_aware_iso(metadata["started_at"])
                f_dt = _parse_aware_iso(metadata["finished_at"])
                if f_dt < s_dt:
                    diffs.append("metadata finished_at precedes started_at")
        except ValueError:
            pass
        el = metadata.get("elapsed_monotonic_seconds")
        if isinstance(el, bool) or not isinstance(el, (int, float)) \
                or not math.isfinite(float(el)) or not float(el) >= 0:
            diffs.append("metadata elapsed_monotonic_seconds invalid")
        peak = metadata.get("peak_python_allocation_bytes", None)
        if "peak_python_allocation_bytes" not in metadata:
            diffs.append("metadata.peak_python_allocation_bytes missing")
        elif peak is not None and (isinstance(peak, bool)
                                   or not isinstance(peak, int) or peak < 0):
            diffs.append("metadata peak_python_allocation_bytes invalid")
        if metadata.get("allocation_note") != "peak_python_allocation_bytes unmeasured":
            diffs.append("metadata allocation_note mismatch")
        if not _is_sha256_hex(metadata.get("source_config_id")):
            diffs.append("metadata source_config_id missing or not sha256")
        src = metadata.get("source_run")
        if not isinstance(src, dict):
            diffs.append("metadata source_run must be a dict")
        else:
            for k in ("path", "run_id", "config_id"):
                v = src.get(k)
                if not isinstance(v, str) or not v.strip():
                    diffs.append(f"metadata source_run.{k} missing")
            if isinstance(src.get("config_id"), str) \
                    and not _is_sha256_hex(src.get("config_id")):
                diffs.append("metadata source_run.config_id not sha256")
        cmd = metadata.get("command")
        if not isinstance(cmd, dict):
            diffs.append("metadata command must be a dict")
        else:
            for k in ("shell", "argv", "orig_argv", "cwd",
                      "rerun_shell", "rerun_executable"):
                if k not in cmd:
                    diffs.append(f"metadata command.{k} missing")
            for k in ("shell", "cwd", "rerun_shell", "rerun_executable"):
                v = cmd.get(k)
                if not isinstance(v, str) or not v.strip():
                    diffs.append(f"metadata command.{k} missing or empty")
            for k in ("argv", "orig_argv"):
                vals = cmd.get(k)
                if not isinstance(vals, list) or not vals:
                    diffs.append(f"metadata command.{k} missing or empty")
                elif any(not isinstance(v, str) for v in vals):
                    diffs.append(f"metadata command.{k} must be a list of strings")
        env = metadata.get("environment")
        if not isinstance(env, dict) or not env:
            diffs.append("metadata environment missing or empty")
        else:
            for k in ("python_version", "platform", "machine",
                      "hostname", "distributions"):
                if k not in env:
                    diffs.append(f"metadata environment.{k} missing")
            for k in ("python_version", "platform", "machine", "hostname"):
                v = env.get(k)
                if not isinstance(v, str) or not v.strip():
                    diffs.append(f"metadata environment.{k} missing or empty")
            if "distributions" in env:
                dists = env.get("distributions")
                if not isinstance(dists, list):
                    diffs.append("metadata environment.distributions must be a list")
                elif any(not isinstance(v, str) for v in dists):
                    diffs.append("metadata environment.distributions must be a list of strings")
        git = metadata.get("git")
        if not isinstance(git, dict):
            diffs.append("metadata git must be a dict")
        else:
            head = git.get("head")
            if not isinstance(head, str) or not head.strip():
                diffs.append("metadata git.head missing or empty")
            for k in ("branch", "status_porcelain"):
                if k not in git or not isinstance(git.get(k), str):
                    diffs.append(f"metadata git.{k} missing")
        fh = metadata.get("file_hashes")
        if not isinstance(fh, dict) or not fh:
            diffs.append("metadata file_hashes missing or empty")
        elif set(fh.keys()) != set(EXPECTED_FILE_HASH_KEYS):
            diffs.append(
                "metadata file_hashes keys must be exactly "
                f"{sorted(EXPECTED_FILE_HASH_KEYS)}")
        else:
            # Exact keys required for the NEW format; digest VALUES may
            # differ from current files (historical drift allowed, never
            # equality-checked here).
            for k, v in fh.items():
                if not isinstance(k, str) or not k.strip():
                    diffs.append("metadata file_hashes key missing or empty")
                    break
                if not _is_sha256_hex(v):
                    diffs.append(f"metadata file_hashes[{k!r}] not sha256")
                    break
    else:
        diffs.append("metadata must be a dict")
    try:
        src_cfg_raw = load_strict_json(str(root / "source_config.json"))
        from reliable_alerting import pipeline as _pipeline
        try:
            resolved_src = _pipeline.validate_config(src_cfg_raw)
        except Exception as e:
            diffs.append(f"source_config invalid: {e}")
            resolved_src = None
        if resolved_src is not None:
            recomputed_src_id = _pipeline.config_id_of(resolved_src)
            if metadata is not None and isinstance(metadata, dict):
                if metadata.get("source_config_id") != recomputed_src_id:
                    diffs.append("metadata source_config_id != recomputed source_config")
                src_link = metadata.get("source_run") or {}
                if isinstance(src_link, dict) and src_link.get("config_id") != recomputed_src_id:
                    diffs.append("metadata source_run.config_id != recomputed source_config")
            try:
                expected = _pipeline.compute_trace(resolved_src)
            except Exception as e:
                diffs.append(f"source_config recompute failed: {e}")
                expected = None
            if expected is not None:
                exp_scores = [{"window_id": r["window_id"],
                               "start_index": r["start_index"],
                               "end_index": r["end_index"],
                               "score": float(r["score"])}
                              for r in expected["rows"]]
                if exp_scores != scores:
                    diffs.append("persisted source_scores != recomputed source trace")
                if expected["calibration_rows"] != cals:
                    diffs.append("persisted calibration != recomputed calibration")
    except Exception as e:
        diffs.append(f"source_config unreadable: {e}")
    try:
        persisted_ver = load_strict_json(str(root / "verification.json"))
        if persisted_ver != verification:
            diffs.append("persisted verification != recomputed verification")
    except Exception as e:
        diffs.append(f"verification unreadable: {e}")
    if source_run is not None:
        try:
            from reliable_alerting import evidence as _evidence
            run = _evidence._read_run(source_run)
            check = []
            if not _evidence._verify_recompute("source", run, check):
                diffs.append(f"source run failed recompute: {check}")
            else:
                src_scores = [{"window_id": r["window_id"],
                               "start_index": r["start_index"],
                               "end_index": r["end_index"],
                               "score": float(r["score"])}
                              for r in run["predictions"]]
                if src_scores != scores:
                    diffs.append("source_run scores != persisted source_scores")
                src_cals = [{"window_id": r["window_id"],
                             "start_index": r["start_index"],
                             "end_index": r["end_index"],
                             "score": float(r["score"])}
                            for r in run["calibration"]]
                if src_cals != cals:
                    diffs.append("source_run calibration != persisted calibration")
        except Exception as e:
            diffs.append(f"source_run unreadable: {e}")
    status = bool(verification.get("status")) and not diffs
    return {"path": str(base), "status": bool(status),
            "differences": diffs, "document": document,
            "metadata": metadata, "config": resolved,
            "verification": verification}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reliable_alerting.diagnostics")
    ap.add_argument("--run", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    result = run_diagnostic(args.run, args.config, args.output)
    print(json.dumps({"output": result["output"],
                      "diagnostic_id": result["diagnostic_id"],
                      "diagnostic_config_id": result["diagnostic_config_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
