# Day 8, Saturday 26 September: audit first, then the single held-out run and the full draft

Day 8 assembles everything into a trustworthy story. An independent audit comes before any held-out scoring; only a passed audit with the Day 7 freeze complete unlocks the single held-out run with the frozen policy set. The rest of the day builds the full report draft and slide deck from ongoing sources, leaving Day 9 for supervisor review and corrections, Day 10 for printing, signatures, and binding, and Day 11 as buffer. The day runs about three focused hours per person: twenty minutes together to open, about 130 minutes of work, and thirty minutes of joint review — one audit pass owned across the team, not three repeated full audits.

## Audit before access

Nakul leads the audit because he owns metrics and leakage but did not implement the scoring path, which keeps the check independent. He re-verifies the causal contract on the frozen code path, confirms development labels entered only after predictions froze while held-out labels were reserved before outcomes and remain untouched, confirms every retained baseline — fixed, rolling, K-consecutive, M-of-N, hysteresis, plus any frozen candidate — is present with its development operating point, and confirms volumes and coverages were reported actual rather than forced to match. Pratyush supports with a spot recomputation of golden evaluator cases from Day 3, confirming episode grouping, denominators, and undefined-with-counts handling on hand-checkable examples.

A failure found at this stage, before any held-out access, does not invalidate the target. A bug fixed before the target is read needs no exposure note — the target is still untouched. What contaminates a target is a methodological change made after its outcomes were seen; that distinction is recorded plainly so the team knows which situation it is in. A disappointing development number, by contrast, is filed as measured, never treated as a pipeline failure.

## One held-out run, then no retuning

Only a passed audit unlocks the run, which Aman executes once through the same pipeline using the saved configs, with the documented calibration carry or reset and warmup applied from source and development history only. The evaluator freezes every per-window decision first, groups adjacent alert windows into episodes, and only then joins held-out labels under the frozen overlap convention, reporting false-alert episodes, recall and precision with denominators, delay with misses separate, deferral and decision coverage, alerted-window fraction, episode rate, and timing at actual values. Running the identical saved config again to confirm reproducibility is permitted; it is a reproducibility check, not a second tuning run, and nothing changes on seeing the results. Runs with few or zero events are reported descriptively as inconclusive rather than dressed into confidence claims.

## Assembling the full draft and deck

Pratyush leads the draft assembly while the audit and scoring proceed, so writing never stalls behind them. The report lead works from the [Guidelines for Report](../Guidelines%20for%20Report.md): ten to fifteen pages, ten required sections from front page through references, and a ten-to-fifteen-slide deck for the classroom viva — the exact counts live in the Guidelines, which the draft follows section by section. The result book anchoring the draft is the existing results summary, one prose section per stream with each policy row at actual volume and coverage plus links to its traces and configs, not a new system. Aman extends the methods and results prose, Nakul the metrics and audit notes, Pratyush the figures and slide allocation, inside solo writing time.

Empirical statements trace to the manifest or a saved trace, config, or metric table; literature statements trace to the verified papers themselves, never to the manifest. The evening check confirms the rerun reproduces, the audit names residual risks, the held-out section reports what was actually seen, and the page and slide counts already match the classroom requirements with signature and binding logistics queued.

If readiness fails — the freeze is incomplete, the audit finds a leak, or the target's metadata does not verify — the team does not push through. Development results stay explicitly preliminary, the unseen target is preserved for later, and Days 9 through 11 keep their roles of review, signatures, printing, binding, and rehearsal.

## Navigation

Previous: [Day 7](./day-07.md). Next: [Day 9](./day-09.md). Shared contract: [reference](./reference.md). Report requirements: [Guidelines for Report](../Guidelines%20for%20Report.md).
