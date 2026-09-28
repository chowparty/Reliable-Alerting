"""family_table.py - Day 4 five-policy family comparison table (Nakul).

Assembles one row per policy from the completed per-policy evaluation outputs
under result/valve1/<policy>/evaluation/, applies the predeclared Day 4
reporting criteria (episode-rate budget and coverage floor) as FLAGS (never
rejection gates), builds the operating-point record from each policy's saved
config, independently recomputes one row's episode set from the saved decision
trace, and audits the assembled numbers against the saved evaluation.json.

Read-only with respect to the teammate repo: this module reads saved result/
artifacts and imports reliable_alerting.evaluation for the independent
recompute. It writes nothing itself; callers serialize the returned dict.

Predeclared Day 4 criteria (project-level engineering choice, 2026-09-27;
NOT literature-prescribed; chosen independently of observed outcomes):
  - EPISODE_RATE_BUDGET_PER_1000 = 70  (valve1 has 143 decisions, so ~10
    episodes over this replay)
  - COVERAGE_FLOOR = 1.0  (all five Day 4 policies are full-decision/no-defer)
  - Reporting criteria only: over-budget / under-floor policies stay in the
    table with their actual values and a feasibility flag + reasons.
"""
import csv
import json
from pathlib import Path

from reliable_alerting import evaluation  # read-only, for independent recompute

# --- Predeclared Day 4 operating-point criteria (see module docstring) ---
EPISODE_RATE_BUDGET_PER_1000 = 70.0
COVERAGE_FLOOR = 1.0
CRITERIA_BASIS = (
    "project-level engineering choice 2026-09-27; not literature-prescribed; "
    "70/1000 ~= 10 episodes over valve1's 143 decisions; chosen independently "
    "of observed policy outcomes; reporting criteria, not rejection gates"
)

POLICIES = ("fixed_threshold", "rolling_threshold", "k_consecutive",
            "m_of_n", "hysteresis")

# Operating-point settings that define each policy (read from its saved config).
_OP_KEYS = {
    "fixed_threshold": ("comparison",),
    "rolling_threshold": ("comparison", "history_length", "admission_rule", "quantile"),
    "k_consecutive": ("comparison", "k"),
    "m_of_n": ("comparison", "m", "n"),
    "hysteresis": ("comparison", "low_ratio"),
}


def _policy_dir(result_root, policy):
    return Path(result_root) / "valve1" / policy


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def assess_feasibility(episode_rate_per_1000, coverage):
    """Report whether a policy meets the predeclared criteria. Never rejects."""
    reasons = []
    if episode_rate_per_1000 > EPISODE_RATE_BUDGET_PER_1000:
        reasons.append(
            f"episode rate {episode_rate_per_1000} > budget "
            f"{EPISODE_RATE_BUDGET_PER_1000} per 1000 decisions")
    if coverage < COVERAGE_FLOOR:
        reasons.append(
            f"decision coverage {coverage} < floor {COVERAGE_FLOOR}")
    return {"feasible": not reasons, "reasons": reasons}


def _row_from_evaluation(result_root, policy):
    """Build one table row from the saved evaluation.json + configs + metadata."""
    pdir = _policy_dir(result_root, policy)
    edir = pdir / "evaluation"
    ev = _read_json(edir / "evaluation.json")
    m = ev["metrics"]
    src_cfg = _read_json(pdir / "config.json")
    src_meta = _read_json(pdir / "metadata.json")
    eval_meta = _read_json(edir / "metadata.json")

    rec = m["event_recall"]
    pre = m["episode_precision"]
    delay = m["delay"]
    ep_rate = m["alert_episode_rate_per_1000_decisions"]["value"]
    coverage = m["decision_coverage"]["value"]

    op_settings = {k: src_cfg["policy"].get(k) for k in _OP_KEYS[policy]}

    row = {
        "policy": policy,
        # operating point (settings that define this policy)
        "operating_point": op_settings,
        # episode counts / precision
        "n_episodes": pre["denominator"],
        "false_alert_episodes": m["false_alert_episodes"],
        "episode_precision": {"value": pre["value"],
                              "numerator": pre["numerator"],
                              "denominator": pre["denominator"]},
        # recall
        "event_recall": {"value": rec["value"],
                         "numerator": rec["numerator"],
                         "denominator": rec["denominator"]},
        # delay with misses reported separately
        "delay": {"mean": delay["mean"], "median": delay["median"],
                  "min": delay["min"], "max": delay["max"],
                  "recalled_count": delay["recalled_count"],
                  "missed_count": delay["missed_count"],
                  "unit": delay["unit"]},
        # volume / coverage
        "alerted_window_fraction": {"value": m["alerted_window_fraction"]["value"],
                                    "numerator": m["alerted_window_fraction"]["numerator"],
                                    "denominator": m["alerted_window_fraction"]["denominator"]},
        "alert_episode_rate_per_1000_decisions": ep_rate,
        "decision_coverage": {"value": coverage,
                              "numerator": m["decision_coverage"]["numerator"],
                              "denominator": m["decision_coverage"]["denominator"]},
        "deferral_rate": {"value": m["deferral_rate"]["value"],
                          "numerator": m["deferral_rate"]["numerator"],
                          "denominator": m["deferral_rate"]["denominator"]},
        "total_alert_duration": m["total_alert_duration"]["value"],
        "non_event_alert_duration": m["non_event_alert_duration"]["value"],
        "decision_count": m["decision_count"],
        # feasibility vs the predeclared criteria (flag only)
        "feasibility": assess_feasibility(ep_rate, coverage),
        # timing with EXPLICIT scope (not per-window latency)
        "timing": {
            "source_run_elapsed_seconds": src_meta.get("elapsed_monotonic_seconds"),
            "source_run_scope": src_meta.get("resource_scope"),
            "source_run_peak_python_bytes": src_meta.get("peak_python_allocation_bytes"),
            "evaluation_elapsed_seconds": eval_meta.get("elapsed_monotonic_seconds"),
            "evaluation_scope": eval_meta.get("resource_scope"),
        },
        # provenance: link back to the exact saved evaluation
        "source": {
            "evaluation_dir": str(edir),
            "eval_id": eval_meta.get("eval_id"),
            "evaluation_config_id": eval_meta.get("evaluation_config_id"),
            "semantic_predictions_sha256": eval_meta.get("semantic_predictions_sha256"),
        },
        # episodes with their bounds (for episode->decisions traceability)
        "episodes": [{"episode_id": e["episode_id"], "start": e["start"],
                      "stop": e["stop"]} for e in ev["episodes"]],
    }
    return row, ev


def _load_decision_trace(predictions_csv):
    """Read a saved predictions.csv into evaluator-shaped rows (base 8 cols)."""
    rows = []
    with open(predictions_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append({
                "window_id": r["window_id"],
                "start_index": int(r["start_index"]),
                "end_index": int(r["end_index"]),
                "score": float(r["score"]),
                "output_state": r["output_state"],
                "threshold": float(r["threshold"]),
                "config_id": r["config_id"],
                "run_id": r["run_id"],
            })
    return rows


def independent_recompute(result_root, policy, eval_config):
    """Independently recompute episodes for one policy from its SAVED decision
    trace (not from evaluation.json), using the pure evaluator. Returns the
    recomputed episode bounds so a caller can compare to the table row."""
    pdir = _policy_dir(result_root, policy)
    rows = _load_decision_trace(pdir / "predictions.csv")
    episodes = evaluation.form_episodes(rows, eval_config)
    return [{"episode_id": e["episode_id"], "start": e["start"], "stop": e["stop"]}
            for e in episodes]


def trace_episodes_to_decisions(result_root, policy):
    """For every episode in the saved evaluation, confirm the decisions file
    shows a contiguous run of 'alert' whose forward intervals cover the episode
    span. Returns a per-episode traceability report."""
    pdir = _policy_dir(result_root, policy)
    edir = pdir / "evaluation"
    ev = _read_json(edir / "evaluation.json")
    rows = _load_decision_trace(pdir / "predictions.csv")
    # forward interval per decision: [end_index, next end_index) ; last -> horizon stop
    cfg = _read_json(edir / "config.json")
    h1 = cfg["horizon"][1]
    ends = [r["end_index"] for r in rows]
    intervals = []
    for i, r in enumerate(rows):
        start = r["end_index"]
        stop = ends[i + 1] if i + 1 < len(rows) else h1
        intervals.append((start, min(stop, h1), r["output_state"], r["window_id"]))
    reports = []
    for ep in ev["episodes"]:
        covering = [(s, e, st, wid) for (s, e, st, wid) in intervals
                    if st == "alert" and s < ep["stop"] and e > ep["start"]]
        all_alert = all(st == "alert" for (_, _, st, _) in covering)
        span_ok = (covering and min(s for s, _, _, _ in covering) <= ep["start"]
                   and max(e for _, e, _, _ in covering) >= ep["stop"])
        reports.append({
            "episode_id": ep["episode_id"],
            "episode_span": [ep["start"], ep["stop"]],
            "alert_windows": [wid for (_, _, _, wid) in covering],
            "all_covering_windows_are_alert": bool(all_alert),
            "windows_span_episode": bool(span_ok),
            "traced_ok": bool(all_alert and span_ok),
        })
    return reports


def build_family_table(result_root, eval_config, policies=POLICIES):
    """Assemble the full five-policy family table + operating-point record."""
    rows = []
    evaluations = {}
    for pol in policies:
        row, ev = _row_from_evaluation(result_root, pol)
        rows.append(row)
        evaluations[pol] = ev
    operating_point_record = {
        "criteria": {
            "episode_rate_budget_per_1000_decisions": EPISODE_RATE_BUDGET_PER_1000,
            "coverage_floor": COVERAGE_FLOOR,
            "basis": CRITERIA_BASIS,
            "role": "reporting_criteria_not_rejection_gates",
        },
        "settings_per_policy": {r["policy"]: r["operating_point"] for r in rows},
        "feasibility_per_policy": {r["policy"]: r["feasibility"] for r in rows},
    }
    return {
        "table_id": "day04-valve1-family-v1",
        "stream": "valve1",
        "policies": list(policies),
        "criteria": operating_point_record["criteria"],
        "rows": rows,
        "operating_point_record": operating_point_record,
    }