# Reliable Alerting for Time-Series Anomaly Detection under Changing Conditions

**Group report — Phase I mid-semester evaluation**
*B.Tech research project, September 2026*
*Team: Aman, Nakul, Pratyush*

---

## Table of Contents

1. Introduction
2. Motivation
3. Literature Survey
4. Problem Statement
5. Objective and Methodology
6. Simulation Platform and Requirements
7. Conclusion
8. References

---

## 1. Introduction

Time-series anomaly detection systems are typically trained on data from a
stable operating period and then deployed on streams that may evolve over
time. A detector that was well-calibrated on historical normal behaviour can
become unreliable when the underlying process drifts: a frozen threshold may
alert constantly as scores shift upward with the stream, or remain silent as a
genuine anomaly stays below a stale cutoff. Recovering from either failure
mode in deployment requires either human re-calibration or an automatic
adaptation rule — and each adaptation rule introduces its own failure mode.

This project studies a specific deployment question: after a detector is
fitted on older normal data, can simple signals available at decision time —
recent anomaly scores, recent decisions, and cheap distributional diagnostics
— select safer alerting behaviour on later stream segments, compared against
a frozen threshold and established temporal baselines, when alert volume is
reported honestly alongside recall?

We study this question on real time-series streams with documented
chronological structure. All comparisons are run on identical anomaly scores
so any observed difference is attributable to the decision rule alone. The
evaluation follows strict causal and label-use rules described in detail in
Section 5. Negative and null results — cases where no rule outperforms the
fixed baseline — are treated as valid findings and reported as such.

---

## 2. Motivation

### 2.1 The deployment gap

Most anomaly detection benchmarks evaluate detectors in a static held-out
setting: the detector is trained, a held-out segment is scored, and metrics
are computed. This setup does not reflect the deployment situation, where
the "test set" is an ongoing stream arriving after deployment. In deployment,
the choice of *when* and *how* to alert — the decision rule — is as
consequential as the choice of detector.

### 2.2 Failure modes of simple rules

**Fixed threshold.** A threshold set at the 95th percentile of source-normal
scores alerts whenever a new score exceeds that value. When the stream drifts
upward, every score may exceed the frozen threshold, producing constant alerts
that operators learn to ignore (the always-alert trap). When the stream drifts
downward, genuine anomalies may fall below the frozen cutoff and go undetected.

**Rolling threshold.** A threshold that recomputes its cutoff from recent
scores can track gradual drift. However, a full-recent rolling rule absorbs
anomalies into its normal pool, potentially suppressing the very signal it is
meant to detect. An accepted-normal buffer (updating only from windows the
policy itself called normal) can confirm its own mistakes: a gradual anomaly
accepted as normal lowers the threshold further, making subsequent anomalous
windows look more normal.

**Temporal persistence rules.** Requiring K consecutive exceedances before
alerting (K-consecutive), or M exceedances in the most recent N windows
(M-of-N), reduces false alerts from isolated spikes at the cost of a detection
lag. Hysteresis rules with separate on/off thresholds prevent alert flicker
around a single boundary.

None of these rules is universally better. Each has operating conditions under
which it outperforms the others, and conditions under which it fails. The
question is whether lightweight diagnostic signals can identify those
conditions at decision time.

### 2.3 The deferral option

A decision rule may decline to commit on a window, outputting *defer* rather
than *normal* or *alert*. A run of deferred windows (a defer streak) arises
when scores fall in an ambiguous region. This streak could indicate a building
anomaly, a new operating regime the detector has not seen, a mismatched
calibrator, or simply detector uncertainty. Retrospective label analysis can
suggest which interpretation applies on a given stream but cannot prove it
from a single run. Deferral is treated as a candidate mechanism to investigate,
not a claimed contribution; its utility depends on whether diagnostic signals
can resolve the ambiguity.

---

## 3. Literature Survey

*Primary citations come only from the seven allowed platforms: IEEE Xplore,
ACM Digital Library, SpringerLink, ScienceDirect/Elsevier, NeurIPS
Proceedings, PMLR (including ICML and AISTATS), and the ACL Anthology. Each
entry states what was checked and where. Claims rest only on the official
abstract unless full text is stated.*

### 3.1 Benchmark pathologies in time-series anomaly detection

Wu and Keogh argue that most exemplars in widely used anomaly detection
benchmarks suffer from one or more of four flaws. As a result, many published
comparisons may be unreliable and apparent progress may be illusory [TS-1].
This motivates starting from a simple statistical scorer and treating complex
or learned scorers as a gated extension that must earn its place on
development evidence. (Title and authors match the arXiv version, which is
discovery only. The IEEE Xplore record could not be read on 2026-09-27, so
venue and DOI are inherited from the team paper ledger and not rechecked.)

### 3.2 TSB-AD and the VUS-PR measure

Liu and Paparrizos (NeurIPS 2024, Datasets and Benchmarks Track) introduce
TSB-AD, a curated benchmark of 1070 time series from 40 datasets. The paper
identifies VUS-PR as the most reliable evaluation measure among those it
studies, and reports that simpler architectures and statistical methods often
outperform advanced neural models [TS-2]. VUS-PR is a scorer-level measure,
computed over threshold sweeps of one score trace. Two decision rules applied
to identical scores therefore share one VUS-PR value, so it cannot separate
them. We compute it at most once per scorer and never use it to choose a
policy operating point. (Official abstract checked 2026-09-27.)

### 3.3 Temporal distribution shift benchmarks

Yao et al. (NeurIPS 2022, Datasets and Benchmarks Track) present Wild-Time,
five datasets with real temporal distribution shift in applications such as
drug discovery, patient prognosis, and news classification. Their primary
protocol trains on data before a fixed time split and evaluates on data after
it (Eval-Fix), and they report an average performance drop of about 20% from
in-distribution to out-of-distribution data across the 13 approaches they
benchmark [TS-4]. Wild-Time is not an anomaly detection benchmark. We cite it
only for its point that shifts arising from the passage of time degrade
models, and that evaluating with a fixed chronological split exposes this.
Our pipeline uses the same style of evaluation: source-fit, calibration,
development replay, and held-out segments in time order, never shuffled.
(Official abstract checked 2026-09-27.)

### 3.4 Leakage-free thresholding from a calibration set

Xu and Boström (COPA 2026, PMLR 329) point out that evaluations often leak
through flawed thresholding. They propose a conformal method that uses
latent-space features to set alarm thresholds from the calibration set only,
and report matching or exceeding a popular but problematic thresholding
method [TS-7]. This is the closest work found so far to our calibration
design, in which cutoffs are fitted on a dedicated calibration segment and
frozen before later data. The differences are that their method is conformal
and uses latent features, whereas our baseline is a nearest-rank quantile of
scalar scores, and that we make no conformal coverage claim. No comparison of
results is claimed without full-text reading. (Official abstract and BibTeX
checked 2026-09-27.)

### 3.5 Conformal methods for time-series data (pending)

The paper ledger's TS-6 entry (ACM DOI 10.1145/3576841.3585931) could not be
verified: the ACM record returned HTTP 403 on 2026-09-27. A search snippet of
that record describes conformal out-of-distribution detection for time series
in cyber-physical systems, using deviation from temporal equivariance as the
non-conformity measure (ICCPS 2023 proceedings). Title and authors are not
confirmed from the official page, so TS-6 is not cited in this report until
they are. Conformal coverage guarantees rest on exchangeability assumptions
that chronological drift violates. Our deferral mechanism is not conformal
prediction, and we make no coverage guarantee.

### 3.6 Dataset source

The development and held-out streams come from the Skoltech Anomaly Benchmark
(SKAB), a set of multivariate sensor recordings from a water-circulation
testbed. Each file is one experiment containing one labelled anomaly. The
upstream repository documents the columns, gives a dataset DOI
(10.34740/KAGGLE/DSV/1693952), and declares a GPL-3.0 licence. Its README
lists the position paper as submitted for publication, and no allowed-platform
paper record for SKAB was found in this check. SKAB is therefore cited as a
dataset [D-1], not as academic evidence.

### 3.7 Discovery leads (unverified, not cited as evidence)

Hydra, Choose Wisely, and MSAD-style multi-stream selector benchmarks remain
leads to verify on the allowed platforms before any claim depends on them.

### 3.8 Gap and novelty status

The verified entries establish: (a) benchmark and measure problems in
time-series anomaly detection [TS-1, TS-2], (b) that simple methods are often
competitive [TS-2], (c) that temporal shift degrades models under
chronological evaluation [TS-4], and (d) that leakage-free thresholding from a
calibration set is an active topic [TS-7]. Whether a deployment-time choice
among alert, defer, fixed, and cautious behaviours is new relative to this
work is not yet established. No novelty claim is made.

---

## 4. Problem Statement

Let $\{x_t\}$ be a univariate or multivariate sensor stream sampled at a
fixed interval. The stream is segmented into non-overlapping windows of fixed
length $W$. A scorer $f$ maps each window to an anomaly score $s_t \in
\mathbb{R}$, oriented so that larger values indicate greater departure from
normal behaviour. The scorer is fitted on a source-normal segment of the
stream and applied forward without refitting.

A decision rule $\pi$ maps each score $s_t$ (together with thresholds and
history established before time $t$) to an output state $d_t \in \{$normal,
alert, defer$\}$. A threshold controller separately decides whether to update
calibration parameters; this is a distinct action from the per-window
decision.

The stream may undergo distributional change after the source-fit period.
Under such change, a frozen threshold may produce excessive false alerts or
miss genuine anomalies. The **research question** is: given simple signals
available at decision time — the current score $s_t$, recent scores, recent
decisions, and distributional diagnostics computed causally — can a decision
rule $\pi$ select safer behaviour compared against a frozen threshold
$\pi_\text{fixed}$ and standard temporal baselines ($\pi_\text{consec}$,
$\pi_\text{M-of-N}$, $\pi_\text{hyst}$), at honestly reported alert volumes?

Safer behaviour is measured by event recall, episode precision, delay to
recall, false-alert episode count, alerted-window fraction, and decision
coverage, as defined in Section 5. Operating points are selected on
development data and evaluated once on a reserved held-out segment.

---

## 5. Objective and Methodology

### 5.1 Pipeline overview

```
source-fit segment --> fit scorer and scaling
calibration segment --> set fixed quantile threshold
development replay --> compare decision rules, examine diagnostics
held-out segment --> single evaluation pass, no retuning
```

All steps proceed in strict chronological order. The same scorer and
the same anomaly scores are used for all policy comparisons in the
development replay; the comparison therefore reflects only the decision
rule, not the scoring function.

### 5.2 Honesty rules (strictly enforced)

**Causality.** A decision at window end-index $t$ uses only the current score
$s_t$ plus thresholds and history established before $t$. Anything learned
from window $t$ — including whether it appears anomalous — applies from
$t+1$ onward. The scorer's reference statistics (mean, standard deviation) are
fitted on the source-normal segment only and frozen before any downstream
window is scored.

**Label discipline.** Source labels are used only to select source-normal
windows for scorer fitting; this use is declared explicitly in the data
manifest. Development labels guide rule selection only offline, after all
causal decisions have been saved; they never enter the scorer or policy at
runtime. Held-out labels are reserved before any outcome is inspected and
evaluated exactly once; no rule choice is revised after seeing held-out
outcomes.

**Comparison honesty.** Operating points are selected on development data
aiming for a comparable label-free alert-episode budget or tolerance.
Held-out results report actual alert volume and actual decision coverage
alongside recall and precision, with no retuning to force a match. Alert
volume, coverage, and compute are reported as separate quantities.

### 5.3 Evaluation metrics

All metrics are computed on the saved prediction trace after decisions are
frozen, before labels are consulted. Consecutive alert windows are merged
into alert episodes before any label is joined.

| Metric | Definition |
|--------|------------|
| Event recall | Recalled events / total clipped events in horizon |
| Episode precision | True-positive episodes / total episodes |
| Detection delay | Per event: max(0, first episode start - event onset) |
| False-alert episodes | Episodes overlapping no labelled event |
| Alerted-window fraction | Alert windows / total windows (label-free) |
| Alert episode rate | Episodes per 1000 decisions (label-free) |
| Decision coverage | Decided windows / total windows |
| Deferral rate | Deferred windows / total windows |

Recall and precision denominators are reported alongside the ratio. Either
is reported as undefined (None) when its denominator is zero — never as zero
or one. An event ending before the first available alert is a miss, not a
hit, even if an input window contained it. These conventions are checked by
hand-derived test cases run against the project evaluator.

Durations and delays are reported in sample-index units unless a stream has a
verified uniform cadence. The development stream does not (Section 5.6).

### 5.4 Dataset selection and reservation

Streams are selected on availability, documented chronological order,
understood label fields, licence permitting academic use, and sufficient
segment lengths. A stream with no measurable shift is a valid and reportable
outcome; streams are never selected or rejected because their results look
convenient.

The held-out target is SKAB file `other/21.csv`, reserved by name on
27 September 2026 before any score was computed on it. Only metadata was
checked: row count (1141), column names, label presence, and first and last
timestamps. It is a separate experiment from the development stream, with its
own source-fit and calibration prefix. Scorer and threshold are fitted fresh
on that prefix, and nothing is transferred from the development stream.

### 5.5 Scorer

The primary scorer is mean-distance from source-normal statistics:

$$s_t = \frac{|\bar{x}_t - \mu_\text{src}|}{\sigma_\text{src} + \varepsilon}$$

where $\bar{x}_t$ is the window mean, $\mu_\text{src}$ and $\sigma_\text{src}$
are the source-fit mean and population standard deviation, and $\varepsilon$
is a predeclared small constant (default $10^{-6}$) to handle zero-variance
sources. All parameters are fitted on the source-normal segment only and
frozen. This scorer is sensitive to level shifts but insensitive to changes
that preserve the window mean (e.g., variance changes, frequency changes);
this limitation is a declared property of the scorer, not a defect to be
silently fixed by refitting.

### 5.6 Development stream and first run

The development stream is SKAB `valve1/0.csv`, a univariate series taken from
the `Current` column (motor amperage). It has 1148 rows and the SHA-256 of the
file is recorded in the data manifest. All timestamps are strictly
increasing, but the cadence is not uniform: steps are 1 s (1095) or 2 s (52),
so 52 seconds are absent from the 1199 s span. Time is therefore measured in
sample index. The segments are source-fit rows [0, 400), calibration
[400, 800), and replay [800, 1148). Windows are 10 rows with stride 10: 40, 40,
and 34 windows respectively, with an 8-row replay tail dropped rather than
padded.

Measured on the first run (fixed threshold, calibration quantile 0.95,
nearest rank): the scorer fitted mean 0.994 and standard deviation 0.280 on
source-fit `Current`. The threshold was 1.243. The 34 replay windows produced
no alerts, so the alerted-window fraction is 0 and decision coverage is 1.
Window-mean `Current` shows no measurable level shift between source-fit
(mean 0.994) and replay (mean 1.027). A second run from the saved config
reproduced every score, decision, and threshold exactly.

**Update (2026-09-27): the calibration boundary was moved to resolve the first property.** Calibration was changed from [400, 800) to [400, 574) so the pool ends before the first anomalous row (574). The calibration pool is now source-normal (0 anomalous rows). The real-stream results were rerun for all five policies on both valve1 and valve2; the fixed threshold is now 1.3085 (valve1) and 1.1387 (valve2). Source-fit [0, 400) was unchanged, so the scorer was not refitted. The window-10 numbers in this subsection describe an earlier superseded stopgap run and are kept for history; the authoritative results use window 4 and the corrected split. The second property (two swapped-column rows) fell in the old calibration segment and is outside the new one.

Two properties of this split were found after the run and are reported as
measured. First, the calibration segment is not source-normal: 226 of its 400
rows fall inside the file's single labelled anomaly, rows [574, 975). The
rank-38 calibration window that sets the threshold lies inside that anomaly.
Second, two calibration rows carry `Current` values near 232 A, while
`Voltage` in the same rows is near 1.2 instead of about 230. This suggests
swapped columns in the raw file, but we have not verified that against the
source. Viewed offline with development labels, the labelled anomaly overlaps
the start of the replay and no alert was raised. Consistent with the
scorer's stated insensitivity (Section 5.5), this first baseline would miss
it. The formal evaluation of this run, and any change to the split, are
pending team decisions. Neither has been made on the basis of these outcomes
without being recorded.

### 5.7 Leakage and causality controls

The scorer's mean and standard deviation were fitted on source-fit rows
[0, 400) of `Current` only. The threshold was fitted on scores of calibration
windows [400, 800) only, before any replay window was scored. Each replay
decision is taken at the window's last row and uses that window's score and
the frozen threshold, nothing else. The loader parses each CSV row but returns
only the value column, so label columns never reach the scorer or policy. The
saved prediction file has no label-derived column.

Labels entered at two points, both declared. Before the run, source labels
were read once to confirm that source-fit rows contain no labelled anomaly
(none did). After decisions were saved, development labels were read offline
to describe the run. Two audits support this. Replacing every label value in
a copy of the file left all scores, decisions, and the threshold unchanged.
Changing `Current` values after row 1000 left every earlier decision
unchanged. The held-out file has not been read by any pipeline code or label
check.

---

## 6. Simulation Platform and Requirements

### 6.1 Software environment

- Language: Python 3.13 (package requires 3.12 or later), global
  interpreter; the installed-package record is kept with the project
- Dependencies: standard library only (no third-party packages required for
  core pipeline)
- Test framework: `unittest` (standard library)
- Version control: git

### 6.2 Pipeline modules

The pipeline is implemented as a set of reusable modules:

| Module | Responsibility |
|--------|---------------|
| Loader | Load stream values from CSV; generate synthetic sequences for testing |
| Splitter | Enforce chronological windows; drop incomplete edge windows |
| Scorer | Fit source-normal statistics; score windows without future data |
| Calibration | Set and hold fixed quantile threshold; rolling rules |
| Policy | Apply fixed, consecutive, M-of-N, hysteresis, and defer-band rules |
| Writer | Save prediction trace and config before labels are joined |
| Evaluator | Form episodes from saved states; join labels; compute metrics |
| Verification | Dataset checks: checksum, ordering, cadence, label structure; refuses held-out label reads |

Each module is tested with synthetic inputs exercising the real components.
There are no disposable prototypes: the Day-1 smoke path uses the same
modules as all subsequent days.

### 6.3 Reproducibility requirements

Every run saves: the resolved config (all parameters explicit), a config_id
(SHA-256 of the serialised config), a run_id (UUID per execution), the full
prediction trace with scores and thresholds, calibration scores, diagnostics,
provenance (environment, git state, file hashes), and the exact command as
executed. An independent rerun of the saved config produces the same trace.

---

## 7. Conclusion

*To be completed on Day 8 after the development comparison and held-out run.*

This section will state: the research question, what the pipeline found on
the development stream(s), whether any decision rule consistently outperformed
the fixed baseline at comparable alert volumes, what the diagnostics showed
about the conditions under which each rule is safer, and whether the failure
map constitutes a reportable contribution. Negative and null findings will be
stated explicitly.

---

## 8. References

Each entry states its verification status as of 2026-09-27.

[TS-1] R. Wu and E. J. Keogh, "Current Time Series Anomaly Detection
Benchmarks are Flawed and are Creating the Illusion of Progress," *IEEE
Transactions on Knowledge and Data Engineering*. IEEE Xplore document
9537291, https://ieeexplore.ieee.org/document/9537291. Title and authors
match the arXiv version (2009.13807, discovery only). Journal, year, and DOI
are inherited from the paper ledger and not yet rechecked on IEEE Xplore.

[TS-2] Liu and Paparrizos, "The Elephant in the Room: Towards A
Reliable Time-Series Anomaly Detection Benchmark," *Advances in Neural
Information Processing Systems 37 (NeurIPS 2024), Datasets and Benchmarks
Track*. DOI 10.52202/079017-3437.
https://proceedings.neurips.cc/paper_files/paper/2024/hash/c3f3c690b7a99fba16d0efd35cb83b2c-Abstract-Datasets_and_Benchmarks_Track.html
Title, abstract, and DOI checked on the official page. Author names are not
shown on that page; surnames as in the paper ledger, full names to confirm.

[TS-4] Yao et al., "Wild-Time: A Benchmark of in-the-Wild Distribution
Shift over Time," *Advances in Neural Information Processing Systems 35
(NeurIPS 2022), Datasets and Benchmarks Track*. DOI 10.52202/068431-0749.
https://proceedings.neurips.cc/paper_files/paper/2022/hash/43119db5d59f07cc08fca7ba6820179a-Abstract-Datasets_and_Benchmarks.html
Title, abstract, and DOI checked on the official page. Author names are not
shown on that page; "Yao et al." as in the paper ledger, full list to confirm.

[TS-7] N. Xu and H. Boström, "Conformalized Time Series Anomaly Thresholding
with Latent Space Features," *Proceedings of the Fifteenth Symposium on
Conformal and Probabilistic Prediction with Applications*, PMLR vol. 329,
pp. 676–688, 2026. https://proceedings.mlr.press/v329/xu26a.html
Title, authors, venue, pages, and abstract checked on the official page.

[D-1] Skoltech Anomaly Benchmark (SKAB), dataset, DOI
10.34740/KAGGLE/DSV/1693952, repository https://github.com/waico/SKAB
(GPL-3.0 per repository README, checked 2026-09-27). Cited as a data
source only.

Not cited pending verification: TS-6 (ACM DOI 10.1145/3576841.3585931,
official page inaccessible on 2026-09-27; title and authors unconfirmed).

---

## Day 3 notes (2026-09-27): evaluator trust, leakage audits, literature

### Metrics notes (Nakul)

The offline evaluator is now exercised by 15 hand-derived cases whose expected
values are computed by hand and checked against the unmodified implementation.
They confirm, on worked examples, the conventions this report relies on:

- **Overlap-existence recall/precision.** An event is recalled iff some
  forward-time alert episode overlaps it; an episode is a true positive iff it
  overlaps any event. Verified on the reference worked example: 5 episodes and
  4 events give event recall 4/4 = 1.00 and episode precision 4/5 = 0.80 with
  one false-alert episode.
- **Durations accompany the ratios.** A single episode spanning two events is
  counted once in the precision denominator (it can flatter precision), and two
  episodes sharing one event are counted twice; total alert duration and
  non-event alert duration are reported alongside the ratios so this stays
  visible.
- **Delay is measured from the original event onset**, not from the first
  decision, with max(0, first_matching_episode_start - onset); a missed event
  records delay None and is counted separately.
- **Undefined reporting.** Recall is None when there are no clipped events;
  precision is None when there are no episodes. Neither is reported as 0 or 1.
- **Units.** Durations, delays, and horizons are in sample-index units, not
  seconds (valve1's cadence is non-uniform; see the development-stream entry).

**valve1 delay floor.** After the calibration boundary correction, the valve1
replay segment is [574, 1148) and the single labelled anomaly begins at row
574 — the first replayed row. The first decision lands at row 577
(= 574 + window_length - 1). Any recall on valve1 therefore carries a delay of
at least a few sample-index units purely from warmup; a hand case pins this so
the delay floor is not misread as detector latency.

### Leakage and causality (Nakul)

Three code/data audits now run as saved tests rather than one-off checks:
- **Code-level label freedom** (
esearch/audit.py): the scorer, all five
  policies, compute_trace, and the loader expose no label parameter, and the
  loader reads only the configured value column.
- **Label-flip invariance** on the real valve1 stream: flipping every label
  leaves scores, decisions, thresholds, and features identical, for the fixed
  and rolling policies (the Day 3 comparison pair).
- **Future-perturbation causality**: changing values in the replay tail leaves
  every earlier decision and the calibration threshold unchanged; and a rolling
  window's own value does not set the cutoff that judges it.

### Real fixed-vs-rolling comparison — BLOCKED (stated as blocked, not filled)

Day 3's headline is the fixed-versus-rolling comparison on development data at
actual alert volume and coverage. The authoritative pipeline outputs exist
(
esult/valve1/{fixed_threshold,rolling_threshold}: scores, decisions,
thresholds), but the offline **evaluator has not yet been run on the real
streams** (no labels join, no episodes, no recall/precision/delay/false-alert
counts under 
esult/). That evaluator run is Pratyush's Day 2/3 deliverable.
Until it exists, this report does not quote real recall, precision, delay, or
false-alert numbers for valve1 — they are recorded here as blocked, not as
placeholders. Label-free quantities that the pipeline already provides
(alerted-window fraction, alert count) are available but are not a substitute
for the episode-level comparison.

### Literature notes (Nakul)

- **Tatbul et al., "Precision and Recall for Time Series" (NeurIPS 2018)** —
  verified on the official NeurIPS proceedings page. It defines a range-based
  precision/recall model (existence, overlap size, position, cardinality) with
  domain-customizable weighting. Our evaluator deliberately uses only
  overlap-existence ratios (recalled clipped events over clipped events;
  overlapping episodes over episodes), which is a simpler, weaker convention;
  we cite Tatbul et al. as the fuller model we are not claiming.
- **TS-2 (Liu and Paparrizos, NeurIPS 2024)**, **TS-4 (Yao et al., Wild-Time,
  NeurIPS 2022)**, **TS-7 (Xu and Bostrom, PMLR 2026)** — verified in prior
  sessions (official pages).
- **TS-1 (Wu and Keogh, IEEE 9537291)** and **TS-6 (Sethi et al., ACM
  3576841.3585931)** — official pages still not machine-readable (no extractable
  content / HTTP 403). Status inherited from the paper ledger; report claims
  needing their full text remain pending.
- Selector-benchmark leads (Hydra, Choose Wisely, MSAD-style) remain unverified
  leads, not cited as findings.

---

## Day 4 notes (2026-09-27): the simple temporal family on shared valve1 scores

### Metrics notes (Nakul)

Day 4 widens the Day 3 fixed-vs-rolling pairing into the full set of simple
temporal controls -- fixed threshold, rolling threshold, K-consecutive,
M-of-N, hysteresis -- all replayed on the **same** valve1 development score
trace (replay [574, 1148), 143 decisions), so any difference is due to the
decision rule, not the scores. Decisions were frozen first and labels joined
only afterward (episodes formed before labels). The single labelled anomaly is
[574, 975).

**Predeclared comparison criterion (before reading outcomes).** Episode-rate
budget <= 70 alert episodes per 1000 decisions; coverage floor >= 1.0. These
are project-level engineering choices (70/1000 is about 10 episodes over
valve1's 143 decisions), not literature-prescribed values, chosen
independently of the observed policy results. They are **reporting criteria,
not rejection gates**: a policy that exceeds the budget stays in the table with
its actual values and a flag. All five Day 4 policies are full-decision
(no defer), so coverage is 1.0 by construction and the floor is satisfied
trivially.

**Family table (valve1).**

| policy | recall | precision | episodes | false-alert | ep/1000 | alerted-window frac | coverage | delay mean | missed | within budget |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_threshold | 1.00 (1/1) | 1.00 (4/4) | 4 | 0 | 28.0 | 0.042 (6/143) | 1.0 | 11 | 0 | yes |
| rolling_threshold | 1.00 (1/1) | 0.704 (19/27) | 27 | 8 | 188.8 | 0.678 (97/143) | 1.0 | 11 | 0 | **no (188.8 > 70)** |
| k_consecutive | 0.00 (0/1) | undefined (0/0) | 0 | 0 | 0.0 | 0.000 (0/143) | 1.0 | undefined | 1 | yes |
| m_of_n | 0.00 (0/1) | undefined (0/0) | 0 | 0 | 0.0 | 0.000 (0/143) | 1.0 | undefined | 1 | yes |
| hysteresis | 1.00 (1/1) | 1.00 (4/4) | 4 | 0 | 28.0 | 0.042 (6/143) | 1.0 | 11 | 0 | yes |

Denominators are carried on every ratio. Precision is reported as **undefined**
(0/0) for k_consecutive and M-of-N because they produce zero episodes -- never
as 0 or 1. Delay is measured from the original event onset (574) and missed
events are counted separately (delay undefined, not zero). Durations and delays
are in sample-index units (valve1's cadence is non-uniform, so seconds are not
used). Timing is recorded with explicit scope (source-run
validated_compute_trace_only; evaluation
saved_run_validation_recompute_and_evaluation_excluding_output), not as
per-window latency.

**Reading the family (measured, no tuning).**
- fixed_threshold and hysteresis behave identically here: 4 episodes, recall
  1/1, precision 1/1, delay 11, 28 episodes/1000 -- comfortably within budget.
  On this trace hysteresis adds nothing over fixed because scores do not hover
  around the cutoff enough to flicker.
- rolling_threshold catches the event (recall 1/1) but at a large alert volume:
  27 episodes, 8 false-alert, 68% of windows alerted, 188.8 episodes/1000 --
  nearly 7x the budget. This is the "over-alert" failure mode: recall looks
  strong while alert volume is high. The rolling cutoff also shrinks after the
  first window (buffer starts unseeded; see the Day 3 note), which drives the
  extra alerts. Kept in the table and flagged, not dropped.
- k_consecutive (k=3) and M-of-N (3-of-5) both suppress everything on this
  trace: 0 episodes, the event missed. The exceedances near the anomaly are not
  sustained enough to satisfy the persistence requirement, so these rules trade
  the event away for zero false alerts here.

**Honest status.** This is one development stream. The family does not tie:
fixed/hysteresis meet the budget with full recall; rolling over-alerts;
persistence rules miss. No rule is selected or dropped on this evidence -- all
five are retained as controls per the plan. A second stream (Day 6) and
diagnostics (Day 5) are where any separation would have to be established.
Whether any of this is a contribution depends on later literature comparison
and supervisor review; a single-stream family comparison is not a claim.

**Verification.** One complete row (fixed_threshold) was recomputed
independently from the raw saved decision trace via the pure evaluator and
matched the saved evaluation on every field (recall, precision, false-alert,
alerted-window fraction, coverage, episode rate, durations, delay, and the
episode set). Every episode in the table traces back to a contiguous run of
alert decisions in the corresponding predictions file. Assembled table values
equal the saved evaluation.json values for all five policies.

---

## Day 5 notes (2026-09-28): diagnostics - hand-inspection and offline feature analysis on valve1

### Metrics / diagnostics notes (Nakul)

Day 5 is the diagnostics day. Working from the SAVED Day 4 valve1 traces (no
new scoring, no policy or threshold change), the five policy decisions were
hand-inspected against the score and the threshold trace, and the two agreed
diagnostic features were analysed offline against the inspected points. The two
hypotheses agreed with the team were **median drift** and **spread/jumpiness**.
Exceedance clustering was explicitly out of scope and not implemented.

The diagnostic features already exist in the pipeline and are saved beside the
scores in every prediction row: `features = [rolling_median, rolling_spread]`,
both with lookback 5 and computed causally over the score sequence (median =
rolling median of the last five scores; spread = rolling sample standard
deviation, n-1 denominator, of the last five scores). Day 5 read these; it did
not build or modify them. Because all five policies share one score trace, the
feature columns are identical across policies (verified byte-identical); the
analysis is therefore done once on the shared columns.

A plotting prerequisite was completed first: the existing figure helper refuses
varying thresholds and so cannot plot the rolling policy. A Nakul module
(inspection_plot.py, tested) draws the score, a stepwise threshold trace that
handles the varying/rolling case, the alert episodes, and the labelled-event
span; five figures were generated at result/valve1/<policy>/day05-inspection.svg.

**Hand-inspection (valve1, event [574, 975); episodes formed before labels).**

| policy | alerts | episodes | clearest false alert | event detection |
|---|---|---|---|---|
| fixed_threshold | 6 | 4 | none | detected; first alert replay:582:585 (end 585), delay 11 |
| rolling_threshold | 97 | 27 | episode ending 1121..1145 (first window replay:1118:1121, score 0.512 vs cutoff 0.258, median 0.177, spread 0.193) | detected; first alert replay:582:585, delay 11 |
| k_consecutive | 0 | 0 | none | MISSED |
| m_of_n | 0 | 0 | none | MISSED |
| hysteresis | 6 | 4 | none | detected; first alert replay:582:585, delay 11 |

The k_consecutive (k=3) and M-of-N (3-of-5) miss traces to the exceedance
pattern, not to scoring or features: only six windows exceed the fixed cutoff,
and only replay:582:585 and replay:586:589 are adjacent (two in a row). The two
very high-score windows (replay:734:737 ~206, replay:766:769 ~209, spread ~93)
are isolated exceedances. Neither count-based rule ever accumulates enough to
alert. This is a decision-rule characteristic on a spiky event.

**Offline feature analysis (dev labels retrospective only; descriptive).**
- **Median drift: no useful separation.** Event-window and normal-window median
  distributions overlap heavily (event median ~0.56 vs normal ~0.43; ranges
  overlap fully). The inspected rolling false-alert window has a below-normal
  median (0.177). Median does not mark where alerting was safer.
- **Spread/jumpiness: no bulk separation.** Event and normal spread overlap
  through the interquartile range (event ~0.24-0.42; normal ~0.24-0.34). The
  only distinctive spread signal is the two isolated in-event spikes (~93),
  which are exactly the windows the count-based policies miss. Spread does not
  separate the bulk of the event from normal.

**Honest status.** On valve1, neither of the two agreed diagnostic features
provides useful separation between the anomaly window and normal behaviour.
This is a valid negative/mixed finding, reported as measured, with no tuning
and no significance claim. Spread's behaviour on the isolated spikes is noted
as a lead only. No defer band and no candidate rule were proposed or built
(Day 5 exploration is gated, and nothing surfaced that justified a mechanism).
All five baseline rows are preserved. Whether the second stream (Day 6) changes
this picture is the open question; two negative streams would themselves be the
reportable finding.

### Leakage / audit (Nakul)

- **Feature spot-check** (research/audit.py recompute_median_feature_from_scores):
  the persisted rolling-median column recomputes from the saved score sequence
  via the same causal component (RollingMedianFeature, length 5) and matches to
  1e-9, confirming the saved feature is exactly what the declared feature
  produces from the recorded scores, with no hidden input.
- **Leakage/causality now covers all five policies, features included**
  (test_realstream_leakage.py): flipping every label leaves scores, decisions,
  thresholds, AND the saved median/spread values identical for all five
  policies; and a future value change leaves every earlier window's decision
  and feature values unchanged. Runs the unmodified pipeline on temp copies
  outside both repos.


---
## Repo report-source content carried forward (2026-09-28 integration)
The material below is preserved verbatim from the earlier repository report
source (`Reliable-Alerting/report/outline.md`, Aman/Pratyush). It is appended
here so nothing important is lost when this Nakul outline becomes the
authoritative report source. Nothing above this line was deleted. Where the
two sources overlap (e.g. Tatbul, the evaluator conventions), both readings
are retained; the sections are labelled by origin.

### Additional verified literature carried from the repo report source
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

### Objective/Methodology material from the repo report source (valve2 results, synthetic diagnostic evidence, evaluator contract, resource scopes)
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

### Simulation platform / figures / verification note from the repo report source
## Simulation Platform and Requirements

Python `>= 3.12` (baseline 3.12); stdlib `unittest`; no extra dependencies.
Reproduce with `.venv/bin/python -m unittest discover -s tests -v` and the
pipeline/compare commands in `README.md`. Each output needs a new
directory (existing output dir or file is refused).

### Submission and evaluation logistics from the repo report source
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

### References carried from the repo report source (local fulltext under results/)
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
