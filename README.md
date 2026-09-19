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
  src/reliable_alerting/__init__.py - identifies the package
```

`src/` houses continuing code; only the package exists now.

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

Tests use `unittest` once real behavior lands. There are no runnable
experiment commands yet.

## Optional tooling

`opencode.json` enables the Superpowers plugin and Context7 and arXiv
servers. It needs optional OpenCode and `uvx` installations, and the
enabled plugin and servers need network. Portable launch is not tested.

ArXiv is for discovery and background only. Primary evidence must use the
seven-platform allowlist in `AGENTS.md`.

Opencode docs: [configuration](https://opencode.ai/docs/config/),
[plugins](https://opencode.ai/docs/plugins/), and
[MCP servers](https://opencode.ai/docs/mcp-servers/).
