"""test_audit_code.py - tests for research/audit.py (Nakul, Day 3).

Confirms that no runtime component (scorer, five policies, compute_trace,
loader) exposes a label parameter, and that the CSV loader reads only the
configured value column. Uses the read-only import bridge in conftest.py.
"""
import csv
import json
import sys
import unittest
from pathlib import Path

# reliable_alerting imports directly (editable install). Add the sibling
# research/ folder so the Nakul module below resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "research"))

import audit  # noqa: E402


class SignatureHelperTest(unittest.TestCase):
    def test_flags_label_param(self):
        def bad(score, labels):  # noqa: ANN001
            return score
        ok, offending = audit.signature_has_no_label_param(bad)
        self.assertFalse(ok)
        self.assertEqual(offending, ["labels"])

    def test_passes_clean_signature(self):
        def good(score, threshold):  # noqa: ANN001
            return score
        ok, offending = audit.signature_has_no_label_param(good)
        self.assertTrue(ok)
        self.assertEqual(offending, [])


class RuntimeLabelFreedomTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit.audit_runtime_label_freedom()

    def test_all_runtime_components_label_free(self):
        offenders = {name: info["offending"]
                     for name, info in self.report.items() if not info["ok"]}
        self.assertEqual(offenders, {},
                         f"runtime components expose label params: {offenders}")

    def test_expected_components_were_inspected(self):
        # Guard against the audit silently inspecting nothing.
        for required in (
            "scoring.MeanDistanceScorer.score",
            "policy.FixedThresholdPolicy.decide",
            "policy.RollingThresholdPolicy.decide",
            "policy.KConsecutivePolicy.decide",
            "policy.MOfNPolicy.decide",
            "policy.HysteresisPolicy.decide",
            "pipeline.compute_trace",
            "loading.load_csv_stream",
        ):
            self.assertIn(required, self.report)

    def test_compute_trace_has_no_label_param(self):
        self.assertTrue(self.report["pipeline.compute_trace"]["ok"])
        # positive detail: its params are the known label-free set
        self.assertNotIn("labels", self.report["pipeline.compute_trace"]["params"])


class LoaderValueColumnTest(unittest.TestCase):
    def test_loader_reads_only_value_column(self):
        ok, reason = audit.loader_returns_only_value_column()
        self.assertTrue(ok, reason)


class FeatureSpotCheckTest(unittest.TestCase):
    """Task 3 (Day 5): recompute the median feature column from raw scores and
    confirm it matches the saved trace, driving the same teammate component."""

    def test_synthetic_median_recompute_matches(self):
        # Build rows where we know the causal rolling median (length 5).
        from reliable_alerting import diagnostics_features
        scores = [0.5, 1.0, 0.2, 0.8, 0.4, 2.0, 0.1]
        feat = diagnostics_features.RollingMedianFeature(5)
        rows = [{"score": s, "features": [feat.update(s), 0.0]} for s in scores]
        ok, n, mismatch = audit.recompute_median_feature_from_scores(rows)
        self.assertTrue(ok, mismatch)
        self.assertEqual(n, len(scores))

    def test_detects_tampered_median_column(self):
        from reliable_alerting import diagnostics_features
        scores = [0.5, 1.0, 0.2, 0.8, 0.4]
        feat = diagnostics_features.RollingMedianFeature(5)
        rows = [{"score": s, "features": [feat.update(s), 0.0]} for s in scores]
        rows[3]["features"][0] += 0.5  # tamper
        ok, n, mismatch = audit.recompute_median_feature_from_scores(rows)
        self.assertFalse(ok)
        self.assertEqual(mismatch["index"], 3)

    def test_saved_valve1_median_column_recomputes(self):
        _BTP_ROOT = Path(__file__).resolve().parents[1]
        pred = (_BTP_ROOT / "result" / "valve1"
                / "fixed_threshold" / "predictions.csv")
        if not pred.is_file():
            self.skipTest("valve1 fixed_threshold predictions.csv absent")
        rows = []
        with open(pred, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append({"score": float(r["score"]),
                             "features": json.loads(r["features"])})
        ok, n, mismatch = audit.recompute_median_feature_from_scores(rows)
        self.assertTrue(ok, mismatch)
        self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main()