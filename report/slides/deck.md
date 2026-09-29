---
title: When Should an Alert Threshold Learn?
subtitle: Admission-separated recalibration as a decision-time action for time-series anomaly alerting
author: Nakul Somani (2023UCS1592) · Aman Pandey (2023UCS1595) · Pratyush Chaudhary (2023UCS1616)
institute: Supervisor Dr. Vijay Kumar Bohat, Assistant Professor, Department of CSE · Netaji Subhas University of Technology
date: B.Tech Project-I (Phase-I) mid-semester evaluation · 30 September 2026
---

# How alerting works: a score per window, a threshold, an operator

**Our data:** SKAB, a public benchmark recorded on a laboratory water-circulation rig. We
use one sensor, the current drawn by its electric motor. **Two ways to fail:** miss a
real fault, or raise false alerts. Each false alert costs an operator's time; too many,
and people stop trusting the alerts.

![](figures/fig-basics.png){width=100%}

::: notes
First, the setting, in half a minute. A machine carries sensors. We use one: the
current drawn by the electric motor of a water-circulation rig, from SKAB, a public
laboratory benchmark. The signal
is cut into short windows. A fixed scorer, which is not our contribution, gives each
window an anomaly score: higher means more unusual. A policy turns each score into a
decision; the simplest one alerts when the score is above a threshold. An operator then
checks every alert. So the system can fail in two ways: it can miss a real fault, or it
can raise false alerts, and each false alert spends someone's time. Our research is
about the policy, box three.
:::

# Normal drifts, so thresholds learn, but from which windows?

When normal **shifts up** (a repair, a new load), a fixed threshold floods the operator
with false alerts, so systems **recalibrate**: they re-set the threshold from recent
scores. **Which windows should it learn from?** The two obvious answers both fail.

![](figures/fig-dilemma.png){width=100%}

::: notes
The threshold starts at theta-zero, set once on early data. But normal drifts. After
a repair or under a new load the whole signal can sit higher, and a fixed threshold
then alerts all the time. So real systems let the threshold learn from recent scores;
this is called recalibration. The question is what it should learn from. If it learns
only from windows it already called normal, it can only move down: the solid blue
line. If it learns from every window, a long fault pulls it up until the fault looks
normal: the dashed line. Ours is the orange line: it waits while a rise is
unconfirmed, then learns only as a guarded decision and stays inside the shaded band.
The next slide shows the first failure with six numbers.
:::

# A threshold that learns only from "normal" windows can only fall

A threshold keeps its last 3 admitted scores, sets itself to their maximum, and admits a
new score **only if it judged that score normal**. Score 9 is normal at step 1 and an
alert at step 6: the alerts come from the threshold, not the signal.

| Step | Score | Judged against | Decision | Threshold after |
|:-:|:-:|:-:|:--|:-:|
| 1 | 9 | 10 | normal, admitted | 9 |
| 2 | 12 | 9 | alert, rejected | 9 |
| 3 | 8 | 9 | normal, admitted | 9 |
| 4 | 7 | 9 | normal, admitted | 9 |
| 5 | 6 | 9 | normal, admitted | 8 |
| 6 | **9** | 8 | **alert**, rejected | 8 |

::: notes
Here is the first failure, worked by hand. This threshold learns only from scores it
already called normal, and sets itself to the largest of its last three. Every score
it admits is at or below it, so it can only stay the same or fall. Score 9 is normal at
step one and an alert at step six, though nothing about the signal changed: the alert
comes from the threshold. Run that for a long time and ordinary scores become alerts.
:::

# Our direction: recalibration as a guarded, auditable action

Recalibrate only as a deliberate decision, from data chosen **neither by the threshold
itself nor unconditionally**, and judge every policy on **identical scores**.
Tags: PROVED = theorem · MEASURED = saved, recomputed result · IMPLEMENTED = tested
code · PROPOSED = not yet tested.

| Evidence | What we claim |
|:------|:-----------------------------|
| [PROVED]{.tag} | C1: learning only from "normal" windows means the threshold never rises |
| [MEASURED]{.tag} | C2: on SKAB that costs 16.2× and 3.9× the alert windows |
| [MEASURED]{.tag} | C3: the scorer, not the policy, limits detection |
| [IMPLEMENTED]{.tag} | C4: a four-action controller, recalibration bounded to $[\theta_0, 4\theta_0]$ |
| [MEASURED]{.tag} | C5: identical to fixed on SKAB, so no harm and no benefit |
| [MEASURED]{.tag} | C6: under stress it works on a step and fails on a ramp |
| [PROPOSED]{.tag} | C7: a benefit on real regime changes, decided by a kill test |

::: notes
This is our direction in one sentence: treat recalibration as a deliberate decision,
learn from data the threshold did not choose for itself, and compare every policy on
exactly the same scores, so a difference can only come from the policy. Read the
tags as a strength scale, from a theorem down to an untested proposal. We have one
proof, several measurements, a working controller, and an honest gap: we have not yet
shown a benefit on real data.
:::

# Isn't this just X? Each ingredient exists; the combination does not

**Open in the nine papers checked:** action policies compared on one frozen score trace.
A bounded search, not proof of absence.

| Closest work | Already does | Ours differs |
|:---------|:-------------|:-------------|
| FITNESS (ICML 2022) | Shows dropping self-flagged anomalies fails | We claim only the ratchet proof |
| Sun et al. (ICML 2024) | Abstains with guarantees | Re-implemented and measured |
| Perini & Davis | Rejects on a fixed stability threshold | Defer is charged to coverage |
| DDADE, ADAPTS, CDDIA | Retrain the model on drift | Scorer frozen; only actions change |
| Hu (in press) | Evaluates alerts by workload | Same frame, plus a controller |
| SEAD, Dynamic-XY | New score; suppression from alert history | One score trace, explicit actions |

::: notes
Every examiner question of the form "isn't this just X" is answered by this table.
FITNESS already names the failure, so we do not claim it; we claim a proof for
quantile thresholds. Sun et al. already abstain, so we re-implemented their method and
measured it on our scores. Drift methods retrain the model; we freeze it. Hu already
evaluates by workload; we borrow that. What we did not find, in nine papers, is
policies compared on one fixed score trace. We say "not found", never "does not exist".
:::

# Every policy sees identical scores; labels arrive only afterwards

![](figures/fig-flow.png){height=78%}

::: notes
This is the pipeline, and it is mostly discipline. Each stream is cut in time into a
fitting part, a calibration part and a replay part. The scorer is fit once and frozen.
One score trace goes to every policy, like setting every student the same exam, so any
difference we report comes from the policy, never from the scorer. Predictions are
saved before labels are read, so no policy can peek at the answers. The reserved
stream in the manifest was never opened.
:::

# Proved, then observed: the self-referential threshold only falls

[PROVED]{.tag} **Proposition 1.** Admit $s$ only if $s \le \theta$ and set $\theta$ to the
buffer's nearest-rank quantile; then $\theta_{t+1} \le \theta_t$ for every score sequence.
[MEASURED]{.tag} **0** increases in 143 and 140 steps; valve1 1.309 → **0.258**,
valve2 1.126 → **0.406**.

![](figures/fig-ratchet.png){width=86%}

::: notes
The one thing we prove: if a threshold admits only what it called normal and sets
itself to a quantile of that buffer, it can never go up, for any data. The proof is a
short rank argument. The saved SKAB traces agree: zero increases, and the threshold
slides from 1.3 to 0.26 on valve1 and from 1.13 to 0.41 on valve2, below the typical
score. That sinking line is why the rolling baseline alerts so often.
:::

# Same single event, up to 16× the alerts; our controller equals fixed

[MEASURED]{.tag} 97 vs 6 (16.2×) and 70 vs 18 (3.9×) alert windows for the same event.
Our controller: 0 deferrals, 0 recalibrations, **no harm and no evidence of benefit.**
*False-alert time* = alerted samples outside the event · *recall* = events caught ·
*coverage* = windows decided rather than deferred.

| Policy (valve1 / valve2) | Alert windows | False-alert time | Recall | Coverage |
|:-----------|:-------:|:-------:|:----:|:-------:|
| Fixed threshold | 6 / 18 | 0 / 20 | 1/1 | full |
| Rolling, normal-only | **97 / 70** | 109 / 104 | 1/1 | full |
| Rolling, admit-all | 10 / 13 | 10 / 12 | 1/1 | full |
| k-consecutive | 0 / 0 | 0 / 0 | 0/1 | full |
| **Our controller** | 6 / 18 | 0 / 20 | 1/1 | full |
| Sun et al. | 3 / 2 | 0 / 4 | 1/1 | **54/143 · 57/140** |

::: notes
The SKAB table, read narrowly. Every policy that alerts finds the one event per stream.
What separates them is workload. The normal-only rolling policy needs 16 times the alert
windows on valve1 and nearly 4 times on valve2 for the same event: the ratchet's cost.
Our controller is identical to fixed, because its guard never fires on this data. That
is a no-harm check, not a win. Sun et al. look quiet only because they decide on about
40 percent of windows.
:::

# The scorer, not the policy, limits detection on SKAB

[MEASURED]{.tag} Only **6/100** (valve1) and **13/98** (valve2) in-event windows exceed
$\theta_0$, never more than **2** in a row, so rules needing 3 miss the events. Each
event spans about **70%** of replay, so recall 1/1 says little. **A policy can move
alerts in time; it cannot create separation the scorer lacks.**

![](figures/fig-scorer-limit.png){width=86%}

::: notes
Why do the persistence rules miss the events? Because of the scorer. Inside the event
only 6 of 100 windows on valve1 and 13 of 98 on valve2 even cross the threshold, and
never more than two in a row. A rule that waits for three in a row has nothing to fire
on. And since each event covers most of the replay, one alert anywhere scores full
recall, so on SKAB we read workload and false episodes, not recall.
:::

# The controller: four actions, recalibration only inside a bounded band

[IMPLEMENTED]{.tag} `AnchoredRecalibrationPolicy`. Its buffer holds the last 10 scores
of **every** window, so what it learns from never depends on its own decisions. Nothing
was tuned: 10 and 0.95 are the rolling baseline's values; the cap 4 and the stability
bound 2 are declared operating assumptions.

| At a window end | Action |
|:--------------------|:----------------|
| No sustained rise | **hold**, or **alert** if $s > \theta$ |
| Sustained rise that is stable and at most $4\theta_0$ | **recalibrate** up to it |
| Sustained rise, guard fails | **defer**, at most 10 in a row |
| Still failing after 10 deferrals | **escalate**: alert-capable, no recalibration |
| Rise over | **recalibrate** back toward $\theta_0$ |

::: notes
The controller in one table. With no sustained rise it behaves like a fixed threshold.
When the recent median rises and the rise is stable and inside four times the
calibration threshold, it recalibrates. If the rise is unstable it defers, up to ten
times, then escalates and keeps alerting without learning. When the rise ends it
returns toward the anchor. The parameters come from the existing baseline or are
declared assumptions; none was chosen by looking at results.
:::

# Under stress: adapts to a step, fails on a ramp and a step-shaped fault

:::::: columns
::: {.column width="63%"}
![](figures/fig-synthetic-map.png){width=100%}
:::
::: {.column width="37%"}
[MEASURED]{.tag} Seven deterministic cases:

- **Works, Y1 step:** false-alert time **16** vs fixed 597, coverage 260/260
- **Still detects, Y3 and Y7:** later faults caught, recall 1/1
- **Fails, Y2 ramp:** locks into alerts, **204** over 50 episodes
- **Fails as declared, Y4:** a fault shaped like a step is absorbed, 0.020 vs fixed 0.746
:::
::::::

::: notes
These engineered cases show the mechanism and its failures. On a clean benign step it
adapts and cuts false-alert time from 597 to 16 while deciding on every window. After
adapting it still catches later faults. On a slow ramp it locks into repeated alerts, a
real failure we report. And a fault shaped exactly like a benign step is absorbed; we
declared that limit in advance, because no label-free rule can tell the two apart.
:::

# Quiet has two routes: adapt while deciding, or stop deciding

:::::: columns
::: {.column width="66%"}
![](figures/fig-tradeoff.png){width=100%}
:::
::: {.column width="34%"}
**How to read it:** one marker per policy; further right decides on more windows,
lower means less false-alert time.

[MEASURED]{.tag} On Y1 our controller reaches **16** while deciding on **260/260**
windows.

Sun et al. are quiet because they decide on only **22/260**.
:::
::::::

::: notes
Each marker is one policy: to the right means it decided on more windows, lower means
less false-alert time. On SKAB nearly every policy decides on every window. On the
benign step our controller is quiet while still deciding everywhere, whereas Sun et al.
are quiet by abstaining. That is why we always report coverage beside workload.
:::

# The strongest case against us: a simpler rule is quieter

**These results do not establish a useful controller.**

- **Admit-all is quieter on benign shifts:** false-alert time 12 vs our 16 on Y1, and
  28 vs our **204** on Y2.
- **Our only edge is keeping faults visible:** on Y3 it alerts 0.29 of the fault
  against admit-all's 0.04, both at recall 1/1.
- **SKAB gives no evidence either way:** our rows are identical to fixed.
- **Abstention buys quiet with coverage:** Sun et al. decide on 54/143 and 57/140 windows.

**What we claim instead:** a proved mechanism, an honest negative-to-inconclusive
development finding, and a test that can refute the direction.

::: notes
This is the slide we most want to be honest on. On the benign cases the simplest rule,
learning from every window, is quieter than ours: 12 against 16, and 28 against 204.
Our only argument is that we keep faults visible: 0.29 of the Y3 fault against 0.04.
On SKAB we are identical to fixed, so it proves nothing either way. We therefore claim
a mechanism and a finding, not a winner.
:::

# Not yet shown, and the experiment designed to kill the idea

**Not shown:** any benefit on real benign regime changes; any held-out or
generalisation result. **Limits:** one event per stream, one channel (`Current`),
dataset licence not independently verified; `other/21.csv` reserved and never opened.

[PROPOSED]{.tag} Replay all policies on common traces over every other SKAB `valve1`
and `valve2` file, admitted by a label-independent rule, plus one public family with
labelled **benign** regime changes. **The direction is refuted if any one holds:**

1. Where the elevation test fires, it does **not** cut false-alert time versus fixed
   at equal recall.
2. It **loses** an event that fixed detects.
3. Sun et al.'s abstention **matches** it at equal coverage.

A refutation becomes the reported result.

::: notes
To close, what we have not shown and how we will find out. We have no real-world
benefit and no held-out result, the data has one event per stream on one channel, and
we make no claim about the reserved stream. The next experiment is committed in
advance, so we cannot move the goalposts: every policy is replayed on the other SKAB
valve files, chosen without looking at labels, plus a dataset with genuine benign
shifts. Any one of three outcomes kills the direction, and then that becomes our
result. Thank you; we are happy to take questions.
:::
