# Policy study (29 September 2026)

This study implements the frozen protocol's admission-separated recalibration
controller and compares it, on one common score trace per stream, with the
existing baselines, an untruncated-admission rolling variant, three ablations,
and the closest literature abstention baseline. Every arm replays the identical
score trace of its stream; ranking metrics are not reported per policy because
identical score traces give identical ranking metrics by construction.

## Commands

```sh
# 1. (Re)generate the synthetic Y1-Y7 configs, labels, and evaluation config.
.venv/bin/python configs/gen_synthetic_family.py

# 2. Run all 11 arms on valve1, valve2 and Y1-Y7, then evaluate each.
#    Refuses an existing output directory; results/ is gitignored.
.venv/bin/python run_policy_study.py --output-root results/20260929-policy-study-v2

# 3. Independent recompute (does not import reliable_alerting): re-derives every
#    metric of all 99 study rows from the saved predictions and labels.
#    Exit 0 means zero mismatches; the report goes to results/.
python3 scripts/recompute_evaluations.py --all-arms results/20260929-policy-study-v2

# 4. Targeted tests, then the full suite.
.venv/bin/python -m unittest tests.test_policy_anchored tests.test_policy_sun \
    tests.test_policy_h1_property tests.test_policy_study_pipeline \
    tests.test_verification -q
.venv/bin/python -m unittest discover -s tests -q
```

## The arms (11 policy configs)

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

## Implemented vs proposed

- **Implemented** (code merged with tests here): all 11 arms; the label-free
  per-decision action log (`policy_actions.csv`); the defer decision state end
  to end; the synthetic Y1-Y7 family.
- **Measured** (saved and independently recomputed): the study rows reported in the
  Phase-I report's results tables (`deliverables/Phase-I-Report.pdf`, Section 7).
  The five existing arms on valve1/valve2 reproduce the ten corrected
  audit-fresh rows exactly.
- **Proposed** (not established here): any benefit on real benign regime
  changes. The synthetic cases are engineering checks whose outcomes follow
  from construction; they are not evidence of real-world benefit.
- **Declared limit**: Y4 (a fault shaped like a benign step) is absorbed after
  onset — no label-free rule separates a benign shift from a fault of identical
  shape. This is reported whatever it measures (H4).

## No held-out data

This study is development-only. It uses the two SKAB development streams
(`valve1/0.csv`, `valve2/0.csv`) and the deterministic synthetic family.
`SKAB/other/21.csv` is named as reserved in the manifest, but its reservation
authority and recipe are disputed (see the manifest and
[`history.md`](history.md)); it was never opened, and no held-out result or claim exists.
Predictions and the label-free action log are written before any label join,
and episodes are formed from saved states before labels are consulted.

## Which run is current

`results/20260929-policy-study-v2/` is the current study output. The first run
(`results/20260929-policy-study/`) is superseded: its Sun baseline built the
confidence set from a history that already contained the score being judged,
whereas Sun et al. (Def. 2.4, Algorithm 1) decide on `C(p, alpha, S_1:t-1)`.
With that fix only the nine `sun_confidence_sequence` rows changed; the other
90 rows are identical between the two runs.
