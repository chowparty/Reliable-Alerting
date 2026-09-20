"""Day-01 synthetic pipeline: load -> split -> fit -> calibrate -> replay -> save.

Public API: compute_trace(config, values=None) is label-free; it returns
replay rows WITHOUT run_id (run_id differs per execution and is added only
by write_output/CLI), plus calibration rows, diagnostics, and identities.

compute_trace(config, values=<override>) is a pure testing helper: the
write path persists only the synthetic recipe, so write_output always
recomputes the expected trace from the resolved config (validation
recomputation) and rejects any caller-supplied trace that differs, before
creating any output. Full values available in batch is not a streaming
claim; no streaming architecture change here.
"""
import argparse
import hashlib
import json
import math
import time
import tracemalloc
import uuid
from datetime import datetime, timezone

from reliable_alerting import calibration, loading, policy, provenance, scoring, splitting, writing

INTENDED_DAY1 = "2026-09-19"
RESOURCE_SCOPE = "validated_compute_trace_only"


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
    _exact(
        config,
        ["schema_version", "input", "segments", "window", "scoring", "calibration",
         "policy", "missing_policy", "source_label_use", "time_basis", "held_out"],
        "config",
    )
    if not _is_int(config["schema_version"]) or config["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    for k, want in (("missing_policy", "reject"), ("source_label_use", "none"),
                    ("time_basis", "sample_index"),
                    ("held_out", "not_reserved_or_evaluated")):
        if not isinstance(config[k], str) or config[k] != want:
            raise ValueError(f"{k} must be {want!r}")
    inp = _exact(config["input"], ["kind", "length", "pattern", "offsets"], "input")
    if inp["kind"] != "synthetic_periodic_v1":
        raise ValueError("input.kind must be 'synthetic_periodic_v1'")
    if not _is_int(inp["length"]) or inp["length"] <= 0:
        raise ValueError("input.length must be a positive int")
    n = inp["length"]
    pat = inp["pattern"]
    if not isinstance(pat, (list, tuple)) or not pat:
        raise ValueError("input.pattern must be non-empty")
    pattern = [_num(v, "pattern entry") for v in pat]
    offs = inp["offsets"]
    if not isinstance(offs, (list, tuple)):
        raise TypeError("input.offsets must be a list")
    offsets = []
    for e in offs:
        _exact(e, ["start", "stop", "offset"], "offset entry")
        if not _is_int(e["start"]) or not _is_int(e["stop"]):
            raise TypeError("offset start/stop must be ints")
        off = _num(e["offset"], "offset")
        if not (0 <= e["start"] <= e["stop"] <= n):
            raise ValueError(f"offset range out of bounds: {e['start']}:{e['stop']}")
        offsets.append({"start": e["start"], "stop": e["stop"], "offset": off})
    segs = _exact(config["segments"], ["source_fit", "calibration", "replay"], "segments")
    bounds = {}
    for name in ("source_fit", "calibration", "replay"):
        b = segs[name]
        if not isinstance(b, (list, tuple)) or len(b) != 2:
            raise ValueError(f"segments.{name} must be [start, stop]")
        if not _is_int(b[0]) or not _is_int(b[1]):
            raise TypeError(f"segments.{name} bounds must be ints")
        if not (0 <= b[0] < b[1] <= n):
            raise ValueError(f"segments.{name} must satisfy 0 <= start < stop <= {n}")
        bounds[name] = [b[0], b[1]]
    if not (bounds["source_fit"][0] == 0 and bounds["source_fit"][1] == bounds["calibration"][0]
            and bounds["calibration"][1] == bounds["replay"][0]
            and bounds["replay"][1] == n):
        raise ValueError("segments must be contiguous ordered covering full input")
    win = _exact(config["window"],
                 ["length", "stride", "anchor", "edge_policy", "end_index"], "window")
    if not _is_int(win["length"]) or win["length"] < 1:
        raise ValueError("window.length must be >= 1")
    if not _is_int(win["stride"]) or win["stride"] < 1:
        raise ValueError("window.stride must be >= 1")
    if win["anchor"] != "segment_start":
        raise ValueError("window.anchor must be 'segment_start'")
    if win["edge_policy"] != "drop_incomplete":
        raise ValueError("window.edge_policy must be 'drop_incomplete'")
    if win["end_index"] != "inclusive":
        raise ValueError("window.end_index must be 'inclusive'")
    sc = _exact(config["scoring"],
                ["kind", "epsilon", "fit_scope", "standard_deviation"], "scoring")
    if sc["kind"] != "mean_distance":
        raise ValueError("scoring.kind must be 'mean_distance'")
    eps = _num(sc["epsilon"], "epsilon")
    if not eps > 0:
        raise ValueError("scoring.epsilon must be > 0")
    if sc["fit_scope"] != "source_fit":
        raise ValueError("scoring.fit_scope must be 'source_fit'")
    if sc["standard_deviation"] != "population":
        raise ValueError("scoring.standard_deviation must be 'population'")
    cal = _exact(config["calibration"],
                 ["kind", "quantile", "method", "min_samples", "score_segment"],
                 "calibration")
    if cal["kind"] != "fixed_quantile":
        raise ValueError("calibration.kind must be 'fixed_quantile'")
    q = _num(cal["quantile"], "quantile")
    if not 0 < q <= 1:
        raise ValueError("calibration.quantile must satisfy 0 < q <= 1")
    if cal["method"] != "nearest_rank":
        raise ValueError("calibration.method must be 'nearest_rank'")
    if not _is_int(cal["min_samples"]) or cal["min_samples"] < 1:
        raise ValueError("calibration.min_samples must be >= 1")
    if cal["score_segment"] != "calibration":
        raise ValueError("calibration.score_segment must be 'calibration'")
    pol = _exact(config["policy"], ["kind", "comparison"], "policy")
    if pol["kind"] != "fixed_threshold":
        raise ValueError("policy.kind must be 'fixed_threshold'")
    if pol["comparison"] != "strict_greater":
        raise ValueError("policy.comparison must be 'strict_greater'")
    return {
        "schema_version": 1,
        "input": {"kind": "synthetic_periodic_v1", "length": n,
                  "pattern": pattern, "offsets": offsets},
        "segments": bounds,
        "window": {"length": win["length"], "stride": win["stride"],
                   "anchor": "segment_start", "edge_policy": "drop_incomplete",
                   "end_index": "inclusive"},
        "scoring": {"kind": "mean_distance", "epsilon": eps,
                    "fit_scope": "source_fit", "standard_deviation": "population"},
        "calibration": {"kind": "fixed_quantile", "quantile": q,
                        "method": "nearest_rank", "min_samples": cal["min_samples"],
                        "score_segment": "calibration"},
        "policy": {"kind": "fixed_threshold", "comparison": "strict_greater"},
        "missing_policy": "reject",
        "source_label_use": "none",
        "time_basis": "sample_index",
        "held_out": "not_reserved_or_evaluated",
    }


def config_id_of(resolved):
    text = json.dumps(resolved, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def input_hash_of(values):
    text = json.dumps(list(values), separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _seg_info(windows, start, stop, stride, length):
    if not windows:
        return {"bounds": [start, stop], "window_count": 0, "first_end": None,
                "last_end": None, "dropped_tail": stop - start}
    last_start = start + (len(windows) - 1) * stride
    dropped = stop - (last_start + length)
    return {"bounds": [start, stop], "window_count": len(windows),
            "first_end": windows[0].end_index, "last_end": windows[-1].end_index,
            "dropped_tail": dropped}


def compute_trace(config, values=None):
    resolved = validate_config(config)
    n = resolved["input"]["length"]
    if values is None:
        vals = loading.synthetic_values(
            n, resolved["input"]["pattern"], resolved["input"]["offsets"])
    else:
        vals = loading.load_values(values)
        if len(vals) != n:
            raise ValueError(f"values length {len(vals)} != input length {n}")
    ihash = input_hash_of(vals)
    cid = config_id_of(resolved)
    wl, st = resolved["window"]["length"], resolved["window"]["stride"]
    segs = resolved["segments"]
    src = vals[segs["source_fit"][0]:segs["source_fit"][1]]
    if len(src) < 2:
        raise ValueError("need at least two source samples")
    scorer = scoring.MeanDistanceScorer.fit(src, epsilon=resolved["scoring"]["epsilon"])
    wins = {}
    for name in ("source_fit", "calibration", "replay"):
        s, e = segs[name]
        wins[name] = splitting.make_windows(vals, s, e, wl, st, name)
    cal_scores = [scorer.score(w.values) for w in wins["calibration"]]
    quant = calibration.FixedQuantile.fit(
        cal_scores, quantile=resolved["calibration"]["quantile"],
        min_samples=resolved["calibration"]["min_samples"])
    pol = policy.FixedThresholdPolicy(threshold=quant.threshold)
    cal_rows = [{"window_id": w.window_id, "start_index": w.start_index,
                 "end_index": w.end_index, "score": scorer.score(w.values)}
                for w in wins["calibration"]]
    rows = []
    for w in wins["replay"]:
        s = scorer.score(w.values)
        rows.append({"window_id": w.window_id, "start_index": w.start_index,
                     "end_index": w.end_index, "score": s,
                     "output_state": pol.decide(s),
                     "threshold": float(quant.threshold), "config_id": cid})
    alerts = sum(1 for r in rows if r["output_state"] == "alert")
    diagnostics = {
        "config_id": cid,
        "input_hash": ihash,
        "generation_spec": {"kind": "synthetic_periodic_v1", "length": n,
                            "pattern": list(resolved["input"]["pattern"]),
                            "offsets": [dict(o) for o in resolved["input"]["offsets"]]},
        "scorer": {"mean": scorer.mean, "std": scorer.std, "epsilon": scorer.epsilon},
        "quantile": {"threshold": float(quant.threshold), "quantile": quant.quantile,
                     "sample_count": quant.sample_count, "method": quant.method},
        "segments": {k: _seg_info(wins[k], segs[k][0], segs[k][1], st, wl)
                     for k in ("source_fit", "calibration", "replay")},
        "warmup_samples": wl - 1,
        "replay_windows": len(rows),
        "alert_count": alerts,
        "alert_fraction": (alerts / len(rows)) if rows else 0.0,
        "decision_coverage": 1.0 if rows else 0.0,
    }
    return {"config": resolved, "config_id": cid, "values": vals,
            "input_hash": ihash,
            "scorer": {"mean": scorer.mean, "std": scorer.std,
                       "epsilon": scorer.epsilon},
            "threshold": float(quant.threshold),
            "quantile": {"threshold": float(quant.threshold),
                         "quantile": quant.quantile,
                         "sample_count": quant.sample_count,
                         "method": quant.method},
            "rows": rows, "calibration_rows": cal_rows,
            "diagnostics": diagnostics}


def _peak_allocation():
    _, peak = tracemalloc.get_traced_memory()
    return int(peak)


def _traces_match(expected, provided):
    for key in ("config_id", "input_hash", "threshold", "rows",
                "calibration_rows", "diagnostics", "scorer", "quantile"):
        if key not in provided or expected.get(key) != provided.get(key):
            return False
    return True


def write_output(config, trace, output_dir):
    t0 = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    own_tracing = not tracemalloc.is_tracing()
    if own_tracing:
        tracemalloc.start()
    try:
        resolved = validate_config(config)
        # Validation recomputation: persist only the synthetic recipe.
        # Reject values-override or hand-edited traces before any output.
        expected = compute_trace(resolved)
        if not isinstance(trace, dict) or not _traces_match(expected, trace):
            raise ValueError("trace does not match recomputed expected trace")
        cid = expected["config_id"]
        rows = expected["rows"]
        cal_rows = expected["calibration_rows"]
        diagnostics = expected["diagnostics"]
        peak = _peak_allocation()
        elapsed = time.monotonic() - t0
        run_id = uuid.uuid4().hex
        full_rows = [dict(r, run_id=run_id) for r in rows]
        repo = provenance.repo_root()
        metadata = {
            "run_id": run_id,
            "config_id": cid,
            "input_hash": expected.get("input_hash"),
            "started_at": started,
            "started_at_scope": "write_output_entry",
            "intended_day1": INTENDED_DAY1,
            "command": provenance.command_record(),
            "environment": provenance.environment_record(),
            "git": provenance.git_record(str(repo)),
            "file_hashes": provenance.file_hashes(repo),
            "resource_scope": RESOURCE_SCOPE,
            "elapsed_monotonic_seconds": elapsed,
            "peak_python_allocation_bytes": peak,
        }
        writing.write_run(output_dir, full_rows, resolved, metadata,
                           diagnostics, cal_rows)
        return run_id
    finally:
        if own_tracing:
            tracemalloc.stop()


def _load_file(path):
    def _const(x):
        raise ValueError(f"non-finite constant: {x}")
    with open(path) as fh:
        data = json.load(fh, parse_constant=_const)
    return validate_config(data)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    resolved = _load_file(args.config)
    trace = compute_trace(resolved)
    run_id = write_output(resolved, trace, args.output)
    print(run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
