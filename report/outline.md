# Report outline (source, not the completed report)

This file is a report source, not the completed 10-15 page report. The
synthetic snapshots validate implementation arithmetic; the two SKAB
streams below supply development evidence only.

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
| Sun et al. (online quantile thresholding) | Known-p quantile anomalies, independent piecewise-stationary scores, abstaining confidence sequences | Fixed median-gap feature only; no abstain rule, no mistake bound, synthetic check only |
| Navarro et al. (ORTHUS recommendation) | Labelled-history meta-training, per-dataset configuration for an unlabeled new dataset | No recommender; fixed + hysteresis replay on one synthetic trace |
| Volkhonskiy et al. (conformal martingales) | Fixed-reference p-values plus betting, i.i.d. validity for change detection | No martingale/p-values; fixed quantile plus hysteresis control, no validity claimed |

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

- Sun, Sophia Huiwen Sun, Abishek Sankararaman, Balakrishnan Murali
  Narayanaswamy, Online Adaptive Anomaly Thresholding with Confidence
  Sequences, PMLR 235, 2024 (`sun24h`),
  https://proceedings.mlr.press/v235/sun24h.html — targeted abstract,
  Sections 2.1-2.5 and 4-6, fulltext at
  `results/day05-literature/sun24h.txt`. They define anomalies as
  exceeding the known-p tail quantile of the score distribution, model
  scores as independent draws that are piecewise-stationary
  (i.i.d. within segments, detectable separated changes), and abstain
  outside the confidence sequence when the quantile is uncertain. That
  is not a universal semantic-fault guarantee; our provisional median gap
  is a fixed descriptive feature with no abstain rule and no mistake
  bound claimed.
- Navarro, Jose Manuel Navarro, Alexis Huet, Dario Rossi, Meta-Learning
  for Fast Model Recommendation in Unsupervised Multivariate Time Series
  Anomaly Detection, PMLR 224, 2023 (`navarro23a`),
  https://proceedings.mlr.press/v224/navarro23a.html — targeted Sections
  3.1-3.3, fulltext at `results/day05-literature/navarro23a.txt`. Their
  method is ORTHUS (not Hydra): per-dataset scorer-configuration
  recommendation trained (meta-training) on labelled historical datasets
  and applied to an unlabeled new dataset. That is not an online
  alert selector and does not specify our replay policy.
- Volkhonskiy, Denis Volkhonskiy et al., Inductive Conformal Martingales
  for Change-Point Detection, PMLR 60, 2017 (`volkhonskiy17a`),
  https://proceedings.mlr.press/v60/volkhonskiy17a.html — targeted
  Sections 2-3, fulltext at
  `results/day05-literature/volkhonskiy17a.txt`. They build inductive
  conformal martingales from a fixed reference with p-values and a
  betting function; validity is for the i.i.d./exchangeability null, not
  benign-vs-fault identification. Our fixed quantile and hysteresis
  replay use no martingale and claim no such validity.
- Gibbs and Candes (above): their ACI update uses the realised
  miscoverage on the observed `Y_t` as feedback, so it is not a
  label-free alert rule (reaffirmed against `results/literature/gibbs2021.txt`).

Further claims wait for full checks on the seven-platform allowlist.

## Problem Statement

Decide per window (normal/alert) at window end from the current score plus
thresholds and history frozen before it, with preprocessing and scoring
fitted only on permitted source data and labels kept out of runtime paths.

## Objective and Methodology

`loading` and `splitting` preserve order; `scoring` fits on source fit;
`calibration` sets a per-stream threshold; `policy` makes label-free
decisions; `evaluation_io` joins labels only after predictions are saved.
The runtime has fixed, rolling, K-consecutive, M-of-N and hysteresis
policies (`run_real_streams.py`). The CSV loader now rejects missing
`Current` values, as the config declares. Both measured files contain no
blank `Current` cells. Development labels were used offline to locate
source-normal calibration boundaries and to evaluate replay. See
`manifest.md` for exact rows, checksums and that label-use qualification.

The current corrected development runs use
`results/20260928-corrected-development/` and its independent `-b`
rerun. These local ignored outputs are regenerated with the commands in
`README.md`. Both runs agree on every score, threshold, output state and
full evaluation JSON for all ten stream-policy combinations. The older
tracked `result/valve2/` runs used calibration `[400,574)`, overlapping
12 anomalous rows; do not cite them as corrected results. The five
valve1 historical evaluations agree with the corrected rerun.
Saved runtime and evaluation configs are copied into the new runs, and
exact output equality was checked. The provenance file-hash whitelist
does not cover `run_real_streams.py`, `manifest.md`, or the real
evaluation/label configs; do not present it as a complete source audit.

| Development stream | Policy | Alert windows / decisions | Episodes | Event recall | Episode precision | Mean detected delay (sample indices) |
|---|---|---:|---:|---:|---:|---:|
| valve1 | fixed | 6/143 | 4 | 1/1 | 4/4 | 11 |
| valve1 | rolling | 97/143 | 27 | 1/1 | 19/27 | 11 |
| valve1 | K-consecutive | 0/143 | 0 | 0/1 | undefined (0/0) | undefined |
| valve1 | M-of-N | 0/143 | 0 | 0/1 | undefined (0/0) | undefined |
| valve1 | hysteresis | 6/143 | 4 | 1/1 | 4/4 | 11 |
| valve2 | fixed | 18/140 | 12 | 1/1 | 9/12 | 15 |
| valve2 | rolling | 70/140 | 29 | 1/1 | 20/29 | 15 |
| valve2 | K-consecutive | 0/140 | 0 | 0/1 | undefined (0/0) | undefined |
| valve2 | M-of-N | 6/140 | 3 | 1/1 | 2/3 | 27 |
| valve2 | hysteresis | 21/140 | 9 | 1/1 | 6/9 | 15 |

All ten rows have decision coverage 1.0 and zero deferrals. Each stream
has only one labelled event; overlap-based recall and precision are
descriptive, and the policies operate at very different alert volumes.
No rule improvement, concept-drift diagnosis or statistical generalisation
follows from this table. The current instrumentation records
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

Day-05 provisional diagnostic + family (scheduled 23 September 2026;
execution start 2026-09-23T22:21:26+0530 from the shell clock; final saved
experiment chain began 23:20:59+0530 on 23 September, with separate component
timestamps; documentation and verification continued on 24 September): `trailing-median-gap-v1`
(`diagnostics.py`, `diagnostics-v1`) is one setting only —
current-inclusive median of the last 3 replay scores minus the frozen
calibration median, score units, `normalize: false`
(`configs/day05-diagnostic.json`: `trailing_window 3`, `warmup_count 2`,
`reference calibration/median/calibration_scores`,
`time_basis sample_index`, `provisional true`, owner pratyush). First 2
rows are null warmup with `readiness_reason`; each call resets
independently (`independent_call`); calibration strictly precedes scores;
no labels enter. `evidence.py` verifies all 8 rows independently via
fresh sorting arithmetic and joins the diagnostic to the family only in
the saved table/figure. Saved final artifacts:
`results/day05-20260923-final-source-a` / `-b`,
`-diagnostic-a` / `-b`, `-family-a` / `-b`,
`-diagnostic-comparison.json`, `-family-comparison.json`,
`-table-a/b.json`, `-diagnostics-a/b.svg` (both comparisons
`status true`, `scientific_equal true`, head
`a0d1b68ebcef079e33137be77a53b8f7fb4386a9`). The preliminary Day-05
pair without `-final-` is retained history; the final pair corrects the
feature-magnitude figure. Observed final values (synthetic only):
reference median `0.5345219123968882`; 6 ready rows reported separately
from the full 8 policy decisions (five ready features
`0.5345219123968882`, final `2.672609561984441`); fixed and hysteresis
agree on this trace (8 windows, 3 alerts; episodes `[79, 83)`,
`[91, 96)`; recall 2/2, precision 2/2, false 0; delays 7 and 3, mean 5;
durations 9/3/3; coverage 8/8; defer 0/8; 250 per 1000). The tie is not
a policy improvement. The later real-stream comparison above is a separate
development analysis; this diagnostic was not tested as a selector there.
Source-vs-family: source runs fix the scores; families replay both
policies over those identical scores, so identical traces cannot support
a ranking-metric improvement. Limits: the diagnostic-to-policy association
and a justified conditional selector remain absent. The real five-policy
comparison is development-only; authoritative operating points,
held-out reservation, independent pre-held-out audit, and held-out run
remain absent (`held_out: not_reserved_or_evaluated`). Reproduce under fresh
`day05-reproduce-*` paths with the pipeline, `diagnostics`,
`replay`, `compare-diagnostics`, `compare-families`,
`diagnostic-table`, and `diagnostic-plot` commands in `README.md`.

Independent verification on 24 September recomputed every selected column
row in both runs directly from saved scores using three-score
`sum - min - max` arithmetic, independently of the production sort; an
absolute tolerance of `1e-12` covers cancellation roundoff. All 16 rows,
availability indices, contributing histories and warmup states passed.
`results/day05-20260924-independent-audit.json` also records the successful
fresh-path environment-launcher rerun, scientific table equality and
historical Day-4 evaluation equality. Source/configuration and calibration
linkage are checked before the offline feature/outcome join. This is
Pratyush support verification, not verification of a supplied Aman feature
or completion of Nakul's independent audit.

A useful counterexample appears at `replay:80:83`: the current score is
zero while the three-score median gap remains positive
(`0.5345219123968882`). The first ready row `replay:72:75` also has a
positive gap but its score only equals the strict entry cutoff. This
demonstrates why a positive gap is not a fault label. Recent exceedance
rates in the joined table use the same frozen **high** threshold for both
policies, separately from the current judging cutoff and policy state.
Tied policy outcomes provide no observed preference contrast for a selector.
No forecast target, statistical significance, refresh counterfactual or
policy improvement is claimed. No written conditional rule is justified.

Fresh verification: `.venv/bin/python -m unittest discover -s tests -v`
passed **316 tests** in 26.509 seconds; `git diff --check` passed, with the
shell-clock checkpoint at 24 September 2026 11:46:29 IST. Figures were
checked through XML parsing, evidence linkage and geometry/text-extent
checks, not rendered visual inspection. Diagnostic timing excludes
provenance and output writes, includes validation and recomputation, and
  is not end-to-end inference latency; diagnostic peak allocation is unmeasured.

Generated figures: end_index versus score from the saved trace, and
half-open events versus forward episodes from the saved evaluation, using

```sh
.venv/bin/python -m reliable_alerting.evidence figure results/day02-03-20260922-run-a/predictions.csv --output results/day02-03-20260922-scores.svg
.venv/bin/python -m reliable_alerting.evidence evaluation-figure results/day02-03-20260922-eval-a --output results/day02-03-20260922-episodes.svg
```

![Fixed synthetic scores at decision availability](../results/day02-03-20260922-scores.svg)

![Synthetic labelled events and forward-time episodes](../results/day02-03-20260922-episodes.svg)

![Final fixed+hysteresis family (identical scores, forward episodes)](../results/day04-20260922-final-family.svg)

![Day-05 final diagnostic check: scores, forward episodes, ready/warmup lane, and median-gap magnitudes](../results/day05-20260923-final-diagnostics-a.svg)

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

The synthetic diagnostic is a validated arithmetic check, not an observed
selector benefit. Corrected valve1 and valve2 development evaluations
compare five policies at their actual alert volumes; a single event per
stream and unequal volumes prevent broad superiority claims. No held-out
reservation, authoritative freeze, independent pre-held-out audit or
held-out result is recorded. Keep the target and describe Phase-I evidence
as development-only. Null and inconclusive outcomes remain valid.
Research interpretation carried forward: can a diagnostics rule beat an
exceedance-history-only plus constant-selector control on identical scores
at the measured alert volume, duration, coverage, delay, and resources,
across chronological development streams and one untouched final stream?
Phase-I is the mid-semester report plus presentation per
`../Guidelines for Report.md` (10-15 pages, spiral-bound, supervisor
signature, classroom submission before the 30 September 2026 10:00 AM viva;
10-15 slides, 10-minute presentation plus Q&A). This file is an advanced
report source only: it is not the signed, spiral-bound submission and no
page count is claimed without rendering. Phase-II follows
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
- Sophia Huiwen Sun, Abishek Sankararaman, Balakrishnan Murali
  Narayanaswamy, Online Adaptive Anomaly Thresholding with Confidence
  Sequences, PMLR 235, 2024,
  https://proceedings.mlr.press/v235/sun24h.html (local
  `results/day05-literature/sun24h.txt`)
- Jose Manuel Navarro, Alexis Huet, Dario Rossi, Meta-Learning for Fast
  Model Recommendation in Unsupervised Multivariate Time Series Anomaly
  Detection, PMLR 224, 2023,
  https://proceedings.mlr.press/v224/navarro23a.html (local
  `results/day05-literature/navarro23a.txt`; method ORTHUS, not Hydra)
- Denis Volkhonskiy et al., Inductive Conformal Martingales for
  Change-Point Detection, PMLR 60, 2017,
  https://proceedings.mlr.press/v60/volkhonskiy17a.html (local
  `results/day05-literature/volkhonskiy17a.txt`)
