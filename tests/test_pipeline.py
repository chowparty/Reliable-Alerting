"""Day-01 synthetic pipeline integration (label-free, stdlib unittest)."""
import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from reliable_alerting import pipeline  # noqa: E402


def base_config():
    return {
        "schema_version": 1,
        "input": {
            "kind": "synthetic_periodic_v1",
            "length": 96,
            "pattern": [9, 10, 11, 10, 10, 11, 12, 11, 8, 9, 10, 9, 10, 10, 10, 10],
            "offsets": [
                {"start": 72, "stop": 80, "offset": 2},
                {"start": 88, "stop": 96, "offset": -3},
            ],
        },
        "segments": {"source_fit": [0, 32], "calibration": [32, 64], "replay": [64, 96]},
        "window": {
            "length": 4,
            "stride": 4,
            "anchor": "segment_start",
            "edge_policy": "drop_incomplete",
            "end_index": "inclusive",
        },
        "scoring": {
            "kind": "mean_distance",
            "epsilon": 1e-6,
            "fit_scope": "source_fit",
            "standard_deviation": "population",
        },
        "calibration": {
            "kind": "fixed_quantile",
            "quantile": 0.95,
            "method": "nearest_rank",
            "min_samples": 2,
            "score_segment": "calibration",
        },
        "policy": {"kind": "fixed_threshold", "comparison": "strict_greater"},
        "missing_policy": "reject",
        "source_label_use": "none",
        "time_basis": "sample_index",
        "held_out": "not_reserved_or_evaluated",
    }


def strip_run(rows):
    out = []
    for r in rows:
        d = dict(r)
        d.pop("run_id", None)
        out.append(d)
    return out


class ComputeTraceTest(unittest.TestCase):
    def test_public_api_is_label_free(self):
        self.assertTrue(hasattr(pipeline, "compute_trace"))
        params = __import__("inspect").signature(pipeline.compute_trace).parameters
        self.assertIn("config", params)
        for bad in ("label", "labels"):
            self.assertNotIn(bad, params)

    def test_repeat_compute_same_rows(self):
        a = pipeline.compute_trace(base_config())
        b = pipeline.compute_trace(base_config())
        self.assertEqual(strip_run(a["rows"]), strip_run(b["rows"]))
        self.assertEqual(a["config_id"], b["config_id"])
        self.assertEqual(a["rows"][0]["config_id"], a["config_id"])
        # rows carry no run_id (run_id added only at write time)
        for r in a["rows"]:
            self.assertNotIn("run_id", r)
        self.assertGreater(len(a["rows"]), 0)
        self.assertIn("calibration_rows", a)
        self.assertGreater(len(a["calibration_rows"]), 0)

    def test_write_and_reload_config_rerun(self):
        cfg = base_config()
        first = pipeline.compute_trace(cfg)
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out1 = str(Path(tmp) / "run-a")
            out2 = str(Path(tmp) / "run-b")
            run1 = pipeline.write_output(cfg, first, out1)
            run2 = pipeline.write_output(cfg, pipeline.compute_trace(cfg), out2)
            self.assertNotEqual(run1, run2)
            with open(Path(out1) / "predictions.csv", newline="") as fh:
                rows1 = list(csv.DictReader(fh))
            with open(Path(out2) / "predictions.csv", newline="") as fh:
                rows2 = list(csv.DictReader(fh))
            s1 = [{k: v for k, v in r.items() if k != "run_id"} for r in rows1]
            s2 = [{k: v for k, v in r.items() if k != "run_id"} for r in rows2]
            self.assertEqual(s1, s2)
            self.assertNotEqual(rows1[0]["run_id"], rows2[0]["run_id"])
            # reload saved config and rerun
            with open(Path(out1) / "config.json") as fh:
                saved = json.load(fh)
            third = pipeline.compute_trace(saved)
            self.assertEqual(strip_run(third["rows"]), strip_run(first["rows"]))

    def test_mutate_replay_leaves_earlier_rows_and_cutoff(self):
        cfg = base_config()
        before = pipeline.compute_trace(cfg)
        n = len(before["rows"])
        mutated_values = list(before["values"])
        # mutate inside replay tail (last window) only
        mutated_values[-1] += 25.0
        after = pipeline.compute_trace(cfg, values=mutated_values)
        self.assertEqual(after["scorer"]["mean"], before["scorer"]["mean"])
        self.assertEqual(after["scorer"]["std"], before["scorer"]["std"])
        self.assertEqual(after["threshold"], before["threshold"])
        self.assertEqual(strip_run(after["rows"])[: n - 1], strip_run(before["rows"])[: n - 1])
        self.assertNotEqual(
            strip_run(after["rows"])[n - 1], strip_run(before["rows"])[n - 1]
        )

    def test_mutate_calibration_changes_cutoff_not_source_fit(self):
        cfg = base_config()
        before = pipeline.compute_trace(cfg)
        vals = list(before["values"])
        # mutate inside calibration segment [32,64)
        vals[40] += 30.0
        after = pipeline.compute_trace(cfg, values=vals)
        self.assertEqual(after["scorer"], before["scorer"])
        self.assertNotEqual(after["threshold"], before["threshold"])

    def test_label_file_ignored(self):
        cfg = base_config()
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            lab = Path(tmp) / "labels.csv"
            lab.write_text("window_id,label\nreplay:64:67,0\n")
            first = pipeline.compute_trace(cfg)
            out1 = str(Path(tmp) / "run-l1")
            pipeline.write_output(cfg, first, out1)
            with open(Path(out1) / "predictions.csv", newline="") as fh:
                rows1 = list(csv.DictReader(fh))
            # change label file contents, run again, persisted predictions
            # must be identical ignoring run_id
            lab.write_text("window_id,label\nreplay:64:67,1\n")
            lab.write_text(lab.read_text() + "replay:68:71,1\n")
            second = pipeline.compute_trace(cfg)
            out2 = str(Path(tmp) / "run-l2")
            pipeline.write_output(cfg, second, out2)
            with open(Path(out2) / "predictions.csv", newline="") as fh:
                rows2 = list(csv.DictReader(fh))
            s1 = [{k: v for k, v in r.items() if k != "run_id"} for r in rows1]
            s2 = [{k: v for k, v in r.items() if k != "run_id"} for r in rows2]
            self.assertEqual(s1, s2)

    def test_schema_rejects_labels(self):
        for key in ("labels", "label", "y_true"):
            bad = base_config()
            bad[key] = [0, 1]
            with self.assertRaises((KeyError, ValueError, TypeError), msg=key):
                pipeline.compute_trace(bad)
            bad2 = base_config()
            bad2["input"] = dict(bad2["input"])
            bad2["input"][key] = 1
            with self.assertRaises((KeyError, ValueError, TypeError), msg=key):
                pipeline.compute_trace(bad2)

    def test_boundary_nonalignment_drops_tail(self):
        cfg = base_config()
        cfg["segments"] = {"source_fit": [0, 30], "calibration": [30, 62], "replay": [62, 96]}
        got = pipeline.compute_trace(cfg)
        diag = got["diagnostics"]
        # 30 samples with length-4 stride-4 -> 7 windows, 2 dropped tail samples
        self.assertEqual(diag["segments"]["source_fit"]["window_count"], 7)
        self.assertEqual(diag["segments"]["source_fit"]["dropped_tail"], 2)

    def test_unknown_and_invalid_inputs_fail(self):
        bad = base_config()
        bad["window"] = dict(bad["window"])
        bad["window"]["bogus"] = 1
        with self.assertRaises((KeyError, ValueError, TypeError)):
            pipeline.compute_trace(bad)
        missing = base_config()
        del missing["policy"]
        with self.assertRaises((KeyError, ValueError, TypeError)):
            pipeline.compute_trace(missing)
        bad_enum = base_config()
        bad_enum["window"] = dict(bad_enum["window"])
        bad_enum["window"]["anchor"] = "sliding"
        with self.assertRaises((ValueError, TypeError)):
            pipeline.compute_trace(bad_enum)
        bad_bool = base_config()
        bad_bool["input"] = dict(bad_bool["input"])
        bad_bool["input"]["length"] = True
        with self.assertRaises((TypeError, ValueError)):
            pipeline.compute_trace(bad_bool)
        with self.assertRaises((TypeError, ValueError)):
            pipeline.compute_trace(base_config(), values=[1.0, float("nan")] + [1.0] * 94)
        # non-contiguous segments
        gap = base_config()
        gap["segments"] = {"source_fit": [0, 32], "calibration": [33, 64], "replay": [64, 96]}
        with self.assertRaises(ValueError):
            pipeline.compute_trace(gap)

    def test_diagnostics_label_free_and_warmup(self):
        got = pipeline.compute_trace(base_config())
        diag = got["diagnostics"]
        for seg in ("source_fit", "calibration", "replay"):
            info = diag["segments"][seg]
            for k in ("bounds", "window_count", "first_end", "last_end", "dropped_tail"):
                self.assertIn(k, info)
        self.assertEqual(diag["warmup_samples"], 3)
        self.assertIn("alert_count", diag)
        self.assertIn("alert_fraction", diag)
        self.assertIn("decision_coverage", diag)
        blob = json.dumps(diag, allow_nan=False).lower()
        self.assertNotIn("accuracy", blob)
        self.assertNotIn("label", blob)
        self.assertNotIn("episode", blob)

    def test_write_rejects_values_override(self):
        cfg = base_config()
        base = pipeline.compute_trace(cfg)
        vals = list(base["values"])
        vals[70] += 25.0
        forged = pipeline.compute_trace(cfg, values=vals)
        # same config_id (config unchanged) but rows come from override values;
        # write path persists only the synthetic recipe, so must reject.
        self.assertEqual(forged["config_id"], base["config_id"])
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run-override")
            with self.assertRaises(ValueError):
                pipeline.write_output(cfg, forged, out)
            self.assertFalse(Path(out).exists())

    def test_write_rejects_forged_score_and_diagnostics(self):
        cfg = base_config()
        good = pipeline.compute_trace(cfg)
        bad = copy.deepcopy(good)
        # forge one replay score while keeping state consistent so the
        # low-level writer would accept it; pipeline recomputation must not.
        thr = float(bad["rows"][0]["threshold"])
        bad["rows"][0]["score"] = thr + 5.0
        bad["rows"][0]["output_state"] = "alert"
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run-forged")
            with self.assertRaises(ValueError):
                pipeline.write_output(cfg, bad, out)
            self.assertFalse(Path(out).exists())
        bad2 = copy.deepcopy(good)
        bad2["diagnostics"] = dict(bad2["diagnostics"])
        bad2["diagnostics"]["alert_count"] = int(bad2["diagnostics"]["alert_count"]) + 1
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run-forged2")
            with self.assertRaises(ValueError):
                pipeline.write_output(cfg, bad2, out)
            self.assertFalse(Path(out).exists())

    def test_metadata_resource_scope(self):
        cfg = base_config()
        trace = pipeline.compute_trace(cfg)
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "run-scope")
            pipeline.write_output(cfg, trace, out)
            with open(Path(out) / "metadata.json") as fh:
                meta = json.load(fh)
            self.assertEqual(meta.get("resource_scope"), "validated_compute_trace_only")
            self.assertIn("started_at_scope", meta)
            self.assertIn("elapsed_monotonic_seconds", meta)
            self.assertIn("peak_python_allocation_bytes", meta)

    def test_provenance_missing_hash_raises(self):
        from reliable_alerting import provenance

        with mock.patch.object(Path, "is_file", return_value=False):
            with self.assertRaises((FileNotFoundError, RuntimeError, ValueError)):
                provenance.file_hashes(REPO)

    def test_provenance_symlink_hash_raises(self):
        from reliable_alerting import provenance

        real = provenance.file_hashes(REPO)
        self.assertGreater(len(real), 0)
        with mock.patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises((RuntimeError, ValueError)):
                provenance.file_hashes(REPO)

    def test_provenance_git_failure_raises(self):
        from reliable_alerting import provenance

        with mock.patch("subprocess.run", side_effect=FileNotFoundError("no git")):
            with self.assertRaises(RuntimeError):
                provenance.git_record(str(REPO))

    def test_cli_writes_expected_artifacts(self):
        cfg_path = REPO / "configs" / "day01-synthetic.json"
        self.assertTrue(cfg_path.is_file())
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            out = str(Path(tmp) / "cli-run")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.pipeline",
                 "--config", str(cfg_path), "--output", out],
                cwd=str(REPO),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            for name in ("predictions.csv", "calibration_scores.csv", "config.json",
                         "metadata.json", "diagnostics.json"):
                self.assertTrue((Path(out) / name).is_file(), msg=name)
            with open(Path(out) / "metadata.json") as fh:
                meta = json.load(fh)
            self.assertIn("run_id", meta)
            self.assertIn("config_id", meta)
            self.assertIn("command", meta)
            self.assertIn("shell", meta["command"])
            self.assertIn("cwd", meta["command"])
            self.assertIn("started_at", meta)
            self.assertIn("elapsed_monotonic_seconds", meta)
            self.assertIn("peak_python_allocation_bytes", meta)
            blob = json.dumps(meta).lower()
            self.assertNotIn("peak ram", blob)
            # run_id differs per execution
            out2 = str(Path(tmp) / "cli-run2")
            proc2 = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.pipeline",
                 "--config", str(cfg_path), "--output", out2],
                cwd=str(REPO),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc2.returncode, 0, msg=proc2.stderr[-2000:])
            with open(Path(out2) / "metadata.json") as fh:
                meta2 = json.load(fh)
            self.assertNotEqual(meta["run_id"], meta2["run_id"])
            self.assertEqual(meta["config_id"], meta2["config_id"])


if __name__ == "__main__":
    unittest.main()
