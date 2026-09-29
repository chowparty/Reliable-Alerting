# Reliable Alerting for Time-Series Anomaly Detection

## Start here

**What this is.** A Phase-I study of *when an alert threshold should learn*:
recalibration treated as one guarded decision-time action (alongside alert, hold
and defer), with every policy compared on one common score trace and alert
workload, decision coverage, delay and recall reported separately.
Development-only; no held-out result is claimed.

- **Phase-I report.** Source is in [`report/submission/`](report/submission/)
  (see its [`README.md`](report/submission/README.md)). Build the 15-page PDF with:

  ```sh
  sh report/submission/build.sh   # writes build/report.pdf (build/ is gitignored)
  ```

- **Reproduce the study, figures and tables.**
  1. Set up the venv and install the package (see [Setup](#setup) below).
  2. Run the policy study (documented in full under
     [Policy study](#policy-study-29-september-2026); regenerate the synthetic
     family with `configs/gen_synthetic_family.py`, then
     `.venv/bin/python run_policy_study.py --output-root results/<fresh-path>`;
     `results/` is gitignored and runners refuse an existing output dir).
  3. Regenerate the report's figures and tables with the generators in
     [`report/submission/generate/`](report/submission/generate/) and check them
     with their test:

     ```sh
     .venv/bin/python report/submission/generate/test_generators.py
     ```

- **Evidence and literature.** The evidence index is
  [`report/evidence-index.md`](report/evidence-index.md). The reviewed paper
  ledger is [`report/literature/ledger.csv`](report/literature/ledger.csv), and the
  closest-work analysis is
  [`report/literature/closest-work.md`](report/literature/closest-work.md). No paper
  PDFs are stored in the repository.

- **Reserved-stream integrity.** `SKAB/other/21.csv` is named reserved in
  [`manifest.md`](manifest.md); it was never opened and no claim is made on it.

- **Historical material.** The dated implementation sections below (Day-1
  through the Day-05 diagnostic), the day-by-day plan in [`plan/`](plan/), and the
  pre-study report outline [`report/outline.md`](report/outline.md) are historical.
  They record how the work developed, but they do not govern current claims. Current claims are governed by the section below
  and by [`manifest.md`](manifest.md).

## Current evidence for the Phase-I viva (28 September 2026)

The two SKAB streams are **development only**. The corrected valve2 split
ends calibration at its first anomalous row 562; older `result/valve2/`
runs calibrated through row 573 and are not valid for the corrected
comparison. See [manifest.md](manifest.md) for local file SHA-256 values,
label-use qualification and split boundaries. The saved corrected results
are ignored local artifacts under `results/20260928-corrected-development/`;
regenerate them under a fresh path with:

```sh
.venv/bin/python run_real_streams.py --output-root results/my-development-run
for stream in valve1 valve2; do
  for policy in fixed_threshold rolling_threshold k_consecutive m_of_n hysteresis; do
    .venv/bin/python -m reliable_alerting.evaluation_io --run "results/my-development-run/$stream/$policy" --labels "configs/day04-$stream-labels.json" --config "configs/day04-$stream-evaluation.json" --output "results/my-development-run/$stream/$policy/evaluation"
  done
done
```

The command refuses existing policy output directories. `report/outline.md`
records the ten corrected development metric rows and their limits. Two
fresh runs matched on all scientific prediction columns and full evaluation
JSON. The provenance hash inventory omits the real runner, manifest, and
real evaluation/label configs; saved copies and duplicate runs support
reproduction but do not constitute a complete source audit. No held-out
stream was prospectively reserved; there is no
authoritative freeze, independent pre-held-out audit, or held-out result.
Keep the target unseen and present Phase-I findings as development-only.
The sections below retain dated implementation history; this section and
the manifest govern current claims.

## Research question

Does simple decision-time information improve alerting under changing
conditions, compared with fixed thresholds and established temporal rules?

Why it matters: changing normal conditions can cause repeated false alerts,
while careless adaptation may hide real faults.

Diagnostics, deferral, and cautious recalibration are candidates under
study, not claimed contributions.

A defer streak alone is not evidence of an anomaly and not by itself a
trigger for recalibration. Null outcomes are valid results, not automatic
publication.

## Intended pipeline

```text
load -> chronological split
  -> fit preprocessing/scorer -> calibrate
  -> replay policies on same scores
  -> save predictions -> join labels -> evaluate
```

Start with a deterministic scorer. Baselines are fixed thresholds, rolling
thresholds, consecutive exceedances, M-of-N persistence, and hysteresis.
Complex or neural models only with supporting evidence.

Decide at window end using only information available at decision time.
Fit preprocessing and scoring only on permitted source data. Reserve
held-out data before outcome inspection and freeze choices before
evaluation; join labels only after predictions are saved.

## Layout

```text
research/
  README.md - this overview
  AGENTS.md - portable team rules for workflow and scientific integrity
  opencode.json - optional tooling config for plugin and MCP servers
  pyproject.toml - package metadata, requires-python >= 3.12
  .gitignore - excludes venv, build output, local data/results/checkpoints
  configs/day01-synthetic.json - fixed day-01 synthetic recipe (q=0.95, n=8)
  configs/day02-evaluation.json - fixed offline evaluation schedule
    (horizon [64, 96), first_decision 67, decision_stride 4,
    window_length 4, time_basis sample_index, schema_version 1)
  tests/fixtures/day02-synthetic-labels.json - synthetic fixture labels
    (coverage [64, 96), events offset-up [72, 80),
    offset-down [88, 96)); fixture only, not a real-data claim
  src/reliable_alerting/__init__.py - identifies the package
  src/reliable_alerting/loading.py - load_values, synthetic_values
  src/reliable_alerting/splitting.py - make_windows, Window
  src/reliable_alerting/scoring.py - MeanDistanceScorer (source-fit only)
  src/reliable_alerting/calibration.py - FixedQuantile (nearest-rank)
  src/reliable_alerting/policy.py - FixedThresholdPolicy (strict_greater)
    plus HysteresisPolicy (high `strict_greater` on, low `strict_less`
    off; equality holds; initial latch `normal`; independent reset)
  src/reliable_alerting/replay.py - temporal-replay-v1 family replay
    (fixed + hysteresis over one saved score trace; validated `state.json`
    sidecar per policy; `protocol` configs/day04-synthetic-family.json)
  src/reliable_alerting/writing.py - write_run (refuses existing output dir)
  src/reliable_alerting/pipeline.py - compute_trace, write_output, CLI
  src/reliable_alerting/evidence.py - compare_runs, render_figure, CLI
    plus compare_evaluations, write_comparison_evaluations,
    render_evaluation_figure (evidence CLI: compare-evaluations,
    evaluation-figure)
  src/reliable_alerting/evaluation.py - offline core: validate_evaluation_config,
    form_episodes, evaluate, inclusive_events_to_half_open,
    events_from_point_labels (metric_definition_id offline-alert-evaluation-v1)
  src/reliable_alerting/evaluation_io.py - load_predictions_generic,
    load_strict_json, evaluate_saved_predictions, run_evaluation, CLI
  src/reliable_alerting/provenance.py - env, git, file-hash records
  tests/test_source.py - loading / splitting / scoring checks (Aman review pending)
  tests/test_decisions.py - calibration / policy / writer checks
  tests/test_pipeline.py - label-free pipeline integration + CLI artifacts
  tests/test_evidence.py - compare / figure checks on saved artifacts
  tests/test_evaluation.py - offline core contract checks
  tests/test_evaluation_io.py - saved-run verification, label-join,
    compare-evaluations and evaluation-figure checks
  results/literature/ - ignored local fulltext copies (tatbul2018.txt,
    gibbs2021.txt, xu2026.txt) from the proceedings cited in the report
  report/outline.md - minimal report source (not the completed report)
```

Why: source (`loading`, `splitting`, `scoring`) and calibration/policy
(`calibration`, `policy`) stay separate modules so the same components are
reused by synthetic checks; `pipeline` joins them label-free and `evidence`
reads saved runs and verifies them against the configured recipe and current
source hashes. Source-module behaviour needs Aman review; the
eligibility manifest and any real-stream reservation (Nakul) were absent at
that Day-1 checkpoint, so support then was fixed-only synthetic with `source_label_use: none` and no
labels in any runtime signature. Fixed decisions: `quantile: 0.95`,
`method: nearest_rank` over the 8 calibration scores is a reproducibility
convention, not a false-alarm guarantee; `held_out:
not_reserved_or_evaluated`, so there is no held-out claim. Scoring: kind
`mean_distance`, `epsilon: 1e-6`, `fit_scope: source_fit`,
`standard_deviation: population`. Split/windows: segments source-fit
`[0, 32)`, calibration `[32, 64)`, replay `[64, 96)` (stop exclusive); window length 4,
stride 4, `anchor: segment_start`, `edge_policy: drop_incomplete`
(dropped tail recorded in diagnostics), `end_index: inclusive`;
`missing_policy: reject`, `time_basis: sample_index`. Report source:
[report/outline.md](report/outline.md).

## Setup

Requires Python `>= 3.12`; Python 3.12 is the baseline.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -c "import reliable_alerting; print(reliable_alerting.__file__)"
```

Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -c "import reliable_alerting; print(reliable_alerting.__file__)"
```

## Tests and experiments (Day-1 history, dated 19 September 2026)

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m reliable_alerting.pipeline --config configs/day01-synthetic.json --output results/day01-run-a
.venv/bin/python -m reliable_alerting.pipeline --config results/day01-run-a/config.json --output results/day01-run-b
.venv/bin/python -m reliable_alerting.evidence compare results/day01-run-a results/day01-run-b --output results/day01-compare.json
.venv/bin/python -m reliable_alerting.evidence figure results/day01-run-a/predictions.csv --output results/day01-scores.svg
```

The second run replays the saved `config.json` from the first run; `compare`
checks substantive equality excluding only `run_id`. `write_run`,
`write_comparison`, and `render_figure` refuse to overwrite (existing output
dir or file raises `FileExistsError`), so each run needs a new directory.
The historical Day-1 guide records 94 passing tests; that suite also passed
at the start of the 22 September inspection. Run the test command for the
current suite; the personal Day-2/3 guide records the execution snapshot.

## Offline evaluator (Day-2/3, implemented; status as of 22 September 2026)

The evaluator makes forward-time alert behaviour independently checkable.

At the 22 September checkpoint runtime scope was fixed-only synthetic through
`configs/day01-synthetic.json` (`quantile: 0.95`, `method: nearest_rank`
over 8 calibration scores, `source_label_use: none`,
`held_out: not_reserved_or_evaluated`). Policies beyond fixed live only in
the Day-04 replay family (`temporal-replay-v1`, fixed + hysteresis at one
predeclared setting each, no sweep): the runtime writer stays schema-1
strict (`normal`/`alert` only, `output_state` checked against
score/threshold), so there was no runtime defer path then. This dated
description predates the current five-policy real-stream runner. The
independent technical review cited here was not a pre-held-out audit.

### What the evaluator is

- `src/reliable_alerting/evaluation.py` is the pure offline core
  (`metric_definition_id: offline-alert-evaluation-v1`). `form_episodes`
  forms alert episodes from saved `output_state` values before labels are
  consulted; `evaluate` joins those episodes against clipped label events.
  Helpers `inclusive_events_to_half_open` (inclusive stop -> half-open
  `[start, stop+1)`) and `events_from_point_labels` (binary 0/1 runs ->
  half-open intervals) are label adapters only.
- `src/reliable_alerting/evaluation_io.py` is the persistence gate:
  `load_predictions_generic`, `load_strict_json` (rejects NaN/Infinity and
  duplicate keys), `evaluate_saved_predictions` (reusable
  predictions-first, episodes-before-labels join), and `run_evaluation`
  (verifies the saved run by recompute, validates the evaluation schedule
  against runtime replay bounds/window, then persists an exclusive
  evaluation directory with `config.json`, `labels.json`,
  `evaluation.json`, `predictions.csv` copy, and `metadata.json`). The CLI
  is `python -m reliable_alerting.evaluation_io --run <run> --labels
  <labels> --config <eval-config> --output <eval-dir>`.
- `src/reliable_alerting/evidence.py` adds `compare_evaluations` /
  `write_comparison_evaluations` (CLI `compare-evaluations`) and
  `render_evaluation_figure` (CLI `evaluation-figure`, half-open events vs
  forward episodes over the horizon with warmup shading).

Writer/evaluator state contract: the existing runtime writer (`writing.py`)
accepts only `normal`/`alert` and checks `output_state` against
score/threshold, so there is no runtime defer path today. The generic
evaluator loader (`load_predictions_generic`) accepts `defer` (and varying
thresholds) in saved states so future policies can be evaluated without
changing the evaluator; the fixed-trace figure utility
(`render_figure`) still rejects varying thresholds.

### Strict contract (sample_index only)

- Regular schedule only: `time_basis` must be `sample_index`,
  `first_decision` must equal `horizon_start + window_length - 1`, and
  decisions sit at inclusive window-end indexes (`end_index` exactly on
  schedule, `start_index = end_index - window_length + 1`).
- Each decision covers the forward half-open interval from its `end_index`
  to the next decision's `end_index` (final interval expires at the horizon
  stop). Episodes merge adjacent `alert` decisions; `normal` and `defer`
  both break episodes.
- Labels are half-open `[start, stop)` events; coverage must encompass the
  full horizon. Events outside the horizon are excluded (counted); partially
  overlapping events are clipped to the horizon (counted) while keeping the
  original onset for delay.
- Validation rejects missing/extra keys, duplicate `window_id`/`event_id`,
  gaps or off-schedule/unsorted/non-increasing ends, non-finite
  scores/thresholds, start-greater-than-end windows, empty coverage gaps,
  unsorted events, and incomplete coverage. Overlapping label events keep
  their original IDs; durations use the union so overlap is not
  double-counted.
- Recall is recalled clipped events over clipped events; precision is
  overlapping episodes over all episodes. Either value is `null`
  (`None`) when its denominator is zero (no clipped events / no episodes).
  Delay is measured per recalled event against the original (pre-clip)
  onset with `max(0, first_matching_episode_start - original_start)`;
  missed events record `delay: null` and are counted separately.
- Window-label style inputs are unsupported: point labels must be converted
   first via `events_from_point_labels`. Durations use sample-index units,
   not physical seconds; verified cadence or timestamps would be needed
   for a physical-time interpretation.

### Observed synthetic fixture checks (test-backed, not a quality claim)

`tests/test_evaluation_io.py::RoundtripTest` replays the fixed Day-1
synthetic recipe and joins `tests/fixtures/day02-synthetic-labels.json`
under `configs/day02-evaluation.json`. Observed values today:

- 8 replay windows, 3 alerts; episodes `[79, 83)`, `[91, 96)`;
  fixture events `[72, 80)`, `[88, 96)`.
- Recall 2/2, precision 2/2, false-alert episodes 0; per-event delays 7
  (`offset-up`: 79-72) and 3 (`offset-down`: 91-88), mean 5.
- Total alert duration 9, non-event alert duration 3, warmup duration 3
  (`[64, 67)`), alerted-window fraction 3/8, decision coverage 8/8,
  deferral rate 0/8, deferred duration 0.
- Episode rate 250 per 1000 decisions ((2/8)*1000); 2/32 = 0.0625
  episodes per sample-index unit.

These are synthetic fixture checks exercising the same reusable components.
There are no superseded historical real metrics (none existed). Metadata
linkage, checksum, and scope integration bugs found during this work were
fixed before the final runs; the fixture numbers above do not establish
detection quality or novelty.

### Provenance, resources, commands

- Provenance `file_hashes` whitelists current source plus both docs
  (`README.md`, `report/outline.md`). Historical Day-1 `compare` required identical git head,
  environment, and current-source hashes across the pair; the new
  `compare-evaluations` instead requires scientific equality (config,
  persisted evaluation, semantic predictions/labels, recompute match) plus
  provenance-schema validity, while reporting git/file-hash sameness
  separately.
- `command_record` keeps `orig_argv` (interpreter-reported original arguments) separate from
  `rerun_shell`/`rerun_executable` (verified rerun via the current
  `sys.executable`, unresolved so `.venv/bin/python` stays on the venv).
- Resources use the exact recorded scope. Runs: `validated_compute_trace_only`.
  Evaluations (Day-2/3): `saved_run_validation_recompute_and_evaluation_excluding_output`.
  Final family (Day-04, `temporal-replay-v1`):
  `saved_scores_validation_recompute_replay_label_free_persist_single_label_open_and_family_evaluation`,
  i.e. source-run validation recompute plus strict protocol/schedule checks
  plus label-free replay of both policies plus episode formation plus
  label-free file creation/writes plus one labels read plus generic
  evaluation plus artifact serialization/hash; it EXCLUDES provenance
  capture (command/environment/git/file hashes) and completion file writes
  (labels, evaluations, metadata). Per-policy `policy_replay_seconds` is
  wall-clock timed policy validation plus config/run-ID allocation plus row
  allocation plus the actual policy replay under tracing (replay-ID binding
  happens after the timer), not pure policy latency and not whole-run
  latency. `peak_python_allocation_bytes` is family-level only (from
  `family_metadata.json`): peak traced Python allocation, not
  whole-machine RAM and not per-policy; there is no latency or RAM claim.
- Figures use saved evidence only. Local `results/day01-*` files remain
  preserved history; new executions use separate output paths.

Artifact paths and reproduction commands (the personal guide records
which executions were actually verified):

```sh
.venv/bin/python -m reliable_alerting.pipeline --config configs/day01-synthetic.json --output results/day02-03-20260922-run-a
.venv/bin/python -m reliable_alerting.pipeline --config results/day02-03-20260922-run-a/config.json --output results/day02-03-20260922-run-b
.venv/bin/python -m reliable_alerting.evidence compare results/day02-03-20260922-run-a results/day02-03-20260922-run-b --output results/day02-03-20260922-runs-compare.json
.venv/bin/python -m reliable_alerting.evidence figure results/day02-03-20260922-run-a/predictions.csv --output results/day02-03-20260922-scores.svg
.venv/bin/python -m reliable_alerting.evaluation_io --run results/day02-03-20260922-run-a --labels tests/fixtures/day02-synthetic-labels.json --config configs/day02-evaluation.json --output results/day02-03-20260922-eval-a
.venv/bin/python -m reliable_alerting.evaluation_io --run results/day02-03-20260922-run-b --labels tests/fixtures/day02-synthetic-labels.json --config configs/day02-evaluation.json --output results/day02-03-20260922-eval-b
.venv/bin/python -m reliable_alerting.evidence compare-evaluations results/day02-03-20260922-eval-a results/day02-03-20260922-eval-b --output results/day02-03-20260922-evaluations-compare.json
.venv/bin/python -m reliable_alerting.evidence evaluation-figure results/day02-03-20260922-eval-a --output results/day02-03-20260922-episodes.svg
```

All writers refuse to overwrite, so each output needs a fresh path.

## Day-04 final family (fixed + hysteresis; scheduled namespace 20260922; initial inspection 22 September 2026 18:27 IST, resumed final 23 September 2026 17:31 IST; final artifacts 23 September 2026 UTC, no backdating)

Why: the same saved score trace is replayed by two policies so the policy
comparison cannot be explained by different scores.

- Replay `temporal-replay-v1` over one verified source run. High is the
  frozen source calibration threshold
  (`threshold_high: 1.0690438247937764`); low is predeclared
  `0.8 * high` (`threshold_low: 0.8552350598350211`, synthetic only).
  Hysteresis starts `normal` and resets independently per replay: a
  `normal` latch judges `high` with `strict_greater`; an `alert` latch
  judges `low` with `strict_less`; equality holds the latch. Fixed judges
  `high` with `strict_greater` (stateless; `before_state` is always the
  `normal` placeholder). One setting per policy, no sweep; ties retained;
  no real tuning. Tolerance 250 episodes per 1000 decisions, coverage floor
  1.0 (reporting criteria, not rejection gates).
- Both policies give the same saved scores and the same evaluation on this
  fixture: 8 windows, 3 alerts; episodes `[79, 83)`, `[91, 96)` against
  events `[72, 80)`, `[88, 96)`; recall 2/2, precision 2/2, false-alert
  episodes 0; per-event delays 7 and 3, mean 5, misses 0; total alert
  duration 9, non-event 3, warmup 3 (`[64, 67)`), coverage 8/8, defer 0/8;
  episode rate 2/32 = 0.0625 episodes per sample-index unit;
  (2/8)*1000 = 250 episodes per 1000 decisions. Mechanism: at window `replay:72:75` the
  score equals high, so equality holds `normal` and delays the up-crossing
  until window `replay:76:79` (episode start 79); no miss/false was
  observed on this trace. Episode 0 overruns its event by 3
  (`[79, 83)` vs `[72, 80)`).
- The fixed runtime writer remains schema-1 strict; the new `state.json` is
  a replay sidecar only (per-window `before_state`/`after_state`,
  `judging_threshold`, `comparator`, `replay_version`), not a runtime defer
  path.
- Saved final table: `results/day04-20260922-final-table.json`; saved
  figure: `results/day04-20260922-final-family.svg`; families
  `results/day04-20260922-final-family-a` / `-b` verify
  scientifically equal (`results/day04-20260922-final-comparison.json`;
  `created_at` 2026-09-23T12:01:59 / 12:02:00 UTC; run/family IDs,
  timing, and allocation vary by design). The preliminary Day-04 pair
  (`results/day04-20260922-family-a` / `-b`, `-table.json`,
  `-comparison.json`, `-family.svg`) is retained as preliminary history;
  the final pair supersedes only its resource-description error — no
  evaluator defect or metric correction. Day-2 historical metadata keeps
  older hashes; the drift is expected and not rewritten.
- Reproduce under fresh, ignored paths (local `results/*` outputs are
  ignored and regenerable):

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m reliable_alerting.pipeline --config configs/day01-synthetic.json --output results/day04-final-check-source-a
.venv/bin/python -m reliable_alerting.pipeline --config configs/day01-synthetic.json --output results/day04-final-check-source-b
.venv/bin/python -m reliable_alerting.replay --run results/day04-final-check-source-a --protocol configs/day04-synthetic-family.json --evaluation-config configs/day02-evaluation.json --labels tests/fixtures/day02-synthetic-labels.json --output results/day04-final-check-family-a
.venv/bin/python -m reliable_alerting.replay --run results/day04-final-check-source-b --protocol configs/day04-synthetic-family.json --evaluation-config configs/day02-evaluation.json --labels tests/fixtures/day02-synthetic-labels.json --output results/day04-final-check-family-b
.venv/bin/python -m reliable_alerting.evidence compare-families results/day04-final-check-family-a results/day04-final-check-family-b --output results/day04-final-check-comparison.json
.venv/bin/python -m reliable_alerting.evidence family-table results/day04-final-check-family-a --output results/day04-final-check-table.json
.venv/bin/python -m reliable_alerting.evidence family-figure results/day04-final-check-family-a --output results/day04-final-check-family.svg
```

Day-04 completion recorded 247 passing tests. Its earlier reference to a
164-test HEAD described the pre-Day-4 commit, not the current HEAD
`a0d1b68ebcef079e33137be77a53b8f7fb4386a9`. After the uncommitted Day-5
changes, fresh `.venv/bin/python -m unittest discover -s tests -v` passed
**316 tests** in 26.509 seconds on 24 September 2026; `git diff --check`
also passed (shell-clock checkpoint 11:46:29 IST). Regenerate ignored
`results/*` paths locally rather than treating them as tracked evidence.

## Day-05 provisional diagnostic + family (scheduled 23 September; execution 23-24 September 2026)

Why: decision-time diagnostic aid only, not a detection claim. Provisional
Pratyush support; not an Aman deliverable and not a real-scorer result.
The independently checked start was 23 September 22:21:26 IST; the final
experiment chain began 23:20:59 IST that day. Documentation and verification
continued on 24 September. Each component's saved timestamp has its own scope.

- Method (`src/reliable_alerting/diagnostics.py`,
  `diagnostic_id: trailing-median-gap-v1`, `diagnostics-v1`): one setting
  only — current-inclusive median of the last 3 replay scores minus the
  frozen calibration-score median, in score units with `normalize: false`.
  Config `configs/day05-diagnostic.json` (`trailing_window: 3`,
  `warmup_count: 2`, `reference: calibration/median/calibration_scores`,
  `time_basis: sample_index`, `provisional: true`,
  `provisional_owner: pratyush`). First 2 rows are null warmup with an
  explicit `readiness_reason`; each call resets independently
  (`reset: independent_call`, `inclusion: current_inclusive`); calibration
  must strictly precede scores; no labels are read or accepted. Timed
  region is validation recompute plus config check plus build plus
  verification only; provenance capture and file writes are excluded
  (`saved_run_validation_recompute_diagnostic_verification_excluding_output`).
  `src/reliable_alerting/evidence.py` adds the diagnostic/family
  comparison, table, and diagnostics-figure rendering from saved artifacts
  only, with independent recompute of all 8 rows via fresh sorting
  arithmetic (`verify_features`).
- Saved final artifacts (ignored, regenerable):
  `results/day05-20260923-final-source-a` / `-source-b`,
  `results/day05-20260923-final-diagnostic-a` / `-diagnostic-b`,
  `results/day05-20260923-final-family-a` / `-family-b`,
  `results/day05-20260923-final-diagnostic-comparison.json`,
  `results/day05-20260923-final-family-comparison.json`,
  `results/day05-20260923-final-table-a.json` /
  `-table-b.json`,
  `results/day05-20260923-final-diagnostics-a.svg` /
  `-diagnostics-b.svg`.
  The preliminary Day-05 pair (`results/day05-20260923-source-a` / `-b`,
  `-diagnostic-a` / `-b`, `-family-a` / `-b`, `-table-a/b.json`,
  `-diagnostic-comparison.json`, `-family-comparison.json`,
  `-diagnostics-a/b.svg`) is retained as preliminary history; the final
  pair corrects the feature-magnitude figure, not the scores or metrics.
  Final `created_at` 2026-09-23T17:50:59/17:51:00Z; diagnostic comparison
  and family comparison both report `status: true`, `scientific_equal:
  true`, git head `a0d1b68ebcef079e33137be77a53b8f7fb4386a9`.
- Observed final values (synthetic fixture only, same scores as Day-04):
  reference (calibration) median `0.5345219123968882`; high
  `1.0690438247937764`, low `0.8 * high = 0.8552350598350211`. All 8
  diagnostic rows independently recomputed and verified; 6 ready
  (`replay:72:75` through `replay:92:95`) reported separately from the
  full 8 policy decisions. Ready features: five rows
  `0.5345219123968882`, final row `2.672609561984441` (trailing median
  `3.2071314743813293`); warmup rows `null`. Both policies agree on this
  trace: 8 windows, 3 alerts; episodes `[79, 83)`, `[91, 96)` vs events
  `[72, 80)`, `[88, 96)`; recall 2/2, precision 2/2, false 0; delays 7
  and 3 (mean 5), misses 0; total alert duration 9, non-event 3, warmup 3,
  coverage 8/8, defer 0/8; episode rate 250 per 1000 decisions. The tie
  (fixed vs hysteresis identical outputs here) is not a policy
  improvement; this synthetic diagnostic has no real-stream selector result.
  The table's `misleading_feature_example` (`replay:72:75`,
  `feature 0.5345...` with `output_state normal`) is descriptive only.
- Source-vs-family: source runs (`pipeline` on
  `configs/day01-synthetic.json`) fix the scores and calibration; families
  (`replay temporal-replay-v1` over the saved source plus the diagnostic
  join in the table/figure) replay fixed and hysteresis over those
  identical scores and evaluate offline. Identical score traces cannot
  demonstrate a ranking-metric (e.g. VUS-PR) improvement.
- Limits and gates: the diagnostic was not compared as a real-stream
  selector. Authoritative operating points, held-out reservation, and
  independent pre-held-out audit are absent. Real-stream association/candidate selection stays blocked:
  no justified association rule or candidate sketch exists. Held-out
  remains `not_reserved_or_evaluated`; the fixed quantile remains a
  reproducibility convention, not a false-alarm or coverage guarantee.
- Reproduce under fresh, ignored paths (do not reuse existing outputs):

```sh
.venv/bin/python -m reliable_alerting.pipeline --config configs/day01-synthetic.json --output results/day05-reproduce-source-a
.venv/bin/python -m reliable_alerting.pipeline --config configs/day01-synthetic.json --output results/day05-reproduce-source-b
.venv/bin/python -m reliable_alerting.diagnostics --run results/day05-reproduce-source-a --config configs/day05-diagnostic.json --output results/day05-reproduce-diagnostic-a
.venv/bin/python -m reliable_alerting.diagnostics --run results/day05-reproduce-source-b --config configs/day05-diagnostic.json --output results/day05-reproduce-diagnostic-b
.venv/bin/python -m reliable_alerting.replay --run results/day05-reproduce-source-a --protocol configs/day04-synthetic-family.json --evaluation-config configs/day02-evaluation.json --labels tests/fixtures/day02-synthetic-labels.json --output results/day05-reproduce-family-a
.venv/bin/python -m reliable_alerting.replay --run results/day05-reproduce-source-b --protocol configs/day04-synthetic-family.json --evaluation-config configs/day02-evaluation.json --labels tests/fixtures/day02-synthetic-labels.json --output results/day05-reproduce-family-b
.venv/bin/python -m reliable_alerting.evidence compare-diagnostics results/day05-reproduce-diagnostic-a results/day05-reproduce-diagnostic-b --output results/day05-reproduce-diagnostic-comparison.json
.venv/bin/python -m reliable_alerting.evidence compare-families results/day05-reproduce-family-a results/day05-reproduce-family-b --output results/day05-reproduce-family-comparison.json
.venv/bin/python -m reliable_alerting.evidence diagnostic-table --diagnostic results/day05-reproduce-diagnostic-a --family results/day05-reproduce-family-a --output results/day05-reproduce-table-a.json
.venv/bin/python -m reliable_alerting.evidence diagnostic-table --diagnostic results/day05-reproduce-diagnostic-b --family results/day05-reproduce-family-b --output results/day05-reproduce-table-b.json
.venv/bin/python -m reliable_alerting.evidence diagnostic-plot --diagnostic results/day05-reproduce-diagnostic-a --family results/day05-reproduce-family-a --output results/day05-reproduce-diagnostics-a.svg
.venv/bin/python -m reliable_alerting.evidence diagnostic-plot --diagnostic results/day05-reproduce-diagnostic-b --family results/day05-reproduce-family-b --output results/day05-reproduce-diagnostics-b.svg
```

Check the exact CLI subcommand names in `evidence.py`/`diagnostics.py`
before running; all writers refuse to overwrite, so each output needs a
fresh `day05-reproduce-*` path. Figures plot actual saved feature
magnitudes (score units) with ready/warmup separation; they are
engineering checks, not quality claims.

Independent arithmetic audit: `results/day05-20260924-independent-audit.json`
records 16 checked rows across the two runs, using `sum - min - max` for
each three-score median and a separate calibration median calculation.
It also verifies table scientific fields, SVG XML/geometry and historical
Day-4 evaluation equality. Rendered-image inspection was not performed.
The recorded environment launcher was executed with only its output path
changed to `results/day05-20260924-launcher-diagnostic`; scientific equality
held despite documentation hash drift. It used the **source** directory
`results/day05-20260923-final-source-a`, not a family directory.
The exact known Day-4 29-file provenance schema remains compatible alongside
the current 33-file schema; scientific replay/evaluation checks remain strict
and old metadata was not rewritten. The beginner working reference is
`../DAY-05-PRATYUSH-GUIDE.md` outside this repository. Teammate audit is pending.

## Policy study (29 September 2026)

This study implements the frozen protocol's admission-separated recalibration
controller and compares it, on one common score trace per stream, with the
existing baselines, an untruncated-admission rolling variant, three ablations,
and the closest literature abstention baseline. Every arm replays the identical
score trace of its stream; ranking metrics are not reported per policy because
identical score traces give identical ranking metrics by construction.

### Commands

```sh
# 1. (Re)generate the synthetic Y1-Y7 configs, labels, and evaluation config.
.venv/bin/python configs/gen_synthetic_family.py

# 2. Run all 11 arms on valve1, valve2 and Y1-Y7, then evaluate each.
#    Refuses an existing output directory; results/ is gitignored.
.venv/bin/python run_policy_study.py --output-root results/20260929-policy-study-v2

# 3. Regression gate + independent recompute (from report-work/evidence/):
#    - default root recompute keeps recompute-output.json byte-identical
#      (pinned SHA b57e02c3...979bf740d694c008259cd0e8c03c343519147831b6ea126f97fb1d64)
#    - --all-arms recomputes all 99 study rows into a separate file.
python3 recompute_evaluations.py
python3 recompute_evaluations.py --all-arms ../../research/results/20260929-policy-study-v2

# 4. Targeted tests, then the full suite.
.venv/bin/python -m unittest tests.test_policy_anchored tests.test_policy_sun \
    tests.test_policy_h1_property tests.test_policy_study_pipeline \
    tests.test_verification -q
.venv/bin/python -m unittest discover -s tests -q
```

### The arms (11 policy configs)

| arm | what it is |
|---|---|
| `fixed_threshold` | anchor-only baseline (existing) |
| `rolling_threshold` | normal-only rolling recalibration, L=10, q=0.95 (existing; H1) |
| `rolling_threshold_all` | rolling class with `admission_rule="all"`, L=10, q=0.95 (config only) |
| `k_consecutive` | k=3 persistence baseline (existing) |
| `m_of_n` | 3/5 persistence baseline (existing) |
| `hysteresis` | low_ratio 0.8 latch baseline (existing) |
| `anchored_recalibration` | proposed controller, §4 (L=10, q=0.95, kappa=4.0, rho=2.0, D=10) |
| `anchored_no_cap` | ablation: kappa = infinity (`kappa: null`) |
| `anchored_no_stability` | ablation: rho = infinity (`rho: null`) |
| `anchored_no_defer` | ablation: D = 0 (escalate immediately) |
| `sun_confidence_sequence` | re-implementation of Sun et al. (ICML 2024) Algorithm 1 with eq. (1); p=0.95, alpha=0.05; not the authors' code |

Since JSON cannot carry infinity, the two ablations set `kappa`/`rho` to `null`,
which the pipeline reads as "disabled" (infinite cap / infinite stability
tolerance). `defer_limit` accepts `0`.

### Implemented vs proposed

- **Implemented** (code merged with tests here): all 11 arms; the label-free
  per-decision action log (`policy_actions.csv`); the defer decision state end
  to end; the synthetic Y1-Y7 family.
- **Measured** (saved and independently recomputed): the study rows below.
  The five existing arms on valve1/valve2 reproduce the ten corrected
  audit-fresh rows exactly.
- **Proposed** (not established here): any benefit on real benign regime
  changes. The synthetic cases are engineering checks whose outcomes follow
  from construction; they are not evidence of real-world benefit.
- **Declared limit**: Y4 (a fault shaped like a benign step) is absorbed after
  onset — no label-free rule separates a benign shift from a fault of identical
  shape. This is reported whatever it measures (H4).

### No held-out data

This study is development-only. It uses the two SKAB development streams
(`valve1/0.csv`, `valve2/0.csv`) and the deterministic synthetic family.
`SKAB/other/21.csv` is named as reserved in the manifest, but its reservation
authority and recipe are disputed (see the manifest and the current-evidence
section above); it was never opened, and no held-out result or claim exists.
Predictions and the label-free action log are written before any label join,
and episodes are formed from saved states before labels are consulted.

### Which run is current

`results/20260929-policy-study-v2/` is the current study output. The first run
(`results/20260929-policy-study/`) is superseded: its Sun baseline built the
confidence set from a history that already contained the score being judged,
whereas Sun et al. (Def. 2.4, Algorithm 1) decide on `C(p, alpha, S_1:t-1)`.
With that fix only the nine `sun_confidence_sequence` rows changed; the other
90 rows are identical between the two runs.

## Optional tooling

`opencode.json` enables the Superpowers plugin and Context7 and arXiv
servers. It needs optional OpenCode and `uvx` installations, and the
enabled plugin and servers need network. Portable launch is not tested.

ArXiv is for discovery and background only. Primary evidence must use the
seven-platform allowlist in `AGENTS.md`.

Opencode docs: [configuration](https://opencode.ai/docs/config/),
[plugins](https://opencode.ai/docs/plugins/), and
[MCP servers](https://opencode.ai/docs/mcp-servers/).
