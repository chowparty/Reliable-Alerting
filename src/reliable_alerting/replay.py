"""Day-04 replay/persistence: fixed + hysteresis over one saved score run.

Why: the source pipeline fits once on the original run; both policies replay
the same saved validated score rows without labels. Both policies replay,
both episode sets form, and all label-free files persist to the exclusive
output BEFORE labels are opened once. A label failure then leaves a
documented incomplete output (no evaluation/metadata/completion files)
which load_family rejects. The generic evaluator joins labels afterwards.

Budget tolerance is a reporting criterion, not a rejection gate:
infeasible rows are preserved with actual rate/coverage plus a feasible
bool and reasons (see assess_feasibility).

Checksums vs recompute: unkeyed artifact checksums detect ordinary
mutation; coordinated scientific tamper (even with refreshed checksums)
is detected via recompute (source recipe recompute + fresh-state replay +
evaluation recompute). Per-entry score identity rides on the parent
family metadata via source_scores_id; entries link back through
window keys plus config/run/replay identity.

Public API:
  replay_rows(score_rows, policy_config, config_id, run_id)
    -> {"predictions", "state", "policy", "config_id", "run_id",
        "replay_version"}.
  assess_feasibility(episode_count, decision_count, coverage, protocol)
    -> {"episode_rate_per_1000_decisions", "decision_coverage",
        "feasible", "reasons"}.
  write_state_json(path, state) / read_state_json(path): validated
    sidecar write (exclusive) / read with exact typed checks.
  replay_id_for(config_id, run_id): version-bound replay identity.
  run_family(source_run, protocol_path, evaluation_config_path, labels_path,
             output_dir) -> {"family_id", "output", ...}.
  load_family(path) -> verified report dict for the evidence module.
  load_family_predictions(path, policy_name) -> generic prediction rows.

CLI:
  python -m reliable_alerting.replay --run ... --protocol ...
      --evaluation-config ... --labels ... --output ...

State sidecar semantics (temporal-replay-v1): each entry records the score
identity, the latch before/after, the judging threshold and the comparator
used for that decision. Fixed is stateless: before_state is always "normal"
(a documented placeholder, not a latch), high == low == judging threshold,
comparator "strict_greater". Hysteresis: a normal latch tests high with
"strict_greater"; an alert latch tests low with "strict_less" (exit test).
"""
import argparse
import copy
import csv
import hashlib
import json
import math
import time
import tracemalloc
import uuid
from datetime import datetime, timezone
from pathlib import Path

from reliable_alerting import evaluation, evaluation_io, evidence, pipeline, policy, provenance

REPLAY_VERSION = "temporal-replay-v1"
INTENDED_DAY = "2026-09-22"
LOW_RATIO = 0.8
EPISODE_RATE_TOLERANCE_PER_1000 = 250
COVERAGE_FLOOR = 1.0
RESOURCE_SCOPE = "saved_scores_validation_recompute_replay_label_free_persist_single_label_open_and_family_evaluation"
RESOURCE_SCOPE_INHERITED = RESOURCE_SCOPE + "_inherited_tracing"
RESOURCE_DESCRIPTION = (
    "source run validation recompute + strict protocol/schedule checks + "
    "label-free replay of both policies (validation + row allocation timed) "
    "+ episode formation + label-free file creation/writes (source and "
    "per-policy predictions/state/configs) + single labels read + generic "
    "evaluation + artifact serialization/hash; "
    "EXCLUDES provenance capture (command/environment/git/file hashes) "
    "and completion file writes (labels, evaluations, metadata)"
)

POLICY_NAMES = ("fixed", "hysteresis")
POLICY_KIND = {"fixed": "fixed_threshold", "hysteresis": "hysteresis"}

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

STATE_COLUMNS = (
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

SOURCE_SCORES_COLUMNS = ("window_id", "start_index", "end_index", "score")

SOURCE_RUN_KEYS = ("path", "run_id", "config_id")

POLICY_SUMMARY_KEYS = (
    "config_id", "run_id", "replay_id", "policy_kind",
    "policy_replay_seconds", "episode_count", "decision_count",
    "episode_rate_per_1000_decisions", "decision_coverage", "feasible",
)

POLICY_METADATA_KEYS = (
    "policy", "policy_config", "config_id", "run_id", "replay_id",
    "replay_version", "family_id", "source_scores_id",
    "evaluation_config_id", "semantic_predictions_sha256",
    "semantic_label_sha256", "episode_count", "decision_count",
    "episode_rate_per_1000_decisions", "decision_coverage",
    "feasible", "feasibility_reasons", "policy_replay_seconds",
)

FAMILY_METADATA_KEYS = (
    "family_id", "replay_version", "intended_day", "source_run",
    "source_config_id", "source_scores_id", "threshold_high",
    "threshold_low", "policies", "evaluation_config_id", "created_at",
    "created_at_scope", "command", "environment", "git", "file_hashes",
    "artifact_sha256", "resource_scope", "resource_description",
    "allocation_note", "elapsed_monotonic_seconds",
    "peak_python_allocation_bytes",
)

ALLOWED_ARTIFACTS = frozenset((
    "protocol.json",
    "evaluation_config.json",
    "source_config.json",
    "source_diagnostics.json",
    "source_scores.csv",
    "source_calibration_scores.csv",
    "labels.json",
    "fixed/policy_config.json",
    "fixed/predictions.csv",
    "fixed/state.json",
    "fixed/evaluation.json",
    "fixed/metadata.json",
    "hysteresis/policy_config.json",
    "hysteresis/predictions.csv",
    "hysteresis/state.json",
    "hysteresis/evaluation.json",
    "hysteresis/metadata.json",
))


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


def _strict_num(v, name):
    """Exact typed number: int/float only (bools/strings rejected)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a number")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite")
    return f


def _strict_int(v, name):
    if type(v) is not int:
        raise TypeError(f"{name} must be an int")
    if v < 0:
        raise ValueError(f"{name} must be >= 0")
    return v


def _require_id(value, name):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if value.strip() == "":
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_sha(value, name):
    _require_id(value, name)
    if len(value) != 64 or any(c not in "0123456789abcdef"
                               for c in value.lower()):
        raise ValueError(f"{name} must be a sha256 hex digest")
    return value


def _exact(d, allowed, where):
    if not isinstance(d, dict):
        raise TypeError(f"{where} must be a dict")
    keys = set(d.keys())
    if keys != set(allowed):
        missing = set(allowed) - keys
        extra = keys - set(allowed)
        raise ValueError(
            f"{where} must have exactly {allowed} (missing={missing} extra={extra})")
    return d


def validate_protocol(doc):
    """Validate the predeclared family protocol (strict, label-free)."""
    _exact(doc,
           ["schema_version", "scope", "policies", "high_source", "low_ratio",
            "initial_state", "tie_rule", "settings_per_policy",
            "episode_rate_tolerance_per_1000_decisions", "coverage_floor",
            "quality_selection", "recall_targets",
            "authoritative_operating_record", "notes"],
           "protocol")
    if not _is_int(doc["schema_version"]) or doc["schema_version"] != 1:
        raise ValueError("protocol schema_version must be 1")
    if doc["scope"] != "synthetic_engineering_only":
        raise ValueError("protocol scope must be 'synthetic_engineering_only'")
    if list(doc["policies"]) != ["fixed", "hysteresis"]:
        raise ValueError("protocol policies must be ['fixed', 'hysteresis']")
    if doc["high_source"] != "frozen_source_calibration_threshold":
        raise ValueError("protocol high_source must be 'frozen_source_calibration_threshold'")
    if _num(doc["low_ratio"], "low_ratio") != LOW_RATIO:
        raise ValueError(f"protocol low_ratio must be {LOW_RATIO}")
    if doc["initial_state"] != "normal":
        raise ValueError("protocol initial_state must be 'normal'")
    if doc["tie_rule"] != "hold":
        raise ValueError("protocol tie_rule must be 'hold'")
    if not _is_int(doc["settings_per_policy"]) or doc["settings_per_policy"] != 1:
        raise ValueError("protocol settings_per_policy must be 1")
    if _num(doc["episode_rate_tolerance_per_1000_decisions"],
            "episode_rate_tolerance") != EPISODE_RATE_TOLERANCE_PER_1000:
        raise ValueError("protocol episode-rate tolerance must be 250")
    if _num(doc["coverage_floor"], "coverage_floor") != COVERAGE_FLOOR:
        raise ValueError("protocol coverage_floor must be 1.0")
    if doc["quality_selection"] != "none":
        raise ValueError("protocol quality_selection must be 'none'")
    if doc["recall_targets"] != "none":
        raise ValueError("protocol recall_targets must be 'none'")
    if doc["authoritative_operating_record"] is not False:
        raise ValueError("protocol authoritative_operating_record must be false")
    _require_id(doc["notes"], "notes")
    return {
        "schema_version": 1,
        "scope": "synthetic_engineering_only",
        "policies": ["fixed", "hysteresis"],
        "high_source": "frozen_source_calibration_threshold",
        "low_ratio": LOW_RATIO,
        "initial_state": "normal",
        "tie_rule": "hold",
        "settings_per_policy": 1,
        "episode_rate_tolerance_per_1000_decisions": EPISODE_RATE_TOLERANCE_PER_1000,
        "coverage_floor": COVERAGE_FLOOR,
        "quality_selection": "none",
        "recall_targets": "none",
        "authoritative_operating_record": False,
        "notes": doc["notes"],
    }


def validate_policy_config(policy_config):
    """Validate structure (frozen-threshold checks live in run_family)."""
    if not isinstance(policy_config, dict):
        raise TypeError("policy_config must be a dict")
    kind = policy_config.get("kind")
    if kind == "fixed_threshold":
        _exact(policy_config, ["kind", "comparison", "threshold"], "policy_config")
        if policy_config["comparison"] != "strict_greater":
            raise ValueError("fixed comparison must be 'strict_greater'")
        return {"kind": "fixed_threshold", "comparison": "strict_greater",
                "threshold": _num(policy_config["threshold"], "threshold")}
    if kind == "hysteresis":
        _exact(policy_config, ["kind", "low", "high"], "policy_config")
        low = _num(policy_config["low"], "low")
        high = _num(policy_config["high"], "high")
        if not low < high:
            raise ValueError("hysteresis low must be below high")
        return {"kind": "hysteresis", "low": low, "high": high}
    raise ValueError("policy kind must be 'fixed_threshold' or 'hysteresis'")


def policy_config_id(resolved):
    text = json.dumps(resolved, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def replay_id_for(config_id, run_id):
    """Version-bound replay identity: sha256(config_id:run_id:version)."""
    _require_id(config_id, "config_id")
    _require_id(run_id, "run_id")
    return hashlib.sha256(
        f"{config_id}:{run_id}:{REPLAY_VERSION}".encode()).hexdigest()


def source_scores_id(scores, source_identity):
    """Identity of shared scores + source input/scorer/calibration/boundary."""
    _exact(source_identity,
           ["input_hash", "scorer", "threshold_high", "replay_bounds",
            "window_length", "window_stride", "source_config_id"],
           "source_identity")
    payload = {
        "scores": [{k: s[k] for k in SOURCE_SCORES_COLUMNS} for s in scores],
        "source_identity": source_identity,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def assess_feasibility(episode_count, decision_count, coverage, protocol):
    """Report budget feasibility; never rejects (reporting criterion)."""
    if type(episode_count) is not int or episode_count < 0:
        raise TypeError("episode_count must be an int >= 0")
    if type(decision_count) is not int or decision_count < 1:
        raise TypeError("decision_count must be an int >= 1")
    coverage = _num(coverage, "coverage")
    tolerance = _num(protocol["episode_rate_tolerance_per_1000_decisions"],
                     "episode_rate_tolerance")
    floor = _num(protocol["coverage_floor"], "coverage_floor")
    rate = episode_count / decision_count * 1000
    reasons = []
    if rate > tolerance:
        reasons.append(
            f"episode rate {rate} per 1000 decisions above tolerance {tolerance}")
    if coverage < floor:
        reasons.append(
            f"decision coverage {coverage} below floor {floor}")
    return {"episode_rate_per_1000_decisions": float(rate),
            "decision_coverage": float(coverage),
            "feasible": not reasons,
            "reasons": reasons}


def _validate_score_rows(score_rows):
    if score_rows is None or isinstance(score_rows, (str, bytes, dict)):
        raise TypeError("score_rows must be a non-empty sequence of dicts")
    try:
        items = list(score_rows)
    except TypeError:
        raise TypeError("score_rows must be a non-empty sequence of dicts")
    if not items:
        raise ValueError("score_rows must not be empty")
    out = []
    seen = set()
    prev_end = None
    for entry in items:
        if not isinstance(entry, dict):
            raise TypeError("each score row must be a dict")
        _exact(entry, ["window_id", "start_index", "end_index", "score"],
               "score row")
        window_id = _require_id(entry["window_id"], "window_id")
        start = entry["start_index"]
        end = entry["end_index"]
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise TypeError("start_index must be an int >= 0")
        if isinstance(end, bool) or not isinstance(end, int) or end < 0:
            raise TypeError("end_index must be an int >= 0")
        if start > end:
            raise ValueError("start_index must be <= end_index")
        score = _num(entry["score"], "score")
        if window_id in seen:
            raise ValueError("duplicate window_id")
        seen.add(window_id)
        if prev_end is not None and end <= prev_end:
            raise ValueError("end_index must be strictly increasing")
        prev_end = end
        out.append({"window_id": window_id, "start_index": start,
                    "end_index": end, "score": score})
    return out


def replay_rows(score_rows, policy_config, config_id, run_id):
    """Replay one policy over saved score rows (label-free, fresh state)."""
    scores = _validate_score_rows(score_rows)
    resolved = validate_policy_config(policy_config)
    config_id = _require_id(config_id, "config_id")
    run_id = _require_id(run_id, "run_id")
    if resolved["kind"] == "fixed_threshold":
        pol = policy.FixedThresholdPolicy(threshold=resolved["threshold"])
        high = low = float(resolved["threshold"])
    else:
        pol = policy.HysteresisPolicy(low=resolved["low"], high=resolved["high"])
        high, low = float(resolved["high"]), float(resolved["low"])
    predictions = []
    state = []
    for row in scores:
        if resolved["kind"] == "fixed_threshold":
            before = "normal"
            judging, comparator = high, "strict_greater"
            after = pol.decide(row["score"])
        else:
            before = pol.state
            if before == "normal":
                judging, comparator = high, "strict_greater"
            else:
                judging, comparator = low, "strict_less"
            after = pol.decide(row["score"])
        predictions.append({
            "window_id": row["window_id"], "start_index": row["start_index"],
            "end_index": row["end_index"], "score": row["score"],
            "output_state": after, "threshold": judging,
            "config_id": config_id, "run_id": run_id,
        })
        state.append({
            "window_id": row["window_id"], "start_index": row["start_index"],
            "end_index": row["end_index"], "score": row["score"],
            "availability_end": row["end_index"],
            "before_state": before, "after_state": after,
            "high": high, "low": low, "judging_threshold": judging,
            "comparator": comparator, "policy_kind": resolved["kind"],
            "config_id": config_id, "run_id": run_id,
            "replay_version": REPLAY_VERSION,
        })
    return {"predictions": predictions, "state": state, "policy": resolved,
            "config_id": config_id, "run_id": run_id,
            "replay_version": REPLAY_VERSION}


def _validate_state_entries(doc):
    if not isinstance(doc, list) or not doc:
        raise ValueError("state must be a non-empty list")
    out = []
    for entry in doc:
        if not isinstance(entry, dict):
            raise TypeError("each state entry must be a dict")
        _exact(entry, list(STATE_COLUMNS), "state entry")
        out.append(dict(entry))
    seen = set()
    prev_end = None
    for entry in out:
        wid = _require_id(entry["window_id"], "window_id")
        start = _strict_int(entry["start_index"], "start_index")
        end = _strict_int(entry["end_index"], "end_index")
        avail = _strict_int(entry["availability_end"], "availability_end")
        if start > end:
            raise ValueError("state start_index must be <= end_index")
        if avail != end:
            raise ValueError("state availability_end must equal end_index")
        _strict_num(entry["score"], "score")
        _strict_num(entry["high"], "high")
        _strict_num(entry["low"], "low")
        _strict_num(entry["judging_threshold"], "judging_threshold")
        if entry["before_state"] not in ("normal", "alert"):
            raise ValueError("before_state must be 'normal' or 'alert'")
        if entry["after_state"] not in ("normal", "alert"):
            raise ValueError("after_state must be 'normal' or 'alert'")
        if entry["comparator"] not in ("strict_greater", "strict_less"):
            raise ValueError("comparator must be 'strict_greater' or 'strict_less'")
        if entry["policy_kind"] not in ("fixed_threshold", "hysteresis"):
            raise ValueError("policy_kind must be 'fixed_threshold' or 'hysteresis'")
        _require_id(entry["config_id"], "config_id")
        _require_id(entry["run_id"], "run_id")
        if entry["replay_version"] != REPLAY_VERSION:
            raise ValueError(f"replay_version must be {REPLAY_VERSION!r}")
        if wid in seen:
            raise ValueError("duplicate state window_id")
        seen.add(wid)
        if prev_end is not None and end <= prev_end:
            raise ValueError("state end_index must be strictly increasing")
        prev_end = end
    return out


def write_state_json(path, state):
    """Validate sidecar entries and write them to a new file only."""
    entries = _validate_state_entries(state)
    text = json.dumps(entries, sort_keys=True, indent=2,
                      allow_nan=False) + "\n"
    with open(path, "x") as fh:
        fh.write(text)
    return str(path)


def read_state_json(path):
    """Read and strictly validate a persisted state sidecar."""
    return _validate_state_entries(evaluation_io.load_strict_json(path))


def _load_state_json(path):
    return read_state_json(path)


def _predictions_csv_text(rows):
    import io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(list(PREDICTIONS_COLUMNS))
    for r in rows:
        writer.writerow([r["window_id"], r["start_index"], r["end_index"],
                         repr(float(r["score"])), r["output_state"],
                         repr(float(r["threshold"])), r["config_id"],
                         r["run_id"]])
    return out.getvalue()


def _scores_csv_text(scores):
    import io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(list(SOURCE_SCORES_COLUMNS))
    for s in scores:
        writer.writerow([s["window_id"], s["start_index"], s["end_index"],
                         repr(float(s["score"]))])
    return out.getvalue()


def _calibration_csv_text(calibration_rows):
    import io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["window_id", "start_index", "end_index", "score"])
    for r in calibration_rows:
        writer.writerow([r["window_id"], r["start_index"], r["end_index"],
                         repr(float(r["score"]))])
    return out.getvalue()


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n"


def file_sha256_bytes(data: bytes):
    return hashlib.sha256(data).hexdigest()


def _refuse_symlink_chain(path, label):
    """Refuse symlinks on the path and every ancestor up to the workspace.

    Narrow confinement: walks the target plus all parents (so a symlinked
    policy directory or family base cannot bypass the target-only check),
    stopping at the workspace root. Never follows outside symlinks.
    """
    p = Path(path)
    repo = provenance.repo_root()
    for cur in [p, *p.parents]:
        if cur.is_symlink():
            raise ValueError(f"{label}: symlink refused: {cur}")
        if cur == repo or cur == cur.parent:
            break
    return p


def _safe_path(base, rel):
    """Resolve an allowlisted artifact path, refusing symlinks/escapes."""
    if not isinstance(rel, str) or rel not in ALLOWED_ARTIFACTS:
        raise ValueError(f"artifact path not allowlisted: {rel!r}")
    return _refuse_symlink_chain(Path(base) / rel, f"artifact {rel!r}")


def run_family(source_run, protocol_path, evaluation_config_path, labels_path,
               output_dir):
    """Build one exclusive family dir from a verified source run.

    Phase A (label-free): verify source, protocol, schedule; replay BOTH
    policies; form BOTH episode sets; assess feasibility (reporting only).
    Phase B: persist all label-free files to the exclusive output.
    Phase C: open labels ONCE; evaluate both; write completion metadata.
    A label failure leaves a documented incomplete output without
    evaluation/metadata/completion files.
    """
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError(f"output directory already exists: {out}")
    # Refuse symlinked supplied paths before reading anything.
    _refuse_symlink_chain(source_run, "source_run")
    _refuse_symlink_chain(protocol_path, "protocol")
    _refuse_symlink_chain(evaluation_config_path, "evaluation_config")
    _refuse_symlink_chain(labels_path, "labels")
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    own_tracing = not tracemalloc.is_tracing()
    if own_tracing:
        tracemalloc.start()
    try:
        # Phase A: label-free. Single source validation per family
        # (load_family re-verifies).
        run = evidence._read_run(source_run)
        diffs = []
        if not evidence._verify_recompute("source", run, diffs):
            raise ValueError(f"source run failed recompute verification: {diffs}")
        protocol = validate_protocol(
            evaluation_io.load_strict_json(protocol_path))
        raw_eval = evaluation_io.load_strict_json(evaluation_config_path)
        resolved_eval = evaluation.validate_evaluation_config(raw_eval)
        evaluation_io.validate_schedule_against_runtime(
            resolved_eval, run["resolved"])
        source_rows = run["predictions"]
        high = float(run["diagnostics"]["quantile"]["threshold"])
        for r in source_rows:
            if float(r["threshold"]) != high:
                raise ValueError("source run must carry one frozen threshold")
        low = LOW_RATIO * high
        if not (math.isfinite(low) and 0 < low < high):
            raise ValueError("collapsed low (zero/negative/>=high) is inappropriate")
        scores = [{"window_id": r["window_id"], "start_index": r["start_index"],
                   "end_index": r["end_index"], "score": float(r["score"])}
                  for r in source_rows]
        source_identity = {
            "input_hash": run["metadata"].get("input_hash"),
            "scorer": dict(run["diagnostics"]["scorer"]),
            "threshold_high": high,
            "replay_bounds": list(run["resolved"]["segments"]["replay"]),
            "window_length": run["resolved"]["window"]["length"],
            "window_stride": run["resolved"]["window"]["stride"],
            "source_config_id": run["recomputed"],
        }
        scores_id = source_scores_id(scores, source_identity)
        family_id = uuid.uuid4().hex
        eval_cid = evaluation_io.evaluation_config_id(resolved_eval)
        policy_specs = [
            ("fixed", {"kind": "fixed_threshold",
                       "comparison": "strict_greater", "threshold": high}),
            ("hysteresis", {"kind": "hysteresis", "low": low, "high": high}),
        ]
        replayed_policies = {}
        for name, cfg in policy_specs:
            # Timer covers policy validation + replay row allocation.
            t_policy = time.perf_counter()
            resolved_policy = validate_policy_config(cfg)
            cid = policy_config_id(resolved_policy)
            rid = uuid.uuid4().hex
            replayed = replay_rows(scores, resolved_policy, cid, rid)
            policy_seconds = time.perf_counter() - t_policy
            rows = replayed["predictions"]
            # Label-free episode formation for BOTH policies here.
            episodes = evaluation.form_episodes(
                rows, copy.deepcopy(resolved_eval))
            n = len(rows)
            covered = sum(1 for r in rows
                          if r["output_state"] in ("normal", "alert"))
            feasibility = assess_feasibility(
                len(episodes), n, covered / n,
                {"episode_rate_tolerance_per_1000_decisions":
                 protocol["episode_rate_tolerance_per_1000_decisions"],
                 "coverage_floor": protocol["coverage_floor"]})
            replayed_policies[name] = {
                "policy": resolved_policy, "config_id": cid, "run_id": rid,
                "replay_id": replay_id_for(cid, rid),
                "rows": rows, "state": replayed["state"],
                "episodes": episodes,
                "feasibility": feasibility,
                "policy_replay_seconds": policy_seconds,
            }
        label_free_files = {
            "protocol.json": _canonical(protocol).encode(),
            "evaluation_config.json": _canonical(resolved_eval).encode(),
            "source_config.json": _canonical(run["resolved"]).encode(),
            "source_diagnostics.json": _canonical(run["diagnostics"]).encode(),
            "source_scores.csv": _scores_csv_text(scores).encode(),
            "source_calibration_scores.csv":
                _calibration_csv_text(run["calibration"]).encode(),
        }
        for name, rep in replayed_policies.items():
            label_free_files[f"{name}/policy_config.json"] = _canonical(
                rep["policy"]).encode()
            label_free_files[f"{name}/predictions.csv"] = _predictions_csv_text(
                rep["rows"]).encode()
            label_free_files[f"{name}/state.json"] = _canonical(
                rep["state"]).encode()
        # Phase B: persist label-free files before labels are consulted.
        out.mkdir(parents=True, exist_ok=False)
        for rel, data in label_free_files.items():
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "xb") as fh:
                fh.write(data)
        # Phase C: open labels ONCE, then complete the family.
        labels = evaluation_io.load_strict_json(labels_path)
        sem_label = evaluation_io.semantic_label_hash(labels)
        completion_files = {
            "labels.json": _canonical(labels).encode(),
        }
        policy_reports = {}
        for name, rep in replayed_policies.items():
            core = evaluation.evaluate(rep["rows"], copy.deepcopy(labels),
                                       copy.deepcopy(resolved_eval))
            sem_pred = evaluation_io.semantic_predictions_hash(rep["rows"])
            feas = rep["feasibility"]
            policy_meta = {
                "policy": name,
                "policy_config": rep["policy"],
                "config_id": rep["config_id"],
                "run_id": rep["run_id"],
                "replay_id": rep["replay_id"],
                "replay_version": REPLAY_VERSION,
                "family_id": family_id,
                "source_scores_id": scores_id,
                "evaluation_config_id": eval_cid,
                "semantic_predictions_sha256": sem_pred,
                "semantic_label_sha256": sem_label,
                "episode_count": len(rep["episodes"]),
                "decision_count": len(rep["rows"]),
                "episode_rate_per_1000_decisions":
                    feas["episode_rate_per_1000_decisions"],
                "decision_coverage": feas["decision_coverage"],
                "feasible": feas["feasible"],
                "feasibility_reasons": list(feas["reasons"]),
                "policy_replay_seconds": rep["policy_replay_seconds"],
            }
            completion_files[f"{name}/evaluation.json"] = _canonical(
                core).encode()
            completion_files[f"{name}/metadata.json"] = _canonical(
                policy_meta).encode()
            policy_reports[name] = {
                "config_id": rep["config_id"], "run_id": rep["run_id"],
                "replay_id": rep["replay_id"],
                "evaluation": core, "metadata": policy_meta,
                "policy_replay_seconds": rep["policy_replay_seconds"],
                "feasible": feas["feasible"],
            }
        artifacts = {rel: file_sha256_bytes(data)
                     for rel, data in label_free_files.items()}
        artifacts.update({rel: file_sha256_bytes(data)
                          for rel, data in completion_files.items()})
        if own_tracing:
            _, peak = tracemalloc.get_traced_memory()
            peak_val = int(peak)
            scope = RESOURCE_SCOPE
            alloc_note = "scoped_tracemalloc"
        else:
            peak_val = None
            scope = RESOURCE_SCOPE_INHERITED
            alloc_note = "unmeasured_inherited_tracing"
        elapsed = time.monotonic() - t0
        repo = provenance.repo_root()
        # Provenance last among completion writes.
        metadata = {
            "family_id": family_id,
            "replay_version": REPLAY_VERSION,
            "intended_day": INTENDED_DAY,
            "source_run": {
                "path": str(source_run),
                "run_id": run["metadata"].get("run_id"),
                "config_id": run["metadata"].get("config_id"),
            },
            "source_config_id": run["recomputed"],
            "source_scores_id": scores_id,
            "threshold_high": high,
            "threshold_low": low,
            "policies": {name: {
                "config_id": rep["config_id"], "run_id": rep["run_id"],
                "replay_id": rep["replay_id"],
                "policy_kind": rep["policy"]["kind"],
                "policy_replay_seconds": rep["policy_replay_seconds"],
                "episode_count": len(rep["episodes"]),
                "decision_count": len(rep["rows"]),
                "episode_rate_per_1000_decisions":
                    rep["feasibility"]["episode_rate_per_1000_decisions"],
                "decision_coverage": rep["feasibility"]["decision_coverage"],
                "feasible": rep["feasibility"]["feasible"],
            } for name, rep in replayed_policies.items()},
            "evaluation_config_id": eval_cid,
            "created_at": started_at,
            "created_at_scope": "replay_entry",
            "command": provenance.command_record(),
            "environment": provenance.environment_record(),
            "git": provenance.git_record(str(repo)),
            "file_hashes": provenance.file_hashes(repo),
            "artifact_sha256": artifacts,
            "resource_scope": scope,
            "resource_description": RESOURCE_DESCRIPTION,
            "allocation_note": alloc_note,
            "elapsed_monotonic_seconds": elapsed,
            "peak_python_allocation_bytes": peak_val,
        }
        for rel, data in completion_files.items():
            with open(out / rel, "xb") as fh:
                fh.write(data)
        with open(out / "family_metadata.json", "x") as fh:
            fh.write(_canonical(metadata))
        return {"family_id": family_id, "output": str(out),
                "source_scores_id": scores_id,
                "source_config_id": run["recomputed"],
                "policies": policy_reports, "metadata": metadata,
                "resolved_protocol": protocol,
                "resolved_evaluation_config": resolved_eval}
    finally:
        if own_tracing:
            try:
                tracemalloc.stop()
            except Exception:
                pass


def load_family_predictions(path, policy_name):
    """Load one policy's family predictions via the generic loader."""
    if policy_name not in POLICY_NAMES:
        raise ValueError(f"policy must be one of {POLICY_NAMES}")
    return evaluation_io.load_predictions_generic(
        str(_safe_path(Path(path), f"{policy_name}/predictions.csv")))


def _validate_command(doc, label, diffs):
    ok = True
    if not isinstance(doc, dict):
        diffs.append(f"{label}: command must be a dict")
        return False
    for key in ("shell", "argv", "orig_argv", "cwd",
                "rerun_shell", "rerun_executable"):
        if key not in doc:
            diffs.append(f"{label}: command.{key} missing")
            ok = False
    for key in ("shell", "cwd", "rerun_shell", "rerun_executable"):
        v = doc.get(key)
        if not isinstance(v, str) or v.strip() == "":
            diffs.append(f"{label}: command.{key} empty")
            ok = False
    return ok


def _validate_git(doc, label, diffs):
    ok = True
    if not isinstance(doc, dict):
        diffs.append(f"{label}: git must be a dict")
        return False
    head = doc.get("head")
    if not isinstance(head, str) or head.strip() == "":
        diffs.append(f"{label}: git.head missing or empty")
        ok = False
    for key in ("branch", "status_porcelain"):
        if key not in doc or not isinstance(doc.get(key), str):
            diffs.append(f"{label}: git.{key} missing")
            ok = False
    return ok


def _validate_file_hashes(doc, label, diffs):
    if not isinstance(doc, dict):
        diffs.append(f"{label}: file_hashes must be a dict")
        return False
    ok = True
    if set(doc.keys()) != set(provenance.WHITELIST):
        diffs.append(f"{label}: file_hashes keys must equal provenance whitelist")
        ok = False
    for key, value in doc.items():
        try:
            _require_sha(value, f"{label}: file_hashes[{key}]")
        except (TypeError, ValueError):
            diffs.append(f"{label}: file_hashes[{key}] not a sha256 digest")
            ok = False
    return ok


def _validate_family_metadata(doc):
    """Exact-schema validation; returns a list of differences."""
    diffs = []
    try:
        _exact(doc, list(FAMILY_METADATA_KEYS), "family_metadata")
    except (TypeError, ValueError) as e:
        return [f"family_metadata schema: {e}"]
    _require_id(doc["family_id"], "family_id")
    if doc["replay_version"] != REPLAY_VERSION:
        diffs.append("family_metadata replay_version mismatch")
    _require_id(doc["intended_day"], "intended_day")
    try:
        _exact(doc["source_run"], list(SOURCE_RUN_KEYS), "source_run")
        for key in SOURCE_RUN_KEYS:
            _require_id(doc["source_run"][key], f"source_run.{key}")
    except (TypeError, ValueError) as e:
        diffs.append(f"family_metadata source_run: {e}")
    try:
        _require_sha(doc["source_config_id"], "source_config_id")
    except (TypeError, ValueError):
        diffs.append("family_metadata source_config_id not a sha256 digest")
    if not isinstance(doc.get("source_scores_id"), str) or not doc["source_scores_id"]:
        diffs.append("family_metadata source_scores_id missing or empty")
    high = doc.get("threshold_high")
    low = doc.get("threshold_low")
    try:
        high = _strict_num(high, "threshold_high")
        low = _strict_num(low, "threshold_low")
        if not 0 < low < high:
            diffs.append("family_metadata thresholds must satisfy 0 < low < high")
        if low != LOW_RATIO * high:
            diffs.append("family_metadata threshold_low != 0.8*threshold_high")
    except (TypeError, ValueError) as e:
        diffs.append(f"family_metadata thresholds: {e}")
    if not isinstance(doc.get("policies"), dict) or set(doc["policies"]) != set(POLICY_NAMES):
        diffs.append("family_metadata policies must hold exactly fixed+hysteresis")
    else:
        for name in POLICY_NAMES:
            try:
                _exact(doc["policies"][name], list(POLICY_SUMMARY_KEYS),
                       f"policies.{name}")
            except (TypeError, ValueError) as e:
                diffs.append(f"family_metadata policies.{name}: {e}")
                continue
            entry = doc["policies"][name]
            if entry["policy_kind"] != POLICY_KIND[name]:
                diffs.append(f"family_metadata policies.{name}: wrong policy kind")
            for key in ("config_id", "run_id", "replay_id"):
                if not isinstance(entry.get(key), str) or not entry[key]:
                    diffs.append(f"family_metadata policies.{name}.{key} invalid")
            for key in ("policy_replay_seconds",
                        "episode_rate_per_1000_decisions", "decision_coverage"):
                try:
                    v = _strict_num(entry.get(key), key)
                    if v < 0:
                        diffs.append(
                            f"family_metadata policies.{name}.{key} negative")
                except (TypeError, ValueError):
                    diffs.append(
                        f"family_metadata policies.{name}.{key} not a finite number")
            for key in ("episode_count", "decision_count"):
                floor = 0 if key == "episode_count" else 1
                if type(entry.get(key)) is not int or entry[key] < floor:
                    diffs.append(
                        f"family_metadata policies.{name}.{key} invalid")
            if not isinstance(entry.get("feasible"), bool):
                diffs.append(f"family_metadata policies.{name}.feasible not a bool")
    try:
        _require_sha(doc["evaluation_config_id"], "evaluation_config_id")
    except (TypeError, ValueError):
        diffs.append("family_metadata evaluation_config_id not a sha256 digest")
    _require_id(doc["created_at"], "created_at")
    _require_id(doc["created_at_scope"], "created_at_scope")
    _validate_command(doc.get("command"), "family_metadata", diffs)
    if not isinstance(doc.get("environment"), dict) or not doc["environment"]:
        diffs.append("family_metadata environment missing or empty")
    _validate_git(doc.get("git"), "family_metadata", diffs)
    _validate_file_hashes(doc.get("file_hashes"), "family_metadata", diffs)
    recorded = doc.get("artifact_sha256")
    if not isinstance(recorded, dict) or set(recorded) != set(ALLOWED_ARTIFACTS):
        diffs.append("family_metadata artifact_sha256 must cover exactly "
                     "the allowlisted artifacts")
    else:
        for rel, want in recorded.items():
            if not isinstance(want, str):
                diffs.append(f"family_metadata artifact {rel} hash not a string")
            elif len(want) != 64 or any(c not in "0123456789abcdef"
                                        for c in want.lower()):
                diffs.append(f"family_metadata artifact {rel} hash not sha256")
    if doc.get("resource_scope") not in (RESOURCE_SCOPE,
                                          RESOURCE_SCOPE_INHERITED):
        diffs.append("family_metadata resource_scope unexpected")
    if not isinstance(doc.get("resource_description"), str) \
            or not doc["resource_description"]:
        diffs.append("family_metadata resource_description missing")
    if not isinstance(doc.get("allocation_note"), str) or not doc["allocation_note"]:
        diffs.append("family_metadata allocation_note missing")
    try:
        elapsed = _strict_num(doc.get("elapsed_monotonic_seconds"),
                              "elapsed_monotonic_seconds")
        if elapsed < 0:
            diffs.append("family_metadata elapsed_monotonic_seconds negative")
    except (TypeError, ValueError):
        diffs.append("family_metadata elapsed_monotonic_seconds not a finite number")
    peak = doc.get("peak_python_allocation_bytes")
    if peak is not None and (type(peak) is not int or peak < 0):
        diffs.append("family_metadata peak_python_allocation_bytes invalid")
    return diffs


def _validate_policy_metadata(doc, name, family_id, scores_id, eval_cid):
    """Exact-schema + linkage validation for per-policy metadata."""
    diffs = []
    try:
        _exact(doc, list(POLICY_METADATA_KEYS), f"{name}/metadata")
    except (TypeError, ValueError) as e:
        return [f"{name}/metadata schema: {e}"]
    if doc["policy"] != name:
        diffs.append(f"{name}/metadata: policy name mismatch")
    try:
        resolved = validate_policy_config(doc["policy_config"])
    except (TypeError, ValueError) as e:
        diffs.append(f"{name}/metadata policy_config invalid: {e}")
        return diffs
    if resolved["kind"] != POLICY_KIND[name]:
        diffs.append(f"{name}/metadata: wrong policy kind for directory")
    cid = policy_config_id(resolved)
    if doc["config_id"] != cid:
        diffs.append(f"{name}/metadata: config_id != policy config hash")
    if not isinstance(doc.get("run_id"), str) or not doc["run_id"]:
        diffs.append(f"{name}/metadata run_id invalid")
    if doc.get("replay_id") != replay_id_for(doc["config_id"], doc["run_id"]):
        diffs.append(f"{name}/metadata: replay_id != version-bound identity")
    if doc.get("replay_version") != REPLAY_VERSION:
        diffs.append(f"{name}/metadata: replay_version mismatch")
    if doc.get("family_id") != family_id:
        diffs.append(f"{name}/metadata: family_id not linked")
    if doc.get("source_scores_id") != scores_id:
        diffs.append(f"{name}/metadata: source_scores_id not linked")
    if doc.get("evaluation_config_id") != eval_cid:
        diffs.append(f"{name}/metadata: evaluation_config_id not linked")
    for key in ("semantic_predictions_sha256", "semantic_label_sha256"):
        try:
            _require_sha(doc[key], f"{name}/metadata {key}")
        except (TypeError, ValueError):
            diffs.append(f"{name}/metadata {key} not a sha256 digest")
    for key in ("episode_count", "decision_count"):
        floor = 0 if key == "episode_count" else 1
        if type(doc.get(key)) is not int or doc[key] < floor:
            diffs.append(f"{name}/metadata {key} invalid")
    for key in ("episode_rate_per_1000_decisions", "decision_coverage",
                "policy_replay_seconds"):
        try:
            if _strict_num(doc.get(key), key) < 0:
                diffs.append(f"{name}/metadata {key} negative")
        except (TypeError, ValueError):
            diffs.append(f"{name}/metadata {key} not a finite number")
    if not isinstance(doc.get("feasible"), bool):
        diffs.append(f"{name}/metadata feasible not a bool")
    if not isinstance(doc.get("feasibility_reasons"), list) or not all(
            isinstance(r, str) for r in doc["feasibility_reasons"]):
        diffs.append(f"{name}/metadata feasibility_reasons must be a string list")
    return diffs


def load_family(path):
    """Rigorously verify a family dir; return a report dict for evidence.

    Order: strict JSON everywhere except labels first; source recipe
    recompute; shared score identity; per-policy frozen config +
    fresh-state replay equality + episode formation + per-policy metadata
    linkage; labels open only after both policies verify label-free; then
    evaluation recompute; artifact checksums over the exact allowlist;
    provenance schema. Historical file-hash drift is not a scientific
    failure (values schema-checked only).
    """
    base = Path(path)
    diffs = []
    ok = True

    def _fail(msg):
        nonlocal ok
        ok = False
        diffs.append(msg)

    try:
        meta_path = _refuse_symlink_chain(
            base / "family_metadata.json", "family_metadata.json")
    except ValueError as e:
        return {"path": str(base), "status": False,
                "differences": [f"family_metadata unreadable: {e}"]}
    try:
        metadata = evaluation_io.load_strict_json(str(meta_path))
    except Exception as e:
        return {"path": str(base), "status": False,
                "differences": [f"family_metadata unreadable: {e}"]}
    if not isinstance(metadata, dict):
        return {"path": str(base), "status": False,
                "differences": ["family_metadata must be a dict"]}
    for problem in _validate_family_metadata(metadata):
        _fail(problem)
    try:
        protocol = validate_protocol(
            evaluation_io.load_strict_json(str(_safe_path(base, "protocol.json"))))
    except Exception as e:
        _fail(f"protocol invalid: {e}")
        protocol = None
    try:
        eval_raw = evaluation_io.load_strict_json(
            str(_safe_path(base, "evaluation_config.json")))
        resolved_eval = evaluation.validate_evaluation_config(eval_raw)
    except Exception as e:
        _fail(f"evaluation config invalid: {e}")
        resolved_eval = None
    if resolved_eval is not None:
        try:
            eval_cid = evaluation_io.evaluation_config_id(resolved_eval)
        except Exception as e:
            _fail(f"evaluation config id unreadable: {e}")
            eval_cid = None
        if eval_cid is not None and metadata.get("evaluation_config_id") != eval_cid:
            _fail("metadata evaluation_config_id != persisted evaluation config")
    else:
        eval_cid = None
    try:
        source_raw = evaluation_io.load_strict_json(
            str(_safe_path(base, "source_config.json")))
        resolved_source = pipeline.validate_config(source_raw)
        recomputed_cid = pipeline.config_id_of(resolved_source)
    except Exception as e:
        _fail(f"source config invalid: {e}")
        resolved_source = None
        recomputed_cid = None
    expected = None
    if resolved_source is not None:
        try:
            expected = pipeline.compute_trace(resolved_source)
        except Exception as e:
            _fail(f"source recompute failed: {e}")
    scores = None
    try:
        with open(_safe_path(base, "source_scores.csv"), newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            if tuple(header) != tuple(SOURCE_SCORES_COLUMNS):
                raise ValueError("source_scores header mismatch")
            scores = []
            seen = set()
            prev_end = None
            for parts in reader:
                if len(parts) != len(SOURCE_SCORES_COLUMNS):
                    raise ValueError("source_scores row width mismatch")
                d = dict(zip(SOURCE_SCORES_COLUMNS, parts))
                wid = _require_id(d["window_id"], "window_id")
                try:
                    start = int(d["start_index"])
                    end = int(d["end_index"])
                    score = float(d["score"])
                except (TypeError, ValueError) as e:
                    raise ValueError(f"source_scores number parse: {e}") from e
                if start < 0 or end < 0:
                    raise ValueError("source_scores indices must be >= 0")
                if not math.isfinite(score):
                    raise ValueError("source score must be finite")
                if wid in seen:
                    raise ValueError("duplicate source window_id")
                seen.add(wid)
                if prev_end is not None and end <= prev_end:
                    raise ValueError("source end_index must increase")
                prev_end = end
                scores.append({"window_id": wid, "start_index": start,
                               "end_index": end, "score": score})
        if not scores:
            raise ValueError("source_scores must not be empty")
    except Exception as e:
        _fail(f"source_scores unreadable: {e}")
    if expected is not None and scores is not None:
        exp_scores = [{"window_id": r["window_id"],
                       "start_index": r["start_index"],
                       "end_index": r["end_index"],
                       "score": float(r["score"])}
                      for r in expected["rows"]]
        if scores != exp_scores:
            _fail("source_scores != recomputed source trace")
        try:
            calib = evidence._load_calibration_csv(
                str(_safe_path(base, "source_calibration_scores.csv")))
            if calib != expected["calibration_rows"]:
                _fail("source calibration != recomputed calibration")
        except Exception as e:
            _fail(f"source calibration unreadable: {e}")
        try:
            diag = evaluation_io.load_strict_json(
                str(_safe_path(base, "source_diagnostics.json")))
            if diag != expected["diagnostics"]:
                _fail("source diagnostics != recomputed diagnostics")
        except Exception as e:
            _fail(f"source diagnostics unreadable: {e}")
        if metadata.get("source_config_id") != recomputed_cid:
            _fail("metadata source_config_id != recomputed config_id")
    high = None
    if expected is not None:
        high = float(expected["diagnostics"]["quantile"]["threshold"])
        if metadata.get("threshold_high") != high:
            _fail("metadata threshold_high != recomputed high")
        if metadata.get("threshold_low") != LOW_RATIO * high:
            _fail("metadata threshold_low != 0.8*high")
    if (scores is not None and expected is not None
            and isinstance(metadata.get("source_scores_id"), str)
            and metadata["source_scores_id"]):
        source_identity = {
            "input_hash": expected.get("input_hash"),
            "scorer": dict(expected["diagnostics"]["scorer"]),
            "threshold_high": high,
            "replay_bounds": list(resolved_source["segments"]["replay"]),
            "window_length": resolved_source["window"]["length"],
            "window_stride": resolved_source["window"]["stride"],
            "source_config_id": recomputed_cid,
        }
        if source_scores_id(scores, source_identity) != metadata["source_scores_id"]:
            _fail("source_scores_id mismatch")
    elif not metadata.get("source_scores_id"):
        _fail("metadata source_scores_id missing")
    if resolved_eval is not None and resolved_source is not None:
        try:
            evaluation_io.validate_schedule_against_runtime(
                resolved_eval, resolved_source)
        except Exception as e:
            _fail(f"schedule invalid: {e}")
    # Label-free per-policy verification for BOTH policies first.
    verified = {}
    for name in POLICY_NAMES:
        try:
            policy_cfg = validate_policy_config(
                evaluation_io.load_strict_json(
                    str(_safe_path(base, f"{name}/policy_config.json"))))
        except Exception as e:
            _fail(f"policy {name} config invalid: {e}")
            continue
        if policy_cfg["kind"] != POLICY_KIND[name]:
            _fail(f"policy {name}: wrong policy kind for directory")
            continue
        if high is not None:
            if policy_cfg["kind"] == "fixed_threshold":
                if policy_cfg["threshold"] != high:
                    _fail(f"policy {name}: threshold != frozen high")
                    continue
            else:
                if policy_cfg["high"] != high:
                    _fail(f"policy {name}: high != frozen high")
                    continue
                if policy_cfg["low"] != LOW_RATIO * high:
                    _fail(f"policy {name}: low != 0.8*high")
                    continue
        cid = policy_config_id(policy_cfg)
        try:
            rows = evaluation_io.load_predictions_generic(
                str(_safe_path(base, f"{name}/predictions.csv")))
        except Exception as e:
            _fail(f"policy {name} predictions unreadable: {e}")
            continue
        if rows and rows[0]["config_id"] != cid:
            _fail(f"policy {name}: predictions config_id != policy config_id")
            continue
        summary = metadata.get("policies", {}).get(name, {})
        if summary.get("config_id") != cid:
            _fail(f"policy {name}: metadata config_id != policy config_id")
        if rows and summary.get("run_id") != rows[0]["run_id"]:
            _fail(f"policy {name}: metadata run_id != predictions run_id")
        if rows and summary.get("replay_id") != replay_id_for(
                cid, rows[0]["run_id"]):
            _fail(f"policy {name}: metadata replay_id != version-bound identity")
        try:
            persisted_state = read_state_json(
                str(_safe_path(base, f"{name}/state.json")))
        except Exception as e:
            _fail(f"policy {name} state unreadable: {e}")
            continue
        if scores is None:
            _fail(f"policy {name}: no verified scores to replay")
            continue
        # Fresh-state replay must reproduce persisted predictions + state.
        try:
            fresh = replay_rows(scores, policy_cfg, cid, rows[0]["run_id"])
            if fresh["predictions"] != rows:
                _fail(f"policy {name}: predictions != fresh state replay")
                continue
            if fresh["state"] != persisted_state:
                _fail(f"policy {name}: state != fresh state replay")
                continue
        except Exception as e:
            _fail(f"policy {name} replay failed: {e}")
            continue
        # Episodes form (and schedule validates) before labels are opened.
        if resolved_eval is not None:
            try:
                episodes = evaluation.form_episodes(
                    rows, copy.deepcopy(resolved_eval))
            except Exception as e:
                _fail(f"policy {name} episode formation failed: {e}")
                continue
        else:
            episodes = []
        try:
            pmeta = evaluation_io.load_strict_json(
                str(_safe_path(base, f"{name}/metadata.json")))
        except Exception as e:
            _fail(f"policy {name} metadata unreadable: {e}")
            continue
        for problem in _validate_policy_metadata(
                pmeta, name, metadata.get("family_id"),
                metadata.get("source_scores_id"), eval_cid):
            _fail(problem)
        if (pmeta.get("config_id") == cid and rows
                and pmeta.get("run_id") == rows[0]["run_id"]
                and pmeta.get("episode_count") == len(episodes)
                and pmeta.get("decision_count") == len(rows)):
            pass
        else:
            _fail(f"policy {name}: metadata counts/ids != replayed rows")
            continue
        if evaluation_io.semantic_predictions_hash(rows) != pmeta.get(
                "semantic_predictions_sha256"):
            _fail(f"policy {name}: semantic predictions hash mismatch")
            continue
        if summary.get("policy_replay_seconds") != pmeta.get(
                "policy_replay_seconds"):
            _fail(f"policy {name}: timing != family summary timing")
            continue
        verified[name] = {"rows": rows, "episodes": episodes,
                          "config_id": cid, "run_id": rows[0]["run_id"],
                          "metadata": pmeta}
    # Labels open only after BOTH policies verify label-free.
    labels = None
    if len(verified) == len(POLICY_NAMES):
        try:
            labels = evaluation_io.load_strict_json(
                str(_safe_path(base, "labels.json")))
        except Exception as e:
            _fail(f"labels unreadable: {e}")
    policy_reports = {}
    if labels is not None and resolved_eval is not None:
        if evaluation_io.semantic_label_hash(labels) != verified[
                POLICY_NAMES[0]]["metadata"].get("semantic_label_sha256"):
            _fail("semantic label hash mismatch")
        for name in POLICY_NAMES:
            if name not in verified:
                continue
            rows = verified[name]["rows"]
            try:
                recomputed = evaluation.evaluate(
                    rows, copy.deepcopy(labels), copy.deepcopy(resolved_eval))
            except Exception as e:
                _fail(f"policy {name} evaluation failed: {e}")
                continue
            try:
                persisted_eval = evaluation_io.load_strict_json(
                    str(_safe_path(base, f"{name}/evaluation.json")))
            except Exception as e:
                _fail(f"policy {name} evaluation unreadable: {e}")
                continue
            if recomputed != persisted_eval:
                _fail(f"policy {name}: persisted evaluation != recomputed")
                continue
            policy_reports[name] = {"config_id": verified[name]["config_id"],
                                    "run_id": verified[name]["run_id"],
                                    "evaluation": persisted_eval,
                                    "feasible": verified[name]["metadata"].get(
                                        "feasible")}
    # Artifact checksums: exact allowlist, no self reference.
    recorded = metadata.get("artifact_sha256")
    if not isinstance(recorded, dict) or set(recorded) != set(ALLOWED_ARTIFACTS):
        _fail("metadata artifact_sha256 must cover exactly the allowlisted artifacts")
    else:
        for rel in sorted(recorded):
            try:
                got = file_sha256_bytes(_safe_path(base, rel).read_bytes())
            except (OSError, ValueError) as e:
                _fail(f"artifact {rel} unreadable: {e}")
                continue
            if got != recorded[rel]:
                _fail(f"artifact {rel} checksum mismatch")
    return {"path": str(base), "status": bool(ok), "differences": diffs,
            "family_id": metadata.get("family_id"),
            "replay_version": REPLAY_VERSION,
            "source_scores_id": metadata.get("source_scores_id"),
            "source_config_id": metadata.get("source_config_id"),
            "evaluation_config_id": metadata.get("evaluation_config_id"),
            "policies": policy_reports}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reliable_alerting.replay")
    ap.add_argument("--run", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--evaluation-config", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    result = run_family(args.run, args.protocol, args.evaluation_config,
                        args.labels, args.output)
    print(json.dumps({"output": result["output"],
                      "family_id": result["family_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
