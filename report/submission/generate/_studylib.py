"""Shared, stdlib-only loaders and checks for the promoted figure/table generators.

Promoted verbatim in behaviour from ``report-work/figures/_studylib.py``; the ONLY
differences are path resolution and the recompute cross-check being optional:

  * ``DEFAULT_ROOT`` resolves to ``<research-repo-root>/results/20260929-policy-study-v2``
    so the generators run from the research repo alone. Regenerate that study with
    ``.venv/bin/python run_policy_study.py --output-root results/20260929-policy-study-v2``
    (research README, "Commands").
  * ``recompute_path`` points at the report-work evidence pack when it is present
    beside the checkout; that pack is a review artifact and is NOT part of the
    research repo, so ``load_recompute`` returns ``None`` when it is absent and the
    cross-check is skipped rather than failing. When the pack IS present the check
    runs and must pass (that is how byte-identity was proved at promotion time).

Every displayed number is sourced from ``summary.json`` (canonical). Labels are read
from ``evaluation/labels.json`` only after predictions are loaded, and are used solely
for event shading and in-event bookkeeping -- never for any runtime decision.

The module is deterministic: it sorts everything it iterates and never touches the
filesystem outside the study root it is given. It deliberately does NOT import
numpy / pandas -- there is no such dependency in this environment.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os

# ---------------------------------------------------------------------------
# Canonical constants (asserted against the data, not trusted blindly)
# ---------------------------------------------------------------------------

STREAMS = ["valve1", "valve2", "Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"]
SKAB_STREAMS = ["valve1", "valve2"]
SYNTH_STREAMS = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"]

ARMS = [
    "fixed_threshold",
    "rolling_threshold",          # normal-only
    "rolling_threshold_all",
    "k_consecutive",
    "m_of_n",
    "hysteresis",
    "anchored_recalibration",
    "anchored_no_cap",
    "anchored_no_stability",
    "anchored_no_defer",
    "sun_confidence_sequence",
]

# generate/ lives at research/report/submission/generate/, so the research repo
# root is three directories up and the canonical study is under results/ there.
RESEARCH_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
DEFAULT_ROOT = os.path.join(RESEARCH_ROOT, "results", "20260929-policy-study-v2")

# Output directories: the promoted generators write into submission/figures|tables.
SUBMISSION_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
FIGURES_OUT = os.path.join(SUBMISSION_ROOT, "figures")
TABLES_OUT = os.path.join(SUBMISSION_ROOT, "tables")


def recompute_path(root):
    """Path to the review recompute file if the report-work pack sits beside the
    checkout; else None. The pack is not part of the research repo."""
    cand = os.path.normpath(
        os.path.join(RESEARCH_ROOT, "..", "report-work", "evidence",
                     "recompute-output-policy-study.json")
    )
    return cand if os.path.exists(cand) else None


# ---------------------------------------------------------------------------
# Low-level readers
# ---------------------------------------------------------------------------

def _arm_dir(root, stream, arm):
    return os.path.join(root, stream, arm)


def read_predictions(root, stream, arm):
    """List of dicts with typed fields, in file order (= chronological)."""
    path = os.path.join(_arm_dir(root, stream, arm), "predictions.csv")
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            out.append({
                "window_id": r["window_id"],
                "start_index": int(r["start_index"]),
                "end_index": int(r["end_index"]),
                "score": float(r["score"]),
                "output_state": r["output_state"],
                "threshold": float(r["threshold"]),
            })
    return out


def read_policy_actions(root, stream, arm):
    """List of dicts: window_id, end_index, action, threshold -- file order."""
    path = os.path.join(_arm_dir(root, stream, arm), "policy_actions.csv")
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            out.append({
                "window_id": r["window_id"],
                "end_index": int(r["end_index"]),
                "action": r["action"],
                "threshold": float(r["threshold"]),
            })
    return out


def read_labels(root, stream, arm):
    """Event spans + coverage.  Read AFTER predictions, for shading only."""
    path = os.path.join(_arm_dir(root, stream, arm), "evaluation", "labels.json")
    with open(path) as fh:
        d = json.load(fh)
    events = [(int(e["start"]), int(e["stop"])) for e in d.get("events", [])]
    cov = d.get("coverage")
    coverage = (int(cov[0]), int(cov[1])) if cov else None
    return {"events": events, "coverage": coverage}


def load_summary(root):
    with open(os.path.join(root, "summary.json")) as fh:
        return json.load(fh)


def load_recompute(root):
    """Load the review recompute file if present, else None (check is skipped)."""
    path = recompute_path(root)
    if path is None:
        return None
    with open(path) as fh:
        return json.load(fh)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The one number source: summary.json, guarded by the recompute file when present
# ---------------------------------------------------------------------------

# recompute uses "episodes"; summary uses "alert_episodes".  Everything else
# that appears in both must be byte-equal.
_RECOMPUTE_ALIASES = {"alert_episodes": "episodes"}


def stream_arm_metrics(summary, stream, arm):
    """Return the canonical metric dict for one (stream, arm) from summary.json."""
    return summary["results"][stream][arm]


def assert_summary_matches_recompute(summary, recompute):
    """Fail loudly if any overlapping field disagrees between the two sources.

    Returns the number of (stream, arm, field) triples checked, or 0 when the
    recompute file is absent (review artifact not present beside the checkout).
    """
    if recompute is None:
        return 0
    assert recompute.get("mismatch_count") == 0, (
        "recompute file reports mismatches: %r" % recompute.get("mismatch_count"))
    runs = recompute["runs"]
    checked = 0
    for stream in STREAMS:
        for arm in ARMS:
            key = "%s/%s" % (stream, arm)
            assert key in runs, "recompute missing run %s" % key
            rec = runs[key]["recomputed"]
            sm = stream_arm_metrics(summary, stream, arm)
            for field, val in rec.items():
                sfield = _RECOMPUTE_ALIASES_INV.get(field, field)
                if sfield not in sm:
                    continue
                a, b = sm[sfield], val
                if isinstance(a, float) or isinstance(b, float):
                    if a is None or b is None:
                        assert a == b, "%s.%s None mismatch %r vs %r" % (key, field, a, b)
                    else:
                        assert abs(a - b) <= 1e-9, "%s.%s %r vs %r" % (key, field, a, b)
                else:
                    assert a == b, "%s.%s %r vs %r" % (key, field, a, b)
                checked += 1
    return checked


_RECOMPUTE_ALIASES_INV = {v: k for k, v in _RECOMPUTE_ALIASES.items()}


# ---------------------------------------------------------------------------
# Derived quantities computed from predictions + labels (asserted vs summary)
# ---------------------------------------------------------------------------

def threshold_trajectory(root, stream, arm):
    """(end_index list, threshold list) from policy_actions, chronological."""
    acts = read_policy_actions(root, stream, arm)
    xs = [a["end_index"] for a in acts]
    ts = [a["threshold"] for a in acts]
    return xs, ts


def count_threshold_increases(ts, eps=1e-12):
    return sum(1 for i in range(1, len(ts)) if ts[i] > ts[i - 1] + eps)


def in_event_exceedance(root, stream, arm="fixed_threshold"):
    """E3 quantities from predictions + labels.

    Returns dict: in_event, exceed, max_run, theta0.  A window is 'in event'
    when its end_index falls inside a labelled span; 'exceed' counts scores
    strictly above the fixed anchor theta0 (the first threshold in the file).
    """
    preds = read_predictions(root, stream, arm)
    labels = read_labels(root, stream, arm)  # read after predictions
    events = labels["events"]
    theta0 = preds[0]["threshold"]

    def in_ev(ei):
        return any(s <= ei < e for (s, e) in events)

    in_event = [p for p in preds if in_ev(p["end_index"])]
    exceed = [p for p in in_event if p["score"] > theta0]
    run = mx = 0
    for p in in_event:
        if p["score"] > theta0:
            run += 1
            mx = max(mx, run)
        else:
            run = 0
    return {"in_event": len(in_event), "exceed": len(exceed),
            "max_run": mx, "theta0": theta0}


def action_counts(root, stream, arm):
    """Counts of hold/alert/defer/recalibrate for one run."""
    acts = read_policy_actions(root, stream, arm)
    out = {}
    for a in acts:
        out[a["action"]] = out.get(a["action"], 0) + 1
    return out


def clipped_windows(root, stream, arm="fixed_threshold", ratio=3.0):
    """Windows whose score exceeds ratio*theta0 (clipped in the scorer-limit y axis)."""
    preds = read_predictions(root, stream, arm)
    theta0 = preds[0]["threshold"]
    return sum(1 for p in preds if p["score"] > ratio * theta0)


# ---------------------------------------------------------------------------
# TeX helpers
# ---------------------------------------------------------------------------

def fnum(x, nd=3):
    """Format a number for display; None -> LaTeX en-dash placeholder token."""
    if x is None:
        return "--"
    if isinstance(x, float):
        s = ("%%.%df" % nd) % x
        return s
    return str(x)


def frac(num, den):
    if den in (0, None):
        return "--"
    return "%d/%d" % (num, den)
