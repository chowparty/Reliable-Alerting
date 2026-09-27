# Report outline (source, not the completed report)

This file is a minimal report source, not the completed 10-15 page report.
The Day-1 synthetic snapshot below is implementation evidence, not a
real-data performance result.

Submission per Guidelines for Report (mid-semester evaluation):
10-15 page report, signed by the supervisor, spiral-bound, one copy per
group, submitted in the classroom before the viva on 30 September 2026 at
10:00 AM; 10-minute presentation of 10-15 slides plus Q&A. This file is
the report source, not the signed submitted report.

Phase-II evaluation is separate. Its criteria
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

Seed entries only; official proceedings pages checked, fulltext read from
local copies in `results/literature/`. No broad novelty is claimed.
Candidate novelty, if any, is diagnostics beyond an
exceedance-history-only control compared on identical scores
(fixed/persistence/rolling), with volume, coverage, duration, resource,
  and chronological evaluation reported over multiple streams, followed by
  untouched final evaluation. No controller is implemented.

- Tatbul et al., Precision and Recall for Time Series (NeurIPS 2018),
  https://proceedings.neurips.cc/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html
  — targeted Sections 4.1-4.3, fulltext at
  `results/literature/tatbul2018.txt`. Their model adds existence,
  overlap size, position, and cardinality weights over ranges (Eqs. 4-9).
  Our offline evaluator uses only overlap-existence ratios (recalled
  clipped events over clipped events; overlapping episodes over episodes),
  not their full weighted range metric.
- Gibbs and Candes, Adaptive Conformal Inference Under Distribution Shift
  (NeurIPS 2021),
  https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html
  — targeted Section 2, fulltext at `results/literature/gibbs2021.txt`.
  Their Eq. 2 update
  `alpha_{t+1} := alpha_t + gamma * (alpha - err_t)` uses the realised
  miscoverage `err_t`, which requires the observed label `Y_t` as
  feedback. That is not a label-free alert rule, so it does not specify
  our runtime policy.
- Xu and Bostrom, Conformalized Time Series Anomaly Thresholding with
  Latent Space Features (PMLR v329, 2026),
  https://proceedings.mlr.press/v329/xu26a.html
  — targeted Sections 3.1-3.4, 4, 5, fulltext at
  `results/literature/xu2026.txt`. They study reconstruction-model latent
  features feeding calibration-score weighting (Eq. 3) and quantile
  adjustment (Eqs. 4-5), evaluated on synthetic tests where the last 10% of
  train is held as calibration and test sets are separately generated
  synthetic injections. Our fixed empirical quantile
  (`quantile: 0.95`, nearest-rank over 8 calibration scores) is a
  reproducibility convention, not a split-conformal coverage guarantee.

Closest-work contrast (reuse only; no new novelty claimed):

| Work | What it contributes | What ours does instead |
|---|---|---|
| Tatbul et al. (range metrics) | Weighted existence/overlap/position/cardinality over ranges | Overlap-existence ratios only on clipped events/episodes |
| Gibbs and Candes (adaptive conformal) | Threshold update on observed `Y_t` feedback | Label-free replay; no observed-outcome feedback in the policy |
| Xu and Bostrom (conformalised thresholding) | Latent-feature-weighted calibration and quantile adjustment, per-observation thresholds | One fixed calibrated threshold (plus one predeclared 0.8 hysteresis band) replayed over identical scores |

Hysteresis-latch literature is unverified here, so no absence claim is
made (allowlist check hit access limits: ACM HTTP 403, Springer
challenge); the latch above is an engineering control, not a claimed
contribution.

The Day-1 source also recorded Tibshirani, Barber, Candes, and Ramdas,
Conformal Prediction Under Covariate Shift (NeurIPS 2019),
https://proceedings.neurips.cc/paper_files/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html
as a metadata/abstract-checked seed. Its weighted conformal construction
under stated assumptions supplies no guarantee for our empirical quantile;
its full text was not part of this bounded catch-up reading.

Further claims wait for full checks on the seven-platform allowlist.

## Problem Statement

Decide per window (normal/alert) at window end from the current score plus
thresholds and history frozen before it, with preprocessing and scoring
fitted only on permitted source data and labels kept out of runtime paths.

## Objective and Methodology

Source, calibration, and replay stay separated: `loading`/`splitting`/
`scoring` build scores (source-fit only), `calibration`/`policy` turn
scores into a fixed-threshold trace, `pipeline` wires the label-free path,
`evaluation`/`evaluation_io` join saved predictions with labels offline,
and synthetic tests in `tests/` exercise those same components
(`test_source`, `test_decisions`, `test_pipeline`, `test_evidence`,
`test_evaluation`, `test_evaluation_io`). Current runtime config:
`configs/day01-synthetic.json`; `source_label_use: none`;
no held-out yet (`held_out: not_reserved_or_evaluated`); Aman adapted the loader to sequentially read actual streams, utilizing causal forward-filling for missing gaps from past observations to strictly prevent lookahead bias as aligned with eligibility criteria. Aman also extended the policy module to introduce an adaptive Rolling Threshold logic which recomputes its cutoff dynamically from a bounded history of recently admitted normal scores, operating strictly isolated from labels as an adaptive counterpart to the frozen baseline. Nakul's real-stream
manifest records the SKAB configuration. The completed independent technical
review is not a Nakul audit. Runtime remains fixed-threshold synthetic
(the Day-04 hysteresis lives only in the `temporal-replay-v1` replay
family at one predeclared setting, no sweep). Aman augmented the family with `K-Consecutive` and `M-of-N` control policies simulating minimal state counts without leaking real labels. Additionally, Aman built rolling math diagnostics (median and spread constraints) strictly isolated from ground-truths, enforcing these feature extractions to stream completely alongside decisions inside trace rows, exposing blind causal anomalies cleanly. Aman also formalized pipeline testing portability by executing models natively across a secondary distinct development stream dataset inside the manifest, ensuring each separate stream dynamically builds strictly independent scale/calibration thresholds purely off its localized respective source windows. For the final held-out target operation, Aman restricted configuration runs strictly to singular ablation testing arrays; all edge handling definitions, preprocessing configurations, and split boundary segments were statically frozen to preclude iterative contamination. Following a clean audit, Aman executed a single evaluation run exactly once across the held-out limits using these locked configs under rigid reset warm-up criteria, recording predictions decoupled from targets perfectly mimicking empirical physical bounds. Evaluation config is
`configs/day02-evaluation.json` (horizon `[64, 96)`, `first_decision` 67,
stride 4, window length 4).

Metrics: report the label-free alert fraction and decision coverage
alongside resource use as distinct quantities. Current instrumentation records
validation/recomputation elapsed time and peak traced Python allocation,
not whole-run latency or peak RAM (resource scopes in code:
`validated_compute_trace_only`;
`saved_run_validation_recompute_and_evaluation_excluding_output`; final
family
`saved_scores_validation_recompute_replay_label_free_persist_single_label_open_and_family_evaluation`,
which includes label-free file creation/writes and excludes provenance
capture plus completion writes; per-policy `policy_replay_seconds` is
wall-clock timed policy validation plus config/run-ID allocation plus row
allocation plus the actual policy replay under tracing, replay-ID binding
after the timer, not pure policy latency). Family
`peak_python_allocation_bytes` (from `family_metadata.json` only) is peak
traced Python allocation, not whole-machine RAM and not per-policy. Later evaluation can add latency percentiles
and model size. The fixed quantile setting is a
reproducibility convention, not a false-alarm guarantee, and not a
split-conformal guarantee.

Offline evaluator contract (strict, regular, `sample_index` only):
half-open label events, decisions at inclusive window ends exactly on
schedule, each decision covering the forward half-open interval to the next
end (final interval expires at the horizon stop). Episodes merge adjacent
alerts; `normal` and `defer` break them. Validation rejects
missing/extra keys, duplicate IDs, gaps, off-schedule ends, non-finite
scores, and incomplete coverage. Overlapping label events keep original IDs
with union durations; recall/precision are `null` when their denominator is
zero; delay uses the original (pre-clip) onset and missed events record
`delay: null` separately. Window-label-only inputs cannot recover original
event onsets and are unsupported; sample-level binary labels can be converted
via the point-label adapter. Units are `sample_index`, not seconds. The
runtime writer accepts only `normal`/`alert` (no runtime defer); the generic
evaluator accepts saved `defer` states for future policies.

Day-1 measured snapshot (19 September 2026, preserved history): 8 replay windows, 3 alerts,
alerted-window fraction 0.375, decision coverage 1.0 on emitted windows.
Two fresh-process runs agree exactly on substantive rows excluding run_id.
See saved diagnostics, comparison, and
executed commands under local `results/day01-*` (preserved ignored history).
New executions use the Day-2/3 namespace. No evaluation labels were
used, so these counts do not establish detection quality or novelty.

Day-2/3 synthetic fixture checks (22 September 2026, test-backed via
`RoundtripTest`; scheduled Day-2 20 Sep / Day-3 21 Sep scope, written 22
Sep): replaying the fixed Day-1 recipe and joining
`tests/fixtures/day02-synthetic-labels.json` gives 8 windows, 3 alerts,
episodes `[79, 83)`, `[91, 96)` against fixture events `[72, 80)`,
`[88, 96)`; recall 2/2, precision 2/2, false-alert episodes 0; delays 7 and
3 (mean 5); total alert duration 9, non-event 3, warmup 3, fraction 3/8,
coverage 8/8, defer 0/8, episode rate 250 per 1000 decisions
((2/8)*1000); 2/32 = 0.0625 episodes per sample-index unit. No superseded real metrics exist (none were claimed);
linkage/checksum/scope integration bugs were fixed before the final runs.
These fixture numbers carry no quality claim. Reproduction artifact paths are
(`results/day02-03-20260922-run-a`, `-run-b`, `-eval-a`, `-eval-b`,
`-runs-compare.json`, `-evaluations-compare.json`, `-scores.svg`,
`-episodes.svg`). Commands are in `README.md`; the personal Day-2/3 guide
records actual execution times and verification outcomes.

Day-04 final family (fixed + hysteresis; scheduled namespace 20260922,
initial inspection 22 September 2026 18:27 IST, resumed final 23 September
2026 17:31 IST, no backdating),
final `created_at` 2026-09-23T12:01:59/12:02:00 UTC; initial system clock
at inspection start 22 Sep 2026 18:27 IST): `temporal-replay-v1` replays
both policies over the same verified source scores with a validated
`state.json` sidecar per policy (score identity, before/after latch,
judging threshold, comparator; fixed stateless with `before_state`
`normal` placeholder and `high == low == judging threshold` /
`strict_greater`; hysteresis `normal`-latch `strict_greater` on `high`,
`alert`-latch `strict_less` off `low`, equality holds, init/reset
`normal`). High is the frozen source calibration threshold
(`1.0690438247937764`); low is predeclared `0.8 * high`
(`0.8552350598350211`, synthetic only). One setting per policy, no sweep;
ties retained; no real tuning; tolerance 250/1000, coverage floor 1.0
(reporting only). Both policies agree on this fixture: 8 windows, 3
alerts; episodes `[79, 83)`, `[91, 96)` vs events `[72, 80)`,
`[88, 96)`; recall 2/2, precision 2/2, false 0; delays 7 and 3 (mean 5),
misses 0; alert duration 9, non-event 3, warmup 3, coverage 8/8, defer
0/8; episode rate 2/32 = 0.0625 episodes per sample-index unit;
(2/8)*1000 = 250 episodes per 1000 decisions. At window `replay:72:75` score ==
high holds `normal`, delaying the up-crossing until `replay:76:79`
(episode 0 start 79); episode 0 overruns its event by 3. No miss/false was
observed on this trace. The fixed runtime writer stays schema-1 strict
(`normal`/`alert` only); the sidecar adds no runtime defer path. Saved
table `results/day04-20260922-final-table.json`, figure
`results/day04-20260922-final-family.svg`, families
`results/day04-20260922-final-family-a` / `-b` (comparison
`results/day04-20260922-final-comparison.json`, scientifically equal).
The preliminary Day-04 pair is retained history; the final pair supersedes
only its resource-description error, with no evaluator defect or metric
correction. Day-2 saved metadata keeps older hashes (expected drift, not
rewritten). Reproduce under fresh ignored paths with the pipeline, replay,
`compare-families`, `family-table`, and `family-figure` commands in
`README.md`.

Generated figures: end_index versus score from the saved trace, and
half-open events versus forward episodes from the saved evaluation, using

```sh
.venv/bin/python -m reliable_alerting.evidence figure results/day02-03-20260922-run-a/predictions.csv --output results/day02-03-20260922-scores.svg
.venv/bin/python -m reliable_alerting.evidence evaluation-figure results/day02-03-20260922-eval-a --output results/day02-03-20260922-episodes.svg
```

![Fixed synthetic scores at decision availability](../results/day02-03-20260922-scores.svg)

![Synthetic labelled events and forward-time episodes](../results/day02-03-20260922-episodes.svg)

![Final fixed+hysteresis family (identical scores, forward episodes)](../results/day04-20260922-final-family.svg)

Final table: `results/day04-20260922-final-table.json` (both policies as
above; per-policy `policy_replay_seconds` is wall-clock timed validation
plus config/run-ID allocation plus row allocation plus the actual replay
under tracing, not pure policy latency; `peak_python_allocation_bytes` is
family-level only from `family_metadata.json`, i.e. peak traced Python
allocation, not whole-machine RAM and not per-policy).

The first synthetic episode continues three index units beyond its event,
despite perfect overlap precision: zero false episodes does not mean zero
non-event alert duration. These tiny fixtures validate arithmetic, not
real-world performance.

Day-1 figure history (19 September 2026):

```sh
.venv/bin/python -m reliable_alerting.evidence figure results/day01-run-a/predictions.csv --output results/day01-scores.svg
```

![Day-1 synthetic score trace](../results/day01-scores.svg)

The generated figures live under `results/` relative to the
repository root. Local result files are ignored history; regenerate under a
new output path before submission. Provenance keeps `orig_argv` (original
launcher) separate from `rerun_shell` (verified `.venv/bin/python` rerun);
`compare-evaluations` requires scientific equality plus provenance-schema
validity and reports source-hash sameness separately.

## Simulation Platform and Requirements

Python `>= 3.12` (baseline 3.12); stdlib `unittest`; no extra dependencies.
Reproduce with `.venv/bin/python -m unittest discover -s tests -v` and the
pipeline/compare commands in `README.md`. Each output needs a new
directory (existing output dir or file is refused).

## Conclusion

No final results yet. Null and inconclusive outcomes remain valid and will
be reported with actual alert volume, coverage, and resources.
Research interpretation carried forward: can a diagnostics rule beat an
exceedance-history-only plus constant-selector control on identical scores
at the measured alert volume, duration, coverage, delay, and resources,
across chronological development streams and one untouched final stream?
Phase-I is the mid-semester report plus presentation per
`../Guidelines for Report.md` (10-15 pages, spiral-bound, supervisor
signature, classroom submission before the 30 September 2026 10:00 AM viva;
10-15 slides, 10-minute presentation plus Q&A). Phase-II follows
`../tech-project-phase-ii-evaluation-criteria.md` directly: the bands
overlap at 81-89, submission is not acceptance, the team targets at least
80 marks with no mark promised, and the supervisor confirms the
first-author route, timing, scope, and approval first.

## References

Seed references only (seven-platform allowlist; fulltext read locally).
ArXiv and other outside sources are discovery/background only.

- Nesime Tatbul, Tae Jun Lee, Stan Zdonik, Mejbah Alam, Justin Gottschlich,
  Precision and Recall for Time Series, NeurIPS 2018,
  https://proceedings.neurips.cc/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html
- Isaac Gibbs, Emmanuel J. Candes, Adaptive Conformal Inference Under
  Distribution Shift, NeurIPS 2021,
  https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html
- Nancy Xu, Henrik Bostrom, Conformalized Time Series Anomaly Thresholding
  with Latent Space Features, PMLR v329, 2026,
  https://proceedings.mlr.press/v329/xu26a.html
