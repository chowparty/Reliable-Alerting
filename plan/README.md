# Reliable alerting for time-series anomaly detection under changing conditions

## 1. What our research is

We study a deployment question about time-series anomaly detection, not a contest to build the best detector.

Picture a sensor stream, for example vibration readings from a machine or traffic volumes on a server. A detector was fitted months ago on older normal behaviour. Every new window of readings gets one anomaly score, a number where larger means stranger. A decision rule turns that score into behaviour. Over time the stream can change: the machine is run differently, the seasons shift, the workload grows. Then the old scores and old thresholds can drift apart, and a frozen threshold can either cry wolf constantly or go quiet at the wrong moment.

Our research asks whether simple signals available at decision time can choose safer behaviour on later streams. By signals we mean recent scores, recent decisions, and cheap diagnostics such as how spread out or jumpy recent scores look.

Two kinds of behaviour are kept separate throughout. Per-window decision outputs are normal, alert, and defer, where defer means declining to commit on that window. Update behaviours are separate choices about thresholds, such as keeping a fixed cutoff or refreshing it through a cautious rule. All comparisons run on the same scores, so any difference comes from the decision rule, not from a secretly better detector. An optional extension is a small diagnostic that helps tell these situations apart; it is considered only if development evidence supports it.

A defer streak, several deferred windows in a row, is genuinely ambiguous. It could mean a building anomaly, a harmless new regime the detector has never seen, a mismatched calibrator, or just an uncertain detector. Part of the work is reporting which interpretation the diagnostics support on real streams, including the honest answer that they support none clearly. The streak is one open aspect of the study, not an established centre of the method, and there is no established central method until development evidence says so.

## 2. Why this matters

Static thresholds can go stale under chronological change, and every adaptive fix has a failure mode. A rolling threshold can chase its own tail. Deferral can become mass indecision that decides nothing. Alert logic can flicker on and off around a single line. Updates that learn only from windows the policy itself accepted as normal can confirm their own mistakes. A small honest conditional rule, or an honest map of where no rule helps, is more useful than another leaderboard claiming a universal winner.

Negative, null, and inconclusive outcomes are valid results here, and the plans protect them: a stream with no measurable shift is reported as such, never silently replaced with a more flattering one. No novelty is claimed for building a generic detector or for any single classical rule such as a fixed threshold. A candidate distinction under test is the narrow deployment-time choice among alert, defer, fixed, and cautious behaviours under chronological shift. Whether that distinction is novel requires the literature comparison described below, and held-out runs test its empirical usefulness rather than proving novelty by themselves. No conformal or statistical claim is made unless its assumptions are actually met and checked.

## 3. The question and the candidate contribution

The research question, in one sentence: after a detector is fitted on older normal data, can simple decision-time signals choose safer behaviour on later streams, compared against frozen-threshold and standard temporal baselines at honestly reported alert volumes?

The candidate contribution is a small evaluated decision rule plus its failure map: the conditions under which each behaviour looks safer, the diagnostics that identify those conditions, and the places where nothing beats the fixed baseline. If no stable rule emerges, the failure map and the negative result are valuable evidence for the report; whether they amount to a publication contribution depends on the literature comparison and supervisor review. The reference guide enforces the output-versus-update vocabulary with examples.

## 4. How we answer it

The pipeline is deliberately small, and each step depends on the earlier ones, which is why the days run in order.

```
older time ----------------------------------------------------> newer time
 source-fit            calibration            dev replay           held-out
 (learn scores +     (set thresholds +     (choose rules +       (report once,
  scaling, source-    operating points)     operating points,     no retuning)
  normal selection)                          diagnostics)
        |                    |                    |                    |
        v                    v                    v                    v
    loader -> splitter -> scorer -> calibration -> policy -> evaluator
                                configs pin everything; results save every trace
```

A versioned loader fetches a public stream with verified order and records its URL, licence, checksum, order basis, time unit, and timestamp and label fields. A chronological splitter carves the four segments above in time order without shuffling, handling edge windows so no window spans two segments. A deterministic scorer assigns one score per window, with any scaling fitted on source data only. A calibration module holds fixed cutoffs and any rolling update rule behind one interface. A decision module implements the baselines and a defer band only if investigated. An evaluator freezes decisions first, groups alert windows into episodes, and only then joins labels to score events. Configs and saved results pin every seed, threshold trace, and timing number so an independent rerun reproduces them.

Three honesty rules govern the whole run. First, causality: a decision at time t may use only the current score plus thresholds and history frozen before t; anything learned at t applies from t+1 onward. Second, labels: source labels may be used, declared in the manifest, solely to select source-normal windows; development labels may guide development only offline after causal decisions are saved, and never inside the policy at runtime; the held-out target is reserved by name before its outcomes are examined and scored once, where repeating the identical saved config to confirm reproducibility is allowed but no test choice is revised after seeing outcomes. Third, comparison: operating points are chosen on development data, and held-out results report actual alert volume and actual coverage side by side with no retuning to force a match. The reference guide works each of these with numbers.

## 5. Current state: nothing built yet

The verified state is proposals only. No project source code, configs, data manifest, downloaded dataset, or results exist yet. Every implementation path named in these guides is therefore prospective: the team creates it starting Day 1.

The proposed implementation root is `research/`, used consistently across all guides. The suggested reusable shape, not a fixed file list, is: a loader, a chronological splitter, a scorer, a calibration interface, a decision policy, and an evaluator, plus a configs area, a data manifest, a results area, and a report area. Conceptually:

- `research/` — the proposed project root (does not exist yet)
- reusable pipeline pieces for loading, splitting, scoring, calibration, policy, and evaluation
- `configs/` — pinned settings for every run
- `data/manifest.md` — stream URLs, licences, checksums, fields, split positions, reservations
- `results/` — saved scores, thresholds, decisions, and metric tables
- `report/` — the report and slide sources, written from Day 1 alongside the code

No command names or function APIs are prescribed here because no code exists to match them. The team defines those during Day 1 work and keeps them consistent. From Day 1 every piece is reusable: small smoke tests exercise these same real components; there is no separate throwaway prototype. The earlier first-POC note is historical planning context whose falsification questions are reused inside this real pipeline, never scheduled as a disposable build.

All dataset sizes, policy numbers, and scientific settings appearing in guides are illustrative examples until evidence fixes them. Data and settings are undecided. Person-hour budgets and official page/slide counts are not illustrative; they follow the daily plans and the Guidelines. A compact neural scorer of the kind mentioned in the old notes stays optional, not a prerequisite; simple statistical scorers carry the early days, and any learned scorer enters only through the gate described in [Day 7](./day-07.md).

## 6. Day-by-day sequence

Day 1 is Saturday 19 September 2026, the first day of actual execution. Work runs Day 1 through Day 11 (19-29 September), with the mid-semester evaluation on Wednesday 30 September. Each day assumes the previous days' outputs; the team does not skip ahead to held-out data or to report claims the pipeline cannot yet support. Report and slide writing starts early and continues inside the daily effort, not in a final rush.

- Day 1: onboarding plus a reusable thin integrated smoke test on synthetic or toy input; eligible-data metadata review and held-out reservation recorded in the manifest; report outline started.
- Day 2: one real development stream integrated end to end through the frozen interfaces; held-out stays sealed.
- Day 3: evaluator hardened with hand-checkable cases; first fixed-versus-rolling comparison on development data.
- Day 4: simple temporal baselines (consecutive, M-of-N, hysteresis alongside fixed and rolling) on development data.
- Day 5: diagnostic questions examined against explicit hypotheses; a conditional candidate rule is considered but only adopted if justified.
- Day 6: second development stream if feasible; candidate behaviour and operating points provisionally selected on development evidence, with the final freeze on Day 7.
- Day 7: ablations; a tightly gated learned scorer only if development evidence earns it and as an exception (default: no learned scorer).
- Day 8: full freeze and audit; the single held-out run only if the audit passes; full report draft and slide deck.
- Day 9: independent rerun from a clean state plus supervisor report review and corrections; no new held-out selection or retuning after seeing held-out outcomes.
- Day 10: signatures, printing, and binding preparation.
- Day 11: buffer and rehearsal.

The dependency order kept from the older long-horizon timeline is: interfaces and reservation before streams, streams before evaluator trust, evaluator before baseline comparisons, baselines before diagnostics and any candidate, development evidence before any learned scorer, everything before the audit, the audit before the held-out run and review. The old timeline's calendar dates are not the schedule; only this dependency order carries over.

## 7. Effort and ownership

Three teammates, Aman, Nakul, and Pratyush, each contribute about three focused hours per day including collaboration, across the eleven days, totalling roughly 99 person-hours over 19-29 September with a short joint review inside each day. Aman and Pratyush carry most of the implementation, alternating loader, scorer, decision logic, and the reproducibility rerun so neither becomes a single point of failure. Nakul owns dataset verification, metric correctness, diagnostics, leakage and audit work, and the literature thread. Report and slide effort sits inside these assignments from the start.

## 8. September evaluation versus the long horizon

September's Phase-I mid-semester evaluation is distinct from the later Phase-II project evaluation. For September, the team presents for ten minutes with ten to fifteen slides, answers questions, and hands in one spiral-bound ten-to-fifteen-page supervisor-signed group report, submitted in the classroom before the viva. The required report sections are front page, table of contents, introduction, motivation, literature survey, problem statement, objective and methodology, simulation platform and requirements, conclusion, and references. A credible showing means a chronological run on at least one real stream with frozen interfaces, a result book comparing the baseline behaviours with actual alert volume and coverage reported, any deferral analysis actually investigated with diagnostics, and a report that already carries real figures. Saved runs carry the figures; any live demo is optional and never load-bearing. Normal report review and signature preparation is part of the plan. See the [Guidelines for Report](../Guidelines%20for%20Report.md).

The team's longer target is at least 80 marks in Phase-II, read directly from the [Phase-II criteria](../tech-project-phase-ii-evaluation-criteria.md) rather than promised here. The criteria overlap by construction: 81-100 requires one paper with a student as first author accepted or published in an SCI / SCI Expanded / Scopus-indexed / UGC-CARE journal plus viva performance; 72-89 requires one full-length paper with a student as first author accepted or published in a peer-reviewed Scopus-indexed conference, or registration of a start-up, plus viva performance; below 72 rests on viva performance. Submission is not acceptance, and acceptance timing is not guaranteed; interpretation and publication route are confirmed with the supervisor early through the normal review process. No mark is promised here.

Beyond September the work continues as an experiment framework, not an automatic paper:

```
reuse pipeline -> broaden eligible dev + untouched stream set, freeze claims
  -> validate uncertainty per stream, not iid windows
  -> manuscript + supervisor review
  -> qualifying-venue submission distinct from revisions/acceptance
```

September evidence is limited (one or two development streams plus one held-out run) rather than a full study. Broadening, including any justified learned scorers, comes later on that evidence. Literature distinctiveness and a feasible review lead time are pursued early toward 80, with no guaranteed calendar or venue invented here.

## 9. Literature and related reading

Primary academic evidence and citations come strictly from the seven allowed platforms: IEEE Xplore, ACM Digital Library, SpringerLink, ScienceDirect/Elsevier, NeurIPS Proceedings, PMLR (including ICML and AISTATS), and the ACL Anthology. Papers elsewhere are discovery background only. The team reuses the existing paper ledger rather than re-deriving it, and verifies paper-level details against the allowed platforms before repeating any claim. Additional discovery leads (Hydra, Choose Wisely, MSAD-style selector benchmarks) are pending verification, not established findings. A scan entry marked unknown or silent about a feature leaves the question open for direct checking. Gap claims from the scan are not inherited as findings; each claim the report needs is rechecked against the source. No broad rediscovery is scheduled; only small targeted verification needed for a claim is done.

Related history for locating old notes: this direction was labelled C01 in the earlier scan. Start from the [paper ledger](../btech-ai-research-topic-scan/02-paper-ledger.md), then the [final recommendation](../btech-ai-research-topic-scan/10-final-recommendation.md), the [first-POC note](../btech-ai-research-topic-scan/11-first-poc-plan.md) as planning context, and the [long-horizon timeline](../btech-ai-research-topic-scan/12-project-and-publication-timeline.md) for dependency order.

## 10. Where to go next

Start with the [shared reference](./reference.md), then work [Day 1](./day-01.md) through [Day 11](./day-11.md) in order ([Day 2](./day-02.md), [Day 3](./day-03.md), [Day 4](./day-04.md), [Day 5](./day-05.md), [Day 6](./day-06.md), [Day 7](./day-07.md), [Day 8](./day-08.md), [Day 9](./day-09.md), [Day 10](./day-10.md)) and the [evaluation day](./evaluation-day.md); this README states the question, the honesty rules, and the schedule those files follow.
