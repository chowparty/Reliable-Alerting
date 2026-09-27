# Day 3, Monday 21 September: a trusted evaluator and the first rolling comparison

Day 3 makes every later comparison possible. The Day 2 evaluator is stress-tested with hand-checkable cases until its episode logic can be trusted. Only then does a rolling threshold meet the frozen fixed baseline on development data. One well-understood comparison with actual volumes reported teaches more than five rules nobody can explain. The day fits about 20 minutes together plus about 130 minutes solo including about 20 minutes of report writing plus 30 minutes of joint review, inside three focused hours per person.

If the real Day 2 integration failed, repair it first through the same loader, splitter, scorer, calibration, policy, and writer modules before any rolling work; defer rolling and extra tuning, keep the early report lines, and file no pretend result.

## Prove the evaluator on paper cases: hand checks and audit

Nakul owns the hand-case tests and the audit, plus closing the literature thread. He builds tiny synthetic decision sequences with known answers and runs them through the real evaluator. The cases cover a clean event caught with delay, an event ending before its window closes counted as a miss per the [reference](./reference.md#9-from-windows-to-episodes-to-metrics), zero predicted episodes with precision reported as undefined, a stretch with no labelled events where recall is undefined, and an always-alert run where strong recall is exposed by alert volume.

The grouping cases are precise: adjacent alert windows merge into one episode, while alerts separated by a normal or deferred window remain separate episodes. A long episode spanning two events and two episodes sharing one event are included to show why durations accompany the ratios. Nakul also audits that labels are absent from the scorer and policy paths and that appending future windows leaves saved prefix decisions unchanged.

## Fix what the cases expose: evaluator corrections

Pratyush owns the evaluator fixes. Each failing hand case gets a direct action: a grouping bug means the episode logic is corrected, a denominator bug means the undefined-with-counts reporting is corrected, and a causality breach means the offending future access is removed. Any development numbers produced by the broken logic are invalidated and recomputed after the fix. They are never filed as negative evidence for a policy, because a broken instrument says nothing about the rule it measured.

The fixed expectations stay as regression checks in the reusable module.

## Meet the first adaptive cutoff: rolling rule and control

Aman implements the rolling threshold, which recomputes its cutoff from recent history under a predeclared rule, beside a frozen-calibration control differing in exactly the update rule. The admission rule for any accepted-normal buffer is written in config before the run. Threshold updates use scores and past decisions only, never labels.

Settings stay bounded and predeclared rather than grid-searched. The threshold trace is saved beside scores and decisions. Deferral stays exploratory and optional today.

## Reading the comparison

Each behaviour reports its actual alert volume and coverage: false-alert episodes, recall and precision with denominators, delay with misses separate, alerted-window fraction, episode rate, coverage, timing, and the threshold trace showing whether the cutoff tracked drift, stalled, or chased anomalies. The interpretation paragraph matters as much as the numbers: where rolling helped, where it merely alerted more, and what remains open.

Nakul closes the literature thread within the 60–90-minute total, filing short verified paragraphs on what the closest papers actually establish and leaving the rest pending. Report work stays shared: Aman extends the methods, Pratyush adds the figures, Nakul the metrics and literature notes.

If rolling shows nothing, that null result is filed as measured and shapes whether adaptivity is kept. It never justifies swapping streams or widening the search for a flattering setting.

## Navigation

Previous: [Day 2](./day-02.md). Next: [Day 4](./day-04.md). Shared contract: [reference](./reference.md).
