# Day 2, Sunday 20 September: the first real development stream

Day 2 runs the Day 1 path against one real development stream while the held-out target stays untouched. The same loader, splitter, scorer, calibration, policy, and writer now handle real timestamps, gaps, and labels without changing their interfaces. The evaluator appears in its simplest form; hardening waits for Day 3. The day fits about 20 minutes together plus about 130 minutes solo including about 20 minutes of report writing plus 30 minutes of joint review, inside three focused hours per person.

## Opening check

The prerequisite is the rerunnable Day 1 smoke path with its agreed columns and a manifest holding at least a development candidate. The day opens with about twenty minutes together: confirm the smoke reruns, confirm or record one revision of a Day 1 provisional, and confirm the held-out reservation. If Day 1 deferred it, this session freezes the reservation before any outcomes are inspected. Afterwards the held-out target gets metadata checks only, with no scoring and no outcome inspection.

## Bring the real stream in: loader and preprocessing

Aman adapts the loader to the actual stream chosen under the eligibility rule. TSB-AD and SKAB leads are candidates to verify against licence, label presence, and ordering, not datasets already chosen. He records URL, checksum, field semantics, and exact split positions, then confirms window length, stride, edge handling, and causal gap treatment with a sentence of reason each.

Scaling stays fitted on source-fit data and applied forward. Gaps are handled from past observations only. No window straddles two segments. A stream with barely any shift is reported as measured, never quietly swapped.

## Freeze decisions then join labels: evaluator and fixed baseline

Pratyush completes the basic evaluator and freezes the source-calibrated fixed threshold as the week's reference. The evaluator freezes every per-window decision first, groups adjacent alert windows into episodes, and only then joins development labels. The matching convention is overlap as defined in the [reference](./reference.md#9-from-windows-to-episodes-to-metrics): an event counts as recalled when at least one forward-time alert episode overlaps it, with delay measured from the earliest active alert within the event and an event ending before the first available alert counted as a miss.

Recall and precision carry their denominators. Delay runs forward from event start with misses counted separately. Zero denominators report as undefined with counts. Alerted-window fraction, episode rate, deferral, coverage, latency, and memory accompany the ratios.

## Confirm the run is honest: verification and leakage note

Nakul verifies timestamp or index order, gap handling, and development label coverage, then writes the shift description as a measured observation rather than a selection criterion. He drafts the leakage paragraph stating where preprocessing was fitted, what each decision used, and where labels first entered. He continues the literature thread for about twenty minutes within the total budget.

For the report, the stream identifier and interface description plus the first genuine figure enter the existing source. Nakul adds the metrics notes, Aman the methods sentences, Pratyush the figure.

## What the evening shows

Success means one real development stream saved end to end with traces and configs, a frozen fixed baseline with its figure, a shift description that may be flat, and a leakage note matching the code path. Cross-checks: split indices replay exactly, checksums verify, the held-out area holds no traces, and a hand-crafted decisions file behaves as the reference example says.

If real data cannot be fetched today, the fallback keeps the synthetic smoke green, records the blocker and metadata gap in the manifest, and carries the integration into Day 3 without touching held-out outcomes.

## Navigation

Previous: [Day 1](./day-01.md). Next: [Day 3](./day-03.md). Shared contract: [reference](./reference.md).
