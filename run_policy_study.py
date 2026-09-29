#!/usr/bin/env python3
"""Run the frozen-protocol policy study (sections 5-7).

Runs all 11 policy configs (arms) on the two SKAB development streams
(valve1, valve2) and the seven synthetic scenarios (Y1-Y7), on each stream's
single common score trace, then evaluates every run through the existing
offline evaluation path and writes:

    <output-root>/<stream>/<arm>/                 (runtime run: predictions,
                                                   calibration, config,
                                                   metadata, diagnostics,
                                                   policy_actions.csv)
    <output-root>/<stream>/<arm>/evaluation/      (offline evaluation)
    <output-root>/summary.json                    (sorted keys, no timestamps)
    <output-root>/summary.md                      (human tables)

The 11 arms (5 existing + rolling_all + anchored + 3 ablations + sun):
    fixed_threshold, rolling_threshold, rolling_threshold_all, k_consecutive,
    m_of_n, hysteresis, anchored_recalibration, anchored_no_cap,
    anchored_no_stability, anchored_no_defer, sun_confidence_sequence.

Refuses an existing output root. Standard library + reliable_alerting only.

Usage:
    .venv/bin/python run_policy_study.py --output-root results/20260929-policy-study
"""
import argparse
import csv
import json
import sys
import time
import tracemalloc
import uuid
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "src"))

from reliable_alerting import pipeline, writing, provenance, evaluation_io  # noqa: E402

_CONFIGS = _HERE / "configs"

# ---- arms (11 policy configs) ------------------------------------------- #
ARMS = {
    "fixed_threshold": {"kind": "fixed_threshold", "comparison": "strict_greater"},
    "rolling_threshold": {"kind": "rolling_threshold", "comparison": "strict_greater",
                          "history_length": 10, "admission_rule": "normal_only",
                          "quantile": 0.95},
    "rolling_threshold_all": {"kind": "rolling_threshold", "comparison": "strict_greater",
                              "history_length": 10, "admission_rule": "all",
                              "quantile": 0.95},
    "k_consecutive": {"kind": "k_consecutive", "comparison": "strict_greater", "k": 3},
    "m_of_n": {"kind": "m_of_n", "comparison": "strict_greater", "m": 3, "n": 5},
    "hysteresis": {"kind": "hysteresis", "comparison": "strict_greater", "low_ratio": 0.8},
    "anchored_recalibration": {"kind": "anchored_recalibration", "comparison": "strict_greater",
                               "history_length": 10, "quantile": 0.95, "kappa": 4.0,
                               "rho": 2.0, "defer_limit": 10},
    "anchored_no_cap": {"kind": "anchored_recalibration", "comparison": "strict_greater",
                        "history_length": 10, "quantile": 0.95, "kappa": None,
                        "rho": 2.0, "defer_limit": 10},
    "anchored_no_stability": {"kind": "anchored_recalibration", "comparison": "strict_greater",
                              "history_length": 10, "quantile": 0.95, "kappa": 4.0,
                              "rho": None, "defer_limit": 10},
    "anchored_no_defer": {"kind": "anchored_recalibration", "comparison": "strict_greater",
                          "history_length": 10, "quantile": 0.95, "kappa": 4.0,
                          "rho": 2.0, "defer_limit": 0},
    "sun_confidence_sequence": {"kind": "sun_confidence_sequence", "comparison": "strict_greater",
                                "p": 0.95, "alpha": 0.05},
}
ARM_ORDER = list(ARMS.keys())

# ---- streams ------------------------------------------------------------ #
# SKAB development streams: (path, length, calibration_end).
SKAB = {
    "valve1": ("SKAB/valve1/0.csv", 1148, 574),
    "valve2": ("SKAB/valve2/0.csv", 1125, 562),
}
SKAB_LABELS = {
    # Labelled anomaly runs are half-open, derived from the streams' own anomaly
    # column via research/verification.label_runs (offline; development streams
    # only): valve1 -> [574,975), valve2 -> [562,956). These match the ten
    # corrected audit-fresh rows and are joined only after the causal run is
    # saved.
    "valve1": {"schema_version": 1, "time_basis": "sample_index",
               "coverage": [574, 1148],
               "events": [{"event_id": "valve1-anomaly-0", "start": 574, "stop": 975}]},
    "valve2": {"schema_version": 1, "time_basis": "sample_index",
               "coverage": [562, 1125],
               "events": [{"event_id": "valve2-anomaly-0", "start": 562, "stop": 956}]},
}
SYNTH = ("Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7")
STREAM_ORDER = ["valve1", "valve2"] + list(SYNTH)


def skab_run_config(path, length, calibration_end, policy):
    return {
        "schema_version": 1,
        "input": {"kind": "csv_stream", "path": str(path), "value_column": "Current",
                  "length": length, "delimiter": ";"},
        "segments": {"source_fit": [0, 400], "calibration": [400, calibration_end],
                     "replay": [calibration_end, length]},
        "window": {"length": 4, "stride": 4, "anchor": "segment_start",
                   "edge_policy": "drop_incomplete", "end_index": "inclusive"},
        "scoring": {"kind": "mean_distance", "epsilon": 1e-06,
                    "fit_scope": "source_fit", "standard_deviation": "population"},
        "calibration": {"kind": "fixed_quantile", "quantile": 0.95,
                        "method": "nearest_rank", "min_samples": 2,
                        "score_segment": "calibration"},
        "policy": policy,
        "missing_policy": "reject", "source_label_use": "none",
        "time_basis": "sample_index", "held_out": "not_reserved_or_evaluated",
    }


def skab_eval_config(calibration_end, length):
    return {"schema_version": 1, "time_basis": "sample_index",
            "horizon": [calibration_end, length],
            "first_decision": calibration_end + 3, "decision_stride": 4,
            "window_length": 4}


def synth_run_config(name, policy):
    cfg = json.load(open(_CONFIGS / f"policy-study-{name}.json"))
    cfg = dict(cfg)
    cfg["policy"] = policy
    return cfg


def synth_labels(name):
    return json.load(open(_CONFIGS / f"policy-study-{name}-labels.json"))


def synth_eval_config():
    return json.load(open(_CONFIGS / "policy-study-synthetic-evaluation.json"))


def _write_json(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2, allow_nan=False)
        fh.write("\n")


def _write_run_dir(run_dir, trace):
    t0 = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    own = not tracemalloc.is_tracing()
    if own:
        tracemalloc.start()
    try:
        run_id = uuid.uuid4().hex
        full_rows = [dict(r, run_id=run_id) for r in trace["rows"]]
        _, peak = tracemalloc.get_traced_memory()
        elapsed = time.monotonic() - t0
        repo = provenance.repo_root()
        metadata = {
            "run_id": run_id, "config_id": trace["config_id"],
            "input_hash": trace.get("input_hash"), "started_at": started,
            "started_at_scope": "write_output_entry",
            "intended_day1": pipeline.INTENDED_DAY1,
            "command": provenance.command_record(),
            "environment": provenance.environment_record(),
            "git": provenance.git_record(str(repo)),
            "file_hashes": provenance.file_hashes(repo),
            "resource_scope": pipeline.RESOURCE_SCOPE,
            "elapsed_monotonic_seconds": elapsed,
            "peak_python_allocation_bytes": int(peak),
        }
        writing.write_run(run_dir, full_rows, trace["config"], metadata,
                          trace["diagnostics"], trace["calibration_rows"],
                          action_rows=trace["action_rows"])
        return metadata
    finally:
        if own:
            tracemalloc.stop()


def _action_counts(run_dir):
    """Recalibration count and deferral count from the action log."""
    recal = defer = 0
    with open(Path(run_dir) / "policy_actions.csv", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if r["action"] == "recalibrate":
                recal += 1
            elif r["action"] == "defer":
                defer += 1
    return recal, defer


def summarize_metrics(core, recal_count, event_union_len):
    m = core["metrics"]
    total = m["total_alert_duration"]["value"]
    non_event = m["non_event_alert_duration"]["value"]
    in_event_dur = total - non_event
    if event_union_len:
        in_event_frac = in_event_dur / event_union_len
    else:
        in_event_frac = None
    return {
        "decisions": m["decision_count"],
        "alert_windows": m["alerted_window_fraction"]["numerator"],
        "alert_episodes": m["alert_episode_rate_per_1000_decisions"]["numerator"],
        "event_recall_num": m["event_recall"]["numerator"],
        "event_recall_den": m["event_recall"]["denominator"],
        "episode_precision_num": m["episode_precision"]["numerator"],
        "episode_precision_den": m["episode_precision"]["denominator"],
        "false_episodes": m["false_alert_episodes"],
        "mean_delay": m["delay"]["mean"],
        "total_alert_duration": total,
        "non_event_alert_duration": non_event,
        "in_event_alerted_duration": in_event_dur,
        "clipped_event_duration": event_union_len,
        "in_event_alerted_fraction": in_event_frac,
        "episodes_per_1000_decisions": m["alert_episode_rate_per_1000_decisions"]["value"],
        "coverage_num": m["decision_coverage"]["numerator"],
        "coverage_den": m["decision_coverage"]["denominator"],
        "deferrals": m["deferral_rate"]["numerator"],
        "recalibration_count": recal_count,
    }


def _event_union_len(core):
    clipped = core["events"]["clipped"]
    if not clipped:
        return 0
    ivs = sorted((c["start"], c["stop"]) for c in clipped)
    total = 0
    cs, ce = ivs[0]
    for s, e in ivs[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            total += ce - cs
            cs, ce = s, e
    total += ce - cs
    return total


_COLUMNS = (
    "decisions", "alert_windows", "alert_episodes",
    "event_recall_num", "event_recall_den",
    "episode_precision_num", "episode_precision_den",
    "false_episodes", "mean_delay",
    "total_alert_duration", "non_event_alert_duration",
    "in_event_alerted_duration", "clipped_event_duration",
    "in_event_alerted_fraction",
    "episodes_per_1000_decisions",
    "coverage_num", "coverage_den", "deferrals", "recalibration_count",
    "elapsed_seconds", "peak_python_allocation_bytes",
)


def _fmt(name, v):
    if v is None:
        return "undef"
    if name in ("mean_delay", "episodes_per_1000_decisions",
                "in_event_alerted_fraction", "elapsed_seconds"):
        return f"{float(v):.3f}"
    return str(v)


def run(output_root):
    out = Path(output_root)
    if out.exists():
        raise FileExistsError(f"output root already exists: {out}")
    out.mkdir(parents=True, exist_ok=False)

    summary = {"arms": ARM_ORDER, "streams": STREAM_ORDER, "results": {}}

    for stream in STREAM_ORDER:
        summary["results"][stream] = {}
        for arm in ARM_ORDER:
            policy = dict(ARMS[arm])
            if stream in SKAB:
                path, length, cend = SKAB[stream]
                run_config = skab_run_config(path, length, cend, policy)
                labels = SKAB_LABELS[stream]
                eval_cfg = skab_eval_config(cend, length)
            else:
                run_config = synth_run_config(stream, policy)
                labels = synth_labels(stream)
                eval_cfg = synth_eval_config()

            run_dir = out / stream / arm
            resolved = pipeline.validate_config(run_config)
            trace = pipeline.compute_trace(resolved)
            metadata = _write_run_dir(run_dir, trace)
            recal_count, _defer = _action_counts(run_dir)

            # Evaluate through the existing offline path (verifies the saved run,
            # forms episodes before labels, then joins labels).
            labels_path = run_dir / "labels_source.json"
            eval_cfg_path = run_dir / "evaluation_config.json"
            _write_json(labels_path, labels)
            _write_json(eval_cfg_path, eval_cfg)
            eval_out = run_dir / "evaluation"
            result = evaluation_io.run_evaluation(str(run_dir), str(labels_path),
                                                  str(eval_cfg_path), str(eval_out))
            core = result["core"]
            row = summarize_metrics(core, recal_count, _event_union_len(core))
            row["elapsed_seconds"] = metadata["elapsed_monotonic_seconds"]
            row["peak_python_allocation_bytes"] = metadata["peak_python_allocation_bytes"]
            summary["results"][stream][arm] = row
            print(f"  {stream}/{arm}: recall {row['event_recall_num']}/"
                  f"{row['event_recall_den']} alerts {row['alert_windows']} "
                  f"episodes {row['alert_episodes']} defer {row['deferrals']} "
                  f"recal {row['recalibration_count']}")

    _write_json(out / "summary.json", summary)
    _write_summary_md(out / "summary.md", summary)
    print(f"study complete -> {out}")
    return summary


def _write_summary_md(path, summary):
    lines = ["# Policy study summary (29 September 2026)", ""]
    lines.append(f"Arms ({len(ARM_ORDER)}): " + ", ".join(ARM_ORDER))
    lines.append("")
    lines.append("Columns are the section-7 metrics; in_event_alerted_fraction "
                 "and recalibration_count are derived (the latter from the "
                 "label-free action log). Ranking metrics are not reported: "
                 "identical score traces give identical ranking metrics by "
                 "construction.")
    lines.append("")
    header = "| arm | " + " | ".join(_COLUMNS) + " |"
    sep = "|" + "---|" * (len(_COLUMNS) + 1)
    for stream in STREAM_ORDER:
        lines.append(f"## {stream}")
        lines.append("")
        lines.append(header)
        lines.append(sep)
        for arm in ARM_ORDER:
            row = summary["results"][stream][arm]
            cells = [_fmt(c, row.get(c)) for c in _COLUMNS]
            lines.append(f"| {arm} | " + " | ".join(cells) + " |")
        lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", required=True)
    args = ap.parse_args(argv)
    run(args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
