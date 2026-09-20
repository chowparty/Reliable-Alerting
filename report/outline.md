# Report outline (source, not the completed report)

This file is a minimal report source, not the completed 10-15 page report.
The Day-1 synthetic snapshot below is implementation evidence, not a
real-data performance result.

Submission per [Guidelines for Report](../../Guidelines%20for%20Report.md):
10-15 page report, signed by the supervisor, spiral-bound, one copy per
group, submitted in the classroom before the viva on 30 September 2026 at
10:00 AM; 10-minute presentation of 10-15 slides plus Q&A.

Phase-II evaluation is separate. Its [criteria](../../tech-project-phase-ii-evaluation-criteria.md)
list 81-100 for a student-first-author paper accepted/published in an SCI,
SCI Expanded, Scopus-indexed or UGC-CARE journal plus viva performance;
72-89 for a student-first-author full paper accepted/published in a
peer-reviewed Scopus-indexed conference OR start-up registration plus viva;
and below 72 on viva performance. The bands overlap at 81-89. Confirm their
interpretation, the first-author condition for all three teammates, and the
publication route with the supervisor. Submission is not acceptance; no
mark is promised.

## Front Page

- Project title: Reliable Alerting for Time-Series Anomaly Detection under Changing Conditions.
- Team: Pratyush, Aman, Nakul.
- Supervisor name: pending (to be confirmed; no signature or logo added here).
- NSUT logo: required in the final front page; obtain the approved asset.

## Table of Contents

To be generated from the final report headings.

## Introduction

Our research studies whether simple decision-time information improves
alerting when streams change after the detector was fitted, compared with
fixed thresholds and established temporal rules. Diagnostics, deferral, and
cautious recalibration are candidates under study, not claimed
contributions.

## Motivation

Changing normal conditions can cause repeated false alerts, while careless
adaptation may hide real faults. A frozen-threshold ablation therefore runs
alongside any adaptive variant so failures stay visible.

## Literature Survey

Seed entries only; official metadata and abstracts checked on 19 September
2026. No broad novelty is claimed.

- Tatbul et al., Precision and Recall for Time Series (NeurIPS 2018),
  https://proceedings.neurips.cc/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html
  — supports range-based anomaly evaluation; it does not specify our
  evaluation implementation.
- Tibshirani, Barber, Candes, and Ramdas, Conformal Prediction Under
  Covariate Shift (NeurIPS 2019),
  https://proceedings.neurips.cc/paper_files/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html
  — weighted conformal construction under stated assumptions; not a
  guarantee for our empirical quantile (`quantile: 0.95`, nearest-rank over
  8 calibration scores).

Further claims wait for full checks on the seven-platform allowlist.

## Problem Statement

Decide per window (normal/alert) at window end from the current score plus
thresholds and history frozen before it, with preprocessing and scoring
fitted only on permitted source data and labels kept out of runtime paths.

## Objective and Methodology

Source, calibration, and replay stay separated: `loading`/`splitting`/
`scoring` build scores (source-fit only), `calibration`/`policy` turn
scores into a fixed-threshold trace, `pipeline` wires the label-free path,
and synthetic tests in `tests/` exercise those same components
(`test_source`, `test_decisions`, `test_pipeline`, `test_evidence`).
Current config: `configs/day01-synthetic.json`; `source_label_use: none`;
no held-out yet (`held_out: not_reserved_or_evaluated`); source modules need
Aman review and the real-stream manifest/reservation (Nakul) is pending.

Metrics seed: report the label-free alert fraction and decision coverage
alongside resource use as distinct quantities. Current instrumentation records
validation/recomputation elapsed time and peak traced Python allocation,
not whole-run latency or peak RAM. Later evaluation can add latency percentiles
and model size. No precision/recall
until the offline evaluator lands (later); the fixed quantile setting is a
reproducibility convention, not a false-alarm guarantee.

Day-1 measured snapshot (19 September 2026): 8 replay windows, 3 alerts,
alerted-window fraction 0.375, decision coverage 1.0 on emitted windows.
Two fresh-process runs agree exactly on substantive rows excluding run_id.
See [saved diagnostics](../results/day01-run-a/diagnostics.json),
[comparison](../results/day01-compare.json), and
[executed commands](../results/day01-commands.txt). No evaluation labels were
used, so these counts do not establish detection quality or novelty.

Generated figure: end_index versus score from the saved trace, using

```sh
.venv/bin/python -m reliable_alerting.evidence figure results/day01-run-a/predictions.csv --output results/day01-scores.svg
```

![Day-1 synthetic score trace](../results/day01-scores.svg)

The generated figure is at `results/day01-scores.svg` relative to the
repository root. Use a new output path when regenerating it.

## Simulation Platform and Requirements

Python `>= 3.12` (baseline 3.12); stdlib `unittest`; no extra dependencies.
Reproduce with `.venv/bin/python -m unittest discover -s tests -v` and the
pipeline/compare commands in `README.md`. Each output needs a new
directory (existing output dir or file is refused).

## Conclusion

No final results yet. Null and inconclusive outcomes remain valid and will
be reported with actual alert volume, coverage, and resources.

## References

To be completed from primary sources on the seven-platform allowlist.
ArXiv and other outside sources are discovery/background only.
