"""Decision calibration / policy / run-writer checks.

Exercises the real FixedQuantile / FixedThresholdPolicy / write_run
components with hand-computed values. No labels flow through runtime paths.
"""
import csv
import dataclasses
import inspect
import json
import math
import tempfile
import unittest
from pathlib import Path

from reliable_alerting import calibration, policy, writing

REPO = Path(__file__).resolve().parents[1]


def _valid_rows():
    return [
        {
            "window_id": "seg:0:1",
            "start_index": 0,
            "end_index": 1,
            "score": 0.5,
            "output_state": "normal",
            "threshold": 1.0,
            "config_id": "cfg",
            "run_id": "run1",
        },
        {
            "window_id": "seg:2:3",
            "start_index": 2,
            "end_index": 3,
            "score": 2.5,
            "output_state": "alert",
            "threshold": 1.0,
            "config_id": "cfg",
            "run_id": "run1",
        },
    ]


def _valid_calibration():
    return [
        {"window_id": "cal:0:1", "start_index": 0, "end_index": 1, "score": 0.2},
        {"window_id": "cal:2:3", "start_index": 2, "end_index": 3, "score": 0.9},
    ]


class FixedQuantileTest(unittest.TestCase):
    def test_hand_quantile_half_of_four(self):
        got = calibration.FixedQuantile.fit([1, 2, 3, 4], quantile=0.5)
        self.assertEqual(got.threshold, 2.0)
        self.assertEqual(got.quantile, 0.5)
        self.assertEqual(got.sample_count, 4)
        self.assertEqual(got.method, "nearest_rank")

    def test_quantile_one_gives_max(self):
        got = calibration.FixedQuantile.fit([3, 1, 2], quantile=1.0)
        self.assertEqual(got.threshold, 3.0)

    def test_no_interpolation(self):
        # ceil(0.75*4)=3 -> third smallest = 3.0 (linear interpolation: 3.25).
        got = calibration.FixedQuantile.fit([1, 2, 3, 4], quantile=0.75)
        self.assertEqual(got.threshold, 3.0)

    def test_retains_duplicates(self):
        got = calibration.FixedQuantile.fit([5, 5, 5, 10], quantile=0.5)
        self.assertEqual(got.threshold, 5.0)

    def test_default_quantile(self):
        params = inspect.signature(calibration.FixedQuantile.fit).parameters
        self.assertAlmostEqual(params["quantile"].default, 0.95)
        self.assertEqual(params["min_samples"].default, 2)

    def test_frozen_and_fields(self):
        got = calibration.FixedQuantile.fit([1, 2], quantile=0.5)
        self.assertEqual(
            [f.name for f in dataclasses.fields(calibration.FixedQuantile)],
            ["threshold", "quantile", "sample_count", "method"],
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            got.threshold = 0.0

    def test_rejects_empty_and_nonfinite(self):
        with self.assertRaises(ValueError):
            calibration.FixedQuantile.fit([])
        for bad in ([float("nan"), 1.0], [1.0, float("inf")], [float("-inf")]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                calibration.FixedQuantile.fit(bad)

    def test_rejects_bool_and_missing_scores(self):
        with self.assertRaises((TypeError, ValueError)):
            calibration.FixedQuantile.fit([1.0, True])
        with self.assertRaises((TypeError, ValueError)):
            calibration.FixedQuantile.fit([None, 1.0])
        with self.assertRaises((TypeError, ValueError)):
            calibration.FixedQuantile.fit(["1", 2.0])
        with self.assertRaises(TypeError):
            calibration.FixedQuantile.fit(None)

    def test_rejects_shortage(self):
        with self.assertRaises(ValueError):
            calibration.FixedQuantile.fit([1.0], quantile=0.5)
        with self.assertRaises(ValueError):
            calibration.FixedQuantile.fit([1.0, 2.0], quantile=0.5, min_samples=3)

    def test_rejects_bad_quantile(self):
        for bad in (0, -0.1, 1.5, 2.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=repr(bad)):
                calibration.FixedQuantile.fit([1.0, 2.0], quantile=bad)
        for bad in (True, False, None, "0.9"):
            with self.assertRaises(TypeError, msg=repr(bad)):
                calibration.FixedQuantile.fit([1.0, 2.0], quantile=bad)

    def test_rejects_bad_min_samples(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError, msg=repr(bad)):
                calibration.FixedQuantile.fit([1.0, 2.0], min_samples=bad)
        for bad in (True, False, 2.5, "2", None):
            with self.assertRaises(TypeError, msg=repr(bad)):
                calibration.FixedQuantile.fit([1.0, 2.0], min_samples=bad)

    def test_accepts_no_labels(self):
        params = inspect.signature(calibration.FixedQuantile.fit).parameters
        self.assertNotIn("labels", params)
        self.assertNotIn("label", params)


class FixedThresholdPolicyTest(unittest.TestCase):
    def test_ties_are_normal(self):
        pol = policy.FixedThresholdPolicy(threshold=2.0)
        self.assertEqual(pol.decide(2.0), "normal")
        self.assertEqual(pol.decide(1.9), "normal")
        self.assertEqual(pol.decide(2.0001), "alert")

    def test_frozen(self):
        pol = policy.FixedThresholdPolicy(threshold=1.0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            pol.threshold = 0.0

    def test_rejects_bad_threshold(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=repr(bad)):
                policy.FixedThresholdPolicy(threshold=bad)
        for bad in (True, False, None, "1.0"):
            with self.assertRaises(TypeError, msg=repr(bad)):
                policy.FixedThresholdPolicy(threshold=bad)

    def test_rejects_bad_score(self):
        pol = policy.FixedThresholdPolicy(threshold=1.0)
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=repr(bad)):
                pol.decide(bad)
        for bad in (None, True, False, "1.0", object()):
            with self.assertRaises(TypeError, msg=repr(bad)):
                pol.decide(bad)

    def test_accepts_no_labels(self):
        self.assertNotIn("label", inspect.signature(policy.FixedThresholdPolicy.decide).parameters)
        self.assertNotIn("labels", inspect.signature(policy.FixedThresholdPolicy.decide).parameters)


class WriteRunTest(unittest.TestCase):
    def test_roundtrip_schema_and_json(self):
        rows = _valid_rows()
        calib = _valid_calibration()
        config = {"threshold": 1.0}
        metadata = {"source": "synthetic"}
        diagnostics = {"n": 2}
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run1")
            writing.write_run(out, rows, config, metadata, diagnostics, calib)
            out_p = Path(out)
            self.assertTrue((out_p / "predictions.csv").is_file())
            self.assertTrue((out_p / "config.json").is_file())
            self.assertTrue((out_p / "metadata.json").is_file())
            self.assertTrue((out_p / "diagnostics.json").is_file())
            self.assertTrue((out_p / "calibration_scores.csv").is_file())
            with open(out_p / "predictions.csv", newline="") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                self.assertEqual(
                    header,
                    ["window_id", "start_index", "end_index", "score",
                     "output_state", "threshold", "config_id", "run_id"],
                )
                body = list(reader)
            self.assertEqual(len(body), 2)
            self.assertEqual(body[0][0], "seg:0:1")
            self.assertEqual(body[0][4], "normal")
            self.assertEqual(body[1][4], "alert")
            with open(out_p / "calibration_scores.csv", newline="") as fh:
                reader = csv.reader(fh)
                cheader = next(reader)
                self.assertEqual(cheader, ["window_id", "start_index", "end_index", "score"])
                cbody = list(reader)
            self.assertEqual(len(cbody), 2)
            for path, expected in (
                ("config.json", config),
                ("metadata.json", metadata),
                ("diagnostics.json", diagnostics),
            ):
                with open(out_p / path) as fh:
                    self.assertEqual(json.load(fh), expected)

    def test_no_output_on_validation_failure(self):
        rows = _valid_rows()
        bad = [dict(rows[0], window_id="duplicate"), dict(rows[1], window_id="duplicate")]
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run-bad")
            with self.assertRaises(ValueError):
                writing.write_run(out, bad, {}, {}, {}, _valid_calibration())
            self.assertFalse(Path(out).exists())

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run1")
            writing.write_run(out, _valid_rows(), {"a": 1}, {}, {}, _valid_calibration())
            marker = Path(out) / "predictions.csv"
            before = marker.read_text()
            with self.assertRaises(FileExistsError):
                writing.write_run(out, _valid_rows(), {"a": 2}, {}, {}, _valid_calibration())
            self.assertEqual(marker.read_text(), before)

    def test_rejects_extra_missing_keys(self):
        base = _valid_rows()
        extra = [dict(base[0], extra_col=1), dict(base[1])]
        missing = [dict(base[0]), dict(base[1])]
        del missing[0]["score"]
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            with self.assertRaises(ValueError):
                writing.write_run(str(Path(tmp) / "a"), extra, {}, {}, {}, _valid_calibration())
            with self.assertRaises(ValueError):
                writing.write_run(str(Path(tmp) / "b"), missing, {}, {}, {}, _valid_calibration())

    def test_rejects_bad_ids_indices_and_states(self):
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            i = 0

            def _run(rows):
                nonlocal i
                i += 1
                with self.assertRaises(ValueError):
                    writing.write_run(
                        str(Path(tmp) / f"bad-{i}"), rows, {}, {}, {}, _valid_calibration()
                    )
                self.assertFalse((Path(tmp) / f"bad-{i}").exists())

            base = _valid_rows()
            _run([dict(base[0], window_id=""), dict(base[1])])
            _run([dict(base[0], start_index=-1), dict(base[1])])
            _run([dict(base[0], start_index=2, end_index=1), dict(base[1])])
            _run([dict(base[0], score=float("nan")), dict(base[1])])
            _run([dict(base[0], threshold=float("inf")), dict(base[1])])
            _run([dict(base[0], output_state="ALERT"), dict(base[1])])
            dup = [dict(base[0]), dict(base[0])]
            _run(dup)
            non_increasing = [dict(base[0]), dict(base[1], end_index=1)]
            _run(non_increasing)
            mismatch = [dict(base[0]), dict(base[1], config_id="other")]
            _run(mismatch)
            mismatch_run = [dict(base[0]), dict(base[1], run_id="other")]
            _run(mismatch_run)

    def test_rejects_bad_calibration(self):
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            with self.assertRaises(ValueError):
                writing.write_run(str(Path(tmp) / "c0"), _valid_rows(), {}, {}, {}, [])
            bad_label = [dict(_valid_calibration()[0], label=0), dict(_valid_calibration()[1])]
            with self.assertRaises(ValueError):
                writing.write_run(str(Path(tmp) / "c1"), _valid_rows(), {}, {}, {}, bad_label)
            bad_score = [dict(_valid_calibration()[0], score=float("nan")),
                         dict(_valid_calibration()[1])]
            with self.assertRaises(ValueError):
                writing.write_run(str(Path(tmp) / "c2"), _valid_rows(), {}, {}, {}, bad_score)

    def test_signature_has_no_labels(self):
        params = inspect.signature(writing.write_run).parameters
        self.assertEqual(
            list(params),
            ["output_dir", "rows", "config", "metadata", "diagnostics",
             "calibration_rows", "action_rows"],
        )
        # action_rows is the optional label-free per-decision action log; it
        # must default to None so existing callers are unaffected.
        self.assertIsNone(params["action_rows"].default)
        self.assertNotIn("labels", params)
        self.assertNotIn("label", params)


if __name__ == "__main__":
    unittest.main()
