"""test_family_table.py - tests for research/family_table.py (Nakul, Day 4).

Verifies the five-policy family table assembles from the saved evaluation
outputs, carries every required metric with denominators, applies the
predeclared criteria as flags (not gates), that one row's episodes recompute
independently from the saved decision trace, and that every episode traces
back to a contiguous alert run in the decisions file.

Skips cleanly if the five evaluation directories are absent.
"""
import json
import sys
import unittest
from pathlib import Path

# reliable_alerting imports directly (editable install). Add the sibling
# research/ folder so the Nakul module below resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "research"))

import family_table as ft  # noqa: E402

_BTP_ROOT = Path(__file__).resolve().parents[1]
_RESULT_ROOT = _BTP_ROOT / "result"
_EVAL_CONFIG_PATH = (_BTP_ROOT / "configs"
                     / "day04-valve1-evaluation.json")


def _eval_config():
    with open(_EVAL_CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _all_present():
    if not _EVAL_CONFIG_PATH.is_file():
        return False
    for pol in ft.POLICIES:
        if not (_RESULT_ROOT / "valve1" / pol / "evaluation"
                / "evaluation.json").is_file():
            return False
    return True


_SKIP = not _all_present()


@unittest.skipIf(_SKIP, "five valve1 evaluation outputs or eval config absent")
class FamilyTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = _eval_config()
        cls.table = ft.build_family_table(str(_RESULT_ROOT), cls.cfg)

    def test_five_rows_one_per_policy(self):
        self.assertEqual([r["policy"] for r in self.table["rows"]],
                         list(ft.POLICIES))

    def test_required_metrics_with_denominators_present(self):
        for r in self.table["rows"]:
            for ratio in ("event_recall", "episode_precision",
                          "alerted_window_fraction", "decision_coverage",
                          "deferral_rate"):
                self.assertIn("numerator", r[ratio], f"{r['policy']} {ratio}")
                self.assertIn("denominator", r[ratio], f"{r['policy']} {ratio}")
                self.assertIn("value", r[ratio], f"{r['policy']} {ratio}")
            self.assertIn("false_alert_episodes", r)
            self.assertIn("alert_episode_rate_per_1000_decisions", r)
            # delay carries misses separately
            self.assertIn("missed_count", r["delay"])
            self.assertIn("recalled_count", r["delay"])
            # timing carries explicit scope, not bare latency
            self.assertIn("source_run_scope", r["timing"])
            self.assertIn("evaluation_scope", r["timing"])

    def test_criteria_are_the_fixed_values(self):
        c = self.table["criteria"]
        self.assertEqual(c["episode_rate_budget_per_1000_decisions"], 70.0)
        self.assertEqual(c["coverage_floor"], 1.0)
        self.assertEqual(c["role"], "reporting_criteria_not_rejection_gates")

    def test_feasibility_is_flag_not_gate(self):
        # Every policy stays in the table regardless of feasibility.
        self.assertEqual(len(self.table["rows"]), len(ft.POLICIES))
        for r in self.table["rows"]:
            self.assertIn("feasible", r["feasibility"])
            self.assertIn("reasons", r["feasibility"])
            # feasibility must be consistent with the row's own values
            over_budget = (r["alert_episode_rate_per_1000_decisions"]
                           > 70.0)
            under_floor = (r["decision_coverage"]["value"] < 1.0)
            expected = not (over_budget or under_floor)
            self.assertEqual(r["feasibility"]["feasible"], expected,
                             f"{r['policy']} feasibility flag inconsistent")

    def test_independent_recompute_matches_table_episodes(self):
        # Recompute episodes for each policy from the SAVED decision trace and
        # compare to the episodes the table took from evaluation.json.
        for r in self.table["rows"]:
            recomputed = ft.independent_recompute(
                str(_RESULT_ROOT), r["policy"], self.cfg)
            self.assertEqual(
                [(e["start"], e["stop"]) for e in recomputed],
                [(e["start"], e["stop"]) for e in r["episodes"]],
                f"{r['policy']}: recomputed episodes != table episodes")

    def test_every_episode_traces_to_alert_decisions(self):
        for pol in ft.POLICIES:
            reports = ft.trace_episodes_to_decisions(str(_RESULT_ROOT), pol)
            for rep in reports:
                self.assertTrue(rep["traced_ok"],
                                f"{pol} {rep['episode_id']} did not trace to "
                                f"a contiguous alert run: {rep}")

    def test_table_precision_matches_saved_evaluation(self):
        # Audit: assembled numbers equal the saved evaluation.json values.
        for pol in ft.POLICIES:
            edir = _RESULT_ROOT / "valve1" / pol / "evaluation"
            ev = json.loads((edir / "evaluation.json").read_text(encoding="utf-8"))
            row = next(r for r in self.table["rows"] if r["policy"] == pol)
            self.assertEqual(row["false_alert_episodes"],
                             ev["metrics"]["false_alert_episodes"])
            self.assertEqual(row["event_recall"]["value"],
                             ev["metrics"]["event_recall"]["value"])
            self.assertEqual(row["episode_precision"]["value"],
                             ev["metrics"]["episode_precision"]["value"])
            self.assertEqual(row["alert_episode_rate_per_1000_decisions"],
                             ev["metrics"]["alert_episode_rate_per_1000_decisions"]["value"])


class FeasibilityHelperTest(unittest.TestCase):
    """assess_feasibility flags but never rejects; independent of saved data."""

    def test_within_budget_and_floor_feasible(self):
        f = ft.assess_feasibility(50.0, 1.0)
        self.assertTrue(f["feasible"])
        self.assertEqual(f["reasons"], [])

    def test_over_budget_flagged(self):
        f = ft.assess_feasibility(120.0, 1.0)
        self.assertFalse(f["feasible"])
        self.assertTrue(any("episode rate" in r for r in f["reasons"]))

    def test_under_floor_flagged(self):
        f = ft.assess_feasibility(10.0, 0.9)
        self.assertFalse(f["feasible"])
        self.assertTrue(any("coverage" in r for r in f["reasons"]))

    def test_at_budget_boundary_is_feasible(self):
        # <= 70 is within budget
        self.assertTrue(ft.assess_feasibility(70.0, 1.0)["feasible"])


if __name__ == "__main__":
    unittest.main()