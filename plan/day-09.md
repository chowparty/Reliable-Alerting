# Day 9, Sunday 27 September: independent rerun, audit to figures, and report review

Our research on reliable alerting for time-series anomaly detection under changing conditions reaches its checkpoint today. Day 8 already ran the audit and, only if ready, the single frozen held-out evaluation with all five baselines plus the candidate only where justified. Day 9 adds no new research. Its purpose is to confirm that an independent rerun reproduces the figures, that the audit traces every figure to a saved source, and that the existing report draft gets supervisor review plus small corrections before physical preparation.

Why now is straightforward. A result nobody else can reproduce from the written steps will not survive viva questions, and small report fixes done today protect Monday printing. The day runs about three focused hours per person including collaboration and any logistical time, keeping the 19–29 September total near 99 person-hours. Roughly ninety minutes go to rerun and audit, sixty to corrections and review preparation, and thirty to joint review.

## Start only from what Day 8 froze

Nothing today starts from memory. The prerequisites are the Day 8 frozen configs, the saved commands recorded alongside those runs, the results area under the proposed `research/` root with scores, threshold traces, decisions and metric tables, the data manifest with reservations, and the full report draft and slide skeleton.

If Day 8 left the held-out run blocked because the freeze was incomplete, the audit found a leak, or target metadata did not verify, that decision stands. The team keeps working dev-only and says so explicitly in the report. No new held-out selection is forced today to fill the gap.

## Reproduce the same configs, nothing new

Aman leads a clean-state rerun of the headline development rows and, where Day 8 ran it, the held-out rows for all frozen policies, using the identical saved configs and the exact command recorded alongside each run. He records environment, dependency versions, and machine name beside the rerun. This identical-config check is legitimate reproducibility work, not a second experiment.

Pratyush independently repeats one headline rerun step from the written instructions alone and traces each report figure back to its trace, config copy, and metric table. Nakul re-verifies the metric chain end to end: episode grouping before label joins, denominators with undefined-with-counts where needed, actual alert volume and decision coverage reported without forced matching, and the scorer-level description never used for policy selection.

A disappointing number is filed as measured. It is not a bug to fix. A genuine bug is different from a bad result, and a bug in development rows does not automatically leave a clean dev-only story either. Affected rows are invalidated, the correction and any target exposure are flagged openly, and the report carries the honest corrected subset or states the result is unavailable. No test-driven correction after seeing the target is presented as untouched.

## Review the draft and fix the small things today

Pratyush owns the review pass on the existing report draft, with Nakul checking the feedback log for completeness and confirming the approval, printing, signature, and binding procedure with who, where, and when. The team confirms the agreed review slot ahead of time. If the supervisor is unavailable on Sunday, the already assembled draft goes earlier at the end of Day 8, with a bounded Monday morning fallback for feedback.

Small corrections such as wrong numbers, unclear figures, missing links to traces and configs, and straightforward supervisor comments are addressed today inside the three hours. Larger requested method changes or new test choices are deferred as future work, leaving Day 10 for proofreading and essentials.

## What counts as done, and what fails honestly

The evening check is short. The rerun reproduces within the declared tolerance, the audit names residual risks, the held-out paragraph states whether the provisional rule survived, weakened, or failed, and small corrections plus the feedback log are complete. If the rerun diverges or a leak surfaces, the fallback documents the issue openly, withdraws or flags the affected claim, and carries only the bounded correction cost into Day 10.

## Navigation

Previous: [Day 8](./day-08.md). Next: [Day 10](./day-10.md). Shared contract: [reference](./reference.md). Report requirements: [Guidelines for Report](../Guidelines%20for%20Report.md).
