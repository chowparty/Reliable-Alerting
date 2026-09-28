# Data Manifest

**Manifest version:** 6
**Last updated:** 2026-09-28 (Day 5: diagnostics hand-inspection + offline median/spread analysis on valve1 - negative separation; feature spot-check + all-five leakage/causality with features)
**Sole editor:** Nakul

This file is the authoritative record of every dataset used in or reserved
for this project. No stream is scored, loaded into the pipeline, or inspected
for outcomes unless it appears here first, with its role and status declared.
Silence on reservation status is never acceptable: every stream either has an
explicit reservation record or an explicit statement that no reservation exists
and why.

---

## Held-Out Reservation Status

**Current status: RESERVED — SKAB/other/21.csv**

**Reservation date:** 2026-09-27

**File:** `SKAB/other/21.csv` (committed in Reliable-Alerting repository,
path relative to repo root)

**Role:** Held-out evaluation target — separate stream from the development
stream (SKAB valve1/0.csv). This is not a tail of the development stream.

**Access state (re-confirmed 2026-09-27, end of Day 2):** untouched since
the metadata check below. No config, result, source file, or test in either
repository references it (searched). `research/verification.py` refuses to
read labels from it (`RESERVED_HELD_OUT`), enforced by tests.

**Metadata-only check performed (permitted by reference.md §4):**
Prior to reservation, the following structural facts were verified by
reading file metadata only — no scores were computed, no pipeline was run,
and no outcome was inspected:
- Row count: 1141 data rows (plus 1 header row)
- Column structure: identical to SKAB valve1/0.csv —
  `datetime;Accelerometer1RMS;Accelerometer2RMS;Current;Pressure;
  Temperature;Thermocouple;Voltage;Volume Flow RateRMS;anomaly;changepoint`
- Value field: `Current` (same as development stream)
- Label field: `anomaly` (binary point labels, 0/1)
- Label presence confirmed: 402 rows carry `anomaly=1` — labels exist
- Timestamps (first/last row): `2020-02-08 18:34:51` → `2020-02-08 18:54:54`
  — a distinct experimental session from valve1 (`2020-03-09`), confirming
  this is a separate run, not a continuation
- First labelled anomaly at data row 569 (0-indexed).

**Correction (2026-09-27, Day 2):** the version-2 text of this entry said
rows [0,569) were "well above the 800 rows required for source-fit [0,400)
plus calibration [400,800)". That was wrong: 569 is less than 800. What the
metadata actually shows is that the source-fit prefix [0,400) precedes the
first labelled anomaly, while the calibration prefix [400,800) extends past
it (the first labelled anomaly at row 569 falls inside [400,800)). No further
label inspection of this file has been done to establish how much of
[569,800) is labelled; doing so is not needed to see the problem and is
deliberately avoided.

**Open decision (must be settled before any access to this file):** under
the recipe below, this file's fixed threshold would be calibrated on a
segment that includes labelled-anomalous rows. The development stream has
the same property (see below), so the decision should be made once and
applied to both. Until it is made, the recipe below stands as written and
the file stays untouched. Any recipe change is recorded here, dated, before
the file is accessed.

**What has NOT been done:**
- No anomaly scores have been computed on this file
- No threshold has been applied to this file
- No outcome metrics have been computed or inspected
- The signal shape, drift characteristics, and detectability of anomalies
  in this file are unknown and deliberately uninspected
- This reservation constitutes no claim about this file's shift or results

**Source/calibration prefix (frozen before any access; see open decision):**
- Source-fit segment: rows [0, 400) — to be used to fit the scorer
  (MeanDistanceScorer on `Current` values)
- Calibration segment: rows [400, 574) — to be used to fit the fixed
  (moved 2026-09-27 from [400,800) so the pool precedes the first anomalous row)
  quantile threshold
- Evaluation segment: rows [574, 1141) — untouched until the single
  (start moved from 800 to stay contiguous with the calibration end)
  frozen evaluation pass

**Fit recipe (frozen as of this reservation date; see open decision):**
- Scorer: MeanDistanceScorer fitted on `Current` values from rows [0, 400)
  of this file only. Population standard deviation, epsilon=1e-6.
- Threshold: FixedQuantile at quantile=0.95, nearest-rank method, fitted
  on calibration-segment scores (rows [400, 574) of this file only)
- Window length 10, stride 10, anchor segment_start, drop_incomplete edge
  policy — matching the development config `configs/day02-valve1.json`
  (confirmed Day 2; previously recorded as provisional).
- No scorer parameters, no threshold value, and no scaling statistics
  from SKAB valve1/0.csv (the development stream) will be transferred
  to this file. Fresh fit from this file's own prefix only.

**Permitted actions before frozen evaluation:**
- Metadata checks only: confirm row count, column names, label presence,
  and timestamp ordering (row count, columns, label presence done above;
  timestamp ordering not yet checked for this file)
- Running the identical saved config to confirm reproducibility after
  the evaluation is complete (reference.md §4)

**Prohibited actions before frozen evaluation:**
- Computing scores on any segment of this file
- Inspecting the distribution of `Current` values beyond what is already
  recorded above
- Using this file's outcomes to revise any rule, operating point, or
  threshold choice
- Evaluating more than once (except the identical-config reproducibility
  rerun)

---

## Development Stream

### Stream: SKAB valve1/0.csv (Day 2 development stream)

**Status:** Verified and run end to end on Day 2 (fixed-threshold baseline).
Not yet fully eligible: URL/provenance outstanding (see prerequisites).

- **Role:** Development stream (Day 2 onwards)
- **File path (in repo):** `SKAB/valve1/0.csv` (committed in
  Reliable-Alerting repository, commit 5bdd9a8, 2026-09-27, by Aman)
- **URL:** NOT YET RECORDED — outstanding prerequisite. We do not know
  where Aman obtained this copy.
- **Licence:** The upstream SKAB repository README
  (https://github.com/waico/SKAB, checked 2026-09-27) declares GPL v3.0 and
  gives the dataset DOI 10.34740/KAGGLE/DSV/1693952. That applies to our copy
  only if our copy came from that source, which is tied to the URL
  prerequisite. Recorded as "upstream declares GPL-3.0; provenance of our
  copy unconfirmed".
- **Checksum - two recorded values for the same data (line-ending state differs):**
  - Raw file as stored on this checkout (CRLF): `90f70a75cf359e5e7b0fffa0644fdbac6733a71510e7891b6d0427effd750cb6`
    (132,924 bytes, CRLF, no BOM; computed 2026-09-27, authoritative for this Windows working tree).
  - Same content normalized to LF line endings: `14ea55a5987f2074f3c9851f3963e3308c8668eeeca2249fc3de6491cb7e1b74`
    (recorded in the earlier repo manifest via `shasum` on an LF checkout).
  Verified 2026-09-28: hashing the raw on-disk bytes reproduces the CRLF value, and
  converting CRLF->LF reproduces the LF value. These are the SAME data in two
  line-ending states, NOT two competing authoritative hashes. The CRLF value is
  authoritative here because it matches the bytes git checks out on this machine.
- **Order basis:** Verified 2026-09-27: all 1148 `datetime` values strictly
  increasing (0 violations). `load_csv_stream()` itself still does not check
  ordering; this is a one-time manual verification pinned by
  `tests/test_verification.py`, not a loader guarantee.
- **Cadence (measured):** consecutive timestamp steps are 1 s (1095 steps)
  or 2 s (52 steps). Wall-clock span 1199 s over 1148 rows, so 52 one-second
  samples are absent. Rows are therefore NOT uniformly 1 s apart.
- **Time unit:** sample index (row number). The version-2 statement "1 row =
  1 second" is withdrawn given the cadence above. Physical durations in
  seconds are not reported for this stream; delays and durations are in
  sample-index units.
- **Timestamp field:** `datetime` (format `%Y-%m-%d %H:%M:%S`)
- **Value field:** `Current` (motor amperage per upstream README)
- **Missing values:** 0 empty `Current` cells in 1148 rows (verified).
- **Label field:** `anomaly`, encoded as the strings `0.0` (747 rows) and
  `1.0` (401 rows). Note for the evaluator: `events_from_point_labels()`
  requires strict ints 0/1, so these values need explicit conversion.
- **Label structure (dev labels, read offline after decisions were saved):**
  one contiguous labelled run, rows [574, 975) half-open.
- **Changepoint field:** `changepoint`, 4 rows with `1.0`; not used.
- **Total data rows:** 1148
- **First / last timestamp:** `2020-03-09 10:14:33` / `2020-03-09 10:34:32`
- **Segment split positions (as run, `configs/day02-valve1.json`):**
  - Source-fit: rows [0, 400) — 40 windows
  - Calibration: rows [400, 574) — 43 windows (corrected 2026-09-27; source-normal)
  - Dev replay: rows [574, 1148) — 143 windows (window 4, stride 4) in the
    AUTHORITATIVE result/ runs after the calibration fix. (The earlier
    "[800,1148), 34 windows" here described my superseded window-10 stopgap;
    corrected 2026-09-27 record-only, no boundary change.) Aman's manifest.md
    still says replay 800..1150; his replay start is stale vs the [400,574)
    calibration boundary and is his to update.
- **Labelled rows per segment (authoritative [0,400)/[400,574)/[574,1148)):**
  source-fit 0 of 400; calibration 0 of 174 (source-normal after the fix);
  replay 401 of 574 (the whole anomaly run [574,975) is in replay). (The
  earlier "calibration 226 of 400; replay 175 of 348" described the superseded
  [400,800) stopgap; corrected 2026-09-27 record-only.)
- **Source label use (declared):** labels were read once, before the run, to
  verify source-fit [0,400) contains no `anomaly=1` row (result: 0). Config
  value `source_label_use: "verify_source_normal"`. Labels do not enter the
  scorer or policy.
- **Shift description (measured, label-free, from run-a outputs):** see the
  Day 2 findings section below.

**Outstanding prerequisites before this stream is fully eligible:**

1. **URL / provenance missing.** Where our copy came from is unknown.
   Required: Aman records the source URL (and version/commit if from GitHub).
2. **Licence tied to 1.** Upstream declares GPL-3.0; confirm once 1 is known.
3. ~~Checksum not computed.~~ Done 2026-09-27 (above).
4. ~~Timestamp ordering unverified.~~ Done 2026-09-27 (above); loader-level
   ordering check remains an Aman item.
5. ~~Source-normal segment verification pending.~~ Done 2026-09-27: 0
   labelled rows in [0,400).

**Note on Aman's manifest.md:** A `manifest.md` exists in the Reliable-Alerting
repository (committed 2026-09-27) which records SKAB valve1 as the Day 2
development stream and SKAB valve2 as the Day 6 stream. That manifest is
incomplete: it is missing URL, licence, checksum, order-basis statement, and
source-label-use declaration — all of which are required by the eligibility
rule in reference.md §4. This manifest (btp-work/research/data/manifest.md)
is the authoritative record; Aman's manifest.md is not edited by Nakul.

---

## Current Authoritative Pipeline Output (as of pull 2026-09-27)

Aman reworked the pipeline and committed real multi-policy results. As of the
latest pull (`Reliable-Alerting` HEAD `9dee236`), THESE are the authoritative
Day-2/Day-3 baseline outputs, superseding my Day-2 stopgap:

- **Pipeline rework:** commit `0f8f5a8` reworked `src/reliable_alerting/pipeline.py`
  and `writing.py`, added `run_real_streams.py` and `configs/day07-ablation.json`.
  Input kind is now `csv_stream` (not my `real_csv_v1`); window length 4 (not
  10); a `features` block (`rolling_median`, `rolling_spread` of the score)
  is added to each prediction row.
- **Results:** commit `9dee236` added `result/valve1/` and `result/valve2/`,
  each with five policy subdirectories: `fixed_threshold`, `hysteresis`,
  `k_consecutive`, `m_of_n`, `rolling_threshold`. Each holds
  `predictions.csv`, `config.json`, `diagnostics.json`, `metadata.json`,
  `calibration_scores.csv`. Generated on Aman's machine (metadata records
  Python 3.14.2, path `D:\Reliable-Alerting`).
- valve1: 100 source-fit windows, 100 calibration windows, 87 replay windows.
  valve2: analogous, length 1125.

**My Day-2 stopgap is superseded (recorded, not dropped):** the run I made to
unblock verification (`real_csv_v1` input kind, window length 10, threshold
1.2429688332808349, output dirs `results/day02-valve1-run-a` / `-run-b`) was
an exploratory stopgap. It is superseded by Aman's `csv_stream` window-4
results (commits `0f8f5a8` pipeline, `9dee236` results). My `real_csv_v1`
change no longer exists in the tree (his pull overwrote `pipeline.py`), and my
`configs/day02-valve1.json` and stopgap result dirs are gone. The stopgap
established causality/label-discipline and reproducibility on real data, which
still hold under his code (re-audited 2026-09-27, below); its specific threshold
and window are not used going forward.

---

## RESOLVED DECISION — calibration segment boundary moved to [400,574)

**Status: RESOLVED 2026-09-27. Calibration boundary moved from [400,800) to
[400,574). Real-stream results rerun. This section supersedes the earlier
"OPEN DECISION" text (kept below struck-through for history).**

**Decision taken:** move the calibration boundary so it ends immediately before
the first anomalous row. Row 574 is the verified first anomalous row (anomaly
run [574,975), half-open). Calibration is now [400,574); replay is [574,end) to
stay contiguous. Source-fit [0,400) is unchanged, so the scorer statistics are
unchanged (valve1 mean 0.99395 / std 0.27955; scorer refit was not required).

**Result of the fix (verified):**
- New calibration pool [400,574): window length 4 / stride 4 gives 43 windows,
  **0 of which overlap the anomaly** — the calibration pool is now source-normal,
  as reference.md §3/§8 require.
- New fixed threshold: valve1 1.3085423988586153 (was 1.3249013096528448);
  valve2 1.1386923076923078 (was 1.2316165). Thresholds are now calibrated on
  source-normal data only.
- Applies identically to all five policies (shared source-fit/calibration/scores)
  and has been applied to the SKAB/other/21.csv frozen recipe below.
- All 10 real-stream result directories (`result/valve{1,2}/{5 policies}`) were
  rerun with the corrected split via `run_real_streams.py`.

The two suspected swapped-column rows (734, 766) are inside the OLD calibration
segment [400,800) but OUTSIDE the new [400,574); they no longer enter the
calibration pool. (They remain in the raw data and now fall in the replay
segment; that is a separate data-quality observation, not part of this fix.)

<details>
<summary>Superseded OPEN-DECISION text (history, no longer in force)</summary>

The earlier text recorded this as an open, unresolved decision: calibration
[400,800) contained 226 anomalous rows; 57 of 100 window-4 calibration windows
overlapped the anomaly; the rank-95 threshold-setting window calibration:588:591
(score 1.3249013096528448) was itself inside the anomaly. The team has now
resolved it by moving the boundary, as recorded above.

</details>

---## Day 2 Findings (development stream, run `day02-valve1-run-a`)

Recorded as measured. None of these is a selection criterion.

**1. The calibration segment WAS not source-normal; RESOLVED 2026-09-27.** Under the old split [400,800), 226 of 400 rows were labelled anomalous and the rank-38 threshold window was inside the anomaly. The boundary was moved to [400,574) (see RESOLVED DECISION above); the calibration pool is now anomaly-free and the results were rerun. Original finding retained for history: reference.md §3 requires calibration on source-normal windows, which the old split did not provide.

**2. Two calibration rows have out-of-range `Current` values.** Rows 734
and 766 have `Current` = 231.882 and 235.511 (all other rows are near 1).
In those two rows the `Voltage` column holds 1.19858 and 1.16197, where other
rows hold values near 230. This looks like the two columns are swapped in
those rows. That is an interpretation of the raw file, not verified against
the upstream source. They produce the two largest calibration scores (82.3,
83.0, ranks 39–40), so they do not set the rank-38 threshold.

**3. Shift description (label-free).** Raw `Current` mean / population sd:
source-fit 0.9940 / 0.2796, replay 1.0274 / 0.2589 (calibration 2.1583 /
16.4159, dominated by the two rows above). Window scores: calibration median
0.467, p90 1.090; replay median 0.544, p90 0.911, max 1.014. There is no
measurable level shift in `Current` window means between source-fit and
replay. (Numbers in this paragraph are from the superseded window-10 stopgap:
threshold 1.2430, 0 alerts in 34 windows. The authoritative window-4 fixed run
uses threshold 1.3085424 over 143 replay windows with 2 alerts; see result/.
Kept for history, corrected 2026-09-27 record-only.)

**4. Offline label context (dev labels, after decisions were saved).** Rows
[800, 975) of the replay are inside the single labelled run. With zero alert
episodes, that run would be missed (event recall 0 of 1 on the replay
horizon, precision undefined with 0 episodes). This is a preliminary reading.
The formal evaluator run is Pratyush's scope and has not been done. It matches
the known limitation in reference.md §2: a mean-distance scorer does not
respond to changes that leave the window mean unchanged. No scorer change is
proposed here (Day 7 gate).

**5. Reproducibility.** run-b (replayed from run-a's saved config) matched
run-a: predictions identical excluding `run_id`; `config.json`,
`diagnostics.json`, `calibration_scores.csv` byte-identical; same
`config_id` and `input_hash`.

**6. Audits passed.** Replacing every `anomaly` and `changepoint` value in a
temporary copy left scores, decisions, threshold, scorer, and `input_hash`
unchanged. Setting `Current` in rows [1000,1148) to 999 left all 20 windows
ending before row 1000 unchanged (and the threshold and scorer). Temporary
copies were deleted.

**7. Config/loader mismatch (no effect today).** The config declares
`missing_policy: "reject"`, but `load_csv_stream()` forward-fills empty cells
(and would fill a leading empty cell with 0.0) instead of rejecting. With 0
empty cells in this file it changed nothing on Day 2. Flagged for Aman.

---

## Day 6 Development Stream (advance notice)

### Stream: SKAB valve2/0.csv (Day 6 second development stream)

**Status:** Noted only — not yet active. Recorded here so this file is not
mistakenly used or inspected before Day 6.

- **File path:** `SKAB/valve2/0.csv` (committed in Reliable-Alerting repo)
- **Role when activated:** Second development stream (Day 6)
- **Total data rows:** 1125 (noted from metadata; not yet verified)
- **Same outstanding prerequisites as valve1:** URL, licence, checksum,
  ordering verification all missing. Do not use until Day 6 prerequisites
  are satisfied.
- **No pipeline access permitted before Day 6**

---

## Note: `configs/day07-ablation.json` scope label (inert)

Aman's commit `0f8f5a8` added `configs/day07-ablation.json`. It is a static
parameter/description file in the same schema family as
`day04-synthetic-family.json`: it lists the five policy names and prose notes,
with `authoritative_operating_record: false`, `quality_selection: none`,
`recall_targets: none`. It contains **no data path, no stream name, and no
file reference**, and nothing in the repository reads it. It cannot, by itself,
cause any data (including held-out) to be read; it is inert text today.

Its field `"scope": "held_out_validation_ablation"` is premature and
mislabelled relative to the plan: the plan's Day 7 is ablations on development
evidence, and the single held-out run is Day 8, only if the Day 8 audit passes.
Fusing "held_out" and "ablation" into one scope conflates two different days.
This is worth Aman correcting later; it is not a breach and it has not touched
the reserved file. Recorded here so the label is on the record and does not
silently turn into a held-out access later without going through this manifest.

---
## Confirmed Streams

| Stream | Role | Status |
|--------|------|--------|
| SKAB/valve1/0.csv | Development (Day 2) | Verified (checksum, order, source-normal); run end to end; URL/provenance outstanding |
| SKAB/other/21.csv | Held-out evaluation target | **RESERVED 2026-09-27; no outcome inspected; untouched; calibration-prefix decision open** |
| SKAB/valve2/0.csv | Second development (Day 6) | Noted only; do not access before Day 6 |

---

## Source Label Use Declaration

For any stream where source labels are used to select or verify source-normal
windows for scorer fitting: that use is declared explicitly in this manifest
entry under "Source label use" for that stream, with the exact selection rule
stated. Source labels never enter the scorer or policy at runtime. Development
and held-out labels never enter the scorer or policy at any time.

Current declaration (valve1): source labels were used solely to verify that
the source-fit segment [0,400) contains no anomaly=1 rows (result: 0). This
did not change which rows entered the scorer. The run config carries
`source_label_use: "verify_source_normal"`.

---

## Audit Trail

| Date | Action | Who |
|------|--------|-----|
| 2026-09-26 | Manifest created; held-out status explicitly declared as unreserved; two unverified leads recorded | Nakul |
| 2026-09-27 | Held-out reservation made: SKAB/other/21.csv reserved by name, metadata-only check performed, no outcomes inspected, fit recipe frozen; SKAB valve1/0.csv recorded as development stream candidate with all outstanding prerequisites noted; SKAB valve2/0.csv noted as Day 6 stream (no access before then) | Nakul |
| 2026-09-27 | valve1 verified before the run: 0 labelled rows in source-fit [0,400); 1148 timestamps strictly increasing | Nakul |
| 2026-09-27 | valve1 run end to end with `configs/day02-valve1.json` (runs `day02-valve1-run-a`, `-run-b`, local results, gitignored); reproducibility, label-invariance, and future-perturbation audits passed | Nakul |
| 2026-09-27 | valve1 checksum recorded; cadence measured (52 absent seconds; "1 row = 1 s" withdrawn); label format and per-segment label counts recorded; calibration-contamination and swapped-column observations recorded; upstream licence declaration recorded (provenance still outstanding) | Nakul |
| 2026-09-27 | Correction to 21.csv entry: "569 normal rows well above 800" was false; calibration prefix overlaps first labelled anomaly; recipe unchanged pending team decision; file still untouched | Nakul |
| 2026-09-27 | Synced to Aman's pull (HEAD 9dee236): recorded his 5-policy real results for valve1/valve2 as authoritative; marked my real_csv_v1 window-10 stopgap superseded (commits 0f8f5a8, 9dee236); re-ran btp-work audit suite against his result/valve1/fixed_threshold and result/valve2/fixed_threshold; re-ran label-invariance and causality audits against his current csv_stream pipeline.py (both hold) | Nakul |
| 2026-09-27 | Calibration contamination confirmed UNDER Aman's implementation and parked as OPEN DECISION: calibration [400,800) unchanged, 57 of 100 window-4 calibration windows overlap anomaly [574,975), rank-95 threshold window calibration:588:591 is inside the anomaly, threshold 1.3249013096528448; applies to all 5 policies and to the 21.csv recipe; team to decide keep-and-report vs move-boundary; not resolved | Nakul |
| 2026-09-27 | Recorded day07-ablation.json 'held_out_validation_ablation' scope as inert mislabelled text (no data path, unread, touches nothing reserved); flagged for Aman to correct | Nakul |
| 2026-09-27 | RESOLVED calibration contamination: moved boundary [400,800)->[400,574) (row 574 = first anomalous row); source_fit [0,400) unchanged (scorer identical); calibration pool now source-normal (0 anomalous rows, 43 windows); reran all 10 real-stream results (valve1 thr 1.3085424, valve2 thr 1.1386923); updated run_real_streams.py, Aman manifest.md, this manifest, test_verification.py pins, 21.csv frozen recipe; 21.csv itself NOT accessed | Nakul |
| 2026-09-27 | Schema-only fix to src/reliable_alerting/writing.py (_validate_trace_rows): required PREDICTIONS_COLUMNS stay required, 'features' allowed as the one optional field, other unexpected keys rejected. Score/threshold->output_state consistency check intentionally NOT restored (conflicts with stateful policies k_consecutive/m_of_n/hysteresis). test_rejects_extra_missing_keys passes; test_decisions.py 23 pass/1 fail (test_no_output_on_validation_failure left red as a pre-existing fixed-threshold-era contract issue needing a separate policy-aware decision). ONLY writing.py changed; calibration work, run_real_streams.py, result/, and tests untouched | Nakul |
| 2026-09-27 (Day 3) | Added evaluator hand cases 11-15 (reference.md sec 2 miss, sec 9 worked example recall 4/4 precision 4/5 1-false, two-episodes-one-event durations, always-alert volume, valve1 replay-start delay floor); all pass against the UNMODIFIED evaluator (no defect to route to Pratyush). | Nakul |
| 2026-09-27 (Day 3) | Added research/audit.py + test_audit_code.py: static label-freedom check on scorer, all 5 policies, compute_trace, loader; loader reads only value_column. All pass. | Nakul |
| 2026-09-27 (Day 3) | Added test_realstream_leakage.py: label-flip invariance and future-perturbation causality on FIXED and ROLLING (Day 3 pair) over valve1, plus rolling 'own-window value does not set its own cutoff'. Runs the real pipeline against temp copies outside both repos; writes nothing to result/ or results/. All pass. | Nakul |
| 2026-09-27 (Day 3) | Made test_audit threshold-consistency policy-aware: static policies (fixed/k_consecutive/m_of_n) check every row == calibration threshold; rolling checks first decision == calibration threshold; hysteresis exempt. Audit now passes against all 5 valve1 result dirs. | Nakul |
| 2026-09-27 (Day 3) | Record-only corrections to stale window-10 stopgap lines (dev-replay window count, per-segment label counts, shift-description threshold) to the authoritative window-4 facts. No boundary/result change. | Nakul |
| 2026-09-27 (Day 3) | DEFERRED (noted, not changed): valve2 calibration [400,574) still overlaps its anomaly (first anomalous row 562) - to verify/resolve at Day 6. 21.csv reserved recipe calibration [400,574) runs past its first anomaly (row 569) and cites window 10 / configs/day02-valve1.json which no longer exist - to resolve at Day 8. Neither is used in Day 3; boundaries/recipes/results left unchanged per instruction. | Nakul |
| 2026-09-27 (Day 3) | Literature: verified Tatbul et al. 2018 'Precision and Recall for Time Series' on the official NeurIPS page (range-based P/R vs our overlap-only metric). TS-1 (IEEE 9537291) and TS-6 (ACM 3576841.3585931) still not machine-readable (no content / HTTP 403) - remain pending, inherited from ledger. Selector leads (Hydra, Choose Wisely, MSAD) remain unverified leads. | Nakul |
| 2026-09-27 (Day 4 Phase A) | Produced five real-stream evaluations for valve1 (fixed_threshold, rolling_threshold, k_consecutive, m_of_n, hysteresis) via reliable_alerting.evaluation_io, output under result/valve1/<policy>/evaluation/. Built the two prerequisite inputs (configs/day04-valve1-labels.json: coverage [574,1148), event [574,975); configs/day04-valve1-evaluation.json: horizon [574,1148], window 4, stride 4, first_decision 577). As Pratyush's stand-in with approval. | Nakul |
| 2026-09-27 (Day 4 Phase A) | Scoped evaluation-path loader fix (Pratyush stand-in): evidence.load_predictions_csv and evaluation_io.load_predictions_generic now accept the optional 'features' column and no longer impose the obsolete score/threshold->output_state consistency assumption (invalid for stateful policies). Backward-compatible with the 8-column format; 4 pre-existing unrelated failures remain. Aman policy code, result predictions, thresholds, calibration, replay boundaries, and the Day 3 writer contract unchanged. | Nakul |
| 2026-09-27 (Day 4 operating-point criterion) | Predeclared BEFORE reading comparative outcomes: episode-rate budget <= 70 alert episodes per 1000 decisions; coverage floor >= 1.0. Project-level engineering choice (70/1000 ~= 10 episodes over valve1's 143 decisions), NOT literature-prescribed; chosen independently of observed results; synthetic 250/1000 explicitly not used. Reporting/comparison criteria, not rejection gates. | Nakul |
| 2026-09-27 (Day 4 Phase B) | Built the five-policy valve1 family table (research/family_table.py + tests) from the saved evaluations; every metric with denominators, delay with misses separate, false-alert episodes, coverage, alerted-window fraction, episode rate, timing with explicit scope. Operating-point record with per-policy settings + feasibility flags. Independent full-row recompute of fixed_threshold from the raw decision trace matched the saved evaluation on every field; every episode traced to a contiguous alert run. Artifact result/valve1/day04-family-table.json. Over-budget rolling_threshold kept and flagged (188.8/1000), not dropped. | Nakul |
| 2026-09-28 (Day 5 integration) | Merged the authoritative Nakul manifest into Reliable-Alerting/manifest.md. Held-out status = RESERVED SKAB/other/21.csv (this manifest governs; earlier repo 'none reserved' retained as superseded historical note). valve1 checksum records both the CRLF raw hash (90f70a75...) authoritative here and the LF-normalized hash (14ea55a5...) as the same data in two line-ending states (verified). Appended valve2 provenance + calibration-correction note carried from the earlier repo manifest. | Nakul |
| 2026-09-28 (Day 5 prereq PR1) | Built research/inspection_plot.py (+ test_inspection_plot.py): score points + STEPWISE threshold trace (holds each decision's cutoff across its forward interval; handles varying/rolling thresholds that evidence.render_figure rejects), alert-episode bands, labelled-event span; plain stdlib SVG, refuse-overwrite. Generated five figures result/valve1/<policy>/day05-inspection.svg from the saved traces. Pratyush stand-in for a varying-threshold figure. No policy/threshold/scorer/evaluator change. | Nakul |
| 2026-09-28 (Day 5) | Hand-inspected all five valve1 policies from the saved Day 4 traces. Episodes formed from predictions BEFORE joining the event label [574,975), then traced to exact window IDs with score/threshold/state/median/spread. Clearest false alert: rolling episode ending 1121..1145 (first window replay:1118:1121, score 0.512 vs shrunken cutoff 0.258). fixed/hysteresis: no false alert, event detected, delay 11. k_consecutive (k=3) and m_of_n (3-of-5): 0 episodes, event MISSED - traced to only 2 adjacent exceedances (replay:582:585, replay:586:589) with the big spikes replay:734:737 (~206) and replay:766:769 (~209) isolated; a count-based-policy characteristic, not a scoring/feature defect. | Nakul |
| 2026-09-28 (Day 5) | Offline median + spread analysis (agreed hypotheses: median drift, spread/jumpiness; clustering NOT implemented). Dev labels read retrospectively only, after decisions saved, to mark inspected points. Verified the median/spread feature columns are byte-identical across all five policies (shared score trace). MEDIAN: event vs normal distributions overlap (event median ~0.56 vs normal ~0.43, ranges overlap; inspected false-alert window median 0.177 below normal) -> no useful separation. SPREAD: bulk overlaps (event IQR ~0.24-0.42 vs normal ~0.24-0.34); only the two isolated spike windows stand out (~93), which are exactly the ones k/m miss -> no bulk separation. Conclusion: neither feature separates the event from normal on valve1. Negative/mixed finding, filed as measured; no tuning, no significance claims. No defer band / candidate rule proposed or built (gated exploration; none justified). | Nakul |
| 2026-09-28 (Day 5) | Feature spot-check folded into audit: research/audit.py recompute_median_feature_from_scores() re-drives the teammate RollingMedianFeature(5) over the saved scores and confirms the persisted median column matches to 1e-9 (+ tests: synthetic match, tamper detection, real valve1 fixed_threshold column). | Nakul |
| 2026-09-28 (Day 5) | Extended research/tests/test_realstream_leakage.py from the Day 3 fixed/rolling pair to ALL FIVE valve1 policies. Added explicit feature-value invariance under label flip (median/spread columns byte-identical) and feature causality under future perturbation (a future value leaves earlier windows' feature values unchanged). Runs the unmodified pipeline against temp copies outside both repos; writes nothing to result/ or results/. All pass. | Nakul |
| 2026-09-28 (Day 5) | DEFERRED (noted, not changed): valve2 calibration [400,574) still overlaps its anomaly (first anomalous row 562) - to resolve at Day 6. 21.csv reserved recipe unchanged and file untouched - to resolve at Day 8. Neither used in Day 5. | Nakul |


## valve2 Development Stream (Day 6) - provenance carried from the earlier repo manifest

Recorded here so valve2 provenance is not lost. valve2 stays a Day 6 stream;
no access before Day 6 (as already stated in the "Day 6 Development Stream"
note above). Facts below are from the earlier Reliable-Alerting/manifest.md
(Aman), retained as project provenance:

- File: `SKAB/valve2/0.csv`; 1125 rows.
- SHA-256 (LF checkout, `shasum`): `893e9f555603657ed871d00975e1154a3139daca523118daabdb18c9b0124a6c`.
- Segments recorded there: source-fit [0,400), calibration [400,562),
  replay [562,1125); first anomalous row 562; labelled event [562,956).
- Calibration correction (Aman, scientific-integrity note, retained):
  earlier valve2 runs in `result/valve2/` used calibration [400,574), which
  includes twelve anomalous rows; those results MUST NOT support the corrected
  development comparison. The corrected valve2 calibration is [400,562), ending
  before the first anomalous row. The correction was made after inspecting
  development labels; it is not a held-out or prospectively selected test.
- These values are unverified by Nakul as of Day 5 (valve2 is not yet active);
  they are carried as-is and will be independently verified at Day 6 before use.

## Historical note - superseded held-out statement from the earlier repo manifest

The earlier Reliable-Alerting/manifest.md stated: "No held-out stream was
reserved by name before outcome inspection." That statement is SUPERSEDED and
is NOT the current status. It is retained here only as historical context.

Current authoritative status (this manifest): SKAB/other/21.csv is RESERVED as
the held-out target (see "Held-Out Reservation Status" above), reserved by name
on 2026-09-27, untouched, to be evaluated once at Day 8. Where the earlier repo
manifest and this manifest disagreed on held-out status, THIS manifest governs.
