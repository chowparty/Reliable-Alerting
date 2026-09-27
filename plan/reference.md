# Shared reference: beginner tutorial for our research decisions

Read this once on Day 1. Daily plans refer back to it instead of re-deciding these points.

Audience: teammates who know ML and programming but are executing this research for the first time on 19 September 2026. No code or results exist yet. Every number below is illustrative unless a daily plan says it was measured. The proposed code root everywhere is `research/` (prospective, does not exist yet).

Why: frozen thresholds can fail silently when streams drift, and every adaptive fix can fail in its own way. This tutorial gives the team one shared numerical language for scores, calibration, decisions, and metrics so the daily work compares behaviours honestly.

## 1. Running sensor example

Imagine a machine vibration sensor sampled once per second. We cut it into non-overlapping 60-second windows. Each window gets one anomaly score: larger means stranger. Scores are not probabilities; 0.83 does not mean 83% anomalous. It only orders windows from most normal to strangest.

```
time -->  window 38   window 39   window 40   window 41   window 42
samples   60 values   60 values   60 values   60 values   60 values
scores      0.21        0.34        0.58        0.71        0.66
```

Suppose calibration on older normal data set a fixed threshold at 0.60. Then windows 38, 39, and 40 are below the line and read normal, while windows 41 and 42 are above it and read alert under a fixed rule. That is the whole decision problem: one number per window, one or two cutoffs, one output per window.

```
score
 0.71 |                     41
 0.66 |                           42
      |
 0.60 | - - - fixed threshold - - -
      |
 0.58 |               40
 0.34 |         39
 0.21 |   38
      +------------------------------
        38  39  40  41  42   window
```

Concept: calibration means choosing cutoffs on older data and freezing them before they touch later data. A policy outputs normal, alert, or defer per window. A controller separately decides whether to hold or refresh thresholds. Those two vocabularies stay separate (Section 7).

## 2. From raw readings to one score per window

A scorer maps a window of raw readings to one number, oriented so larger always means more anomalous; where a raw measure runs the other way (for example isolation depth, where larger often means more normal) the config states the orienting transform. One deterministic example used throughout is a standardized distance of the window mean from the source mean:

```
score(w) = | mean(w) - source_mean | / (source_sd + eps)
```

with `source_mean` and `source_sd` fitted on source-fit data only and `eps` predeclared in config (for example `eps = 1e-6`) so a constant source stream with zero variance gives a defined score instead of a division failure. The result is approximate whenever `eps` is material; the recorded value keeps reruns identical.

Numerical illustration (standalone, approximate): suppose the source vibration has `source_mean = 10.00` and `source_sd = 0.50`. A new window with mean 10.35 gives about `0.70`. A window with mean 10.10 gives about `0.20`. These two arithmetic examples are illustrative only and do not generate the five-value trace in Section 1, which is a separate hand-chosen illustration. A mean-distance detector responds to level shifts but is insensitive to changes preserving the window mean, so it may miss pure variability or frequency changes; any follow-up scorer is a sensitivity change to test, not a tuning fix. Other scorers such as reconstruction error are allowed, with the same rule that any scaling or reference statistics come from source data only.

Three rules keep comparisons honest:

1. Fit any scaling on source data only. If source vibration centres on 10.0 and later data centres on 12.0, record the shift rather than quietly refitting.
2. Compare decision rules on unchanged scores with the same windows, labels, and metric settings. If the fixed rule and the rolling rule see different scores, the comparison says nothing about the rule. A learned scorer changes the scores themselves, so its comparison is labelled separately as a scorer change, not a policy win.
3. Ranking measures computed on identical scores are identical. Two policies sharing the same score trace share the same score ranking and differ only in where they cut it. The optional VUS-PR measure (volume under the surface for the precision-recall curve, a range-based scorer description) is therefore scorer-level only: compute it once per scorer, never per policy, and never use it to select a policy operating point.

Timing and labels for operational event metrics: retain each original labelled event interval on the verified index/time axis. A window score/decision becomes available at that window END; its alert state starts then and persists until the next decision changes it, clipped to the evaluated horizon under the predeclared endpoint convention. Form contiguous episodes from these causal forward-time alert intervals, then intersect them with the original event intervals; never backdate an alert to its input-window start. Simple overlap decides recall/precision as in Section 9.

Delay for a recalled event is the earliest active alert time within the event minus event onset (zero if already active at onset); misses contribute no delay and are counted separately. An event ending before the first available alert is a miss even if the input window overlapped it: for example event [15,25] with first window [0,60] deciding at 60 is a miss, not a negative delay or a backdated hit.

Projection of labels onto the window grid is used only for optional scorer-ranking descriptions, with its rule and short-event loss recorded; event recall keeps all original events in scope and never silently drops them under a majority-window rule. Where a dataset supplies only window labels, evaluate on the stated window-end-labelled grid, disclose its coarseness, and make no original-onset claim. Report physical durations only with valid timestamps or a documented sampling cadence; otherwise report indices/windows. Predeclare the horizon edge/endpoint convention and count and explain warmup-invalid rows rather than silently excluding them from coverage.

## 3. Calibration: fixed and rolling with numbers

Calibration turns old scores into cutoffs. Suppose 200 source-normal windows have scores sorted lowest to highest. As one example convention, the nearest-rank 95th percentile takes the score at position `ceil(0.95 * 200) = 190`, say 0.60. The config records which convention is used so a rerun reproduces the same cutoff. A fixed rule says: alert whenever a later score exceeds 0.60, unless a later section explicitly changes the rule.

A rolling rule recomputes the cutoff from recent history. Two variants behave differently. A full-recent window takes the percentile over all recent scores; when the stream drifts upward it can rise, say 0.60 to 0.68 to 0.75, but the rising pool absorbs anomalies as well as normal drift. An accepted-normal buffer takes the percentile only over recent windows the policy itself called normal; because its pool is truncated near the old cutoff, it generally cannot track a large upward drift, and instead its cutoff stalls, shrinks as confident-normal points dominate, or contaminates when a gradual anomaly is repeatedly accepted as normal and then looks normal forever.

```
cutoff
0.80 |                         full-recent ~~~ rising
0.60 | fixed ---------------- accepted-normal ... stalling
     |        scores drifting up  .  .  .
     +----------------------------------> time
```

Two traps follow from this:

- Circular accepted-normal calibration. The buffer confirms its own mistakes, so a frozen-calibration ablation that never updates runs alongside any adaptive variant, and the exact admission rule is written in config before the run. A narrow admission band does not make this safe by itself; it only changes which mistakes enter the pool.
- Always-alert trap. When drift pushes every score above a frozen cutoff, the policy alerts constantly and recall looks strong while operators ignore everything. Alert volume is reported alongside recall so this failure stays visible.

Causal contract: the decision at time t uses the current score at t plus thresholds and history established strictly before t. Anything learned from window t, including whether t looked normal, applies from t+1 onward. Window t never sets the cutoff that judges window t.

## 4. Chronological splitting

Cut each stream in time order. Never shuffle.

```
older --------------------------------------------------> newer
| source-fit | calibration | dev replay | held-out target |
| learn      | set cutoffs | choose     | report once,    |
| scores +   | + operating | rules +    | no retuning     |
| scaling    | points      | points     |                 |
```

- Source-fit: learn the scorer and any scaling, using source-normal windows. Source labels may be used, declared explicitly in the manifest, solely to select and verify these source-normal windows.
- Calibration: set fixed cutoffs and rolling rules.
- Dev replay: try decision rules and diagnostics. Dev labels guide development only offline after causal decisions are saved, never inside the policy at runtime.
- Held-out: reserved by stream name in the manifest on Day 1 or Day 2 before anyone inspects its outcomes. Until the frozen evaluation only metadata checks are allowed (order basis, time unit, label presence, length). Then it is scored once, where repeating the identical saved config to confirm reproducibility is allowed but no test choice is revised. All choices are frozen before evaluating.

Streams are not chosen because their shift looks convenient or their results look good. Eligibility rests on availability, documented order, understood timestamp and label fields, licence, and sufficient source-normal and calibration length. A stream with no measurable shift is a valid outcome, reported as such, not grounds for silent replacement. The primary reservation is a later tail of the same stream; a separate reserved stream is allowed only with its declared source/calibration prefix and untouched evaluation tail, the replay fit recipe frozen before access, and no source thresholds transferred blindly across different score distributions. Evaluating a window-label-only grid carries the coarseness limit noted in Section 2.

Windows and time basis: no window may contain samples from two segments. The splitter drops or explicitly reassigns edge windows and records the rule. Verified order is sufficient as the time basis; the manifest records the order basis and the time unit (for example sample index with a 1-second sampling interval). Physical durations in seconds are reported only with valid per-sample timestamps or a documented sampling cadence; otherwise report indices/windows.

## 5. Causal preprocessing, windows, and missing data

All preprocessing is fitted on source only and applied forward:

- Window length and stride are fixed in config (for example 60 samples, stride 60).
- Scaling (mean, variance, min-max) is computed on source-fit data and frozen, with the zero-variance handling from Section 2 predeclared.
- Missing values are handled causally using only past observations within the window's own past, for example forward-fill from earlier samples. Never interpolate from the future. The chosen policy is written in config.
- Labels aggregated to windows by a frozen rule (for example a window is anomalous if it overlaps a labelled interval by at least half) are recorded before evaluation and used only for optional scorer-ranking descriptions; operational event metrics in Section 9 keep the original event intervals.

ASCII of a clean split with an edge window dropped:

```
samples: ... | seg A ends | GAP | seg B starts | ...
windows:  [38][39][DROP][40][41]   (DROP straddled the boundary)
```

## 6. Decision rules with worked examples

All examples use the trace 0.21, 0.34, 0.58, 0.71, 0.66 with fixed cutoff 0.60.

Fixed threshold: alert if score above 0.60. Outputs: normal, normal, normal, alert, alert.

K-consecutive (K=2): alert only once 2 windows in a row exceed 0.60. Windows 41 and 42 qualify, so 42 alerts while 41 alone stays silent. This suppresses single spikes at the cost of a K-1 lag relative to the first sustained exceedance, not an event-latency guarantee, since the true event may start earlier or later than the sustained run.

M-of-N (2-of-3): alert when at least 2 of the latest 3 windows exceed 0.60. If the trace had been 0.71, 0.50, 0.66, the third window alerts despite the middle dip, which a strict consecutive rule would have reset on.

Hysteresis: a higher threshold turns an alert on (say 0.65) and a lower one turns it off (say 0.45). Score 0.71 turns the alert on; 0.66 keeps it on because it remains above 0.45; only a score below 0.45 turns it off. This prevents flicker when scores hover near one line.

Defer band: two cutoffs, for example normal below 0.40, defer between 0.40 and 0.70, alert above 0.70. Then 0.21 is normal, 0.58 and 0.66 defer, and 0.71 alerts.

Defer streak example: scores 0.55, 0.58, 0.62, 0.59 all inside a 0.40-0.70 band give four defers in a row. This streak is ambiguous: a building anomaly, a benign new regime the detector never saw, a mismatched calibrator, or detector uncertainty all fit the pattern. Retrospective label analysis can suggest but never prove which interpretation matches ground truth, so the streak stays an open aspect to report honestly rather than a settled method.

## 7. Outputs versus controller actions

Policy outputs per window are normal, alert, and defer. Controller actions about thresholds are holding an update, refreshing a cutoff, or freezing calibration. The daily notes keep these in separate columns:

| Policy output (per window) | Controller action (about thresholds) |
|---|---|
| "Windows 40-45 output defer." | "The controller held the rolling update over those windows." |
| "Window 41 outputs alert." | "The fixed cutoff stayed 0.60." |
| "6 of 100 windows deferred, so decision coverage is 94%." | "Thresholds were refreshed on the decided windows per the frozen rule." |

Fixed, consecutive, M-of-N, and hysteresis rules without a defer band decide every window, so their decision coverage is full by construction.

## 8. Source, dev, and held-out label discipline

- Source labels: used only as declared in the manifest, solely to select and verify source-normal training and calibration windows. Source label files and interfaces stay separate from dev label paths.
- Dev labels: used only offline after causal decisions are saved, to score and compare rules. They never enter the scorer or the policy at runtime.
- Held-out labels: reserved before outcome inspection. Rules and operating points are frozen on dev evidence, then evaluated once, where repeating the identical saved config to confirm reproducibility is allowed but no test choice is revised. No reselection or retuning follows held-out outcomes.

## 9. From windows to episodes to metrics

Work through one small hand example with actual counts. Suppose the late dev replay has 1,000 windows containing 4 labelled events. The policy outputs one state per window, and consecutive alert windows merge into alert episodes before labels are consulted. Say 30 alert windows form 5 episodes E1-E5, and the frozen matching convention is overlap: an event counts as recalled when at least one episode overlaps it, and an episode counts as true-positive when it overlaps any event.

Concretely, suppose E1 overlaps event A, E2 and E3 both overlap event B, E4 spans events C and D, E5 overlaps nothing, and no other overlaps exist. Then recalled events are A, B, C, D (4 of 4) and true-positive episodes are E1-E4 (4 of 5). The worked result is event recall 4/4 = 1.00 and episode precision 4/5 = 0.80, with 1 false-alert episode (E5). The same example shows why duration accompanies these ratios: E4 recalls two events yet counts once in the precision denominator, which flatters precision for long episodes, and E2 plus E3 recall one event while counting twice. Time in alert and time in false or non-event alert stays alongside the episode ratios so these effects remain visible.

Per-output duration keeps this concrete: alert duration is the length of each episode in windows, defer duration is the length of each defer run, and ambiguity can be summarized as the distribution of defer-run lengths plus the defer rate. Operational timing follows Section 2: delay for a recalled event is the earliest active alert time within the event minus event onset, zero when already active at onset; an event ending before the first available alert is a miss, and misses contribute no delay and are counted separately. Event recall keeps every original event inside the evaluated scope.

When a run predicts zero episodes, precision has a zero denominator and is reported as undefined alongside the zero count, never as zero or one; with no labelled events at all, recall is likewise undefined. Grouping episodes before joining labels is what keeps these metrics honest.

Three alert quantities stay distinct:

- Alerted-window fraction: share of windows the policy labelled alert. Computable without labels.
- Alert episode rate: number of alert episodes per 1,000 windows. Also label-free and the closest thing to a deployable alert budget.
- False-alert episodes: number of episodes overlapping no labelled event. This needs labels, so it is an outcome measure rather than a deployable budget.

Deferral rate is deferred windows over total windows. Coverage here is decision coverage, decided windows over total windows: the share of windows the policy committed on, which is lower for deferral policies and full by construction for full-decision rules. Deferral assumes no human oracle: undecided windows stay in coverage, a missed event stays missed unless an actual causal alert fires, later alerts never relabel past defers, and defer is not ground-truth confidence. This is unrelated to conformal prediction coverage and the two are never compared. Comparing a deferral policy against a full-coverage rule at equal coverage is impossible without discarding decisions, so the plans never promise it. Resource units are wall-clock latency percentiles (p50/p95 per window batch on the named machine), peak RAM, and model size or parameter count.

Comparison discipline: operating-point sweeps on dev data select each policy's settings before any held-out run, aiming for a comparable prechosen label-free alert-episode budget or tolerance plus a coverage floor wherever feasible and recording infeasible cases openly. Held-out results report actual alert volume and actual coverage side by side with no retuning of the test trace to force a match. Alert volume, coverage, and compute are different constraints; none is forced to equal another.

## 10. What stays unclaimed

Empirical behaviour on drifting streams does not by itself establish formal coverage, significance, or novelty. Small dev gains are reported with their actual volumes and coverages rather than treated as proof, and building a detector or restating a classical rule is not presented as a contribution. The study tests whether the narrow deployment-time choice helps empirically; the literature comparison decides whether that help is new. Negative, null, and inconclusive results are valid and reportable.

## 11. Short primary-source reading list

The [paper ledger](../btech-ai-research-topic-scan/02-paper-ledger.md) holds the full records; the rows below are entry points for the time-series thread. Details are rechecked against the allowed platforms before any report claim relies on them. Abstract checked 19 September 2026 applies only to TS-2 and TS-7 below; other statuses are inherited from the ledger, not rechecked for this guide.

- TS-1, Wu and Keogh (2023) on benchmark pathologies, IEEE Xplore ([official record](https://ieeexplore.ieee.org/document/9537291)) — ledger status verified official metadata (inherited, not rechecked for this guide).
- TS-2, Liu and Paparrizos (2024) on TSB-AD and VUS-PR, NeurIPS ([official abstract](https://proceedings.neurips.cc/paper_files/paper/2024/hash/c3f3c690b7a99fba16d0efd35cb83b2c-Abstract-Datasets_and_Benchmarks_Track.html)) — official abstract checked 19 September 2026: benchmark and measure issues with some simple methods competitive.
- TS-4, Yao et al. (2022) on chronological shift protocols, NeurIPS ([official abstract](https://proceedings.neurips.cc/paper_files/paper/2022/hash/43119db5d59f07cc08fca7ba6820179a-Abstract-Datasets_and_Benchmarks.html)) — ledger status verified official landing page (inherited, not rechecked for this guide).
- TS-6, Sethi et al. (2023) on conformal-style time-series detection, ACM Digital Library ([official record](https://dl.acm.org/doi/10.1145/3576841.3585931)) — ledger status partial official metadata, so report claims needing its full text wait for full access.
- TS-7, Xu and Bostrom (2026) on separating calibration from training for anomaly thresholds, PMLR ([official record](https://proceedings.mlr.press/v329/xu26a.html)) — official abstract checked 19 September 2026: calibration-only threshold method.

Additional discovery leads (Hydra, Choose Wisely, MSAD-style selector benchmarks) remain pending allowed-platform verification. A scan entry marked unknown leaves the corresponding question open for direct checking.

## 12. Reusable shape from Day 1 (prospective)

The proposed `research/` root does not exist yet; Day 1 creates its first thin integrated path and each following day reuses it. The suggested shape, not a fixed file list, is a versioned loader, a chronological splitter, a deterministic scorer, a calibration interface holding fixed and rolling rules, a decision policy implementing the baselines and a defer band only if investigated, and an evaluator that freezes decisions before joining labels, plus pinned configs, a data manifest with URLs, licences, checksums, fields, split positions and reservations, and a results area saving every score, threshold, decision, and metric table. Small smoke tests exercise these same components; there is no throwaway prototype.

## Navigation

Back: [README](./README.md). Next: [Day 1](./day-01.md).
