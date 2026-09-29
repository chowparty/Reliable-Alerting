# Evidence index — Phase-I report

Maps every claim ID used in the final report (`research/report/submission/report.tex`) to its
source file, the run or commit it belongs to, and — for result files — a SHA-256. This file
holds pointers only; no raw results are committed (`results/` is git-ignored). The study can be
regenerated with `.venv/bin/python run_policy_study.py --output-root results/20260929-policy-study-v2`
(see `README.md`), and the figures/tables from
`research/report/submission/generate/{make_figures.py,make_tables.py}`.

## Pinned provenance

| Item | Value |
|---|---|
| Study run (all figure/table/synthetic numbers) | `results/20260929-policy-study-v2` |
| Study branch / commit | `phase1-policy-study` @ `f88679e` |
| Study `summary.json` SHA-256 | `0de6e0f8deb82dbb5c60fb38e2e1579cd9cf2938720b640244aae971ee14ac76` |
| Independent recompute | `report-work/evidence/recompute-output-policy-study.json` — 99 runs, 0 mismatches |
| P1 tracked-source evidence commit | `0363e24a6998e1a21d7444706c776835a02a8a9b` (github.com/chowparty/Reliable-Alerting) |
| Fresh audit rerun (baseline rows, thresholds) | `results/20260929-results-audit-fresh` (clean @ `0363e24`) |
| Claim register (full text of C01–C31) | `report-work/evidence/claim-register.md` |

Result-file rows below give the SHA of the `summary.json` that carries the value, since
per-arm outputs (`predictions.csv`, `policy_actions.csv`, `evaluation/labels.json`) are the
inputs the generators recompute and are pinned collectively by the recompute file (99 runs,
0 mismatches) rather than by a single digest here.

## Claim → source

| ID | What it supports in the report | Source file | Run / commit | SHA-256 |
|---|---|---|---|---|
| C01 | window 4 / stride 4, chronological splits, scorer + calibration setup | `run_real_streams.py` L17–19, L34–77 | `0363e24` | (tracked source; git blob) |
| C04 | held-out boundary: `SKAB/other/21.csv` named reserved, disputed, never opened | `manifest.md` L18–31 | `0363e24` | (tracked source) |
| C08 | calibration thresholds 1.308542250880009 (valve1, 43 win) / 1.1255423193543013 (valve2, 40 win) | `results/20260929-results-audit-fresh/valve{1,2}/fixed_threshold/diagnostics.json` | audit-fresh @ `0363e24` | reproduced by `recompute-output.json` (pinned `b57e02c3…`) |
| C09 | valve1 ten-row baseline (fixed/rolling/k-consec/m-of-n/hysteresis) | `report-work/evidence/results-audit.md`; `summary.json` valve1 | v2 @ `f88679e` | `0de6e0f8…ac76` (summary.json) |
| C10 | valve2 ten-row baseline | `results-audit.md`; `summary.json` valve2 | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C11 | shared byte-identical score trace per stream | `results-audit.md`; `verification-log.md` | `0363e24` | (tracked source) |
| C12 | full coverage, zero deferrals for the five existing arms | `summary.json`; `policy.py` | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C13 | rolling vs fixed alert-volume multiples (97 vs 6; 70 vs 18) | `summary.json` valve{1,2} rolling_threshold / fixed_threshold | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C15 | saved configs record `held_out: not_reserved_or_evaluated`, `source_label_use: none` | `results/…/valve1/fixed_threshold/config.json`; `pipeline.py` L56–69 | `0363e24` | (tracked source) |
| C16 | held-out record conflict (runner vs manifest) | `discrepancy-list.md`; `manifest.md` L16–31 | `0363e24` | (tracked source) |
| C17 | univariate `Current` scoring; predictions saved before label join | `loading.py` L30–44; `run_real_streams.py` L34–76 | `0363e24` | (tracked source) |
| C18 | one labelled event per stream (valve1 [574,975), valve2 [562,956)) | `configs/day04-valve{1,2}-labels.json` | `0363e24` | (tracked source) |
| C20 | provenance limit; origin/licence not independently verified; development-only | `provenance-audit.md`; `discrepancy-list.md` (D06/D07) | `0363e24` | (tracked source) |
| C22 | every tabulated per-(stream,arm) cell equals the saved study, recomputed | `summary.json`; `recompute-output-policy-study.json` | v2 @ `f88679e` | `0de6e0f8…ac76` (summary.json); recompute 99/0 |
| C23 | ratchet: 0 increases in 143/140; ends 0.258 / 0.406 from 1.309 / 1.126 | `summary.json` + `policy_actions.csv` rolling_threshold valve{1,2} | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C24 | E3: in-event exceedance 6/100, 13/98; max run 2 | `predictions.csv` + `evaluation/labels.json` fixed_threshold valve{1,2} | v2 @ `f88679e` | inputs pinned by recompute 99/0 |
| C25 | rolling recalls same event at higher volume (97 vs 6; 70 vs 18) | `summary.json` valve{1,2} | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C26 | Sun coverage 54/143, 57/140; 22–90/260 on Y1–Y7 | `summary.json` `<stream>.sun_confidence_sequence` | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C27 | Y2 ramp lock-in: 1 recal, 3 defer, 51 alert windows, non-event 204, 50 episodes | `summary.json` Y2.anchored_recalibration | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C28 | Y4 declared limit: in-event fraction 0.020 vs fixed 0.746 | `summary.json` Y4.anchored_recalibration / fixed_threshold | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C29 | Y6 cap load-bearing: non-event 757 / 10 defer vs no-cap 16 | `summary.json` Y6.anchored_recalibration / anchored_no_cap | v2 @ `f88679e` | `0de6e0f8…ac76` |
| C31 | Y3/Y7 still alert post-shift fault at recall 1/1, in-event 0.29 | `summary.json` Y3/Y7.anchored_recalibration | v2 @ `f88679e` | `0de6e0f8…ac76` |

Claim IDs C02, C03, C05, C06, C07, C14, C19, C21, C30 back the report's framing, scope and
integrity statements (development-only scope, strongest-opposing-conclusion stance, the v2
study provenance) rather than a single printed number; their full text and sources are in
`report-work/evidence/claim-register.md`. C30 is the v2-study provenance row summarised in
"Pinned provenance" above.
