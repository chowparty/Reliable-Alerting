#!/usr/bin/env python3
"""Deterministic booktabs table generator for the NSUT Phase-I report (P6).

Emits bare ``\\begin{tabular}...\\end{tabular}`` LaTeX fragments (no float, no
caption) meant to be wrapped in a table environment in the report or a beamer
frame, plus ``tables-manifest.json``.  Requires the ``booktabs`` package in the
including document.

Every displayed number comes from summary.json and is cross-checked against
report-work/evidence/recompute-output-policy-study.json (99 runs, 0 mismatches)
before any table is written.  Undefined values print as ``--`` (see the footnote
text recorded in the manifest / README).

Usage:
    python3 make_tables.py [STUDY_ROOT]
"""

from __future__ import annotations

import json
import os
import sys

# _studylib is a sibling module in generate/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _studylib as L

HERE = os.path.dirname(os.path.abspath(__file__))
# Promoted: fragments, preview and manifest are written into submission/tables.
OUT = L.TABLES_OUT

# Short, page-safe arm labels.
ARM_LABEL = {
    "fixed_threshold": "fixed",
    "rolling_threshold": "rolling (n.o.)",
    "rolling_threshold_all": "rolling (all)",
    "k_consecutive": "k-consec.",
    "m_of_n": "m-of-n",
    "hysteresis": "hysteresis",
    "anchored_recalibration": "anchored",
    "anchored_no_cap": "no-cap",
    "anchored_no_stability": "no-stability",
    "anchored_no_defer": "no-defer",
    "sun_confidence_sequence": "Sun",
}

DASH = "--"  # printed for undefined values; meaning stated in the footnote.


def cell(m, key):
    v = m.get(key)
    return DASH if v is None else v


def num(v, nd=1):
    if v is None:
        return DASH
    if isinstance(v, float):
        return ("%%.%df" % nd) % v
    return str(v)


# ---------------------------------------------------------------------------
# tab-skab: valve1 + valve2 x 11 arms, full metric set
# ---------------------------------------------------------------------------

def tab_skab(summary):
    cols = ("Stream & Arm & Alert & Epis. & Recall & False & Mean & Non-ev. & "
            "In-ev. & Cover. & Def. & Recal. \\\\\n")
    units = ("& & win. & & $n/d$ & epis. & delay & dur. & alert & $n/d$ & & \\\\\n")
    lines = []
    lines.append("\\begin{tabular}{llrrcrrrrcrr}\n")
    lines.append("\\toprule\n")
    lines.append(cols)
    lines.append(units)
    lines.append("\\midrule\n")
    for si, stream in enumerate(L.SKAB_STREAMS):
        for ai, arm in enumerate(L.ARMS):
            m = L.stream_arm_metrics(summary, stream, arm)
            row = [
                stream if ai == 0 else "",
                ARM_LABEL[arm],
                str(m["alert_windows"]),
                str(m["alert_episodes"]),
                L.frac(m["event_recall_num"], m["event_recall_den"]),
                str(m["false_episodes"]),
                num(m["mean_delay"], 1),
                str(m["non_event_alert_duration"]),
                num(m["in_event_alerted_fraction"], 3),
                L.frac(m["coverage_num"], m["coverage_den"]),
                str(m["deferrals"]),
                str(m["recalibration_count"]),
            ]
            lines.append(" & ".join(row) + " \\\\\n")
        if si == 0:
            lines.append("\\midrule\n")
    lines.append("\\bottomrule\n")
    lines.append("\\end{tabular}%\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# tab-synthetic: Y1-Y7 x subset of arms, purpose columns only (one page width)
# ---------------------------------------------------------------------------

SYNTH_ARMS = [
    "fixed_threshold", "rolling_threshold", "rolling_threshold_all",
    "anchored_recalibration", "anchored_no_cap", "anchored_no_stability",
    "anchored_no_defer", "sun_confidence_sequence",
]


def tab_synthetic(summary, arms=SYNTH_ARMS):
    lines = []
    lines.append("\\begin{tabular}{llrrcrr}\n")
    lines.append("\\toprule\n")
    lines.append("Scen. & Arm & Non-ev. & In-ev. & Recall & Cover. & "
                 "Def./Rec. \\\\\n")
    lines.append("& & dur. & alert & $n/d$ & $n/d$ & \\\\\n")
    lines.append("\\midrule\n")
    for si, stream in enumerate(L.SYNTH_STREAMS):
        for ai, arm in enumerate(arms):
            m = L.stream_arm_metrics(summary, stream, arm)
            recall = (L.frac(m["event_recall_num"], m["event_recall_den"])
                      if m["event_recall_den"] else DASH)
            row = [
                stream if ai == 0 else "",
                ARM_LABEL[arm],
                str(m["non_event_alert_duration"]),
                num(m["in_event_alerted_fraction"], 3),
                recall,
                L.frac(m["coverage_num"], m["coverage_den"]),
                "%d/%d" % (m["deferrals"], m["recalibration_count"]),
            ]
            lines.append(" & ".join(row) + " \\\\\n")
        if si != len(L.SYNTH_STREAMS) - 1:
            lines.append("\\midrule\n")
    lines.append("\\bottomrule\n")
    lines.append("\\end{tabular}%\n")
    return "".join(lines)


# Compact synthetic arm subset for the page budget: the anchor (fixed), the
# unconditional pole (rolling all), the controller, its cap ablation, and the
# abstention baseline. Same cells and same summary-equals check, fewer rows.
COMPACT_SYNTH_ARMS = [
    "fixed_threshold", "rolling_threshold_all", "anchored_recalibration",
    "anchored_no_cap", "sun_confidence_sequence",
]


def tab_synthetic_compact(summary):
    return tab_synthetic(summary, arms=COMPACT_SYNTH_ARMS)


# ---------------------------------------------------------------------------
# tab-ablation: which guard component changes which synthetic outcome
# Built from measured deltas of each ablation vs the full controller.
# ---------------------------------------------------------------------------

def _outcome(summary, stream, arm):
    m = L.stream_arm_metrics(summary, stream, arm)
    return {
        "nonev": m["non_event_alert_duration"],
        "defer": m["deferrals"],
        "recal": m["recalibration_count"],
        "inev": m["in_event_alerted_fraction"],
        "cover": (m["coverage_num"], m["coverage_den"]),
    }


def tab_ablation(summary):
    # Compare each ablation against the full anchored controller per scenario,
    # and describe the measured effect.  All facts are measured, not asserted.
    ablations = [
        ("anchored_no_cap", "cap $\\kappa$"),
        ("anchored_no_stability", "stability $\\rho$"),
        ("anchored_no_defer", "deferral $D$"),
    ]
    lines = []
    lines.append("\\begin{tabular}{llrrrr}\n")
    lines.append("\\toprule\n")
    lines.append("Removed guard & Scen. & $\\Delta$non-ev. & $\\Delta$defer & "
                 "$\\Delta$recal. & $\\Delta$in-ev. \\\\\n")
    lines.append("\\midrule\n")
    any_row = False
    for arm, label in ablations:
        first = True
        for stream in L.SYNTH_STREAMS:
            full = _outcome(summary, stream, "anchored_recalibration")
            abl = _outcome(summary, stream, arm)
            d_nonev = abl["nonev"] - full["nonev"]
            d_defer = abl["defer"] - full["defer"]
            d_recal = abl["recal"] - full["recal"]
            if abl["inev"] is None or full["inev"] is None:
                d_inev = None
            else:
                d_inev = abl["inev"] - full["inev"]
            # only show scenarios where the ablation changes an outcome
            changed_inev = (d_inev is not None and abs(d_inev) >= 1e-9)
            if (d_nonev == 0 and d_defer == 0 and d_recal == 0
                    and not changed_inev):
                continue
            row = [
                label if first else "",
                stream,
                ("%+d" % d_nonev),
                ("%+d" % d_defer),
                ("%+d" % d_recal),
                (DASH if d_inev is None else "%+.3f" % d_inev),
            ]
            lines.append(" & ".join(row) + " \\\\\n")
            first = False
            any_row = True
        if not first:
            lines.append("\\midrule\n")
    # drop a trailing midrule if present
    if lines[-1] == "\\midrule\n":
        lines.pop()
    if not any_row:
        lines.append("\\multicolumn{6}{c}{no measured change} \\\\\n")
    lines.append("\\bottomrule\n")
    lines.append("\\end{tabular}%\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Preview + manifest
# ---------------------------------------------------------------------------

FOOTNOTE = ("`--' marks a value that is undefined for that row: mean delay is "
            "undefined when the arm raises no in-event alert (recall $0/d$); "
            "recall $n/d$ is shown as `--' only where the scenario has no "
            "labelled event ($d=0$). All durations and delays are in "
            "sample-index units.")

CAPTIONS = {
    "tab-skab":
        "SKAB development streams (valve1, valve2) $\\times$ 11 arms on the shared "
        "score trace: alert windows, alert episodes, event recall $n/d$, false "
        "episodes, mean delay, non-event alert duration, in-event alerted fraction, "
        "decision coverage $n/d$, deferrals and recalibrations. Every arm keeps "
        "event recall $1/1$ where it alerts; the rolling (normal-only) arm carries "
        "many times the alert windows of fixed at the same recall, and the Sun arm "
        "trades coverage for abstention. Sample-index units; `--' as in the "
        "footnote.",
    "tab-synthetic":
        "Synthetic stress family Y1--Y7 $\\times$ 8 arms, purpose columns only: "
        "non-event alert duration, in-event alerted fraction, event recall $n/d$, "
        "decision coverage $n/d$, and deferrals/recalibrations. These are "
        "deterministic engineering checks, not evidence of real-world benefit. "
        "Sample-index units; `--' as in the footnote.",
    "tab-synthetic-compact":
        "Synthetic stress family Y1--Y7, compact 5-arm view (fixed, rolling all, "
        "anchored, no-cap, Sun) for the page budget: non-event alert duration, "
        "in-event alerted fraction, event recall $n/d$, decision coverage $n/d$, and "
        "deferrals/recalibrations. Same values and same summary-equals check as the "
        "full 8-arm table. Deterministic engineering checks, not evidence of "
        "real-world benefit. Sample-index units; `--' as in the footnote.",
    "tab-ablation":
        "Ablation map: measured change in each synthetic outcome when a single guard "
        "component (cap $\\kappa$, stability $\\rho$, deferral $D$) is removed from "
        "the anchored controller, relative to the full controller on the same trace. "
        "Only rows with a non-zero measured change are shown. Sample-index units.",
}

TABLE_LABEL_MAP = {
    "tab-skab": ["tab:baseline"],
    "tab-synthetic": [],
    "tab-synthetic-compact": [],
    "tab-ablation": [],
}

GEN_CMD = "python3 research/report/submission/generate/make_tables.py"


PREVIEW_TEMPLATE = (
    r"""\documentclass[11pt]{article}
\usepackage[a4paper,landscape,margin=12mm]{geometry}
\usepackage{booktabs}
\usepackage{amsmath}
\pagestyle{empty}
\begin{document}
"""
    "%% Each table shown once; check it fits one page width.\n"
    "\\begin{center}\\textbf{tab-skab}\\end{center}\n"
    "\\begin{center}\\small\\input{tab-skab.tex}\\end{center}\n"
    "\\clearpage\n"
    "\\begin{center}\\textbf{tab-synthetic}\\end{center}\n"
    "\\begin{center}\\small\\input{tab-synthetic.tex}\\end{center}\n"
    "\\clearpage\n"
    "\\begin{center}\\textbf{tab-ablation}\\end{center}\n"
    "\\begin{center}\\small\\input{tab-ablation.tex}\\end{center}\n"
    "\\end{document}\n"
)


def build_manifest(root, files):
    inputs = [os.path.join(root, "summary.json")]
    rc = L.recompute_path(root)
    if rc is not None:
        inputs.append(rc)
    manifest = {
        "generator": "research/report/submission/generate/make_tables.py",
        "regenerate_command": "%s %s" % (GEN_CMD, root),
        "number_source": ("summary.json; cross-checked against the review recompute "
                          "file report-work/evidence/recompute-output-policy-study.json "
                          "(99 runs, 0 mismatches) when that review pack is present"),
        "undefined_marker": DASH,
        "footnote": FOOTNOTE,
        "table_label_map": TABLE_LABEL_MAP,
        "input_paths": [os.path.relpath(p, L.RESEARCH_ROOT) for p in inputs],
        "input_sha256": {os.path.relpath(p, L.RESEARCH_ROOT):
                         L.sha256_file(p) for p in inputs},
        "tables": {},
    }
    for tid, path in files.items():
        manifest["tables"][tid] = {
            "output_file": os.path.basename(path),
            "output_sha256": L.sha256_file(path),
            "caption": CAPTIONS[tid],
            "report_labels": TABLE_LABEL_MAP[tid],
            "licence": ("Generated from our own saved study outputs "
                        "(research repo, branch phase1-policy-study, commit f88679e); "
                        "SKAB data licence per report-work/visuals/asset-ledger.md."),
        }
    return manifest


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else L.DEFAULT_ROOT)
    summary = L.load_summary(root)
    recompute = L.load_recompute(root)
    L.assert_summary_matches_recompute(summary, recompute)

    os.makedirs(OUT, exist_ok=True)
    frags = {
        "tab-skab": tab_skab(summary),
        "tab-synthetic": tab_synthetic(summary),
        "tab-synthetic-compact": tab_synthetic_compact(summary),
        "tab-ablation": tab_ablation(summary),
    }
    files = {}
    for tid, text in frags.items():
        path = os.path.join(OUT, tid + ".tex")
        with open(path, "w") as fh:
            fh.write(text)
        files[tid] = path

    with open(os.path.join(OUT, "tables-preview.tex"), "w") as fh:
        fh.write(PREVIEW_TEMPLATE)

    manifest = build_manifest(root, files)
    with open(os.path.join(OUT, "tables-manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("wrote:", ", ".join(sorted(os.path.basename(p) for p in files.values())),
          "+ tables-preview.tex + tables-manifest.json")


if __name__ == "__main__":
    main()
