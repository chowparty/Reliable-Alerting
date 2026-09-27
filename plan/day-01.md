# Day 1, Saturday 19 September: onboarding, shared interfaces, and the first thin smoke run

Our research studies reliable alerting for time-series anomaly detection when streams change after the detector was fitted. The team starts with no code, no data, and no results. Everything built today is reusable: the same loader, splitter, scorer, calibration, policy, and writer carry forward into Days 2–4. The closing smoke test runs those real modules on synthetic input. There is no disposable prototype. The proposed `research/` root is prospective and does not exist yet; today creates its first thin path.

## Starting from zero knowledge

Nobody is expected to have read the full tutorial in advance. The opening joint session walks through the plan README and the shared reference at a pace newcomers can follow. 

Three overrides from that old note apply from today. There is no required neural scorer; simple statistical scorers carry the early days. Streams are never chosen because their measured shift looks convenient. And coverage is never forced to match by retuning.

## The first 30 minutes together

About thirty minutes open the day as a joint session: guided walkthrough, then agreement on module boundaries and the data contract. The group settles what each module consumes and produces, which config fields pin a run, what the manifest records, and where the report source lives.

The data contract is minimal so independent work can start the same afternoon. Trace rows carry a window identifier, the window end index, the score, the output state, and the threshold that judged it, plus config and run identifiers. Raw labels travel on a separate path that only the evaluator reads. After this session nobody edits the same module in parallel.

```
config + synthetic input --> loader --> splitter --> scorer
      --> fixed calibration --> fixed policy --> writer
      --> saved traces + config copy
```

## Define the score pipeline: loader, splitter, scorer

Aman owns the versioned loader, the chronological splitter, and the deterministic scorer. The splitter enforces the edge-window rule and causal missing-value handling. The scorer fits any scaling on source data only. He records the minimal reproducible environment: Python version, dependency list, and machine name saved beside the run. For the report he drafts the methods sentences.

## Turn scores into a trace: calibration, policy, writer

Pratyush owns the fixed-calibration holder with a source-fitted quantile, the fixed-threshold policy, and the results writer. He wires the full smoke path and saves the exact command as executed alongside the traces and config copy, so a rerun reproduces the same rows. He drafts the first score figure. No rolling logic and no extra rules today. He also ensures the report outline covers the required sections with links to the Guidelines.

## Verify data entry: eligibility, manifest, metrics, literature

Nakul owns eligibility checking and is the manifest's sole editor. He records the development candidate and, where feasible, the reserved held-out stream or tail by name before outcomes are seen, with URL, licence, order basis, time unit, and field semantics. Order may come from timestamps or a documented ordered index.

He audits the smoke run for label discipline and confirms every number names its config. He spends roughly twenty to thirty minutes starting the literature thread, which totals 60–90 minutes across Days 1–3, reusing the paper ledger and verifying claims only on the seven allowed platforms. Selector leads such as Hydra, Choose Wisely, and MSAD-style benchmarks stay marked as pending discovery where unverified. For the report he drafts the literature-survey seed and the metrics notes.

## Decisions frozen today

Source labels may be used, declared in the manifest, solely to select source-normal windows. They never enter the scorer or policy, and development labels only meet frozen decisions offline. Each decision is made at window end from the current score plus thresholds and history frozen before it. Anything learned applies from the next window onward. New vocabulary (outputs versus controller actions, decision coverage) follows the reference and is not redefined here.

Deferral is not a required method; an exploratory static band may come later. Config is minimal: score source, window length, stride, scaling scope, gap policy, segment conventions, and the baseline field, each with a one-sentence reason. The day fits 30 minutes together plus about 120 minutes solo plus 30 minutes handoff inside the three-hour budget.

A short supervisor note, coordinated by Nakul after the technical manifest is set, requests a review window around 26–27 September and asks early about signature, printing, and binding procedure and turnaround, plus general clarification of the Phase-II publication route and marks interpretation. No mark is promised.

## Evening outputs and checks

The day closes with about thirty minutes of handoff inside the three-hour budget. The smoke path reruns from a clean state with identical trace length and boundary handling. The manifest holds the reservation or notes that it freezes on Day 2 before outcomes. The report source carries its outline in the required sections plus the first methods, metrics, and figure seeds.

## If setup runs slow

The fallback drops the real-loader polish, the missing-value refinements, and the optional plot, and moves calibration polish to Day 2. The loader, splitter, scorer, fixed calibration, fixed policy, and writer on synthetic input are preserved because a thin runnable pipeline outranks breadth.

## Navigation

Previous: [README](./README.md) and [shared reference](./reference.md). Next: [Day 2](./day-02.md).
