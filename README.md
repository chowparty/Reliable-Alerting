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
  src/reliable_alerting/__init__.py - identifies the package
  src/reliable_alerting/loading.py - load_values, synthetic_values
  src/reliable_alerting/splitting.py - make_windows, Window
  src/reliable_alerting/scoring.py - MeanDistanceScorer (source-fit only)
  src/reliable_alerting/calibration.py - FixedQuantile (nearest-rank)
  src/reliable_alerting/policy.py - FixedThresholdPolicy (strict_greater)
  src/reliable_alerting/writing.py - write_run (refuses existing output dir)
  src/reliable_alerting/pipeline.py - compute_trace, write_output, CLI
  src/reliable_alerting/evidence.py - compare_runs, render_figure, CLI
  src/reliable_alerting/provenance.py - env, git, file-hash records
  tests/test_source.py - loading / splitting / scoring checks (Aman review pending)
  tests/test_decisions.py - calibration / policy / writer checks
  tests/test_pipeline.py - label-free pipeline integration + CLI artifacts
  tests/test_evidence.py - compare / figure checks on saved artifacts
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

## Tests and experiments

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
No test or run counts are claimed here; run the commands to obtain evidence.

## Optional tooling

`opencode.json` enables the Superpowers plugin and Context7 and arXiv
servers. It needs optional OpenCode and `uvx` installations, and the
enabled plugin and servers need network. Portable launch is not tested.

ArXiv is for discovery and background only. Primary evidence must use the
seven-platform allowlist in `AGENTS.md`.

Opencode docs: [configuration](https://opencode.ai/docs/config/),
[plugins](https://opencode.ai/docs/plugins/), and
[MCP servers](https://opencode.ai/docs/mcp-servers/).
