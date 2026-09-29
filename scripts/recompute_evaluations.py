#!/usr/bin/env python3
"""Independent recomputation of the offline alert-evaluation metrics.

This script re-implements the metric semantics of
``research/src/reliable_alerting/evaluation.py`` from scratch using only the
Python standard library. It deliberately does NOT import ``reliable_alerting``
so that agreement with the saved ``evaluation.json`` is an independent check
rather than a tautology.

For each stream/policy run directory it:

  1. reads ``evaluation/predictions.csv`` and forms alert episodes from the
     ``output_state`` column BEFORE touching any labels;
  2. reads ``evaluation/labels.json`` and ``evaluation/config.json``;
  3. recomputes decisions, alert windows, episodes, event recall (num/den),
     episode precision (num/den or undefined), false episodes, mean delay
     (sample-index units), total alert duration, non-event alert duration,
     alert episodes per 1000 decisions, coverage (covered/total) and deferrals;
  4. compares every recomputed field against the saved ``evaluation.json``.

It prints a fixed-order table, a mismatch count, and the SHA-256 of every
input file it reads. Machine-readable output is written with sorted keys and
no timestamps so reruns are byte-identical. Exit status is 0 iff there are
zero mismatches across all evaluated runs, else 1.

Usage:
    python3 scripts/recompute_evaluations.py [--all-arms] [RESULTS_ROOT]

Without --all-arms it checks the five corrected baseline arms on valve1/valve2
(RESULTS_ROOT defaults to results/20260929-results-audit-fresh). With --all-arms it
discovers every stream/arm pair under RESULTS_ROOT, e.g. the policy study
results/20260929-policy-study-v2. The JSON report is written into results/,
which is git-ignored.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

# Repository layout: this file lives at scripts/; results live in results/.
_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = _REPO_ROOT / "results" / "20260929-results-audit-fresh"

STREAMS = ("valve1", "valve2")
POLICIES = ("fixed_threshold", "rolling_threshold", "k_consecutive", "m_of_n", "hysteresis")


# --------------------------------------------------------------------------- #
# input helpers                                                               #
# --------------------------------------------------------------------------- #
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_predictions(path):
    """Read predictions.csv into a list of decision rows (schedule order)."""
    rows = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append({
                "start_index": int(r["start_index"]),
                "end_index": int(r["end_index"]),
                "output_state": r["output_state"],
            })
    rows.sort(key=lambda x: x["end_index"])
    return rows


# --------------------------------------------------------------------------- #
# metric core (independent re-implementation)                                 #
# --------------------------------------------------------------------------- #
def form_episodes(rows, horizon_stop):
    """Form alert episodes from output_state BEFORE consulting labels.

    Each decision at end_index e covers the half-open interval
    [e, next_end_index), and the final decision covers [e, horizon_stop).
    Adjacent alert intervals merge into a single episode.
    """
    intervals = []
    n = len(rows)
    for i, row in enumerate(rows):
        start = row["end_index"]
        stop = rows[i + 1]["end_index"] if i + 1 < n else horizon_stop
        if stop > horizon_stop:
            stop = horizon_stop
        intervals.append((start, stop, row["output_state"]))

    episodes = []
    run_start = run_stop = None
    for start, stop, state in intervals:
        if state == "alert":
            if run_start is None:
                run_start, run_stop = start, stop
            else:
                run_stop = stop
        else:
            if run_start is not None:
                episodes.append((run_start, run_stop))
                run_start = run_stop = None
    if run_start is not None:
        episodes.append((run_start, run_stop))
    return episodes


def overlaps(a_start, a_stop, b_start, b_stop):
    return a_start < b_stop and b_start < a_stop


def clip_events(events, h0, h1):
    """Clip labelled events to the horizon; drop empty ones. Keep original start."""
    clipped = []
    for e in events:
        cs = max(e["start"], h0)
        ce = min(e["stop"], h1)
        if not cs < ce:
            continue
        clipped.append({
            "event_id": e["event_id"],
            "start": cs,
            "stop": ce,
            "original_start": e["start"],
        })
    return clipped


def merge_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = []
    cs, ce = ordered[0]
    for s, e in ordered[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            merged.append((cs, ce))
            cs, ce = s, e
    merged.append((cs, ce))
    return merged


def recompute(rows, labels, config):
    """Recompute the offline metrics independently from rows + labels + config."""
    h0, h1 = config["horizon"]
    first = config["first_decision"]
    n = len(rows)
    horizon_length = h1 - h0

    episodes = form_episodes(rows, h1)
    n_episodes = len(episodes)

    clipped = clip_events(labels["events"], h0, h1)
    n_clipped = len(clipped)

    # recall + delay: per clipped event, does any episode overlap it?
    recalled_delays = []
    for c in clipped:
        hits = [ep for ep in episodes if overlaps(ep[0], ep[1], c["start"], c["stop"])]
        if hits:
            first_start = min(ep[0] for ep in hits)
            recalled_delays.append(max(0, first_start - c["original_start"]))
    n_recalled = len(recalled_delays)

    # episode precision: episodes that overlap any clipped event
    tp_episodes = sum(
        1 for ep in episodes
        if any(overlaps(ep[0], ep[1], c["start"], c["stop"]) for c in clipped)
    )
    false_episodes = n_episodes - tp_episodes

    recall_value = (n_recalled / n_clipped) if n_clipped else None
    precision_value = (tp_episodes / n_episodes) if n_episodes else None

    mean_delay = float(sum(recalled_delays) / n_recalled) if n_recalled else None

    n_alert = sum(1 for r in rows if r["output_state"] == "alert")
    n_defer = sum(1 for r in rows if r["output_state"] == "defer")
    n_covered = sum(1 for r in rows if r["output_state"] in ("normal", "alert"))

    total_alert = sum(stop - start for start, stop in episodes)
    merged_events = merge_intervals([(c["start"], c["stop"]) for c in clipped])
    overlap_len = 0
    for ep_s, ep_e in episodes:
        for s, e in merged_events:
            lo = max(ep_s, s)
            hi = min(ep_e, e)
            if hi > lo:
                overlap_len += hi - lo
    non_event_alert = total_alert - overlap_len

    episodes_per_1000 = (n_episodes / n * 1000) if n else None

    return {
        "decisions": n,
        "alert_windows": n_alert,
        "episodes": n_episodes,
        "event_recall_num": n_recalled,
        "event_recall_den": n_clipped,
        "episode_precision_num": tp_episodes,
        "episode_precision_den": n_episodes,
        "false_episodes": false_episodes,
        "mean_delay": mean_delay,
        "total_alert_duration": total_alert,
        "non_event_alert_duration": non_event_alert,
        "episodes_per_1000_decisions": episodes_per_1000,
        "coverage_num": n_covered,
        "coverage_den": n,
        "deferrals": n_defer,
    }


def extract_saved(ev):
    """Pull the comparable fields out of a saved evaluation.json object."""
    m = ev["metrics"]
    delay = m["delay"]["mean"]
    return {
        "decisions": m["decision_count"],
        "alert_windows": m["alerted_window_fraction"]["numerator"],
        "episodes": m["alert_episode_rate_per_1000_decisions"]["numerator"],
        "event_recall_num": m["event_recall"]["numerator"],
        "event_recall_den": m["event_recall"]["denominator"],
        "episode_precision_num": m["episode_precision"]["numerator"],
        "episode_precision_den": m["episode_precision"]["denominator"],
        "false_episodes": m["false_alert_episodes"],
        "mean_delay": delay,
        "total_alert_duration": m["total_alert_duration"]["value"],
        "non_event_alert_duration": m["non_event_alert_duration"]["value"],
        "episodes_per_1000_decisions": m["alert_episode_rate_per_1000_decisions"]["value"],
        "coverage_num": m["decision_coverage"]["numerator"],
        "coverage_den": m["decision_coverage"]["denominator"],
        "deferrals": m["deferral_rate"]["numerator"],
    }


_FLOAT_FIELDS = {"mean_delay", "episodes_per_1000_decisions"}
_FIELD_ORDER = (
    "decisions", "alert_windows", "episodes",
    "event_recall_num", "event_recall_den",
    "episode_precision_num", "episode_precision_den",
    "false_episodes", "mean_delay",
    "total_alert_duration", "non_event_alert_duration",
    "episodes_per_1000_decisions",
    "coverage_num", "coverage_den", "deferrals",
)


def equal_field(name, a, b):
    if a is None or b is None:
        return a is None and b is None
    if name in _FLOAT_FIELDS:
        return abs(float(a) - float(b)) <= 1e-9
    return a == b


def fmt(name, v):
    if v is None:
        return "undef"
    if name in _FLOAT_FIELDS:
        return f"{float(v):.3f}"
    return str(v)


# --------------------------------------------------------------------------- #
# driver                                                                      #
# --------------------------------------------------------------------------- #
def _discover_pairs(root):
    """Discover (stream, policy) pairs under root that have an evaluation.json.

    Used by --all-arms so the walker also covers the new arms/streams (the
    anchored controller, its ablations, Sun, rolling_all, and the synthetic
    Y1-Y7). Deterministic sorted order.
    """
    pairs = []
    for stream_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for arm_dir in sorted(p for p in stream_dir.iterdir() if p.is_dir()):
            if (arm_dir / "evaluation" / "evaluation.json").is_file():
                pairs.append((stream_dir.name, arm_dir.name))
    return pairs


def main(argv):
    args = [a for a in argv[1:] if a != "--all-arms"]
    all_arms = "--all-arms" in argv[1:]
    root = Path(args[0]).resolve() if args else DEFAULT_ROOT
    if not root.is_dir():
        print(f"ERROR: results root not found: {root}", file=sys.stderr)
        return 2

    if all_arms:
        pairs = _discover_pairs(root)
        out_name = "recompute-output-policy-study.json"
    else:
        pairs = [(s, p) for s in STREAMS for p in POLICIES]
        out_name = "recompute-output.json"

    input_hashes = {}
    table_rows = []
    mismatches = []
    machine = {"results_root": str(root), "runs": {}}

    for stream, policy in pairs:
            evdir = root / stream / policy / "evaluation"
            pred = evdir / "predictions.csv"
            labels_path = evdir / "labels.json"
            config_path = evdir / "config.json"
            saved_path = evdir / "evaluation.json"
            if not saved_path.is_file():
                print(f"ERROR: missing {saved_path}", file=sys.stderr)
                return 2

            for p in (pred, labels_path, config_path, saved_path):
                rel = str(p.relative_to(root))
                input_hashes[rel] = sha256_of(p)

            rows = read_predictions(pred)
            with open(labels_path) as fh:
                labels = json.load(fh)
            with open(config_path) as fh:
                config = json.load(fh)
            with open(saved_path) as fh:
                saved_ev = json.load(fh)

            got = recompute(rows, labels, config)
            want = extract_saved(saved_ev)

            row_mismatch = []
            for name in _FIELD_ORDER:
                if not equal_field(name, got[name], want[name]):
                    row_mismatch.append(name)
                    mismatches.append(f"{stream}/{policy}:{name} "
                                      f"recomputed={got[name]} saved={want[name]}")
            table_rows.append((stream, policy, got, want, row_mismatch))
            machine["runs"][f"{stream}/{policy}"] = {
                "recomputed": got,
                "saved": want,
                "mismatched_fields": sorted(row_mismatch),
            }

    # fixed-order human table
    header = ["stream", "policy"] + list(_FIELD_ORDER) + ["match"]
    print("\t".join(header))
    for stream, policy, got, _want, row_mismatch in table_rows:
        cells = [stream, policy] + [fmt(name, got[name]) for name in _FIELD_ORDER]
        cells.append("OK" if not row_mismatch else "MISMATCH:" + ",".join(row_mismatch))
        print("\t".join(cells))

    print()
    print(f"mismatch_count= {len(mismatches)}")
    if mismatches:
        for m in mismatches:
            print("  MISMATCH " + m)

    print()
    print("input file SHA-256 (sorted):")
    for rel in sorted(input_hashes):
        print(f"  {input_hashes[rel]}  {rel}")

    machine["input_sha256"] = input_hashes
    machine["mismatch_count"] = len(mismatches)
    machine["mismatches"] = sorted(mismatches)

    out_json = _REPO_ROOT / "results" / out_name
    with open(out_json, "w") as fh:
        json.dump(machine, fh, sort_keys=True, indent=2)
        fh.write("\n")

    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
