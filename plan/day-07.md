# Day 7, Friday 25 September: ablate what exists, then freeze

Day 7 stops growth and starts proof. Whatever is actually implemented by this morning — the five baselines plus at most the small Day 5–6 candidate — gets ablated on development data, and every choice the held-out run needs is frozen. No new policy family enters after today. The day runs about three focused hours per person: twenty minutes together to open, about 130 minutes solo including some thirty minutes of report writing each, and thirty minutes of joint review.

## Where Day 7 begins

The opening starts from exact existing runs: the Day 6 development results with their saved configs and the commands recorded alongside them. The group confirms which policies are truly implemented and runnable, then agrees the ablation list — each item differing from its control in exactly one declared element. Anything not implemented is not ablated; its absence is recorded rather than improvised around.

## Subtract one thing at a time

Aman carries the ablation runs. He tests only what applies: frozen calibration against the conservative rolling update where a rolling rule was actually implemented, defer band on against full-decision no-defer where a band was actually implemented, and at most a narrow pair of settings checks such as a shorter against longer calibration block. Prior update rules and any admission discipline stay fixed as declared before the run; the optional admission variant runs only if it was predeclared. Each run saves per-window decisions, threshold traces, and config copies in the continuing results area on identical scores, reporting actual alert volume and coverage. New branches, features, or thresholds invented to rescue a weak row are out of scope.

Nakul turns the traces into the fair comparison. Every ablation row reports false-alert episodes, event recall and episode precision with denominators and undefined-with-counts where denominators are zero, detection delay with misses counted separately, deferral and decision coverage, alerted-window fraction, episode rate, and timing, with the optional volume-under-surface description kept scorer-level only on identical scores and never used to select an operating point. He consolidates the rows into the failure summary, marking each cell by the strength of its support and stating that narrow development evidence cannot establish general regimes. Pratyush records cost and stability beside the same rows and adds the ablation figures and failure-summary section to the existing `research/report/` source, with Aman extending methods and Nakul the metrics notes inside their solo writing time.

## The scorer gate stays shut by default

The default is clear: no unvalidated scorer is frozen. A learned scorer gets at most a narrow pilot beyond the core ablation work, and only if the Day 6 gate was affirmatively passed with its concrete sensitivity reason, stable pipeline and evaluation setup, and budget intact. Even then it must earn its place through scorer-comparison metrics on the same development data, stable development validation, and documented cost — and the pilot reuses the same policy definitions with thresholds recalibrated per scorer from allowed calibration data under dev-only selection, never raw thresholds copied across different score distributions. If any condition fails, the scorer stays future research beyond September and the deterministic scorer remains the frozen evaluation vehicle.

## Freeze everything the held-out run needs

The evening freezes preprocessing with window length, stride, edge handling, and causal gap policy; dataset identifiers with URLs, licences, checksums, and exact split positions; policy logic with settings and the metric-matching convention; and each baseline's operating point chosen on development budgets — all pinned in configs with one-sentence reasons. The freeze note records how held-out calibration state carries or resets with warmup, derived from source and development history and causal information only, since held-out outcomes remain uninspected.

If ablations contradict each other across streams, the fallback keeps the contradiction visible, freezes the simpler well-supported choice, and lets the failure map carry the nuance into Day 8.

## Navigation

Previous: [Day 6](./day-06.md). Next: [Day 8](./day-08.md). Shared contract: [reference](./reference.md). Report requirements: [Guidelines for Report](../Guidelines%20for%20Report.md).
