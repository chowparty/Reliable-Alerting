# Reliable Alerting for Time-Series Anomaly Detection

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
eligibility manifest and any real-stream reservation (Nakul) are absent, so
current support is fixed-only synthetic with `source_label_use: none` and no
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

Runtime scope is unchanged: fixed-only synthetic through
`configs/day01-synthetic.json` (`quantile: 0.95`, `method: nearest_rank`
over 8 calibration scores, `source_label_use: none`,
`held_out: not_reserved_or_evaluated`). No eligibility manifest, no
real-stream reservation, no real config, and no rolling/persistence/
hysteresis policy exists. Aman source-module review and the Nakul
independent audit are pending.

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
- Episode rate per 1000 decisions 250 (2/8), per sample_index 2/32.

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
- Resources now use the accurate long scope recorded in code
  (`validated_compute_trace_only` for runs;
  `saved_run_validation_recompute_and_evaluation_excluding_output` for
  evaluations): validation/recompute plus hashing, excluding output
  directory creation and file writes. `peak_python_allocation_bytes` is peak
  traced Python allocation, not whole-machine RAM; there is no latency or
  RAM claim.
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

## Optional tooling

`opencode.json` enables the Superpowers plugin and Context7 and arXiv
servers. It needs optional OpenCode and `uvx` installations, and the
enabled plugin and servers need network. Portable launch is not tested.

ArXiv is for discovery and background only. Primary evidence must use the
seven-platform allowlist in `AGENTS.md`.

Opencode docs: [configuration](https://opencode.ai/docs/config/),
[plugins](https://opencode.ai/docs/plugins/), and
[MCP servers](https://opencode.ai/docs/mcp-servers/).
