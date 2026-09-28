"""Offline evaluation persistence (saved predictions joined after verification).

Why: loads an existing saved run's predictions before opening labels,
forms episodes before labels are consulted, validates the evaluation
schedule against the saved runtime replay bounds/window, then persists
a self-contained evaluation directory with provenance.
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

from reliable_alerting import evaluation, provenance

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

_GENERIC_STATES = ("normal", "alert", "defer")
_RESOURCE_SCOPE = "saved_run_validation_recompute_and_evaluation_excluding_output"
_RESOURCE_SCOPE_INHERITED = (
    "saved_run_validation_recompute_and_evaluation_excluding_output_inherited_tracing"
)
_RESOURCE_DESCRIPTION = (
    "saved run validation + recompute + schedule check + generic load + "
    "episode formation + label join + hashing; excludes output directory "
    "creation and file writes"
)


def _require_id(value, name):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if value.strip() == "":
        raise ValueError(f"{name} must be non-empty")
    return value


def _parse_int(raw, name):
    if isinstance(raw, bool):
        raise TypeError(f"{name} must be an int")
    if isinstance(raw, int):
        v = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if s == "":
            raise ValueError(f"{name} must be >= 0")
        try:
            v = int(s)
        except ValueError as e:
            raise ValueError(f"{name} must be an int") from e
    else:
        raise TypeError(f"{name} must be an int")
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int")
    if v < 0:
        raise ValueError(f"{name} must be >= 0")
    return v


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


def load_predictions_generic(path):
    """Load predictions.csv accepting defer/varying thresholds (no score check)."""
    p = Path(path)
    with open(p, newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as e:
            raise ValueError("predictions.csv must not be empty") from e
        # Accept the base 8-column schema, or that schema plus a trailing
        # optional "features" column emitted by the multi-policy pipeline.
        # This generic loader already allows defer states and varying
        # thresholds and imposes no score/threshold consistency assumption;
        # only the base columns are consumed here.
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
            if state not in _GENERIC_STATES:
                raise ValueError("output_state must be 'normal', 'alert' or 'defer'")
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


def _reject_duplicate_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate object key: {k!r}")
        out[k] = v
    return out


def load_strict_json(path):
    """Load JSON rejecting NaN/Infinity and duplicate object keys."""
    def _const(x):
        raise ValueError(f"non-finite constant: {x}")
    with open(path) as fh:
        return json.load(fh, parse_constant=_const,
                         object_pairs_hook=_reject_duplicate_keys)


def write_strict_json(path, obj):
    text = json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(path, "w") as fh:
        fh.write(text)
    return text


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def semantic_predictions_hash(rows):
    """Hash substantive predictions excluding run_id only."""
    stripped = [{k: r[k] for k in PREDICTIONS_COLUMNS if k != "run_id"} for r in rows]
    text = json.dumps(stripped, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def semantic_label_hash(labels):
    text = json.dumps(labels, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def evaluation_config_id(resolved):
    text = json.dumps(resolved, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def validate_schedule_against_runtime(eval_resolved, runtime_resolved):
    """Check eval horizon/stride/window against runtime replay bounds/window."""
    h0, h1 = list(eval_resolved["horizon"])
    r0, r1 = list(runtime_resolved["segments"]["replay"])
    if [h0, h1] != [r0, r1]:
        raise ValueError(f"horizon {[h0, h1]} must equal runtime replay {[r0, r1]}")
    wl = runtime_resolved["window"]["length"]
    st = runtime_resolved["window"]["stride"]
    if eval_resolved["window_length"] != wl:
        raise ValueError("evaluation window_length must equal runtime window length")
    if eval_resolved["decision_stride"] != st:
        raise ValueError("evaluation decision_stride must equal runtime window stride")
    if eval_resolved["first_decision"] != r0 + wl - 1:
        raise ValueError("first_decision must equal replay_start + window_length - 1")
    return True


def evaluate_saved_predictions(predictions_path, labels_path, config):
    """Reusable join: predictions first, episodes before labels, then evaluate."""
    rows = load_predictions_generic(predictions_path)
    resolved = evaluation.validate_evaluation_config(copy.deepcopy(config))
    # Form episodes before consulting labels (ordering guarantee).
    evaluation.form_episodes(rows, resolved)
    labels = load_strict_json(labels_path)
    return evaluation.evaluate(rows, labels, resolved)


def run_evaluation(run_dir, labels_path, config_path, output_dir):
    """Verify saved run, join labels, persist exclusive evaluation directory."""
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError(f"output directory already exists: {out}")
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    own_tracing = not tracemalloc.is_tracing()
    if own_tracing:
        tracemalloc.start()
    try:
        # 1. Verify saved trace identity/config/linkage BEFORE opening labels.
        from reliable_alerting import evidence as _evidence
        run = _evidence._read_run(run_dir)
        diffs = []
        if not _evidence._verify_recompute("run", run, diffs):
            raise ValueError(f"saved run failed recompute verification: {diffs}")
        # 2. Load eval config (strict) before labels.
        raw_config = load_strict_json(config_path)
        resolved_eval = evaluation.validate_evaluation_config(raw_config)
        # 3. Schedule/horizon against runtime replay bounds/window.
        validate_schedule_against_runtime(resolved_eval, run["resolved"])
        # 4. Generic predictions (defer/varying allowed) before labels.
        rows = load_predictions_generic(Path(run_dir) / "predictions.csv")
        # 5. Form episodes before labels.
        evaluation.form_episodes(rows, resolved_eval)
        # 6. Now open labels.
        labels = load_strict_json(labels_path)
        core = evaluation.evaluate(rows, labels, resolved_eval)
        # Hashes of source inputs.
        pred_file = Path(run_dir) / "predictions.csv"
        pred_bytes = pred_file.read_bytes()
        pred_sha = hashlib.sha256(pred_bytes).hexdigest()
        persisted_pred_sha = hashlib.sha256(pred_bytes).hexdigest()
        sem_pred = semantic_predictions_hash(rows)
        label_src_sha = file_sha256(labels_path)
        sem_label = semantic_label_hash(labels)
        eval_cid = evaluation_config_id(resolved_eval)
        if own_tracing:
            _, peak = tracemalloc.get_traced_memory()
            peak_val: object = int(peak)
            scope = _RESOURCE_SCOPE
        else:
            peak_val = None
            scope = _RESOURCE_SCOPE_INHERITED
        elapsed = time.monotonic() - t0
        repo = provenance.repo_root()
        eval_id = uuid.uuid4().hex
        # Precompute all serializations and provenance BEFORE mkdir so a
        # provenance failure leaves no partial output directory.
        config_text = json.dumps(resolved_eval, sort_keys=True, indent=2,
                                 allow_nan=False) + "\n"
        labels_text = json.dumps(labels, sort_keys=True, indent=2,
                                 allow_nan=False) + "\n"
        persisted_labels_sha = hashlib.sha256(labels_text.encode()).hexdigest()
        eval_text = json.dumps(core, sort_keys=True, indent=2,
                               allow_nan=False) + "\n"
        metadata = {
            "eval_id": eval_id,
            "evaluator_id": evaluation.METRIC_DEFINITION_ID,
            "evaluation_config_id": eval_cid,
            "source_run": {
                "path": str(run_dir),
                "run_id": run["metadata"].get("run_id"),
                "config_id": run["metadata"].get("config_id"),
            },
            "source_config_id": run["recomputed"],
            "input_predictions_file_sha256": pred_sha,
            "persisted_predictions_file_sha256": persisted_pred_sha,
            "semantic_predictions_sha256": sem_pred,
            "label_file_sha256": label_src_sha,
            "persisted_labels_file_sha256": persisted_labels_sha,
            "checksum_note": (
                "label_file_sha256 is the raw source labels file; "
                "persisted_labels_file_sha256 is the raw eval-dir labels.json copy; "
                "bytes may differ after canonical reserialization; "
                "semantic_label_sha256 covers scientific equality. "
                "input_predictions_file_sha256 is the raw source run predictions.csv; "
                "persisted_predictions_file_sha256 is the raw eval-dir copy."
            ),
            "semantic_label_sha256": sem_label,
            "created_at": started_at,
            "created_at_scope": "evaluation_io_entry",
            "command": provenance.command_record(),
            "environment": provenance.environment_record(),
            "git": provenance.git_record(str(repo)),
            "file_hashes": provenance.file_hashes(repo),
            "resource_scope": scope,
            "resource_description": _RESOURCE_DESCRIPTION,
            "evaluated_decision_count": len(rows),
            "elapsed_monotonic_seconds": elapsed,
            "peak_python_allocation_bytes": peak_val,
        }
        metadata_text = json.dumps(metadata, sort_keys=True, indent=2,
                                   allow_nan=False) + "\n"
        # Exclusive creation only after validation/provenance complete.
        out.mkdir(parents=True, exist_ok=False)
        with open(out / "config.json", "w") as fh:
            fh.write(config_text)
        with open(out / "labels.json", "w") as fh:
            fh.write(labels_text)
        with open(out / "evaluation.json", "w") as fh:
            fh.write(eval_text)
        with open(out / "predictions.csv", "wb") as fh:
            fh.write(pred_bytes)
        with open(out / "metadata.json", "w") as fh:
            fh.write(metadata_text)
        return {"core": core, "metadata": metadata, "output": str(out),
                "resolved_config": resolved_eval}
    finally:
        if own_tracing:
            try:
                tracemalloc.stop()
            except Exception:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reliable_alerting.evaluation_io")
    ap.add_argument("--run", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    result = run_evaluation(args.run, args.labels, args.config, args.output)
    print(json.dumps({"output": result["output"],
                      "eval_id": result["metadata"]["eval_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
