# Day 6, Thursday 24 September: a second development stream tests what survived

A rule that looks sensible on one stream is still an anecdote, so Day 6 meets new development data. The team brings a second development stream through the identical pipeline, reports the baselines and any sketched candidate on it, and decides what should be provisionally frozen. The reserved held-out target stays sealed; the second stream comes from the pre-existing eligibility ordering in the manifest, never by repurposing the reserved target. The day runs about three focused hours per person: twenty minutes together to open, about 130 minutes solo including some thirty minutes of report writing each, and thirty minutes of joint review.

## Twenty minutes together, then solo work

The opening is short on purpose. The group replays the Day 5 outputs from saved configs with the exact commands recorded alongside those runs, notes which candidate — if any — exists as a written sketch, and pulls the next eligible development candidate from the manifest ordering. If no second stream passes eligibility on licence, ordering, label fields, and sufficient source-normal and calibration length, the team files that outcome and continues with one solid development stream rather than hunting for favourable data. A stream with little visible shift is reported as measured, not replaced.

If the second stream fails or its integration runs too long, keep the first development stream and test the implemented candidate there, or fall back to the simpler baseline comparison; never repurpose the reserved target to fill the gap, and mark any single-stream finding as no transfer claim.

## A second stream through the existing loader

Aman integrates the new stream using the existing loader format only, and only if feasible within the day. He records URL, licence, checksum, field semantics, and exact split positions in the manifest with the held-out entry visibly untouched, then runs every implemented policy end to end into the continuing results area with config copies and threshold traces.

Source statistics, scaling, and gap handling are fitted on this stream's own source segment and applied forward. Raw thresholds are never carried across streams or across scorers whose score distributions differ; each stream recalibrates its cutoffs from its own source and calibration data under the frozen convention. The per-stream preprocessing and calibration declaration makes that explicit, so no cross-stream leak hides in a reused number.

## Transfer, compare, and the provisional choice

Transfer means running the unchanged Day 5 sketch — if it was implemented — on the new stream first, exactly as defined. Any tuning afterwards is development-only, explicitly declared, bounded, and saved with its config. Held-out outcomes play no role.

Pratyush takes one of two jobs, not both: either the optional simple candidate implementation from the Day 5 sketch, or an independent rerun confirming Aman's new-stream headline rows from the saved config. The sketch counts as tested only once implemented and run; a paper sketch alone is not a reported result. Nakul places the two development streams side by side at actual alert volumes and coverages, each row carrying false-alert episodes, recall and precision with denominators, delay with misses separate, deferral and decision coverage, alerted-window fraction, episode rate, and timing, with durations beside the ratios. He writes the short regime paragraph as observed association only and states plainly that one or two streams cannot support universal claims. Operating points are approximately matched on development budgets chosen beforehand, never forced to match later.

The team keeps a candidate only if it shows usefulness and distinction against the retained baselines with its rationale intact, checked against a bounded pass of the closest verified literature rather than a presumed gap. Otherwise the negative result stands as valid evidence — though a null alone is not automatically publishable — and the best baseline carries forward alongside all five retained controls; the held-out run still carries every implemented baseline rather than only the best-looking row. Every choice stays provisional pending Day 7. The evaluation note records how calibration state carries or resets with warmup between segments from source and development history plus causal information only.

The learned-scorer gate defaults to no. A learned scorer enters only with a concrete development reason such as clearly missing score sensitivity, plus a stable pipeline, evaluation data, and environment, plus a fit inside the existing personal budget through the same pipeline without delaying shared writing. There is no implied promise that a temporal convolutional network trains in two hours; if those conditions fail, it is deferred beyond 30 September as future research.

Shared report writing inside solo time is assigned: Aman carries methods, Pratyush carries figures, Nakul carries the comparison and limits.

## Navigation

Previous: [Day 5](./day-05.md). Next: [Day 7](./day-07.md). Shared contract: [reference](./reference.md). Report requirements: [Guidelines for Report](../Guidelines%20for%20Report.md).
