"""Evaluation persistence/evidence integration (TDD, stdlib unittest).

Why: saved predictions are joined with labels only after the run is
verified; episodes form from predictions before labels are consulted.
All temps stay inside the repo.
"""
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
            "length": 4, "stride": 4, "anchor": "segment_start",
            "edge_policy": "drop_incomplete", "end_index": "inclusive",
        },
        "scoring": {
            "kind": "mean_distance", "epsilon": 1e-6,
            "fit_scope": "source_fit", "standard_deviation": "population",
        },
        "calibration": {
            "kind": "fixed_quantile", "quantile": 0.95,
            "method": "nearest_rank", "min_samples": 2,
            "score_segment": "calibration",
        },
        "policy": {"kind": "fixed_threshold", "comparison": "strict_greater"},
        "missing_policy": "reject",
        "source_label_use": "none",
        "time_basis": "sample_index",
        "held_out": "not_reserved_or_evaluated",
    }


def eval_config():
    with open(REPO / "configs" / "day02-evaluation.json") as fh:
        return json.load(fh)


def make_run(tmp, name="run"):
    cfg = base_config()
    trace = pipeline.compute_trace(cfg)
    out = str(Path(tmp) / name)
    pipeline.write_output(cfg, trace, out)
    return out


class RoundtripTest(unittest.TestCase):
    def test_pipeline_writer_evaluation_roundtrip_expected_scores(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            res = evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            self.assertTrue((Path(out) / "evaluation.json").is_file())
            self.assertTrue((Path(out) / "config.json").is_file())
            self.assertTrue((Path(out) / "labels.json").is_file())
            self.assertTrue((Path(out) / "metadata.json").is_file())
            core = res["core"] if isinstance(res, dict) and "core" in res else res
            eps = [(e["start"], e["stop"]) for e in core["episodes"]]
            self.assertEqual(eps, [(79, 83), (91, 96)])
            self.assertEqual(core["metrics"]["event_recall"]["numerator"], 2)
            self.assertEqual(core["metrics"]["event_recall"]["denominator"], 2)
            self.assertEqual(core["metrics"]["event_recall"]["value"], 1.0)
            self.assertEqual(core["metrics"]["episode_precision"]["numerator"], 2)
            self.assertEqual(core["metrics"]["episode_precision"]["denominator"], 2)
            self.assertEqual(core["metrics"]["episode_precision"]["value"], 1.0)
            delays = {m["event_id"]: m["delay"] for m in core["matches"]}
            self.assertEqual(delays, {"offset-up": 7, "offset-down": 3})
            self.assertEqual(core["metrics"]["total_alert_duration"]["value"], 9)
            self.assertEqual(core["metrics"]["non_event_alert_duration"]["value"], 3)

    def test_evaluate_saved_predictions_reusable(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            core = evaluation_io.evaluate_saved_predictions(
                str(Path(run) / "predictions.csv"),
                str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                eval_config())
            eps = [(e["start"], e["stop"]) for e in core["episodes"]]
            self.assertEqual(eps, [(79, 83), (91, 96)])

    def test_label_changes_do_not_change_predictions_scorer_policy(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            with open(Path(run) / "predictions.csv", "rb") as fh:
                before = fh.read()
            with open(Path(run) / "diagnostics.json") as fh:
                diag_before = json.load(fh)
            alt = {"schema_version": 1, "time_basis": "sample_index",
                   "coverage": [64, 96],
                   "events": [{"event_id": "x", "start": 64, "stop": 68}]}
            alt_p = str(Path(tmp) / "alt.json")
            with open(alt_p, "w") as fh:
                fh.write(json.dumps(alt, sort_keys=True, indent=2, allow_nan=False) + "\n")
            evaluation_io.evaluate_saved_predictions(
                str(Path(run) / "predictions.csv"), alt_p, eval_config())
            with open(Path(run) / "predictions.csv", "rb") as fh:
                after = fh.read()
            self.assertEqual(before, after)
            with open(Path(run) / "diagnostics.json") as fh:
                diag_after = json.load(fh)
            self.assertEqual(diag_before["scorer"], diag_after["scorer"])
            self.assertEqual(diag_before["quantile"], diag_after["quantile"])

    def test_two_fresh_runs_equal_eval_despite_run_id(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a = make_run(tmp, "a")
            b = make_run(tmp, "b")
            ca = evaluation_io.evaluate_saved_predictions(
                str(Path(a) / "predictions.csv"),
                str(REPO / "tests/fixtures/day02-synthetic-labels.json"), eval_config())
            cb = evaluation_io.evaluate_saved_predictions(
                str(Path(b) / "predictions.csv"),
                str(REPO / "tests/fixtures/day02-synthetic-labels.json"), eval_config())
            # strip run_id-dependent? core has no run_id; must be exactly equal
            self.assertEqual(ca, cb)
            # semantic predictions equal excluding run_id, file hashes differ
            ra = evaluation_io.semantic_predictions_hash(
                evaluation_io.load_predictions_generic(str(Path(a) / "predictions.csv")))
            rb = evaluation_io.semantic_predictions_hash(
                evaluation_io.load_predictions_generic(str(Path(b) / "predictions.csv")))
            self.assertEqual(ra, rb)

    def test_future_append_earlier_stable(self):
        from reliable_alerting import evaluation
        pre_cfg = {"schema_version": 1, "time_basis": "sample_index",
                   "horizon": [0, 6], "first_decision": 1,
                   "decision_stride": 1, "window_length": 2}
        full_cfg = {"schema_version": 1, "time_basis": "sample_index",
                    "horizon": [0, 8], "first_decision": 1,
                    "decision_stride": 1, "window_length": 2}

        def _rows(cfg, states):
            h0, h1 = cfg["horizon"]
            first, stride, wlen = cfg["first_decision"], cfg["decision_stride"], cfg["window_length"]
            ends = []
            k = 0
            while first + k * stride < h1:
                ends.append(first + k * stride)
                k += 1
            rows = []
            for i, (e, st) in enumerate(zip(ends, states)):
                rows.append({"window_id": f"w:{i}", "start_index": e - wlen + 1,
                             "end_index": e, "score": 2.5 if st == "alert" else 0.1,
                             "output_state": st, "threshold": 1.0,
                             "config_id": "c", "run_id": "r"})
            return rows
        pre = _rows(pre_cfg, ["alert", "alert", "normal", "alert", "alert"])
        full = _rows(full_cfg, ["alert", "alert", "normal", "alert", "alert",
                                "normal", "normal"])
        pre_eps = evaluation.form_episodes(pre, pre_cfg)
        full_eps = evaluation.form_episodes(full, full_cfg)
        self.assertEqual(full_eps[:len(pre_eps)], pre_eps)


class GenericLoaderTest(unittest.TestCase):
    def test_generic_accepts_defer_varying_threshold(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            p = str(Path(tmp) / "pred.csv")
            header = ["window_id", "start_index", "end_index", "score",
                      "output_state", "threshold", "config_id", "run_id"]
            with open(p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(header)
                w.writerow(["w:0", 0, 1, 0.1, "defer", 1.0, "c", "r"])
                w.writerow(["w:1", 1, 2, 2.5, "alert", 9.0, "c", "r"])
            rows = evaluation_io.load_predictions_generic(p)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["output_state"], "defer")

    def test_fixed_validator_still_rejects_defer(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            p = str(Path(tmp) / "pred.csv")
            with open(p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["window_id", "start_index", "end_index", "score",
                            "output_state", "threshold", "config_id", "run_id"])
                w.writerow(["w:0", 0, 1, 0.1, "defer", 1.0, "c", "r"])
            with self.assertRaises((TypeError, ValueError)):
                evidence.load_predictions_csv(p)


class StrictJsonTest(unittest.TestCase):
    def test_rejects_nan_infinity_duplicate_keys(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            for bad in ('{"a": NaN}', '{"a": Infinity}'):
                p = Path(tmp) / "bad.json"
                p.write_text(bad)
                with self.assertRaises(ValueError):
                    evaluation_io.load_strict_json(str(p))
            dup = '{"a": 1, "a": 2}'
            p = Path(tmp) / "dup.json"
            p.write_text(dup)
            with self.assertRaises(ValueError):
                evaluation_io.load_strict_json(str(p))

    def test_write_rejects_nonfinite(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            # tamper labels with NaN via raw write then run CLI helper should refuse?
            # direct: strict writer refuses NaN
            with self.assertRaises(ValueError):
                evaluation_io.write_strict_json(str(Path(tmp) / "o.json"), {"a": float("nan")})


class ScheduleMismatchTest(unittest.TestCase):
    def test_schedule_mismatch_fails_before_side_effects(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            bad_cfg = dict(eval_config())
            bad_cfg["horizon"] = [0, 10]
            bad_p = str(Path(tmp) / "badcfg.json")
            with open(bad_p, "w") as fh:
                fh.write(json.dumps(bad_cfg, sort_keys=True, indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "eval")
            with self.assertRaises(ValueError):
                evaluation_io.run_evaluation(
                    run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                    bad_p, out)
            self.assertFalse(Path(out).exists())


class OverwriteTest(unittest.TestCase):
    def test_overwrite_refused_before_side_effects(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            before = sorted(p.name for p in Path(out).iterdir())
            with self.assertRaises(FileExistsError):
                evaluation_io.run_evaluation(
                    run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                    str(REPO / "configs/day02-evaluation.json"), out)
            self.assertEqual(sorted(p.name for p in Path(out).iterdir()), before)


class TamperTest(unittest.TestCase):
    def test_tampered_metric_detected_and_both_forged(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            a = str(Path(tmp) / "ea")
            b = str(Path(tmp) / "eb")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), a)
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), b)
            # forge same metric in both
            for d in (a, b):
                p = Path(d) / "evaluation.json"
                doc = json.loads(p.read_text())
                doc["metrics"]["event_recall"]["value"] = 0.0
                p.write_text(json.dumps(doc, sort_keys=True, indent=2, allow_nan=False) + "\n")
            rep = evidence.compare_evaluations(a, b)
            self.assertFalse(rep["status"])
            self.assertFalse(rep["scientific_equal"])
            # single tamper also fails
            c = str(Path(tmp) / "ec")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), c)
            out = str(Path(tmp) / "cmp.json")
            rep2 = evidence.compare_evaluations(a, c)
            self.assertFalse(rep2["status"])

    def test_tampered_labels_predictions_hashes_detected(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            a = str(Path(tmp) / "ea")
            b = str(Path(tmp) / "eb")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), a)
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), b)
            # tamper labels copy in b
            lp = Path(b) / "labels.json"
            doc = json.loads(lp.read_text())
            doc["events"][0]["start"] = 65
            lp.write_text(json.dumps(doc, sort_keys=True, indent=2, allow_nan=False) + "\n")
            rep = evidence.compare_evaluations(a, b)
            self.assertFalse(rep["status"])

    def test_predictions_before_labels_ordering(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            # corrupt predictions header, missing labels file: must raise predictions error first
            p = Path(run) / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                bad = dict(rows[0])
                bad["output_state"] = "bogus"
                w.writerow(bad)
                for r in rows[1:]:
                    w.writerow(r)
            with self.assertRaises((TypeError, ValueError)):
                evaluation_io.evaluate_saved_predictions(
                    str(p), str(Path(tmp) / "missing-labels.json"), eval_config())


class ProvenanceTest(unittest.TestCase):
    def test_command_launcher_rerun_shell_uses_venv_unresolved(self):
        from reliable_alerting import provenance
        rec = provenance.command_record()
        self.assertIn("rerun_shell", rec)
        self.assertIn("shell", rec)
        self.assertIn("orig_argv", rec)
        self.assertIn("cwd", rec)
        # must use sys.executable without resolving symlink
        self.assertEqual(rec.get("rerun_executable"), sys.executable)
        self.assertIn(sys.executable, rec["rerun_shell"])
        self.assertIn(".venv", sys.executable)
        # launched subprocess uses same environment interpreter
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; print(sys.executable)"],
            cwd=str(REPO), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(".venv", proc.stdout)

    def test_whitelist_covers_new_files(self):
        from reliable_alerting import provenance
        for rel in ("src/reliable_alerting/evaluation_io.py",
                    "configs/day02-evaluation.json",
                    "tests/test_evaluation_io.py",
                    "tests/fixtures/day02-synthetic-labels.json",
                    "report/outline.md"):
            self.assertIn(rel, provenance.WHITELIST)
            self.assertTrue((REPO / rel).is_file(), msg=rel)
        hashes = provenance.file_hashes(REPO)
        for rel in ("src/reliable_alerting/evaluation_io.py",
                    "configs/day02-evaluation.json",
                    "tests/fixtures/day02-synthetic-labels.json"):
            self.assertIn(rel, hashes)

    def test_metadata_provenance_fields(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            meta = json.loads((Path(out) / "metadata.json").read_text())
            for k in ("input_predictions_file_sha256", "semantic_predictions_sha256",
                      "label_file_sha256", "semantic_label_sha256",
                      "evaluation_config_id", "evaluator_id",
                      "source_run", "command", "environment", "git",
                      "file_hashes", "elapsed_monotonic_seconds",
                      "peak_python_allocation_bytes", "resource_scope"):
                self.assertIn(k, meta, msg=k)
            self.assertIn("rerun_shell", meta["command"])
            blob = json.dumps(meta).lower()
            self.assertNotIn("peak ram", blob)
            self.assertNotIn("latency", blob)


class CliTest(unittest.TestCase):
    def test_cli_and_evidence_compare_figure(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evaluation_io",
                 "--run", run,
                 "--labels", str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                 "--config", str(REPO / "configs/day02-evaluation.json"),
                 "--output", out],
                cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue((Path(out) / "evaluation.json").is_file())
            # second eval for compare
            out2 = str(Path(tmp) / "eval2")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evaluation_io",
                 "--run", run,
                 "--labels", str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                 "--config", str(REPO / "configs/day02-evaluation.json"),
                 "--output", out2],
                cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            from reliable_alerting import evidence
            rep = evidence.compare_evaluations(out, out2)
            self.assertTrue(rep["status"])
            self.assertTrue(rep["scientific_equal"])
            svg = str(Path(tmp) / "eval.svg")
            proc3 = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "evaluation-figure", out, "--output", svg],
                cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(proc3.returncode, 0, msg=proc3.stderr[-2000:])
            self.assertTrue(Path(svg).is_file())
            blob = Path(svg).read_text().lower()
            self.assertIn("synthetic", blob)
            self.assertIn("sample_index", blob)


class ForgedRunMetadataTest(unittest.TestCase):
    def test_forged_metadata_run_id_rejected_before_labels(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            with open(Path(run) / "metadata.json") as fh:
                meta = json.load(fh)
            meta["run_id"] = "forged-run-id"
            with open(Path(run) / "metadata.json", "w") as fh:
                fh.write(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "eval")
            with self.assertRaises(ValueError):
                evaluation_io.run_evaluation(
                    run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                    str(REPO / "configs/day02-evaluation.json"), out)
            self.assertFalse(Path(out).exists())

    def test_forged_metadata_config_id_rejected_before_labels(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            with open(Path(run) / "metadata.json") as fh:
                meta = json.load(fh)
            meta["config_id"] = "0" * 64
            with open(Path(run) / "metadata.json", "w") as fh:
                fh.write(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "eval")
            with self.assertRaises(ValueError):
                evaluation_io.run_evaluation(
                    run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                    str(REPO / "configs/day02-evaluation.json"), out)
            self.assertFalse(Path(out).exists())

    def test_forged_metadata_input_hash_rejected_before_labels(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            with open(Path(run) / "metadata.json") as fh:
                meta = json.load(fh)
            meta["input_hash"] = "0" * 64
            with open(Path(run) / "metadata.json", "w") as fh:
                fh.write(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "eval")
            with self.assertRaises(ValueError):
                evaluation_io.run_evaluation(
                    run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                    str(REPO / "configs/day02-evaluation.json"), out)
            self.assertFalse(Path(out).exists())


class ResourceScopeTest(unittest.TestCase):
    def test_scope_names_validation_and_hashing_span(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            res = evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            meta = res["metadata"]
            self.assertEqual(
                meta["resource_scope"],
                "saved_run_validation_recompute_and_evaluation_excluding_output")
            self.assertIn("resource_description", meta)
            self.assertIn("recompute", meta["resource_description"])
            self.assertEqual(meta.get("evaluated_decision_count"), 8)
            self.assertEqual(meta.get("created_at_scope"), "evaluation_io_entry")

    def test_entry_timestamp_precedes_output_files(self):
        from reliable_alerting import evaluation_io
        from datetime import datetime
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            res = evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            created = datetime.fromisoformat(res["metadata"]["created_at"])
            mtime = datetime.fromtimestamp(
                (Path(out) / "metadata.json").stat().st_mtime).astimezone()
            self.assertLessEqual(created, mtime)


class RawIntegrityTest(unittest.TestCase):
    def test_eval_copy_run_id_forgery_detected(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            p = Path(out) / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            for r in rows:
                r["run_id"] = "forged-run"
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            ev = evidence._read_evaluation(out)
            diffs = []
            self.assertFalse(evidence._verify_evaluation_recompute("x", ev, diffs))

    def test_eval_source_run_linkage_forgery_detected(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            mp = Path(out) / "metadata.json"
            meta = json.loads(mp.read_text())
            meta["source_run"]["run_id"] = "forged"
            mp.write_text(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n")
            ev = evidence._read_evaluation(out)
            diffs = []
            self.assertFalse(evidence._verify_evaluation_recompute("x", ev, diffs))

    def test_distinct_label_checksums_saved(self):
        from reliable_alerting import evaluation_io
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            res = evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            meta = res["metadata"]
            self.assertIn("persisted_labels_file_sha256", meta)
            self.assertIn("persisted_predictions_file_sha256", meta)
            self.assertEqual(
                meta["label_file_sha256"],
                evaluation_io.file_sha256(
                    str(REPO / "tests/fixtures/day02-synthetic-labels.json")))
            self.assertEqual(
                meta["persisted_labels_file_sha256"],
                evaluation_io.file_sha256(str(Path(out) / "labels.json")))
            self.assertEqual(
                meta["persisted_predictions_file_sha256"],
                evaluation_io.file_sha256(str(Path(out) / "predictions.csv")))


class StrictRunJsonTest(unittest.TestCase):
    def test_run_config_duplicate_keys_rejected(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            raw = (Path(run) / "config.json").read_text()
            dup = raw.replace('"schema_version": 1',
                              '"schema_version": 1, "schema_version": 1', 1)
            (Path(run) / "config.json").write_text(dup)
            with self.assertRaises(ValueError):
                evidence._read_run(run)

    def test_run_metadata_duplicate_keys_rejected(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            with open(Path(run) / "metadata.json") as fh:
                meta = json.load(fh)
            rid = meta["run_id"]
            raw = (Path(run) / "metadata.json").read_text()
            dup = raw.replace(f'"run_id": "{rid}"',
                              f'"run_id": "{rid}", "run_id": "dup-{rid}"', 1)
            self.assertNotEqual(dup, raw)
            (Path(run) / "metadata.json").write_text(dup)
            with self.assertRaisesRegex(ValueError, "duplicate object key"):
                evidence._read_run(run)


class PartialOutputTest(unittest.TestCase):
    def test_provenance_failure_leaves_no_partial_output(self):
        from unittest import mock
        from reliable_alerting import evaluation_io, provenance
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            with mock.patch.object(
                    provenance, "file_hashes",
                    side_effect=RuntimeError("simulated provenance failure")):
                with self.assertRaises(RuntimeError):
                    evaluation_io.run_evaluation(
                        run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                        str(REPO / "configs/day02-evaluation.json"), out)
            self.assertFalse(Path(out).exists())


class ProvenanceValidityTest(unittest.TestCase):
    def test_stripped_provenance_fails_status_but_keeps_scientific(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            a = str(Path(tmp) / "ea")
            b = str(Path(tmp) / "eb")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), a)
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), b)
            mp = Path(b) / "metadata.json"
            meta = json.loads(mp.read_text())
            del meta["environment"]
            mp.write_text(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n")
            rep = evidence.compare_evaluations(a, b)
            self.assertFalse(rep["provenance_valid"])
            self.assertFalse(rep["status"])
            self.assertTrue(rep["scientific_equal"])

    def test_figure_refuses_missing_provenance(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            out = str(Path(tmp) / "eval")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), out)
            mp = Path(out) / "metadata.json"
            meta = json.loads(mp.read_text())
            del meta["git"]
            mp.write_text(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n")
            with self.assertRaises(ValueError):
                evidence.render_evaluation_figure(out, str(Path(tmp) / "o.svg"))
            self.assertFalse((Path(tmp) / "o.svg").exists())

    def test_compare_reports_variable_fields(self):
        from reliable_alerting import evaluation_io
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            run = make_run(tmp)
            a = str(Path(tmp) / "ea")
            b = str(Path(tmp) / "eb")
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), a)
            evaluation_io.run_evaluation(
                run, str(REPO / "tests/fixtures/day02-synthetic-labels.json"),
                str(REPO / "configs/day02-evaluation.json"), b)
            rep = evidence.compare_evaluations(a, b)
            self.assertIn("varying_metadata", rep)
            for k in ("eval_id", "created_at", "elapsed_monotonic_seconds",
                      "source_run_path", "source_run_id"):
                self.assertIn(k, rep["varying_metadata"])


if __name__ == "__main__":
    unittest.main()
