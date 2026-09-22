"""Offline evaluation core checks (TDD).

Exercises validate_evaluation_config, form_episodes, evaluate and the
label adapters on hand-computed timelines. No runtime policy changes;
episodes form from saved states before labels are consulted.
"""
import copy
import json
import unittest
from pathlib import Path

from reliable_alerting import evaluation
from reliable_alerting.writing import PREDICTIONS_COLUMNS

REPO = Path(__file__).resolve().parents[1]


def _config(horizon=(0, 10), window_length=2, stride=1):
    start, stop = horizon
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "horizon": [start, stop],
        "first_decision": start + window_length - 1,
        "decision_stride": stride,
        "window_length": window_length,
    }


def _rows(config, states, threshold=1.0):
    # Build expected schedule without calling implementation under test
    # for row construction: replicate schedule formula directly.
    h0, h1 = list(config["horizon"])
    first = config["first_decision"]
    stride = config["decision_stride"]
    wlen = config["window_length"]
    ends = []
    k = 0
    while first + k * stride < h1:
        ends.append(first + k * stride)
        k += 1
    assert len(ends) == len(states), f"{len(ends)} != {len(states)}"
    rows = []
    for i, (e, st) in enumerate(zip(ends, states)):
        # alternate score/threshold so defer states do not match score logic
        s = 2.5 if st == "alert" else 0.1
        if st == "defer":
            s = 0.1
        rows.append({
            "window_id": f"w:{i}",
            "start_index": e - wlen + 1,
            "end_index": e,
            "score": float(s),
            "output_state": st,
            "threshold": float(threshold),
            "config_id": "cfg",
            "run_id": "run1",
        })
    return rows


def _labels(coverage=(0, 10), events=()):
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "coverage": [coverage[0], coverage[1]],
        "events": [{"event_id": eid, "start": s, "stop": e} for eid, s, e in events],
    }


class ConfigTest(unittest.TestCase):
    def test_valid_resolves(self):
        got = evaluation.validate_evaluation_config(_config())
        self.assertEqual(got["schema_version"], 1)
        self.assertEqual(got["time_basis"], "sample_index")
        self.assertEqual(list(got["horizon"]), [0, 10])
        self.assertEqual(got["first_decision"], 1)
        self.assertEqual(got["decision_stride"], 1)
        self.assertEqual(got["window_length"], 2)

    def test_rejects_missing_extra_keys(self):
        base = _config()
        bad = dict(base)
        del bad["window_length"]
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(bad)
        bad2 = dict(base, extra=1)
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(bad2)

    def test_rejects_bad_schema_timebasis(self):
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(dict(_config(), schema_version=2))
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(dict(_config(), schema_version=True))
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(dict(_config(), time_basis="seconds"))

    def test_rejects_bad_horizon_stride_window(self):
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(dict(_config(), horizon=[5, 5]))
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(dict(_config(), horizon=[-1, 5]))
        with self.assertRaises((TypeError, ValueError)):
            evaluation.validate_evaluation_config(dict(_config(), decision_stride=0))
        with self.assertRaises((TypeError, ValueError)):
            evaluation.validate_evaluation_config(dict(_config(), decision_stride=True))
        with self.assertRaises((TypeError, ValueError)):
            evaluation.validate_evaluation_config(dict(_config(), window_length=0))

    def test_rejects_first_decision_mismatch(self):
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(dict(_config(), first_decision=2))
        # window longer than horizon: first would be >= stop
        with self.assertRaises(ValueError):
            evaluation.validate_evaluation_config(_config(horizon=(0, 2), window_length=5, stride=1))

    def test_uses_predictions_columns(self):
        self.assertEqual(
            tuple(PREDICTIONS_COLUMNS),
            ("window_id", "start_index", "end_index", "score", "output_state",
             "threshold", "config_id", "run_id"),
        )


class EpisodeTest(unittest.TestCase):
    def test_adjacent_alerts_merge(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        # ends 1,2,3,4,5 ; alerts at 1,2 merge, normal break, alerts 4,5 merge
        rows = _rows(cfg, ["alert", "alert", "normal", "alert", "alert"])
        eps = evaluation.form_episodes(rows, cfg)
        self.assertEqual([(e["start"], e["stop"]) for e in eps], [(1, 3), (4, 6)])
        self.assertEqual([e["episode_id"] for e in eps], ["episode-0", "episode-1"])

    def test_normal_defer_separate(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["alert", "defer", "alert", "normal", "alert"])
        eps = evaluation.form_episodes(rows, cfg)
        self.assertEqual([(e["start"], e["stop"]) for e in eps], [(1, 2), (3, 4), (5, 6)])

    def test_final_clipped(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=2)
        # ends 1,3,5,7,9 ; last interval [9,10) clipped to horizon stop
        rows = _rows(cfg, ["normal", "normal", "normal", "normal", "alert"])
        eps = evaluation.form_episodes(rows, cfg)
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["start"], 9)
        self.assertEqual(eps[0]["stop"], 10)

    def test_warmup_is_before_first_decision(self):
        cfg = _config(horizon=(0, 10), window_length=4, stride=1)
        # first = 3, warmup [0,3)
        rows = _rows(cfg, ["alert"] * 7)
        eps = evaluation.form_episodes(rows, cfg)
        self.assertEqual(eps[0]["start"], 3)
        out = evaluation.evaluate(rows, _labels((0, 10), []), cfg)
        self.assertEqual(out["metrics"]["warmup_duration"]["value"], 3)

    def test_does_not_infer_state_from_score(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["alert", "normal", "defer", "normal", "normal"])
        # force scores to contradict states: alert has low score, normal high
        rows[0]["score"] = 0.0
        rows[1]["score"] = 9.0
        eps = evaluation.form_episodes(rows, cfg)
        self.assertEqual([(e["start"], e["stop"]) for e in eps], [(1, 2)])

    def test_rejects_empty_missing_offschedule_irregular(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        with self.assertRaises(ValueError):
            evaluation.form_episodes([], cfg)
        rows = _rows(cfg, ["normal"] * 5)
        missing = [dict(r) for r in rows]
        del missing[0]["score"]
        with self.assertRaises(ValueError):
            evaluation.form_episodes(missing, cfg)
        extra = [dict(r, extra=1) for r in rows]
        with self.assertRaises(ValueError):
            evaluation.form_episodes(extra, cfg)
        off = [dict(r) for r in rows]
        off[2]["end_index"] = 99
        with self.assertRaises(ValueError):
            evaluation.form_episodes(off, cfg)
        gap = [r for i, r in enumerate(rows) if i != 2]
        with self.assertRaises(ValueError):
            evaluation.form_episodes(gap, cfg)
        bad_start = [dict(r) for r in rows]
        bad_start[1]["start_index"] = 0
        with self.assertRaises(ValueError):
            evaluation.form_episodes(bad_start, cfg)

    def test_rejects_duplicate_unsorted_nonfinite(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["normal"] * 5)
        dup = [dict(r) for r in rows]
        dup[1]["window_id"] = dup[0]["window_id"]
        with self.assertRaises(ValueError):
            evaluation.form_episodes(dup, cfg)
        unsorted = [dict(r) for r in reversed(rows)]
        with self.assertRaises(ValueError):
            evaluation.form_episodes(unsorted, cfg)
        bad = [dict(r) for r in rows]
        bad[0]["score"] = float("nan")
        with self.assertRaises(ValueError):
            evaluation.form_episodes(bad, cfg)
        bad2 = [dict(r) for r in rows]
        bad2[0]["threshold"] = float("inf")
        with self.assertRaises(ValueError):
            evaluation.form_episodes(bad2, cfg)


class AdapterTest(unittest.TestCase):
    def test_inclusive_to_half_open(self):
        out = evaluation.inclusive_events_to_half_open([
            {"event_id": "a", "start": 2, "stop": 4},
            {"event_id": "b", "start": 5, "stop": 5},
        ])
        self.assertEqual(out, [
            {"event_id": "a", "start": 2, "stop": 5},
            {"event_id": "b", "start": 5, "stop": 6},
        ])

    def test_point_labels_basic_and_short(self):
        out = evaluation.events_from_point_labels([0, 1, 1, 0, 1], start_index=10)
        self.assertEqual(out, [
            {"event_id": "event-0", "start": 11, "stop": 13},
            {"event_id": "event-1", "start": 14, "stop": 15},
        ])

    def test_point_labels_reject_empty_bool_missing(self):
        with self.assertRaises(ValueError):
            evaluation.events_from_point_labels([])
        with self.assertRaises(TypeError):
            evaluation.events_from_point_labels([0, True, 1])
        with self.assertRaises((TypeError, ValueError)):
            evaluation.events_from_point_labels([0, 2, 1])
        with self.assertRaises((TypeError, ValueError)):
            evaluation.events_from_point_labels([0, None, 1])


class EvaluateTest(unittest.TestCase):
    def test_reference_graph_recall_precision_durations(self):
        # Horizon [0,12), window 2, stride 1 -> ends 1..11 (11 decisions).
        # Episodes A=[1,3) B=[4,6) C=[7,8) D=[9,10) E=[11,12) false.
        cfg = _config(horizon=(0, 12), window_length=2, stride=1)
        states = ["alert", "alert", "normal", "alert", "alert", "normal",
                  "alert", "normal", "alert", "normal", "alert"]
        rows = _rows(cfg, states)
        labels = _labels((0, 12), [
            ("E1", 1, 3), ("E2", 4, 5), ("E3", 5, 6), ("E4", 7, 10),
        ])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual([(e["start"], e["stop"]) for e in out["episodes"]],
                         [(1, 3), (4, 6), (7, 8), (9, 10), (11, 12)])
        by_id = {m["event_id"]: m for m in out["matches"]}
        self.assertEqual(by_id["E1"]["matching_episode_ids"], ["episode-0"])
        self.assertEqual(by_id["E2"]["matching_episode_ids"], ["episode-1"])
        self.assertEqual(by_id["E3"]["matching_episode_ids"], ["episode-1"])
        self.assertEqual(sorted(by_id["E4"]["matching_episode_ids"]),
                         ["episode-2", "episode-3"])
        self.assertEqual(by_id["E1"]["delay"], 0)
        self.assertEqual(by_id["E4"]["delay"], 0)
        self.assertEqual(out["metrics"]["event_recall"]["numerator"], 4)
        self.assertEqual(out["metrics"]["event_recall"]["denominator"], 4)
        self.assertEqual(out["metrics"]["episode_precision"]["numerator"], 4)
        self.assertEqual(out["metrics"]["episode_precision"]["denominator"], 5)
        self.assertEqual(out["metrics"]["false_alert_episodes"], 1)
        # Durations: total 2+2+1+1+1=7; union [1,3)+[4,6)+[7,10)=7; non-event 1.
        self.assertEqual(out["metrics"]["total_alert_duration"]["value"], 7)
        self.assertEqual(out["metrics"]["non_event_alert_duration"]["value"], 1)
        self.assertEqual(out["metrics"]["warmup_duration"]["value"], 1)
        self.assertEqual(out["metrics"]["decision_count"], 11)
        text = json.dumps(out, sort_keys=True, allow_nan=False)
        self.assertIn("metric_definition_id", out)

    def test_alert_strictly_before_onset_zero_delay(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        states = ["alert", "alert", "normal", "normal", "normal",
                  "normal", "normal", "normal", "normal"]
        rows = _rows(cfg, states)
        # Episode [1,3) starts strictly before onset 2 yet overlaps.
        labels = _labels((0, 10), [("e0", 2, 4)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual(out["matches"][0]["recalled"], True)
        self.assertEqual(out["matches"][0]["delay"], 0)

    def test_first_window_event_miss_despite_first_alert(self):
        cfg = _config(horizon=(0, 10), window_length=4, stride=1)
        # first decision 3; first input window [0,4); event [0,2) ends
        # before the window closes even though decision at 3 alerts.
        rows = _rows(cfg, ["alert"] + ["normal"] * 6)
        labels = _labels((0, 10), [("e0", 0, 2)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual([(e["start"], e["stop"]) for e in out["episodes"]], [(3, 4)])
        self.assertEqual(out["matches"][0]["recalled"], False)
        self.assertIsNone(out["matches"][0]["delay"])

    def test_prefix_stable_when_future_rows_appended(self):
        pre_cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        pre_rows = _rows(pre_cfg, ["alert", "alert", "normal", "alert", "alert"])
        pre_eps = evaluation.form_episodes(pre_rows, pre_cfg)
        full_cfg = _config(horizon=(0, 8), window_length=2, stride=1)
        full_rows = _rows(full_cfg, ["alert", "alert", "normal", "alert", "alert",
                                     "normal", "normal"])
        full_eps = evaluation.form_episodes(full_rows, full_cfg)
        self.assertEqual(full_eps[:len(pre_eps)], pre_eps)
        self.assertEqual([(e["start"], e["stop"]) for e in full_eps], [(1, 3), (4, 6)])

    def test_clipped_event_delay_uses_original_onset(self):
        cfg = _config(horizon=(5, 12), window_length=2, stride=1)
        # ends 6..11; alert only at 8 -> episode [8,9).
        rows = _rows(cfg, ["normal", "normal", "alert", "normal", "normal", "normal"])
        labels = _labels((0, 15), [("e0", 2, 9)])
        out = evaluation.evaluate(rows, labels, cfg)
        m = out["matches"][0]
        self.assertEqual((m["clipped_start"], m["clipped_stop"]), (5, 9))
        self.assertEqual((m["original_start"], m["original_stop"]), (2, 9))
        self.assertEqual(m["delay"], 6)

    def test_diagnostics_scope_zeros_units_and_per1000_rate(self):
        cfg = _config(horizon=(0, 12), window_length=2, stride=1)
        states = ["alert", "alert", "normal", "alert", "alert", "normal",
                  "alert", "normal", "alert", "normal", "alert"]
        rows = _rows(cfg, states)
        labels = _labels((0, 12), [
            ("E1", 1, 3), ("E2", 4, 5), ("E3", 5, 6), ("E4", 7, 10),
        ])
        out = evaluation.evaluate(rows, labels, cfg)
        d = out["diagnostics"]
        self.assertEqual(d["invalid_rows"], 0)
        self.assertEqual(d["excluded_rows"], 0)
        self.assertEqual(d["missing_rows"], 0)
        self.assertEqual(d["missing_policy"], "reject")
        self.assertEqual(out["metrics"]["delay"]["unit"], "sample_index")
        per1k = out["metrics"]["alert_episode_rate_per_1000_decisions"]
        self.assertEqual(per1k["numerator"], 5)
        self.assertEqual(per1k["denominator"], 11)
        self.assertAlmostEqual(per1k["value"], 5 / 11 * 1000)
        self.assertEqual(per1k["unit"], "episodes_per_1000_decisions")
        json.dumps(out, sort_keys=True, allow_nan=False)

    def test_positive_delay(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        states = ["normal", "normal", "normal", "normal", "alert",
                  "normal", "normal", "normal", "normal"]
        rows = _rows(cfg, states)
        labels = _labels((0, 10), [("e0", 2, 9)])
        out = evaluation.evaluate(rows, labels, cfg)
        # episode [5,6) overlaps [2,9): delay 5-2=3
        delays = {m["event_id"]: m["delay"] for m in out["matches"]}
        self.assertEqual(delays["e0"], 3)

    def test_active_at_onset_zero_delay(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        states = ["alert", "normal", "normal", "normal", "normal",
                  "normal", "normal", "normal", "normal"]
        rows = _rows(cfg, states)
        labels = _labels((0, 10), [("e0", 1, 4)])
        out = evaluation.evaluate(rows, labels, cfg)
        delays = {m["event_id"]: m["delay"] for m in out["matches"]}
        self.assertEqual(delays["e0"], 0)

    def test_event_ends_before_alert_miss(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        states = ["normal", "normal", "normal", "normal", "alert",
                  "normal", "normal", "normal", "normal"]
        rows = _rows(cfg, states)
        labels = _labels((0, 10), [("e0", 1, 3)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual(out["metrics"]["event_recall"]["value"], 0.0)
        self.assertEqual(out["matches"][0]["recalled"], False)
        self.assertIsNone(out["matches"][0]["delay"])

    def test_zero_alerts_null_precision(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["normal"] * 5)
        out = evaluation.evaluate(rows, _labels((0, 6), [("e0", 1, 2)]), cfg)
        self.assertIsNone(out["metrics"]["episode_precision"]["value"])
        self.assertEqual(out["metrics"]["episode_precision"]["denominator"], 0)

    def test_zero_events_null_recall(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["alert"] + ["normal"] * 4)
        out = evaluation.evaluate(rows, _labels((0, 6), []), cfg)
        self.assertIsNone(out["metrics"]["event_recall"]["value"])
        self.assertEqual(out["metrics"]["event_recall"]["denominator"], 0)
        self.assertIsNone(out["metrics"]["delay"]["mean"])

    def test_always_alert_duration_volume(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["alert"] * 5)
        out = evaluation.evaluate(rows, _labels((0, 6), []), cfg)
        self.assertEqual(len(out["episodes"]), 1)
        self.assertEqual(out["metrics"]["total_alert_duration"]["value"], 5)
        self.assertEqual(out["metrics"]["alerted_window_fraction"]["value"], 1.0)
        self.assertEqual(out["metrics"]["decision_coverage"]["value"], 1.0)
        self.assertEqual(out["metrics"]["deferral_rate"]["value"], 0.0)

    def test_one_episode_two_events(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        rows = _rows(cfg, ["alert"] * 9)
        labels = _labels((0, 10), [("e0", 2, 3), ("e1", 5, 6)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual(len(out["episodes"]), 1)
        self.assertEqual(out["metrics"]["event_recall"]["value"], 1.0)
        self.assertEqual(out["metrics"]["episode_precision"]["value"], 1.0)

    def test_two_episodes_one_event(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        states = ["alert", "normal", "normal", "normal", "alert",
                  "normal", "normal", "normal", "normal"]
        rows = _rows(cfg, states)
        labels = _labels((0, 10), [("e0", 1, 6)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual(len(out["episodes"]), 2)
        m = out["matches"][0]
        self.assertEqual(m["recalled"], True)
        self.assertEqual(sorted(m["matching_episode_ids"]), ["episode-0", "episode-1"])
        self.assertEqual(m["delay"], 0)

    def test_boundary_touching_no_overlap(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        states = ["normal", "normal", "normal", "normal", "alert",
                  "normal", "normal", "normal", "normal"]
        rows = _rows(cfg, states)
        # episode [5,6); event ends exactly at 5 -> touching, no overlap
        labels = _labels((0, 10), [("e0", 2, 5)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual(out["matches"][0]["recalled"], False)

    def test_overlapping_union_duration(self):
        cfg = _config(horizon=(0, 10), window_length=2, stride=1)
        rows = _rows(cfg, ["alert"] * 9)
        labels = _labels((0, 10), [("e0", 1, 5), ("e1", 3, 7)])
        out = evaluation.evaluate(rows, labels, cfg)
        # union [1,7) length 6; total alert [1,10) length 9; non-event 3
        self.assertEqual(out["metrics"]["total_alert_duration"]["value"], 9)
        self.assertEqual(out["metrics"]["non_event_alert_duration"]["value"], 3)

    def test_warmup_event_miss_and_clipping(self):
        cfg = _config(horizon=(2, 10), window_length=4, stride=2)
        # first = 5; ends 5,7,9 ; warmup [2,5) length 3
        rows = _rows(cfg, ["normal", "normal", "normal"])
        labels = _labels((0, 12), [("e1", 0, 5), ("e0", 2, 4), ("e2", 9, 14)])
        out = evaluation.evaluate(rows, labels, cfg)
        # e0 finishes before alert -> miss; e1 clipped, original onset 0 kept;
        # e2 clipped to [9,10)
        self.assertEqual(out["events"]["excluded_count"], 0)
        self.assertEqual(out["events"]["clipped_count"], 2)
        clipped = {e["event_id"]: (e["start"], e["stop"]) for e in out["events"]["clipped"]}
        self.assertEqual(clipped["e2"], (9, 10))
        orig = {e["event_id"]: (e["start"], e["stop"]) for e in out["events"]["original"]}
        self.assertEqual(orig["e1"], (0, 5))

    def test_excluded_events_and_coverage_rejection(self):
        cfg = _config(horizon=(2, 10), window_length=2, stride=1)
        rows = _rows(cfg, ["normal"] * 7)
        labels = _labels((2, 10), [("e1", 3, 4), ("e0", 20, 25)])
        out = evaluation.evaluate(rows, labels, cfg)
        self.assertEqual(out["events"]["excluded_count"], 1)
        self.assertEqual(out["metrics"]["event_recall"]["denominator"], 1)
        with self.assertRaises(ValueError):
            evaluation.evaluate(rows, _labels((3, 10), [("e1", 3, 4)]), cfg)

    def test_rejects_bad_labels(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["normal"] * 5)
        with self.assertRaises(ValueError):
            evaluation.evaluate(rows, _labels((0, 6), [("e0", 3, 3)]), cfg)
        with self.assertRaises(ValueError):
            evaluation.evaluate(rows, _labels((0, 6), [("e0", 4, 2)]), cfg)
        dup = _labels((0, 6), [("e0", 1, 2), ("e0", 3, 4)])
        with self.assertRaises(ValueError):
            evaluation.evaluate(rows, dup, cfg)
        unsorted = _labels((0, 6), [("e0", 3, 4), ("e1", 1, 2)])
        with self.assertRaises(ValueError):
            evaluation.evaluate(rows, unsorted, cfg)

    def test_deferred_duration_and_rates(self):
        cfg = _config(horizon=(0, 6), window_length=2, stride=1)
        rows = _rows(cfg, ["alert", "defer", "normal", "defer", "normal"])
        out = evaluation.evaluate(rows, _labels((0, 6), []), cfg)
        m = out["metrics"]
        self.assertAlmostEqual(m["alerted_window_fraction"]["value"], 1 / 5)
        self.assertAlmostEqual(m["decision_coverage"]["value"], 3 / 5)
        self.assertAlmostEqual(m["deferral_rate"]["value"], 2 / 5)
        self.assertEqual(m["deferred_duration"]["value"], 2)
        self.assertIn("sample_index", m["alert_episode_rate"]["unit"])
        self.assertIn("sample_index", m["total_alert_duration"]["unit"])

    def test_input_immutability(self):
        cfg = _config()
        rows = _rows(cfg, ["alert", "normal", "alert", "normal", "alert",
                           "normal", "alert", "normal", "alert"])
        labels = _labels((0, 10), [("e0", 1, 2)])
        rc, lc, cc = copy.deepcopy(rows), copy.deepcopy(labels), copy.deepcopy(cfg)
        evaluation.evaluate(rows, labels, cfg)
        evaluation.form_episodes(rows, cfg)
        self.assertEqual(rows, rc)
        self.assertEqual(labels, lc)
        self.assertEqual(cfg, cc)

    def test_strict_json_and_keys(self):
        import tempfile
        cfg = _config()
        rows = _rows(cfg, ["alert", "normal", "alert", "normal", "alert",
                           "normal", "alert", "normal", "alert"])
        labels = _labels((0, 10), [("e0", 1, 2)])
        out = evaluation.evaluate(rows, labels, cfg)
        for key in ("metric_definition_id", "config", "episodes", "events",
                    "matches", "metrics", "diagnostics"):
            self.assertIn(key, out)
        text = json.dumps(out, sort_keys=True, allow_nan=False)
        with __import__("tempfile").TemporaryDirectory(dir=str(REPO)) as tmp:
            p = Path(tmp) / "eval.json"
            p.write_text(text)
            self.assertEqual(json.loads(p.read_text()), out)


if __name__ == "__main__":
    unittest.main()
