"""test_metric_cases.py - hand-case correctness tests for the offline evaluator.

These tests exercise reliable_alerting.evaluation (teammate package,
read-only import via conftest.py) against small synthetic decision sequences
with known ground-truth answers derived by hand from reference.md section 9.

PURPOSE: Verify that the evaluator episode grouping, recall/precision
calculation, delay computation, undefined-denominator reporting, and
coverage metrics match the reference contract exactly. If the teammate
updates evaluation.py in a way that breaks the contract, these tests fail
with a clear value mismatch -- that is intentional, not a bug.

CASES COVERED (Day 1 seed; Day 3 adds the full hardening suite):
  Case 1: Zero predicted episodes -- precision undefined (None), recall 0/N
  Case 2: Single clean event recalled with measured delay
  Case 3: Adjacent alert windows merge into one episode (not two)
  Case 4: A normal window between two alert windows produces two episodes
  Case 5: Event ending before first available alert is a miss (not a hit)
  Case 6: Always-alert run -- strong recall exposed by alert volume
  Case 7: No labelled events -- recall undefined (None), precision 0/0 = None
  Case 8: Long episode spanning two events recalls both; counts once in precision
  Case 9: Defer windows are not alert; defer breaks an episode
  Case 10: Fixture round-trip -- matches the teammate README documented values

HAND-DERIVATION METHOD (applied to every case):
  - Episodes form from saved output_state values before labels are seen.
  - Each decision covers [end_index, next_end_index) forward; final covers
    [end_index, horizon_stop).
  - Adjacent alert intervals merge; normal or defer breaks a run.
  - An event is recalled if any episode overlaps [event.start, event.stop).
  - Delay = max(0, first_matching_episode_start - original_event_start).
  - An event whose stop <= horizon_start is excluded (counted).
  - Precision denominator = total episodes; recall denominator = clipped events.
  - Either is None when its denominator is zero.

IMPORTANT: The evaluation config used here follows the schema_version=1
contract from evaluation.py: time_basis=sample_index, first_decision =
horizon_start + window_length - 1, decisions at inclusive window-end indices.
"""

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bridge. unittest does NOT auto-load conftest.py (that is a pytest
# feature), so it is imported explicitly: it adds Reliable-Alerting/src to
# sys.path and runs the location guard before reliable_alerting is imported.
# ---------------------------------------------------------------------------
# reliable_alerting is importable directly (editable install); no conftest
# bridge is needed in the Reliable-Alerting repo.

from reliable_alerting.evaluation import (
    evaluate,
    form_episodes,
    validate_evaluation_config,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_config(horizon_start, horizon_stop, window_length, stride=None):
    """Build a minimal valid evaluation config for hand cases.

    first_decision = horizon_start + window_length - 1  (schema contract).
    decision_stride defaults to window_length (non-overlapping windows).
    """
    if stride is None:
        stride = window_length
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "horizon": [horizon_start, horizon_stop],
        "first_decision": horizon_start + window_length - 1,
        "decision_stride": stride,
        "window_length": window_length,
    }


def _make_rows(config, states, run_id="run-test", config_id="cfg-test"):
    """Build prediction rows aligned to the evaluation config schedule.

    states: list of output_state strings, one per scheduled decision.
    Scores and thresholds are dummies (0.5 score, 1.0 threshold for
    normal; 1.5 score, 1.0 threshold for alert/defer -- values that
    are consistent with the state for the writer contract but irrelevant
    to the evaluator which only reads output_state).

    NOTE: the generic evaluator loader (load_predictions_generic) accepts
    defer in saved states even though the Day-1 runtime writer does not
    write defer. We use that loader path here to test defer cases.
    """
    resolved = validate_evaluation_config(config)
    h0 = resolved["horizon"][0]
    first = resolved["first_decision"]
    stride = resolved["decision_stride"]
    wlen = resolved["window_length"]

    rows = []
    k = 0
    for state in states:
        end = first + k * stride
        start = end - wlen + 1
        # Assign score/threshold consistent with state for any downstream
        # schema checks (not used by the pure evaluator but good practice).
        if state == "alert":
            score, threshold = 1.5, 1.0
        else:
            score, threshold = 0.5, 1.0
        rows.append({
            "window_id": f"test:{start}:{end}",
            "start_index": start,
            "end_index": end,
            "score": score,
            "output_state": state,
            "threshold": threshold,
            "config_id": config_id,
            "run_id": run_id,
        })
        k += 1
    return rows


def _make_labels(coverage_start, coverage_stop, events):
    """Build a labels dict. events is a list of (start, stop) half-open pairs."""
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "coverage": [coverage_start, coverage_stop],
        "events": [
            {"event_id": f"ev-{i}", "start": s, "stop": e}
            for i, (s, e) in enumerate(events)
        ],
    }


# ---------------------------------------------------------------------------
# Case 1: Zero predicted episodes
# Expected: precision=None (0 episodes), recall=0/1
# ---------------------------------------------------------------------------
class Case01ZeroEpisodesTest(unittest.TestCase):
    """Zero alerts -> zero episodes -> precision undefined, recall 0."""

    def setUp(self):
        # horizon [0, 40), window_length=10, stride=10 -> 4 decisions at
        # end indices 9, 19, 29, 39.
        self.config = _make_config(0, 40, 10)
        self.states = ["normal", "normal", "normal", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [(10, 20)])

    def test_episodes_are_empty(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(episodes, [],
                         "All-normal run must produce zero episodes.")

    def test_precision_is_none(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertIsNone(
            result["metrics"]["episode_precision"]["value"],
            "Precision must be None when there are zero episodes "
            "(zero denominator)."
        )
        self.assertEqual(result["metrics"]["episode_precision"]["denominator"], 0)

    def test_recall_is_zero(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["event_recall"]["value"], 0.0,
            "Recall must be 0.0 when no episodes overlap any event."
        )
        self.assertEqual(result["metrics"]["event_recall"]["numerator"], 0)
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 1)

    def test_decision_coverage_full(self):
        """No-alert, no-defer run must have full decision coverage."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["decision_coverage"]["value"], 1.0,
            "All-normal run must have decision coverage 1.0."
        )

    def test_deferral_rate_zero(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["deferral_rate"]["value"], 0.0
        )


# ---------------------------------------------------------------------------
# Case 2: Single clean event recalled with delay
# horizon [0, 40), window_length=10, stride=10
# decisions at end_index: 9, 19, 29, 39
# states: normal, normal, alert, normal
# episode: [29, 40) (alert at 29, next is end-of-horizon 40)
# event: [10, 25) -> recalled by episode [29, 40)?
#   overlap check: episode [29,40) vs event [10,25): 29<25? No. Miss.
# Adjust: event [20, 35) -> overlap [29,40) vs [20,35): 29<35 and 20<40. Hit.
# delay = max(0, 29 - 20) = 9
# ---------------------------------------------------------------------------
class Case02SingleEventRecalledWithDelayTest(unittest.TestCase):
    """One alert episode, one event overlapping it -- recall 1/1, delay=9."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        # decisions at 9,19,29,39
        self.states = ["normal", "normal", "alert", "normal"]
        self.rows = _make_rows(self.config, self.states)
        # event [20, 35): onset at 20, stop at 35
        self.labels = _make_labels(0, 40, [(20, 35)])

    def test_one_episode_formed(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(len(episodes), 1)
        ep = episodes[0]
        # Alert at end_index=29; next decision end_index=39; episode=[29,39)
        self.assertEqual(ep["start"], 29)
        self.assertEqual(ep["stop"], 39)

    def test_event_recalled(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)
        self.assertEqual(result["metrics"]["event_recall"]["numerator"], 1)
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 1)

    def test_precision_one_of_one(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["episode_precision"]["value"], 1.0)
        self.assertEqual(result["metrics"]["episode_precision"]["numerator"], 1)
        self.assertEqual(result["metrics"]["episode_precision"]["denominator"], 1)

    def test_delay_measured_from_onset(self):
        """Delay = first_episode_start - original_event_start = 29 - 20 = 9."""
        result = evaluate(self.rows, self.labels, self.config)
        delays = result["metrics"]["delay"]
        self.assertEqual(delays["recalled_count"], 1)
        self.assertEqual(delays["missed_count"], 0)
        self.assertEqual(delays["mean"], 9.0)
        per_event = delays["per_event"]
        self.assertEqual(len(per_event), 1)
        self.assertEqual(per_event[0]["delay"], 9)

    def test_false_alert_episodes_zero(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["false_alert_episodes"], 0)


# ---------------------------------------------------------------------------
# Case 3: Adjacent alert windows merge into one episode
# horizon [0, 40), window_length=10, stride=10
# decisions at 9, 19, 29, 39
# states: normal, alert, alert, normal
# intervals: [9,19) normal, [19,29) alert, [29,39) alert, [39,40) normal
# merged episode: [19, 39)
# ---------------------------------------------------------------------------
class Case03AdjacentAlertsMergeTest(unittest.TestCase):
    """Two consecutive alert decisions must merge into one episode."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        self.states = ["normal", "alert", "alert", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [(15, 35)])

    def test_one_episode_not_two(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(
            len(episodes), 1,
            f"Adjacent alert windows must merge into 1 episode, "
            f"got {len(episodes)}: {episodes}"
        )

    def test_merged_episode_bounds(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(len(episodes), 1)
        ep = episodes[0]
        self.assertEqual(ep["start"], 19,
                         "Merged episode must start at first alert end_index.")
        self.assertEqual(ep["stop"], 39,
                         "Merged episode must stop at next non-alert end_index.")


# ---------------------------------------------------------------------------
# Case 4: Normal window between two alert windows -> two separate episodes
# states: alert, normal, alert, normal
# episode 0: [9, 19), episode 1: [29, 39)
# ---------------------------------------------------------------------------
class Case04NormalBreaksEpisodesTest(unittest.TestCase):
    """A normal window between two alerts must produce two separate episodes."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        self.states = ["alert", "normal", "alert", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [])

    def test_two_episodes(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(
            len(episodes), 2,
            f"Normal window must separate two alert runs into 2 episodes, "
            f"got {len(episodes)}: {episodes}"
        )

    def test_episode_bounds(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(episodes[0]["start"], 9)
        self.assertEqual(episodes[0]["stop"], 19)
        self.assertEqual(episodes[1]["start"], 29)
        self.assertEqual(episodes[1]["stop"], 39)

    def test_recall_undefined_no_events(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertIsNone(
            result["metrics"]["event_recall"]["value"],
            "Recall must be None when there are no labelled events."
        )
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 0)

    def test_precision_zero_of_two(self):
        """Two episodes, no events -> precision 0/2 = 0.0, not None."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["episode_precision"]["value"], 0.0)
        self.assertEqual(result["metrics"]["episode_precision"]["numerator"], 0)
        self.assertEqual(result["metrics"]["episode_precision"]["denominator"], 2)


# ---------------------------------------------------------------------------
# Case 5: Event ending before first available alert is a miss
# reference.md: "An event ending before the first available alert is a miss
# even if the input window overlapped it."
# horizon [0, 40), window_length=10, stride=10, decisions at 9,19,29,39
# states: normal, normal, alert, normal -> episode [29,39)
# event [0, 15): ends at 15, first alert available at 29. Miss.
# ---------------------------------------------------------------------------
class Case05EventBeforeFirstAlertIsMissTest(unittest.TestCase):
    """Event that ends before the first alert fires must be a miss."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        self.states = ["normal", "normal", "alert", "normal"]
        self.rows = _make_rows(self.config, self.states)
        # event [0, 15): entirely before the alert at 29
        self.labels = _make_labels(0, 40, [(0, 15)])

    def test_event_is_missed(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["event_recall"]["value"], 0.0,
            "Event ending before the first alert must be a miss."
        )
        self.assertEqual(result["metrics"]["event_recall"]["numerator"], 0)

    def test_miss_counted_separately(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["delay"]["missed_count"], 1,
            "Missed event must be counted in missed_count."
        )
        self.assertEqual(result["metrics"]["delay"]["recalled_count"], 0)

    def test_missed_event_delay_is_null(self):
        result = evaluate(self.rows, self.labels, self.config)
        per_event = result["metrics"]["delay"]["per_event"]
        self.assertEqual(len(per_event), 1)
        self.assertIsNone(
            per_event[0]["delay"],
            "Missed event must have delay=None (null), never a number."
        )


# ---------------------------------------------------------------------------
# Case 6: Always-alert run -- strong recall, alert volume exposed
# All 4 decisions are alert -> one long episode [9, 40)
# With one real event [20, 30): recalled. But alert duration = 31.
# This case ensures alert volume metrics accompany recall.
# ---------------------------------------------------------------------------
class Case06AlwaysAlertTest(unittest.TestCase):
    """Always-alert run: full recall but entire horizon is in alert."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        self.states = ["alert", "alert", "alert", "alert"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [(20, 30)])

    def test_one_episode_full_horizon(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(len(episodes), 1)
        # episode covers [9, 40) -- alert at end_index=9, no next decision
        # before horizon_stop=40
        self.assertEqual(episodes[0]["start"], 9)
        self.assertEqual(episodes[0]["stop"], 40)

    def test_recall_is_one(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)

    def test_alerted_window_fraction_is_one(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["alerted_window_fraction"]["value"], 1.0,
            "All windows alerted: fraction must be 1.0."
        )

    def test_total_alert_duration_large(self):
        result = evaluate(self.rows, self.labels, self.config)
        # episode [9,40) -> duration 31
        self.assertEqual(
            result["metrics"]["total_alert_duration"]["value"], 31
        )

    def test_delay_is_zero_alert_already_active(self):
        """Event onset at 20; alert active since 9 -> delay = max(0, 9-20) = 0."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["delay"]["mean"], 0.0)
        per_event = result["metrics"]["delay"]["per_event"]
        self.assertEqual(per_event[0]["delay"], 0)


# ---------------------------------------------------------------------------
# Case 7: No labelled events -- recall undefined, precision reflects episodes
# ---------------------------------------------------------------------------
class Case07NoLabelledEventsTest(unittest.TestCase):
    """No events in labels: recall=None, precision computed normally."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        self.states = ["normal", "alert", "normal", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [])  # no events

    def test_recall_is_none(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertIsNone(
            result["metrics"]["event_recall"]["value"],
            "Recall must be None when there are no labelled events "
            "(zero denominator -- report as undefined with count, never 0 or 1)."
        )
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 0)

    def test_precision_is_zero(self):
        """One episode, no events -> 0 TP episodes -> precision 0/1 = 0.0."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["episode_precision"]["value"], 0.0)
        self.assertEqual(result["metrics"]["episode_precision"]["denominator"], 1)
        self.assertEqual(result["metrics"]["episode_precision"]["numerator"], 0)


# ---------------------------------------------------------------------------
# Case 8: Long episode spanning two events -- recalled both; counts once in
# precision denominator (precision = 1/1 = 1.0, not 2/1 = 2.0)
# horizon [0, 80), window_length=10, stride=10, 8 decisions
# states: n,n,alert,alert,alert,alert,n,n -> episode [29,69)
# events: [15,35) and [50,65) -> both overlap [29,69). Precision: 1 episode
# overlapping any event = 1 TP out of 1 episode = 1.0.
# Delays: event [15,35) onset 15, first_match_start=29, delay=max(0,29-15)=14
#         event [50,65) onset 50, first_match_start=29, delay=max(0,29-50)=0
# ---------------------------------------------------------------------------
class Case08LongEpisodeTwoEventsTest(unittest.TestCase):
    """One long episode spans two events: recall 2/2, precision 1/1."""

    def setUp(self):
        # 8 decisions at end_index 9,19,29,39,49,59,69,79
        self.config = _make_config(0, 80, 10)
        self.states = ["normal", "normal", "alert", "alert",
                       "alert", "alert", "normal", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 80, [(15, 35), (50, 65)])

    def test_one_episode_formed(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["start"], 29)
        self.assertEqual(episodes[0]["stop"], 69)

    def test_recall_two_of_two(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)
        self.assertEqual(result["metrics"]["event_recall"]["numerator"], 2)
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 2)

    def test_precision_one_of_one(self):
        """One episode overlaps events -> 1 TP out of 1 episode."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["episode_precision"]["value"], 1.0)
        self.assertEqual(result["metrics"]["episode_precision"]["numerator"], 1)
        self.assertEqual(result["metrics"]["episode_precision"]["denominator"], 1)

    def test_delay_event_a(self):
        """Event [15,35): first_match_start=29, delay=max(0,29-15)=14."""
        result = evaluate(self.rows, self.labels, self.config)
        per_event = {m["event_id"]: m["delay"]
                     for m in result["metrics"]["delay"]["per_event"]}
        self.assertEqual(per_event["ev-0"], 14)

    def test_delay_event_b(self):
        """Event [50,65): onset=50, first_match_start=29, delay=max(0,29-50)=0."""
        result = evaluate(self.rows, self.labels, self.config)
        per_event = {m["event_id"]: m["delay"]
                     for m in result["metrics"]["delay"]["per_event"]}
        self.assertEqual(per_event["ev-1"], 0)


# ---------------------------------------------------------------------------
# Case 9: Defer window breaks an episode
# The generic evaluator accepts defer in saved states (though the Day-1
# runtime writer does not write defer). Defer must behave like normal:
# it terminates an alert run and starts no new run.
# states: alert, defer, alert -> two separate episodes
# ---------------------------------------------------------------------------
class Case09DeferBreaksEpisodeTest(unittest.TestCase):
    """A defer window must break an alert run the same way normal does."""

    def setUp(self):
        # 3 decisions at end_index 9, 19, 29
        self.config = _make_config(0, 30, 10)
        self.states = ["alert", "defer", "alert"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 30, [])

    def test_defer_breaks_episode(self):
        episodes = form_episodes(self.rows, self.config)
        self.assertEqual(
            len(episodes), 2,
            f"Defer between two alerts must produce 2 episodes, "
            f"got {len(episodes)}: {episodes}"
        )

    def test_deferral_rate(self):
        result = evaluate(self.rows, self.labels, self.config)
        # 1 defer out of 3 decisions
        self.assertAlmostEqual(
            result["metrics"]["deferral_rate"]["value"], 1/3, places=10
        )

    def test_decision_coverage_excludes_defer(self):
        """Decision coverage = decided (normal+alert) / total.
        Here: 2 alert + 0 normal = 2 covered out of 3 total."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertAlmostEqual(
            result["metrics"]["decision_coverage"]["value"], 2/3, places=10
        )


# ---------------------------------------------------------------------------
# Case 10: Fixture round-trip matching the teammate README documented values
# This uses the exact Day-1 synthetic fixture numbers from the README:
# 8 replay windows, episodes [79,83) and [91,96), events [72,80) and [88,96)
# recall 2/2, precision 2/2, delays 7 and 3, mean 5.
# Config from configs/day02-evaluation.json:
#   horizon [64,96), first_decision=67, decision_stride=4, window_length=4
# ---------------------------------------------------------------------------
class Case10FixtureRoundTripTest(unittest.TestCase):
    """Reproduces the teammate README documented synthetic fixture values.

    This is a cross-check: if the teammate's evaluation.py changes in a
    way that alters these numbers, this test fails and the team must
    jointly review whether the contract changed intentionally.
    Source: Reliable-Alerting/README.md 'Observed synthetic fixture checks'.
    """

    # Exact schedule from configs/day02-evaluation.json
    EVAL_CONFIG = {
        "schema_version": 1,
        "time_basis": "sample_index",
        "horizon": [64, 96],
        "first_decision": 67,
        "decision_stride": 4,
        "window_length": 4,
    }

    # Exact fixture labels from tests/fixtures/day02-synthetic-labels.json
    # coverage [64,96), events [72,80) and [88,96) (half-open)
    LABELS = {
        "schema_version": 1,
        "time_basis": "sample_index",
        "coverage": [64, 96],
        "events": [
            {"event_id": "offset-up", "start": 72, "stop": 80},
            {"event_id": "offset-down", "start": 88, "stop": 96},
        ],
    }

    # Episodes from README: [79,83) and [91,96). Work backward to decisions:
    # Decisions at 67,71,75,79,83,87,91,95 (stride=4, first=67).
    # Episode [79,83): alert at 79, next decision 83 which is not alert.
    # Episode [91,96): alert at 91, next decision 95 which is alert, then
    #   horizon stop 96. So alerts at 91 AND 95 merge -> [91,96).
    # States: n=67,n=71,n=75,A=79,n=83,n=87,A=91,A=95
    STATES_FROM_README = [
        "normal",   # 67
        "normal",   # 71
        "normal",   # 75
        "alert",    # 79
        "normal",   # 83
        "normal",   # 87
        "alert",    # 91
        "alert",    # 95
    ]

    def _make_fixture_rows(self):
        resolved = validate_evaluation_config(self.EVAL_CONFIG)
        first = resolved["first_decision"]
        stride = resolved["decision_stride"]
        wlen = resolved["window_length"]
        rows = []
        for k, state in enumerate(self.STATES_FROM_README):
            end = first + k * stride
            start = end - wlen + 1
            score = 1.5 if state == "alert" else 0.5
            rows.append({
                "window_id": f"replay:{start}:{end}",
                "start_index": start,
                "end_index": end,
                "score": score,
                "output_state": state,
                "threshold": 1.0,
                "config_id": "fixture-cfg",
                "run_id": "fixture-run",
            })
        return rows

    def test_episodes_match_readme(self):
        rows = self._make_fixture_rows()
        episodes = form_episodes(rows, self.EVAL_CONFIG)
        self.assertEqual(len(episodes), 2,
                         f"Expected 2 episodes, got {len(episodes)}: {episodes}")
        starts = [ep["start"] for ep in episodes]
        stops = [ep["stop"] for ep in episodes]
        self.assertEqual(starts, [79, 91])
        self.assertEqual(stops, [83, 96])

    def test_recall_two_of_two(self):
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)
        self.assertEqual(result["metrics"]["event_recall"]["numerator"], 2)
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 2)

    def test_precision_two_of_two(self):
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertEqual(result["metrics"]["episode_precision"]["value"], 1.0)
        self.assertEqual(result["metrics"]["episode_precision"]["numerator"], 2)
        self.assertEqual(result["metrics"]["episode_precision"]["denominator"], 2)

    def test_false_alert_episodes_zero(self):
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertEqual(result["metrics"]["false_alert_episodes"], 0)

    def test_delay_event_offset_up(self):
        """Event [72,80): first_match_start=79, delay=max(0,79-72)=7."""
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        per_event = {m["event_id"]: m["delay"]
                     for m in result["metrics"]["delay"]["per_event"]}
        self.assertEqual(per_event["offset-up"], 7)

    def test_delay_event_offset_down(self):
        """Event [88,96): first_match_start=91, delay=max(0,91-88)=3."""
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        per_event = {m["event_id"]: m["delay"]
                     for m in result["metrics"]["delay"]["per_event"]}
        self.assertEqual(per_event["offset-down"], 3)

    def test_delay_mean_is_five(self):
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertEqual(result["metrics"]["delay"]["mean"], 5.0)

    def test_warmup_duration(self):
        """Warmup = first_decision - horizon_start = 67 - 64 = 3."""
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertEqual(result["metrics"]["warmup_duration"]["value"], 3)

    def test_decision_count(self):
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertEqual(result["metrics"]["decision_count"], 8)

    def test_alerted_window_fraction(self):
        """3 alert windows out of 8 total = 3/8."""
        rows = self._make_fixture_rows()
        result = evaluate(rows, self.LABELS, self.EVAL_CONFIG)
        self.assertAlmostEqual(
            result["metrics"]["alerted_window_fraction"]["value"], 3/8, places=10
        )


# ===========================================================================
# Day 3 additions (2026-09-27): cases 11-15.
#
# These harden the evaluator against the exact worked examples in
# reference.md sections 2 and 9, plus the valve1 replay layout where the
# labelled anomaly begins at the first replayed row. Every expected value is
# derived by hand in the docstring/comments and checked against the UNMODIFIED
# teammate evaluator (reliable_alerting.evaluation). A failure here is a real
# evaluator-contract finding to route to Pratyush, not a reason to edit the
# test.
#
# Evaluator semantics used (verified by reading evaluation.py):
#   - a decision at end_index e covers forward interval [e, next_end) ;
#     the final decision covers [e, horizon_stop).
#   - adjacent 'alert' decisions merge into one episode; 'normal'/'defer' break.
#   - event recalled iff some episode overlaps [event.start, event.stop).
#   - delay = max(0, first_matching_episode_start - ORIGINAL event start) ;
#     a missed event has delay None and is counted separately.
#   - precision denominator = total episodes; TP = episodes overlapping any
#     clipped event. recall denominator = clipped events in horizon.
# ===========================================================================


# ---------------------------------------------------------------------------
# Case 11: reference.md section 2 example -- event ends before the first
# available alert, so it is a MISS even though an input window overlapped it.
# horizon [0,40) window_length 10 stride 10 -> decisions end at 9,19,29,39.
# states: alert, normal, normal, normal -> one episode [9,19).
# event [15,25): does episode [9,19) overlap [15,25)? 9<25 and 15<19 -> YES.
# So with an alert at 9 the event IS recalled. To reproduce the reference
# "ends before first alert" miss we need the event to end at//before the first
# episode start. Use event [2,8): first (only) episode is [9,19); 9<8 is
# false -> no overlap -> MISS. Delay None. This mirrors reference.md's
# "event [15,25] with first window [0,60] deciding at 60 is a miss".
# ---------------------------------------------------------------------------
class Case11EventEndsBeforeFirstAlertMissTest(unittest.TestCase):
    """Event ending before the first available alert time is a miss."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)          # ends 9,19,29,39
        self.states = ["alert", "normal", "normal", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [(2, 8)])    # ends at 8, before ep start 9

    def test_single_episode_from_first_decision(self):
        eps = form_episodes(self.rows, self.config)
        self.assertEqual(len(eps), 1)
        self.assertEqual((eps[0]["start"], eps[0]["stop"]), (9, 19))

    def test_event_is_missed(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["numerator"], 0)
        self.assertEqual(result["metrics"]["event_recall"]["denominator"], 1)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 0.0)

    def test_missed_delay_is_null_and_counted(self):
        result = evaluate(self.rows, self.labels, self.config)
        d = result["metrics"]["delay"]
        self.assertEqual(d["missed_count"], 1)
        self.assertEqual(d["recalled_count"], 0)
        self.assertIsNone(d["per_event"][0]["delay"])


# ---------------------------------------------------------------------------
# Case 12: reference.md section 9 worked example. 5 episodes E1..E5 and 4
# events A,B,C,D. E1 overlaps A; E2 and E3 both overlap B; E4 spans C and D;
# E5 overlaps nothing. Expected: recall 4/4 = 1.00, precision 4/5 = 0.80,
# 1 false-alert episode (E5). Durations accompany the ratios (E4 recalls two
# events but counts once in precision; E2+E3 recall one event, counting twice).
#
# Construct on horizon [0,60), window_length 10, stride 10 -> decisions end at
# 9,19,29,39,49,59 (6 decisions), each covering a forward 10-wide interval:
#   d@9  -> [9,19)   d@19 -> [19,29)  d@29 -> [29,39)
#   d@39 -> [39,49)  d@49 -> [49,59)  d@59 -> [59,60)
# To get 5 separate episodes we need 5 alert decisions each isolated by a
# normal -- but that is 5 alerts + >=4 normals = >=9 slots. Use stride 5 with
# window_length 5 on horizon [0,60): first=4, ends 4,9,14,...,59 (12 decisions,
# each covering width 5). Episodes are single alert decisions separated by
# normals. Place:
#   E1 alert@ end9  -> [9,14)     overlaps A=[10,13)
#   E2 alert@ end19 -> [19,24)    overlaps B=[20,40)
#   E3 alert@ end29 -> [29,34)    overlaps B=[20,40)   (same event B)
#   E4 alert@ end44 -> [44,49)    overlaps C=[45,47) AND D=[47,49) -> spans two
#   E5 alert@ end54 -> [54,59)    overlaps nothing
# All other decisions normal. Events A,B,C,D as above.
# recall: A(E1),B(E2/E3),C(E4),D(E4) = 4/4. precision: TP episodes = E1..E4 = 4
# of 5 -> 0.80. false-alert episodes = 1 (E5).
# ---------------------------------------------------------------------------
class Case12ReferenceSection9WorkedExampleTest(unittest.TestCase):
    """reference.md section 9: recall 4/4, precision 4/5, 1 false episode."""

    def setUp(self):
        # window_length 5, stride 5, horizon [0,60): first=4, ends 4,9,...,59.
        self.config = _make_config(0, 60, 5, stride=5)
        ends = list(range(4, 60, 5))  # 4,9,14,...,59  (12 decisions)
        self.assertEqual(len(ends), 12)
        # map end_index -> alert
        alert_ends = {9, 19, 29, 44, 54}
        states = ["alert" if e in alert_ends else "normal" for e in ends]
        self.states = states
        self.rows = _make_rows(self.config, states)
        self.labels = _make_labels(0, 60, [
            (10, 13),   # ev-0 = A
            (20, 40),   # ev-1 = B
            (45, 47),   # ev-2 = C
            (47, 49),   # ev-3 = D
        ])

    def test_five_episodes(self):
        eps = form_episodes(self.rows, self.config)
        bounds = [(e["start"], e["stop"]) for e in eps]
        self.assertEqual(bounds, [(9, 14), (19, 24), (29, 34), (44, 49), (54, 59)])

    def test_recall_four_of_four(self):
        result = evaluate(self.rows, self.labels, self.config)
        r = result["metrics"]["event_recall"]
        self.assertEqual((r["numerator"], r["denominator"], r["value"]), (4, 4, 1.0))

    def test_precision_four_of_five(self):
        result = evaluate(self.rows, self.labels, self.config)
        p = result["metrics"]["episode_precision"]
        self.assertEqual((p["numerator"], p["denominator"]), (4, 5))
        self.assertEqual(p["value"], 0.8)

    def test_one_false_alert_episode(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["false_alert_episodes"], 1)

    def test_e4_spans_two_events_counts_once(self):
        """E4 [44,49) recalls C and D but is a single TP episode (precision
        denominator counts it once) -- the flattery-for-long-episodes point."""
        result = evaluate(self.rows, self.labels, self.config)
        # C (ev-2) and D (ev-3) both recalled, both matched by episode-3.
        per = {m["event_id"]: m["matching_episode_ids"] for m in result["metrics"]["delay"]["per_event"]}
        self.assertEqual(per["ev-2"], ["episode-3"])
        self.assertEqual(per["ev-3"], ["episode-3"])


# ---------------------------------------------------------------------------
# Case 13: two episodes sharing one event, with alert-duration accounting.
# horizon [0,40) window_length 10 stride 10 -> ends 9,19,29,39.
# states: alert, normal, alert, normal -> episodes [9,19) and [29,39).
# event [5,35): overlaps BOTH episodes. recall 1/1. precision: both episodes
# are TP -> 2/2 = 1.0. Two episodes counted, one event -> duration matters.
# total_alert_duration = 10 + 10 = 20. non_event_alert: event covers [5,35);
# episode [9,19) fully inside event -> 0 non-event; episode [29,39): overlap
# with event is [29,35)=6, non-event part [35,39)=4. So non_event_alert = 4.
# delay: earliest matching episode start = 9, original onset 5 -> max(0,4)=4.
# ---------------------------------------------------------------------------
class Case13TwoEpisodesOneEventDurationsTest(unittest.TestCase):
    """Two episodes overlap one event; durations separate event vs non-event."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)          # ends 9,19,29,39
        self.states = ["alert", "normal", "alert", "normal"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [(5, 35)])

    def test_two_episodes(self):
        eps = form_episodes(self.rows, self.config)
        self.assertEqual([(e["start"], e["stop"]) for e in eps], [(9, 19), (29, 39)])

    def test_recall_one_precision_two_of_two(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)
        p = result["metrics"]["episode_precision"]
        self.assertEqual((p["numerator"], p["denominator"], p["value"]), (2, 2, 1.0))

    def test_total_and_non_event_alert_duration(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["total_alert_duration"]["value"], 20)
        # event [5,35) covers episode1 fully and episode2's [29,35);
        # non-event alert is episode2's [35,39) = 4.
        self.assertEqual(result["metrics"]["non_event_alert_duration"]["value"], 4)

    def test_delay_from_original_onset(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["delay"]["per_event"][0]["delay"], 4)


# ---------------------------------------------------------------------------
# Case 14: always-alert run -- high recall bought with alert volume, made
# visible by non-event alert duration and episode rate.
# horizon [0,40) window_length 10 stride 10 -> ends 9,19,29,39, all alert.
# one episode [9,40) (last decision extends to horizon stop). duration 31.
# event [20,25): recalled. non_event_alert = 31 - overlap. overlap of [9,40)
# with [20,25) = 5. non_event = 26. alerted_window_fraction = 4/4 = 1.0.
# episode rate per 1000 decisions = (1/4)*1000 = 250.
# ---------------------------------------------------------------------------
class Case14AlwaysAlertVolumeExposedTest(unittest.TestCase):
    """Always-alert: recall 1/1 but 26 units of non-event alert time."""

    def setUp(self):
        self.config = _make_config(0, 40, 10)
        self.states = ["alert", "alert", "alert", "alert"]
        self.rows = _make_rows(self.config, self.states)
        self.labels = _make_labels(0, 40, [(20, 25)])

    def test_one_episode_to_horizon_stop(self):
        eps = form_episodes(self.rows, self.config)
        self.assertEqual(len(eps), 1)
        self.assertEqual((eps[0]["start"], eps[0]["stop"]), (9, 40))

    def test_recall_one(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)

    def test_alert_volume_exposed(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["total_alert_duration"]["value"], 31)
        self.assertEqual(result["metrics"]["non_event_alert_duration"]["value"], 26)
        self.assertEqual(result["metrics"]["alerted_window_fraction"]["value"], 1.0)

    def test_episode_rate_per_1000(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(
            result["metrics"]["alert_episode_rate_per_1000_decisions"]["value"],
            250.0)


# ---------------------------------------------------------------------------
# Case 15: valve1-style layout -- the labelled anomaly begins at the first
# replayed row, so the earliest possible alert is delayed by the warmup.
# Mirrors valve1 replay [574,1148): first decision end is 577 (=574+4-1),
# and the anomaly starts at 574. Model it at small scale:
# horizon [574,614) window_length 4 stride 4 -> first_decision 577,
# ends 577,581,585,589,593,597,601,605,609,613 (10 decisions).
# states: first three normal, then alert at 589, rest normal ->
# episode [589,593). event = anomaly starting at replay start [574,600).
# recall 1/1. delay = max(0, 589 - 574) = 15 (measured from the original
# onset at the replay start, NOT from the first decision). This pins the
# "delay floor" behaviour flagged for valve1 in the Day 3 report notes.
# ---------------------------------------------------------------------------
class Case15AnomalyAtReplayStartDelayFloorTest(unittest.TestCase):
    """Event starting at the replay start: delay measured from original onset."""

    def setUp(self):
        self.config = _make_config(574, 614, 4, stride=4)  # first_decision 577
        # ends 577,581,585,589,597... ; alert only at 589
        ends = list(range(577, 614, 4))
        self.assertEqual(ends[0], 577)
        states = ["alert" if e == 589 else "normal" for e in ends]
        self.states = states
        self.rows = _make_rows(self.config, states)
        self.labels = _make_labels(574, 614, [(574, 600)])

    def test_first_decision_is_577(self):
        resolved = validate_evaluation_config(self.config)
        self.assertEqual(resolved["first_decision"], 577)

    def test_one_episode_at_589(self):
        eps = form_episodes(self.rows, self.config)
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["start"], 589)

    def test_event_recalled(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["event_recall"]["value"], 1.0)

    def test_delay_from_original_onset_574(self):
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["delay"]["per_event"][0]["delay"], 15)

    def test_warmup_duration(self):
        """Warmup = first_decision - horizon_start = 577 - 574 = 3."""
        result = evaluate(self.rows, self.labels, self.config)
        self.assertEqual(result["metrics"]["warmup_duration"]["value"], 3)


if __name__ == "__main__":
    unittest.main()
