# Day 4, Tuesday 22 September: the simple temporal family on shared scores

Day 4 widens the Day 3 pairing into the full set of simple temporal controls: fixed threshold, rolling threshold, K-consecutive exceedance, M-of-N persistence, and hysteresis. None is novel, which is their value as fair baselines. Every rule sees the same development score trace, decides first with labels absent, and is scored afterward with actual volume and coverage reported. The day fits about 20 minutes together plus about 130 minutes solo including about 20 minutes of report writing plus 30 minutes of joint review, inside three focused hours per person.

Before reading comparative outcomes the team predeclares the comparison criterion: a label-free episode-rate budget or tolerance plus a coverage floor where applicable, with any recall/delay expectations stated as illustrative development-only targets and their rationale. Exploration stays bounded with no exhaustive grid.

## Catch runs and dips: consecutive and M-of-N

Aman implements K-consecutive and M-of-N behind the unchanged policy interface. Each rule is a small state machine that steps causally through the score trace, carrying only explicit state such as the current run length or the recent window outcomes, plus thresholds frozen before the current window. Nothing reads labels or future scores.

K-consecutive alerts only after K windows in a row cross the cutoff. Its K-minus-one lag is measured relative to the first sustained exceedance, not a fixed delay after the true event onset, since the event may start earlier or later than the sustained run. M-of-N alerts when at least M of the latest N windows cross, tolerating a brief dip that would reset a strict count.

## Steady the flicker: hysteresis and family integration

Pratyush implements hysteresis and runs the whole family. Hysteresis separates the turn-on level from the turn-off level so hovering scores stop flickering: a high score switches alerting on, and only a score below the lower level switches it off. Like Aman's rules it is a causal state machine with explicit on-off state, not a scalar function of one score.

Pratyush saves per-window decisions and threshold traces with config copies for all five rules on the identical scores. The intuition on one illustrative trace (A = alert, . = normal):

```
win     38  39  40  41  42
score  0.21 0.34 0.58 0.71 0.66
fixed   .    .    .    A    A
K=2     .    .    .    .    A      (alerts at second sustained cross)
hyst    .    .    .    A    A      (stays on until below lower level)
```

## Judge the family side by side: comparison and audit

Nakul owns the family table, the operating-point record, and the audit. Each row reports false-alert episodes, recall and precision with denominators, delay with misses separate, deferral and coverage, alerted-window fraction, episode rate, and timing at actual values. The sweep note records which bounded settings were explored on development data and which look worth carrying. Development-side exploration is allowed; held-out data gets no tuning.

His audit confirms no development labels entered any decision and the held-out target holds no traces. One full table row is recomputed from saved traces by someone other than its author, and every annotated episode is traced to the decisions file.

## Keeping all five controls

All five rules are retained as held-out controls because they are cheap to reuse through the same interfaces. Weak or tied rows are filed as measured rather than thinned to a surviving pair; the team may only bound further tuning and extra candidates. The per-rule error stories explain the mechanism: the clearest false-alert episode and the clearest missed or late event per rule, shown on the score plot, or annotated as none where no such case exists.

Report work continues in the existing source: Aman extends the methods, Pratyush the family figure and results prose, Nakul the metrics notes. If the family ties, the second stream and later diagnostics do the separating rather than new complexity.

## Navigation

Previous: [Day 3](./day-03.md). Next: [Day 5](./day-05.md). Shared contract: [reference](./reference.md).
