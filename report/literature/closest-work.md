# Closest work — the "isn't this just X?" defense

**Prepared:** 2026-09-29 (Asia/Kolkata). **Cutoff:** 29 September 2026. **Author of this file:** literature slice, P2-finish.

This is the backbone for the viva defense of our direction. Read the scoping first,
then the per-threat rows, then the component table, then the synthesis. Every claim
about a paper is tied to an official record on one of the seven allowlisted platforms
(IEEE Xplore, ACM DL, SpringerLink, ScienceDirect, NeurIPS Proceedings, PMLR, ACL
Anthology). Where the official full text was blocked, the row says so and does **not**
infer that a feature is absent.

## What "ours" is (judge every overlap against exactly this)

A **decision-time action policy on a common score trace.** One fixed, source-fit
anomaly scorer (mean distance on the univariate `Current` channel, window 4 / stride 4)
produces **one score per window** on SKAB dev streams `valve1/0.csv` and `valve2/0.csv`,
with chronological source-fit / calibration / replay splits. At each window end a policy
chooses exactly one of four actions using only information available at that time:

- **alert** — raise an alert for this window;
- **hold** — no alert, keep the current threshold;
- **defer** — withhold the decision (counted against **decision coverage**);
- **recalibrate** — refresh the threshold from recent **label-free** data.

Every policy — fixed, rolling, k-consecutive, m-of-n, hysteresis, and the proposed
guarded controller — is compared on the **identical score trace**. Because the scores
are frozen, ranking/accuracy measures such as VUS-PR are identical across policies by
construction, so any measured difference is attributable to the **policy**, not the
scorer. Results report **alert workload** (episodes per 1,000 decisions, alert
duration), **decision coverage**, **delay**, and **event recall** separately, with
labels joined **offline only**.

**Measured status (be honest in the viva):** five baseline policies run on two dev
streams with one labelled event each; the **defer/recalibrate controller is PROPOSED,
not implemented**; there is **no held-out result** yet.

The five ingredients an objector will attack: **(A)** the four-action policy
(alert/hold/defer/recalibrate); **(B)** the single common frozen score trace shared by
all policies; **(C)** workload + coverage reporting alongside event recall/delay;
**(D)** the chronological source-fit / calibration / replay split; **(E)** label-free
runtime (labels joined offline only).

---

## Adversarial threat rows

Each row: official citation and access; one-sentence summary; **exact overlap** (which
of A–E it touches); **exact difference**; a **viva line** the student can say aloud; and
the **discriminating experiment** that separates us or shows we are subsumed.

### 1. DDADE — Yang et al., *KBS* 337:115380 (2026), DOI `10.1016/j.knosys.2026.115380`
- **Access:** official ScienceDirect PII `S0950705126001231` (DOI 302-verified to linkinghub.elsevier.com); Crossref-confirmed authors/venue/date. **Abstract + previously indexed section snippets only** — the PII page returned HTTP 400 in this runtime, so no full-text method section was read. Do not infer feature absence from the block.
- **Summary:** a generalizable anomaly-detection framework that uses real-time Mahalanobis drift monitoring plus a diffusion-enhanced anomaly branch; drift results trigger incremental learning or dynamic threshold adjustment for non-stationary industrial series.
- **Overlap:** touches **(A) recalibrate** (drift-triggered threshold adjustment) and, loosely, **(E)** label-free drift monitoring.
- **Difference:** DDADE adapts **detector/model state** (incremental learning + a generative branch); it is not a fixed scorer with a separate causal action policy, has no **defer** action, no shared frozen score trace **(B)**, and no workload/coverage episode budget **(C)** in the checked material.
- **Viva line:** "DDADE changes the detector when it sees drift; we freeze one scorer and change only the *action* at window end, so any difference we report is the policy's, not a new model's."
- **Discriminating experiment:** run DDADE's drift-triggered threshold update as one *recalibrate policy* on **our** frozen `Current` score trace and compare episodes-per-1,000 and coverage against the guarded controller. If DDADE's gate matches the guarded controller at equal workload, we are largely subsumed on (A/E); if it over-alerts under contaminated calibration, our contamination guard is the separation.

### 2. ADAPTS — Li et al., *KBS* 350:116530 (2026), DOI `10.1016/j.knosys.2026.116530`
- **Access:** official ScienceDirect PII `S0950705126012566`; Crossref-confirmed. Record marks Open Access/CC (variant not surfaced). **Abstract + indexed Section-3 module snippets only**; PDF blocked in this runtime.
- **Summary:** unsupervised drift-aware streaming AD that classifies sudden / incremental / recurrent drift and applies drift-specific retraining, controlled fine-tuning, or model reuse from a bounded model pool; stable periods use lightweight updates.
- **Overlap:** touches **(A) recalibrate / hold** in spirit (adapt on drift, stay quiet when stable) and **(E)** label-free drift detection.
- **Difference:** the adaptation object is again the **model/detector** (a pool of reusable models), not a fixed-scorer action policy; no **defer**, no shared score trace **(B)**, no workload/coverage episode contract **(C)**.
- **Viva line:** "ADAPTS decides *which model to reuse* on drift; we decide *whether to alert, hold, defer, or recalibrate* on one fixed score, and we never swap the scorer."
- **Discriminating experiment:** freeze our scorer; expose ADAPTS's "stable-period = lightweight update" rule as a *hold/recalibrate* baseline policy and compare coverage and false-alert workload on the SKAB replay split. Separation shows up as our **defer** action reducing false alerts at matched recall — an action ADAPTS does not have.

### 3. CDDIA — Xu et al., *IEEE Trans. Sustainable Computing* 9(6):913-924 (2024), DOI `10.1109/TSUSC.2024.3386667`
- **Access:** official IEEE abstract + metadata (pp. 913-924). **Abstract-only**; full PDF not retrieved.
- **Summary:** detects concept drift in *normal* data without labels, interprets drift samples with search-optimization + SHAP, filters new/old samples, and retrains the anomaly model to cut false positives; five baselines, three datasets.
- **Overlap:** **(A) recalibrate** (guarded retraining) + **(E)** label-free drift detection.
- **Difference:** interpretation-driven **retraining of the detector**, not a decision-time action selector; no **defer**, no frozen shared score trace **(B)**, no episode/workload budget **(C)**; IoT retraining rather than SKAB fault episodes.
- **Viva line:** "CDDIA retrains the detector after interpreting drift; we keep the detector fixed and only gate the action, so our comparison isolates policy from model."
- **Discriminating experiment:** cast CDDIA's "drift-then-retrain" as a recalibrate-heavy policy on our trace; measure whether its false-positive reduction survives when the scorer cannot be retrained. If it needs retraining to win, it does not compete on our fixed-scorer contract.

### 4. Sun et al. — *Online Adaptive Anomaly Thresholding with Confidence Sequences*, PMLR 235:47105-47132 (ICML 2024), `pmlr-v235-sun24h`
- **Access:** official PMLR record + PDF; local full text (`research/results/day05-literature/sun24h.txt`), **§§2.1-2.5, 5.1, 6-8 read**.
- **Summary:** models scores as piecewise-stationary independent streams, defines anomalies against a known quantile, and outputs `{0,1,abstain}` with confidence-sequence guarantees on FP/FN and shift-dependent bounds.
- **Overlap:** the **strongest** single threat to **(A) defer/abstain** + adaptive thresholding + **(E)** label-free operation. It genuinely has an abstain action and online threshold adaptation.
- **Difference:** Sun's **abstain = uncertainty about the quantile decision** on an i.i.d. piecewise-stationary score stream; ours is a **temporal defer** measured against **decision coverage** with event delay/recall and **workload episodes (C)**. Sun assumes a known quantile and independence; SKAB `Current` is autocorrelated and label-free at runtime. No SKAB fault-episode or workload reporting.
- **Viva line:** "Sun abstains when it is statistically unsure of the *threshold*; we defer as an *operational* action and charge it to decision coverage, then report the alert workload it saves — Sun reports neither coverage nor episodes."
- **Discriminating experiment:** run Sun's confidence-sequence thresholding as a policy on our frozen trace; compare its abstain rate and FP/FN against our defer coverage and episodes-per-1,000 at matched event recall. If Sun's abstain already achieves our workload/coverage tradeoff on SKAB, our (A) novelty collapses to "operational framing"; if its i.i.d. assumption breaks on autocorrelated `Current`, that is our separation.

### 5. Perini & Davis — *Unsupervised Anomaly Detection with Rejection*, NeurIPS 36 (2023), DOI `10.52202/075280-3052`
- **Access:** official NeurIPS record + PDF; **§§1-2 + contribution/eval claims read**.
- **Summary:** label-free rejection using a **constant** threshold on the ExCeeD stability metric, with estimated rejection rate and a theoretical upper bound on rejection rate and expected prediction cost; output is normal / anomaly / **reject**.
- **Overlap:** direct threat to **(A) defer/abstain** + **(E)** label-free abstention with a cost view.
- **Difference:** a **static** reject region on a stability metric for one detector's decisions; no **temporal** defer, no **recalibrate**, no shifting regime, no shared frozen score trace across competing policies **(B)**, no event episodes / delay / workload **(C)**.
- **Viva line:** "Perini & Davis reject uncertain points with a fixed rule and bound the cost; we add a *temporal* defer and a *recalibrate* action and score them by alert workload and coverage over time, which a static reject region does not address."
- **Discriminating experiment:** implement their constant-stability reject as a *defer* baseline on our trace; check whether a static reject region matches the guarded controller's coverage/workload under **drift**. Their bound assumes a stable operating point — drift is the separation.

### 6. SEAD — Shah et al., *Unsupervised Ensemble of Streaming Anomaly Detectors*, PMLR 267:54167-54185 (ICML 2025), `pmlr-v267-shah25c`
- **Access:** official PMLR record + PDF **now reachable (HTTP 200)**; **cached** at `report-work/literature/pdf-cache/shah25c-sead.pdf` (SHA-256 `7b71...cbdf`, 19 pp). **§2 problem setting, Algorithm 1, §5 related work read.**
- **Summary:** the first online model-selection algorithm for streaming unsupervised AD; classical **multiplicative weights** weight base detectors, minimizing anomaly score as an unsupervised proxy for Averaged-Precision (labels never revealed); O(1) per point; adaptive to non-stationarity.
- **Overlap:** strongest threat to **(E) label-free selection** under drift, and to any "we select at runtime without labels" claim.
- **Difference:** SEAD selects among **base detectors** and **emits its own weighted-combination score** — so the score is **not held fixed** across the compared methods, which is the opposite of our **(B)**. It has no **defer** action, no **recalibrate** of a threshold, and no workload/coverage episode budget **(C)**; it selects *models*, we select *policies* on one frozen trace.
- **Viva line:** "SEAD picks the best *detector* and changes the score in doing so; we hold one score fixed and pick the best *action policy*, so our ranking metric is identical across policies and only the policy can move it."
- **Discriminating experiment:** the cleanest separation — SEAD cannot even enter our arena without changing the score, so run it as a *scorer* upstream, then apply all our policies on **its** frozen output. Our contribution is the policy layer that SEAD lacks; if SEAD's own thresholding matches the guarded controller on episodes/coverage, (A) is weakened.

### 7. Dynamic-XY — Bhukar et al., *Dynamic Alert Suppression Policy for Noise Reduction in AIOps*, ICSE-SEIP 2024, DOI `10.1145/3639477.3639752`
- **Access:** official IEEE record; **abstract-only** (CC PDF stamp URL not retrieved).
- **Summary:** learns an unsupervised moving-average-envelope **alert-suppression policy** from historical alerts/events and applies it at runtime to reduce alert noise on log and metric datasets.
- **Overlap:** the closest thing to **(A) hold/suppress** + **(C) workload reduction** + **(E) label-free policy** in the operational-alerting literature.
- **Difference:** it is an **AIOps alert-suppression** policy learned from *historical alert streams*, not a TSAD **score-trace** action policy; the checked abstract shows no **defer** semantics, no **recalibrate**, no chronology-safe calibration split **(D)**, and no common frozen score trace **(B)**. Its input is alerts, ours is a score per window.
- **Viva line:** "Dynamic-XY suppresses noisy alerts learned from past *alerts*; we act on a *score trace* with four explicit actions and a chronological calibration split, and we report coverage, not just suppression."
- **Discriminating experiment:** treat Dynamic-XY's envelope suppression as a *hold* baseline on our episodes; compare alert-duration and episodes-per-1,000 against the guarded controller at equal event recall. If envelope suppression matches us, our workload contribution is incremental; our **defer** + **recalibrate** actions and label-free calibration split are the remaining separation.

### 8. Hu — *A deployment-oriented framework for evaluating streaming integrity alerting under workload constraints*, *ESWA* 333:134305, DOI `10.1016/j.eswa.2026.134305`
- **Access:** official ScienceDirect PII `S0957417426032112`; Crossref-confirmed **in-press / online-first** (DOI year 2026, print 2027-01, created 2026-09-05); publisher page 403. **Abstract/highlights only**; SSRN preprint is discovery-only, not the publisher version.
- **Summary:** an **evaluation framework** whose object is the realized score-to-warning-to-episode stream — paired clean/corrupted replay, matched-burden timeliness, episode-budget and time-in-warning constraints, regime-sliced workload audits, parity-preserving adaptive thresholds, online recalibration.
- **Overlap:** the **strongest threat to (C)** — it already makes alert episodes and workload contracts the object of evaluation, matches burden, and studies online recalibration under non-stationarity. It also touches **(D)** (regime slices) and **(A) recalibrate**.
- **Difference:** it **evaluates detectors/configurations under workload contracts**; from the checked text it does **not** supply our label-free **action/policy selector** (the four-action controller **(A)**) or the single frozen common score trace shared across *policies* **(B)**. It is the measuring stick, not the controller.
- **Viva line:** "Hu gives the *scoreboard* for workload-matched alerting; we bring a *player* — a four-action label-free policy — and we borrow the scoreboard idea to score it. We do not claim workload evaluation itself as new."
- **Discriminating experiment:** adopt Hu's episode-budget / time-in-warning contract as **our** reporting frame and show the guarded controller moving along the feasible frontier that fixed/rolling policies cannot reach on the *same* frozen trace. If Hu already reports a policy selector that dominates ours, we are subsumed; if Hu only ranks detectors/thresholds, the policy layer is ours. **Resolve Hu's publication status before citing.**

### 9. FITNESS — Sankararaman et al., *Online Anomaly Detection in Streams with Drift and Outliers*, PMLR 162 (ICML 2022), `pmlr-v162-sankararaman22a` — added at Gate A (front desk, 2026-09-29)
- **Access:** official PMLR PDF (25 pp.), cached `pdf-cache/sankararaman22a-fitness.pdf`, SHA-256 `3f005bc0d28aede4b03a14c34c1e95c3e5b540db2164478c698727c883e0a8d5`. **§1.1 desiderata, §2 related work, §5.2–5.3 (Prop. 5.5, Remark 5.6) read.**
- **Summary:** formalizes online unsupervised AD under drift plus bounded corruptions as sequential estimation; the fix is to fine-tune the detector only on recent, *similar* samples, with regret bounds for Gaussian streams.
- **Exact quote that matters (p. 3, §2):** "MEMSTREAM discards a sample if it is predicted as an anomaly at the time of scoring … such techniques can fail to distinguish between anomalies and abrupt changes." §5.3 gives a formal buffer version ("only points not marked as anomalies at their time of arrival are added into the buffer").
- **Overlap:** **this is the prior statement of the self-referential-admission failure** that our rolling baseline exhibits, and of the adaptivity–robustness trade-off we build on. Touches **(A) recalibrate**, **(E)**.
- **Difference:** FITNESS adapts the **scorer** (mean/model estimation) by similarity-based admission and proves regret; it has no alert/hold/defer action set, no threshold-level guard anchored to frozen calibration evidence, no common score trace across policies **(B)**, no workload/coverage reporting **(C)**. Our monotone-ratchet proposition is specific to nearest-rank quantile thresholds with decision-gated admission.
- **Viva line:** "FITNESS already showed that learning only from points you called normal fails under abrupt change — we cite it for that. We show that for quantile alert thresholds the failure is a deterministic one-way ratchet, and we test an anchored, admission-separated recalibration *action* against it on one frozen score trace."
- **Self-referential admission / defer-feeds-adaptation check (asked at Gate A):** FITNESS — rejects self-referential admission, no defer state. Sun 2024 — admits every sample (Def. 2.2 treats the current quantile as normal), abstain does not feed adaptation. Perini & Davis — static reject, no adaptation. DDADE/ADAPTS/CDDIA — drift detector gates model adaptation; checked text abstract-only, admission set not verifiable. SEAD — weights detectors on all points. Hu — evaluation only. Dynamic-XY — learned from historical alerts.
- **Related, named only:** MemStream, Bhatia et al., *Proc. ACM Web Conference 2022*, pp. 610–621, DOI `10.1145/3485447.3512221` (ACM DL; Crossref-verified metadata, full text not read) — the method FITNESS criticizes.

### Neighbours worth naming (not in the core eight)

- **Xu & Boström**, *Conformalized TS Anomaly Thresholding with Latent Space Features*, PMLR 329:676-688 (2026) — calibration-only leakage-safe thresholding; occupies **(D)**-adjacent leakage safety, but is a *scorer/threshold*, not an action policy. Full text read (base B03).
- **Hennhöfer, Kirsch & Preisach**, *Conformal Anomaly Detection ... with nonconform*, PMLR 329:613-632 (2026) — converts scores to calibrated p-values + FDR control; same volume as Xu. Occupies the "move beyond heuristic thresholds" framing our fixed empirical-quantile threshold sits in, but has no defer/recalibrate/policy replay. Abstract-only.
- **CODiT (conf.)** ACM ICCPS 2023 `10.1145/3576841.3585931` and **CODiT (journal)** ACM TCPS 8(4):1-27 (2024) `10.1145/3648005` — conformal temporal-OOD detection with bounded false-alarm guarantees; a candidate **defer/OOD-gate** baseline, but OOD detection for CPS, not TSAD fault-episode policy. **ACM 403; abstract/Crossref only** (journal section detail seen only via non-official Paperity preview — verify before use). The "Sethi 2023" attribution in the source brief is **wrong**: this DOI is **Kaur et al., CODiT**.
- **Sankararaman et al.** FITNESS, PMLR 162 (2022); **Rebjock et al.** online-FDR, NeurIPS 2021; **Nguyen et al.** D3M, NeurIPS 2025 — occupy contamination-safe online adaptation, precision/FDR control, and label-free deterioration monitoring respectively (see proceedings-notes.md). None is a four-action policy on a frozen shared trace.
- **VUS / VUS-PR** — Boniol et al., *The VLDB Journal* 34:32 (2025) `10.1007/s00778-025-00907-x`, and Liu & Paparrizos TSB-AD (NeurIPS 2024) — the evidence that ranking metrics are functions of the score trace, which is *why* our identical-trace design forces any difference to be the policy's.
- **Altay**, *Response inertia in sequential detection*, *KBS* 351:116716 — **the single most dangerous framing collision** (a common causal evidence stream + policy-level selective temporal adaptation + delay/stability metrics). **Published 2026-10 (issue 9 Oct 2026), AFTER our 29 Sep 2026 cutoff**; not citable as prior published work at Phase-I. Recheck after 2026-10-09; do not cite the SSRN preprint or the future issue as an existing threat.

---

## Component-occupation table (reuse in the report)

For each of our five components, which threats already occupy it and how strong the
occupation is. "Occupied" = a checked paper does essentially this; "adjacent" = does a
close cousin; "open" = not found in the papers checked.

| Our component | Occupied by | Adjacent | Occupation strength | Not found in the N checked |
|---|---|---|---|---|
| **A. alert action** | all detectors (trivially) | — | fully occupied (not novel alone) | — |
| **A. hold action** | Dynamic-XY (suppress), ADAPTS (stable-period quiet) | DDADE, CDDIA | occupied | — |
| **A. defer / abstain action** | Sun 2024 (`abstain`), Perini & Davis (`reject`) | CODiT (OOD gate) | **strongly occupied as a concept**; temporal-defer-as-coverage is adjacent, not identical | temporal defer charged to *decision coverage* alongside episodes |
| **A. recalibrate action** | DDADE, ADAPTS, CDDIA, Hu (online recalibration) | Sun 2024 (adaptive threshold) | **strongly occupied** (as detector/threshold adaptation) | recalibrate as one *action among four* on a frozen scorer with a contamination guard |
| **B. common frozen score trace across policies** | — | VUS/TSB-AD (metrics are score-trace functions) | **open** — SEAD, ADAPTS, DDADE, CDDIA all change the score/model | comparing *policies* on one identical trace so ranking metrics cannot differ |
| **C. workload + coverage reporting** | Hu (episode budget, time-in-warning), Rebjock (FDR), Dynamic-XY (noise reduction) | Perini & Davis (cost bound) | **strongly occupied** (esp. Hu) | workload + coverage + delay + recall reported *per policy on the shared trace* |
| **D. chronological source-fit/calib/replay split** | Wild-Time (protocol), Xu (calib-only), Hu (regime slices) | Liu et al. 2023 (persistence) | occupied as protocol hygiene | the specific source-fit → calibration → replay split on SKAB dev streams |
| **E. label-free runtime (labels offline only)** | SEAD, Sun, Perini & Davis, ADAPTS, CDDIA, D3M | most unsupervised TSAD | **fully occupied** (not novel alone) | — |

Blunt reading of the table: **A-alert, A-hold, A-recalibrate, C, and E are each already
occupied**; **A-defer is occupied as a concept** (Sun, Perini & Davis). The **only cell
that is open in the papers we checked is B** — nobody holds one score fixed and competes
*action policies* on it — and the **specific bundling** of a four-action controller +
frozen shared trace + workload/coverage/delay reporting + label-free calibration split.

---

## Synthesis

**Components already occupied (blunt):** alerting, holding/suppression, label-free
operation, and workload/coverage evaluation are not ours to claim — Dynamic-XY suppresses
alerts label-free, Hu already makes workload contracts and online recalibration the object
of evaluation, and SEAD already selects label-free under drift. Abstention is occupied as
a concept by Sun 2024 (statistical `abstain`) and Perini & Davis (cost-bounded `reject`),
and threshold/model recalibration under drift is occupied four times over (DDADE, ADAPTS,
CDDIA, Hu). A report that pitches "adaptive, label-free anomaly alerting" as new is wrong
and will be broken in the viva.

**The combination not found in the papers we checked:** across the 8 core threats and the
named neighbours (roughly 20 records examined on the allowlisted platforms plus the base
inventory), we did not find a method that holds **one fixed score trace** constant and
compares **causal end-of-window action policies** — alert / hold / defer / recalibrate —
on that identical trace, with **defer charged to decision coverage** and **alert workload,
coverage, delay and event recall reported separately** under a **chronological source-fit /
calibration / replay** split and **labels joined offline only**. Every close method either
changes the scorer/model (SEAD, ADAPTS, DDADE, CDDIA), abstains statically or on a
statistical quantile (Perini & Davis, Sun), or evaluates rather than controls (Hu, VUS).
This is a **search result, not a proof of absence.**

**The strongest remaining "this is just X" objection, and the honest answer:** the
strongest objection is *"this is just Sun 2024 / Perini & Davis with an operational
relabelling — abstain becomes defer, and you added a recalibrate action that DDADE/Hu
already do."* The honest answer: the abstain/reject prior work is on i.i.d. or stable
score streams and reports FP/FN or a cost bound, **not** decision coverage, episode
workload and delay under drift; and the recalibrate prior work adapts the **detector or
threshold as model state**, whereas ours is one **action among four on a frozen scorer**,
which is what makes the comparison attributable to the policy. If, on SKAB, Sun's abstain
plus a simple recalibrate baseline matches our guarded controller at equal workload and
coverage, we are honestly subsumed and should say so — that is exactly the discriminating
experiment in rows 4, 5 and 8.

## Gate A amendment (front desk, 2026-09-29)

FITNESS (row 9) moves the self-referential-admission failure into the **occupied** column: we do not claim
the phenomenon or the adaptivity–robustness trade-off. What remains, among the nine threats checked, is the
threshold-level specifics: the monotone-ratchet proposition for decision-gated quantile thresholds, an
anchored and admission-separated recalibration *action* with explicit deferral inside a four-action policy,
and its attribution on one common score trace with workload and coverage reported. Use the amended
sentence below; the original is kept for the audit trail.

> **Amended honest-scope sentence (use this one).** Among the nine closest methods we checked on the seven
> allowlisted platforms, abstention, drift-triggered recalibration, label-free selection, workload-matched
> evaluation and the failure of learning only from self-declared normal points (FITNESS) are each already
> published; what we did not find, in the papers we checked, is recalibration treated as a guarded
> decision-time action whose training data is chosen neither by the threshold being updated nor
> unconditionally, compared with alternatives on one fixed score trace with alert workload, decision
> coverage, delay and event recall reported separately — a bounded search result, not a claim that no such
> method exists.

## Honest-scope sentence (reuse verbatim in the report and viva)

> Across the eight closest methods and named neighbours we examined on IEEE Xplore, the
> ACM Digital Library, SpringerLink, ScienceDirect, NeurIPS Proceedings, PMLR and the ACL
> Anthology, we did not find — **among the papers we checked** — a method that compares
> causal alert / hold / defer / recalibrate action policies on a single fixed anomaly-score
> trace with decision coverage, alert workload, delay and event recall reported separately
> under a chronological, label-free calibration split; the abstention, recalibration,
> label-free-selection and workload-evaluation components are each individually occupied by
> prior work, so our contribution, if it holds, is the specific policy-layer combination and
> its attribution, not any single ingredient — and this is a bounded search result, not a
> claim that no such method exists.
