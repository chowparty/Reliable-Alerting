# Day 5, Wednesday 23 September: what diagnostics actually say on development data

Day 5 turns the Day 4 baseline family into understanding. The team has five behaviours — fixed, rolling, K-consecutive, M-of-N, hysteresis — running on the same development scores with actual alert volumes reported. The question is narrow: do cheap signals available at decision time predict where each rule struggles, and does any of that justify even sketching a small conditional rule. Nothing touches the reserved held-out target. The day runs about three focused hours per person: roughly twenty minutes together to open, about 130 minutes of solo work that includes some thirty minutes of report writing each, and thirty minutes of joint review.

## Start from the Day 4 traces, not from new code

Nakul begins where the evidence already is. Before any new feature column exists, he hand-inspects the saved Day 4 traces: the clearest false-alert episode and the clearest missed or late event per baseline, read against the score plot with the threshold trace beside it. This grounds every later hypothesis in episodes the team can already point to, and it needs no implementation from anyone else first.

The morning opening agrees which two or three bounded hypotheses are worth testing — drift in recent score median, spread or jumpiness of recent scores, clustering of threshold exceedances — and confirms the five baseline rows rerun from saved configs using the exact command recorded alongside those runs. The held-out area is confirmed to hold no traces.

## Small features, tested causally

Aman builds only the agreed diagnostic features, each computed causally from the current score plus history frozen before the current window, with lookbacks written into config and saved as aligned series beside scores and decisions in the continuing results area. Pratyush spot-checks one feature column by recomputation from raw scores, so no future window leaks in unnoticed.

An exploratory static defer band may be tested only if a concrete question justifies it, for example whether near-cutoff hovering explains observed flicker. It is not a required method. And if no defer band is under test, there is no compulsory streak table — a defer streak stays an open aspect to examine when the data actually contains one, not a deliverable to manufacture. No diagnostic is assumed able to classify benign drift; any hypothesis that a feature pattern marks harmless regime change stays unestablished until evidence supports it, and misleading patterns are examined as part of the analysis rather than assumed away.

## A sketch on paper, not a build

Nakul's offline analysis plots each feature against the hand-inspected false-alert episodes and misses, with development labels used only retrospectively after causal decisions froze. He writes whether any single feature cleanly separates cases where holding, alerting, or refreshing looked safer — including the answer that none does.

Pratyush commits at most a written hypothesis or rule sketch, and only if the analysis gives it a rationale distinct from the five baselines. No implementation and no ablations are required today. Wiring a candidate behind the policy interface happens at most on Day 6 and only if budget allows; otherwise the sketch remains analysis, which is a complete Day 5 output. There is deliberately no chain in which Nakul must finish before Pratyush may start before Aman may work — the trace inspection, feature work, baseline audit, and report writing proceed in parallel from the morning's agreement.

All five baseline rows are preserved regardless of how the diagnostics read. A negative finding is filed as measured with its plots, not automatically reframed as a contribution; whether it amounts to anything publishable depends on later literature comparison and supervisor review.

## Evening check and the preliminary draft

The review checks that features recompute cleanly, every diagnostic claim points to a saved trace, the sketch — if any — states its distinct rationale on paper, and shared writing has advanced the preliminary five-to-eight-page draft in the existing `research/report/` source with real methods, the stream identifier, early figures, and limitations. Aman carries methods sentences, Pratyush the figures and results prose, Nakul the metrics and diagnostics notes, about thirty minutes each inside solo time.

If diagnostics separate nothing, the fallback keeps the best simple baseline on its development evidence, files the negative result openly, and carries the open questions into Day 6. Streams are never swapped for flattering shift and settings are never widened until something looks good.

## Navigation

Previous: [Day 4](./day-04.md). Next: [Day 6](./day-06.md). Shared contract: [reference](./reference.md). Report requirements: [Guidelines for Report](../Guidelines%20for%20Report.md).
