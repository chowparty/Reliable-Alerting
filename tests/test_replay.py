"""Day-04 replay/persistence: fixed + hysteresis replay over saved scores.

Why: one frozen source score run is replayed by two policies over the same
validated rows; predictions persist before labels are joined.
All temps stay inside the repo results dir (git-ignored).
"""
import copy
import csv
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from reliable_alerting import pipeline  # noqa: E402

PROTOCOL = REPO / "configs" / "day04-synthetic-family.json"
EVAL_CONFIG = REPO / "configs" / "day02-evaluation.json"
LABELS = REPO / "tests" / "fixtures" / "day02-synthetic-labels.json"


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


def make_source_run(tmp, name="source-run"):
    cfg = base_config()
    trace = pipeline.compute_trace(cfg)
    out = str(Path(tmp) / name)
    pipeline.write_output(cfg, trace, out)
    return out


def score_rows_of(run_dir):
    with open(Path(run_dir) / "predictions.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [
        {"window_id": r["window_id"], "start_index": int(r["start_index"]),
         "end_index": int(r["end_index"]), "score": float(r["score"])}
        for r in rows
    ]


def source_high_of(run_dir):
    with open(Path(run_dir) / "diagnostics.json") as fh:
        diag = json.load(fh)
    return float(diag["quantile"]["threshold"])


def low_recipe_config():
    """Small synthetic recipe whose replay scores hit low exactly.

    Found by search (seed 7): high=0.3656361051117249 and replay scores
    equal 0.8*high bit-for-bit. The [32,36) replay offset lifts only the
    first window above high (source/calibration untouched, high frozen),
    so hysteresis latches alert then faces score==low. Deterministic.
    """
    return {
        "schema_version": 1,
        "input": {
            "kind": "synthetic_periodic_v1",
            "length": 48,
            "pattern": [5, 11, 7, 4, 9, 1, 1, 8],
            "offsets": [{"start": 21, "stop": 24, "offset": 3},
                        {"start": 32, "stop": 36, "offset": 10}],
        },
        "segments": {"source_fit": [0, 16], "calibration": [16, 32],
                     "replay": [32, 48]},
        "window": {
            "length": 4, "stride": 4, "anchor": "segment_start",
            "edge_policy": "drop_incomplete", "end_index": "inclusive",
        },
        "scoring": {
            "kind": "mean_distance", "epsilon": 1e-6,
            "fit_scope": "source_fit", "standard_deviation": "population",
        },
        "calibration": {
            "kind": "fixed_quantile", "quantile": 0.9,
            "method": "nearest_rank", "min_samples": 2,
            "score_segment": "calibration",
        },
        "policy": {"kind": "fixed_threshold", "comparison": "strict_greater"},
        "missing_policy": "reject",
        "source_label_use": "none",
        "time_basis": "sample_index",
        "held_out": "not_reserved_or_evaluated",
    }


def low_recipe_eval_config():
    return {"schema_version": 1, "time_basis": "sample_index",
            "horizon": [32, 48], "first_decision": 35,
            "decision_stride": 4, "window_length": 4}


def low_recipe_labels():
    return {"schema_version": 1, "time_basis": "sample_index",
            "coverage": [32, 48], "events": []}


def make_low_source_run(tmp, name="low-source-run"):
    cfg = low_recipe_config()
    trace = pipeline.compute_trace(cfg)
    out = str(Path(tmp) / name)
    pipeline.write_output(cfg, trace, out)
    return out


def write_json(path, doc):
    with open(path, "w") as fh:
        fh.write(json.dumps(doc, sort_keys=True, indent=2,
                            allow_nan=False) + "\n")


class ReplayApiLabelFreeTest(unittest.TestCase):
    def test_replay_rows_is_label_free(self):
        from reliable_alerting import replay
        params = inspect.signature(replay.replay_rows).parameters
        for bad in ("label", "labels"):
            self.assertNotIn(bad, params)
        for good in ("score_rows", "policy_config", "config_id", "run_id"):
            self.assertIn(good, params)

    def test_fixed_replay_matches_strict_greater(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            high = source_high_of(run)
            scores = score_rows_of(run)
            fixed = {"kind": "fixed_threshold", "comparison": "strict_greater",
                     "threshold": high}
            got = replay.replay_rows(scores, fixed, "cid-fixed", "rid-fixed")
            self.assertEqual(len(got["predictions"]), 8)
            self.assertEqual(len(got["state"]), 8)
            for pred, s in zip(scores, got["predictions"]):
                want = "alert" if pred["score"] > high else "normal"
                self.assertEqual(s["output_state"], want)
            states = [p["output_state"] for p in got["predictions"]]
            self.assertEqual(
                states,
                ["normal", "normal", "normal", "alert",
                 "normal", "normal", "alert", "alert"])
            # equality at the threshold holds normal (strict)
            eq_idx = next(i for i, s in enumerate(scores) if s["score"] == high)
            self.assertEqual(got["predictions"][eq_idx]["output_state"], "normal")
            # fixed sidecar semantics: stateless, high == low == judging
            for entry, pred_row in zip(got["state"], got["predictions"]):
                self.assertEqual(entry["before_state"], "normal")
                self.assertEqual(entry["after_state"],
                                 pred_row["output_state"])
                self.assertEqual(entry["high"], high)
                self.assertEqual(entry["low"], high)
                self.assertEqual(entry["judging_threshold"], high)
                self.assertEqual(entry["comparator"], "strict_greater")

    def test_hysteresis_replay_latches_and_exits(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            high = source_high_of(run)
            low = 0.8 * high
            scores = score_rows_of(run)
            hyst = {"kind": "hysteresis", "low": low, "high": high}
            got = replay.replay_rows(scores, hyst, "cid-hyst", "rid-hyst")
            states = [p["output_state"] for p in got["predictions"]]
            # hand-derived: alert latches at 2.13, exits at 0.0 below low
            self.assertEqual(
                states,
                ["normal", "normal", "normal", "alert",
                 "normal", "normal", "alert", "alert"])
            # comparator refers to the exit under test
            for entry in got["state"]:
                if entry["before_state"] == "normal":
                    self.assertEqual(entry["comparator"], "strict_greater")
                    self.assertEqual(entry["judging_threshold"], high)
                else:
                    self.assertEqual(entry["comparator"], "strict_less")
                    self.assertEqual(entry["judging_threshold"], low)
            # threshold column carries the judging threshold per row
            for p, e in zip(got["predictions"], got["state"]):
                self.assertEqual(p["threshold"], e["judging_threshold"])

    def test_repeat_replay_from_fresh_state_agrees(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            high = source_high_of(run)
            scores = score_rows_of(run)
            hyst = {"kind": "hysteresis", "low": 0.8 * high, "high": high}
            a = replay.replay_rows(scores, copy.deepcopy(hyst), "c", "r")
            b = replay.replay_rows(scores, copy.deepcopy(hyst), "c", "r")
            self.assertEqual(a, b)

    def test_prefix_invariance_to_future_scores(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            high = source_high_of(run)
            scores = score_rows_of(run)
            hyst = {"kind": "hysteresis", "low": 0.8 * high, "high": high}
            prefix = scores[:4]
            full_a = replay.replay_rows(prefix, hyst, "c", "r")
            full_b = replay.replay_rows(scores, hyst, "c", "r")
            self.assertEqual(full_b["predictions"][:4], full_a["predictions"])
            self.assertEqual(full_b["state"][:4], full_a["state"])


class SourceIdentityTest(unittest.TestCase):
    def test_shared_scores_and_distinct_policy_ids(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            res = replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                    str(LABELS), fam)
            fixed_rows = replay.load_family_predictions(fam, "fixed")
            hyst_rows = replay.load_family_predictions(fam, "hysteresis")
            fixed_scores = [(r["window_id"], r["start_index"], r["end_index"],
                             r["score"]) for r in fixed_rows]
            hyst_scores = [(r["window_id"], r["start_index"], r["end_index"],
                            r["score"]) for r in hyst_rows]
            self.assertEqual(fixed_scores, hyst_scores)
            self.assertNotEqual(res["policies"]["fixed"]["config_id"],
                                res["policies"]["hysteresis"]["config_id"])
            self.assertNotEqual(res["source_scores_id"],
                                res["policies"]["fixed"]["config_id"])
            self.assertNotEqual(res["source_scores_id"],
                                res["policies"]["hysteresis"]["config_id"])

    def test_source_high_immutable(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            before = Path(run, "predictions.csv").read_bytes()
            high_before = source_high_of(run)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self.assertEqual(Path(run, "predictions.csv").read_bytes(), before)
            self.assertEqual(source_high_of(run), high_before)


class FamilyRoundtripTest(unittest.TestCase):
    def test_pipeline_writer_family_evaluator_roundtrip(self):
        from reliable_alerting import evaluation_io, replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            res = replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                    str(LABELS), fam)
            self.assertTrue((Path(fam) / "family_metadata.json").is_file())
            report = replay.load_family(fam)
            self.assertTrue(report["status"], msg=report.get("differences"))
            # fixed policy replays the frozen source decisions
            core = evaluation_io.evaluate_saved_predictions(
                str(Path(fam) / "fixed" / "predictions.csv"),
                str(LABELS), json.loads((EVAL_CONFIG).read_text()))
            eps = [(e["start"], e["stop"]) for e in core["episodes"]]
            self.assertEqual(eps, [(79, 83), (91, 96)])
            fam_eps = [(e["start"], e["stop"]) for e in
                       report["policies"]["fixed"]["evaluation"]["episodes"]]
            self.assertEqual(fam_eps, eps)

    def test_labels_mutation_leaves_decisions_fixed(self):
        from reliable_alerting import evaluation_io, replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            pred_path = Path(fam) / "fixed" / "predictions.csv"
            before = pred_path.read_bytes()
            alt = {"schema_version": 1, "time_basis": "sample_index",
                   "coverage": [64, 96],
                   "events": [{"event_id": "other", "start": 64, "stop": 68}]}
            alt_p = str(Path(tmp) / "alt.json")
            with open(alt_p, "w") as fh:
                fh.write(json.dumps(alt, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n")
            evaluation_io.evaluate_saved_predictions(
                str(pred_path), alt_p,
                json.loads(EVAL_CONFIG.read_text()))
            self.assertEqual(pred_path.read_bytes(), before)


class TamperMalformedTest(unittest.TestCase):
    def test_replay_rows_rejects_empty_score_rows(self):
        from reliable_alerting import replay
        with self.assertRaises(ValueError):
            replay.replay_rows(
                [], {"kind": "fixed_threshold",
                     "comparison": "strict_greater", "threshold": 1.0},
                "c", "r")

    def test_malformed_score_rows_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            high = source_high_of(run)
            scores = score_rows_of(run)
            fixed = {"kind": "fixed_threshold", "comparison": "strict_greater",
                     "threshold": high}
            dup = scores + [dict(scores[0])]
            with self.assertRaises(ValueError):
                replay.replay_rows(dup, fixed, "c", "r")
            unordered = list(reversed(scores))
            with self.assertRaises(ValueError):
                replay.replay_rows(unordered, fixed, "c", "r")
            bad = copy.deepcopy(scores)
            bad[0] = {"window_id": bad[0]["window_id"]}
            with self.assertRaises((TypeError, ValueError)):
                replay.replay_rows(bad, fixed, "c", "r")
            nonfinite = copy.deepcopy(scores)
            nonfinite[1]["score"] = float("nan")
            with self.assertRaises(ValueError):
                replay.replay_rows(nonfinite, fixed, "c", "r")
            extra = copy.deepcopy(scores)
            extra[0]["labels"] = [0]
            with self.assertRaises((TypeError, ValueError)):
                replay.replay_rows(extra, fixed, "c", "r")
            with self.assertRaises((TypeError, ValueError)):
                replay.replay_rows(scores, {"kind": "fixed_threshold",
                                            "comparison": "strict_greater",
                                            "threshold": high + 1.0,
                                            "labels": []}, "c", "r")

    def test_tampered_family_predictions_detected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            p = Path(fam) / "fixed" / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[0]["output_state"] = ("alert"
                                       if rows[0]["output_state"] == "normal"
                                       else "normal")
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            report = replay.load_family(fam)
            self.assertFalse(report["status"])

    def test_schedule_mismatch_fails_before_output(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            bad_cfg = json.loads(EVAL_CONFIG.read_text())
            bad_cfg["horizon"] = [0, 10]
            bad_p = str(Path(tmp) / "badcfg.json")
            with open(bad_p, "w") as fh:
                fh.write(json.dumps(bad_cfg, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n")
            out = str(Path(tmp) / "fam")
            with self.assertRaises(ValueError):
                replay.run_family(run, str(PROTOCOL), bad_p, str(LABELS), out)
            self.assertFalse(Path(out).exists())

    def test_nonstrict_protocol_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            dup = PROTOCOL.read_text().replace(
                '"schema_version": 1',
                '"schema_version": 1, "schema_version": 1', 1)
            dup_p = Path(tmp) / "dup-protocol.json"
            dup_p.write_text(dup)
            with self.assertRaises(ValueError):
                replay.run_family(run, str(dup_p), str(EVAL_CONFIG),
                                  str(LABELS), str(Path(tmp) / "fam"))
            self.assertFalse((Path(tmp) / "fam").exists())

    def test_strict_fixed_validator_still_rejects_threshold_equality_alert(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            p = str(Path(tmp) / "pred.csv")
            with open(p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["window_id", "start_index", "end_index", "score",
                            "output_state", "threshold", "config_id", "run_id"])
                w.writerow(["w:0", 0, 1, 1.5, "alert", 1.5, "c", "r"])
            with self.assertRaises(ValueError):
                evidence.load_predictions_csv(p)

    def test_no_overwrite(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            before = sorted(p.name for p in Path(fam).iterdir())
            with self.assertRaises(FileExistsError):
                replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                  str(LABELS), fam)
            self.assertEqual(sorted(p.name for p in Path(fam).iterdir()), before)


class ProvenanceCliTest(unittest.TestCase):
    def test_whitelist_covers_new_files(self):
        from reliable_alerting import provenance
        for rel in ("src/reliable_alerting/replay.py",
                    "tests/test_replay.py",
                    "tests/test_family_evidence.py",
                    "configs/day04-synthetic-family.json",
                    "tests/test_hysteresis.py"):
            self.assertIn(rel, provenance.WHITELIST)
            self.assertTrue((REPO / rel).is_file(), msg=rel)

    def test_family_metadata_provenance_and_checksums(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            meta = json.loads((Path(fam) / "family_metadata.json").read_text())
            for k in ("family_id", "replay_version", "source_run",
                      "source_scores_id", "command", "environment", "git",
                      "file_hashes", "artifact_sha256",
                      "elapsed_monotonic_seconds", "resource_scope"):
                self.assertIn(k, meta, msg=k)
            for f in ("protocol.json", "evaluation_config.json",
                      "source_config.json", "source_scores.csv",
                      "fixed/predictions.csv", "fixed/state.json",
                      "hysteresis/predictions.csv", "hysteresis/state.json"):
                self.assertIn(f, meta["artifact_sha256"], msg=f)
                h = hashlib.sha256((Path(fam) / f).read_bytes()).hexdigest()
                self.assertEqual(meta["artifact_sha256"][f], h)

    def test_cli_produces_verifiable_family(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam-cli")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.replay",
                 "--run", run, "--protocol", str(PROTOCOL),
                 "--evaluation-config", str(EVAL_CONFIG),
                 "--labels", str(LABELS), "--output", fam],
                cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            report = replay.load_family(fam)
            self.assertTrue(report["status"], msg=report.get("differences"))


class LabelOrderingTest(unittest.TestCase):
    def test_labels_opened_once_after_both_policies_persisted(self):
        from reliable_alerting import evaluation, evaluation_io, replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            labels_path = str(LABELS)
            real_load = evaluation_io.load_strict_json
            opens = []

            def observing(path):
                if str(path) == labels_path:
                    opens.append(str(path))
                    # Both policies must already be persisted, readable,
                    # and episode-formable BEFORE labels are opened.
                    for name in ("fixed", "hysteresis"):
                        pred = Path(fam) / name / "predictions.csv"
                        state = Path(fam) / name / "state.json"
                        cfg = Path(fam) / name / "policy_config.json"
                        self.assertTrue(pred.is_file(), msg=name)
                        self.assertTrue(state.is_file(), msg=name)
                        self.assertTrue(cfg.is_file(), msg=name)
                        rows = evaluation_io.load_predictions_generic(str(pred))
                        evaluation.form_episodes(
                            rows, json.loads(EVAL_CONFIG.read_text()))
                        replay.read_state_json(str(state))
                return real_load(path)

            with mock.patch.object(evaluation_io, "load_strict_json",
                                   side_effect=observing):
                replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                  labels_path, fam)
            # Labels opened exactly once (mock only observes I/O ordering).
            self.assertEqual(opens, [labels_path])

    def test_label_failure_leaves_documented_incomplete_output(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            missing = str(Path(tmp) / "no-labels.json")
            with self.assertRaises((FileNotFoundError, OSError, ValueError)):
                replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                  missing, fam)
            # Label-free files persisted; completion metadata absent.
            for rel in ("protocol.json", "source_config.json",
                        "source_scores.csv", "fixed/predictions.csv",
                        "fixed/state.json", "fixed/policy_config.json",
                        "hysteresis/predictions.csv", "hysteresis/state.json",
                        "hysteresis/policy_config.json"):
                self.assertTrue((Path(fam) / rel).is_file(), msg=rel)
            for rel in ("fixed/evaluation.json", "fixed/metadata.json",
                        "hysteresis/evaluation.json",
                        "hysteresis/metadata.json", "labels.json",
                        "family_metadata.json"):
                self.assertFalse((Path(fam) / rel).exists(), msg=rel)
            report = replay.load_family(fam)
            self.assertFalse(report["status"])


class FeasibilityReportingTest(unittest.TestCase):
    def test_tolerance_is_reporting_not_rejection(self):
        from reliable_alerting import replay
        protocol = {"episode_rate_tolerance_per_1000_decisions": 250,
                    "coverage_floor": 1.0}
        bad = replay.assess_feasibility(4, 8, 1.0, protocol)
        self.assertFalse(bad["feasible"])
        self.assertEqual(bad["episode_rate_per_1000_decisions"], 500.0)
        self.assertEqual(bad["decision_coverage"], 1.0)
        self.assertTrue(any("500" in r for r in bad["reasons"]))
        thin = replay.assess_feasibility(1, 8, 0.5, protocol)
        self.assertFalse(thin["feasible"])
        self.assertTrue(any("coverage" in r.lower()
                            for r in thin["reasons"]))
        good = replay.assess_feasibility(2, 8, 1.0, protocol)
        self.assertTrue(good["feasible"])
        self.assertEqual(good["reasons"], [])

    def test_high_episode_toy_preserved_with_reasons_no_override(self):
        # Same schedule as the configured recipe, hand-set scores only
        # (no compute_trace values override): alternating alerts isolate
        # 4 episodes over 8 decisions -> rate 500, preserved not rejected.
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            high = source_high_of(run)
            scores = score_rows_of(run)
            toy = []
            for i, s in enumerate(scores):
                toy.append(dict(s, score=(high + 1.0 if i % 2 else 0.0)))
            fixed = {"kind": "fixed_threshold", "comparison": "strict_greater",
                     "threshold": high}
            got = replay.replay_rows(toy, fixed, "c", "r")
            states = [p["output_state"] for p in got["predictions"]]
            self.assertEqual(states,
                             ["normal", "alert"] * 4)
            from reliable_alerting import evaluation
            episodes = evaluation.form_episodes(
                got["predictions"], json.loads(EVAL_CONFIG.read_text()))
            report = replay.assess_feasibility(
                len(episodes), len(toy), 1.0,
                {"episode_rate_tolerance_per_1000_decisions": 250,
                 "coverage_floor": 1.0})
            self.assertFalse(report["feasible"])
            self.assertEqual(report["episode_rate_per_1000_decisions"], 500.0)

    def test_family_records_actual_feasibility(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            meta = json.loads((Path(fam) / "family_metadata.json").read_text())
            for name in ("fixed", "hysteresis"):
                entry = meta["policies"][name]
                self.assertTrue(entry["feasible"])
                self.assertEqual(entry["episode_rate_per_1000_decisions"], 250.0)
                self.assertEqual(entry["decision_coverage"], 1.0)
                pmeta = json.loads(
                    (Path(fam) / name / "metadata.json").read_text())
                self.assertTrue(pmeta["feasible"])
                self.assertEqual(pmeta["feasibility_reasons"], [])
                self.assertEqual(
                    pmeta["episode_rate_per_1000_decisions"],
                    entry["episode_rate_per_1000_decisions"])

    def test_protocol_notes_say_reporting(self):
        self.assertIn("reporting", PROTOCOL.read_text().lower())


class MetadataIntegrityTest(unittest.TestCase):
    def _rewrite_meta(self, fam, mutate):
        p = Path(fam) / "family_metadata.json"
        meta = json.loads(p.read_text())
        mutate(meta)
        p.write_text(json.dumps(meta, sort_keys=True, indent=2,
                                allow_nan=False) + "\n")

    def _refresh_sha(self, fam, rel):
        from reliable_alerting import replay  # noqa
        import hashlib as _hl
        p = Path(fam) / "family_metadata.json"
        meta = json.loads(p.read_text())
        meta["artifact_sha256"][rel] = _hl.sha256(
            (Path(fam) / rel).read_bytes()).hexdigest()
        p.write_text(json.dumps(meta, sort_keys=True, indent=2,
                                allow_nan=False) + "\n")

    def test_extra_metadata_key_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self._rewrite_meta(fam, lambda m: m.update({"extra": 1}))
            self.assertFalse(replay.load_family(fam)["status"])

    def test_missing_source_scores_id_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self._rewrite_meta(fam, lambda m: m.pop("source_scores_id"))
            self.assertFalse(replay.load_family(fam)["status"])

    def test_policy_metadata_link_mismatch_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            p = Path(fam) / "fixed" / "metadata.json"
            doc = json.loads(p.read_text())
            doc["family_id"] = "forged-family"
            p.write_text(json.dumps(doc, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n")
            self._refresh_sha(fam, "fixed/metadata.json")
            self.assertFalse(replay.load_family(fam)["status"])

    def test_wrong_policy_kind_in_named_dir_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            a = Path(fam) / "fixed" / "policy_config.json"
            b = Path(fam) / "hysteresis" / "policy_config.json"
            ta, tb = a.read_bytes(), b.read_bytes()
            a.write_bytes(tb)
            b.write_bytes(ta)
            self._refresh_sha(fam, "fixed/policy_config.json")
            self._refresh_sha(fam, "hysteresis/policy_config.json")
            report = replay.load_family(fam)
            self.assertFalse(report["status"])

    def test_nonfinite_elapsed_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self._rewrite_meta(
                fam, lambda m: m.update({"elapsed_monotonic_seconds": "soon"}))
            report = replay.load_family(fam)
            self.assertFalse(report["status"])

    def test_file_hashes_incomplete_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self._rewrite_meta(
                fam, lambda m: m["file_hashes"].popitem())
            self.assertFalse(replay.load_family(fam)["status"])

    def test_artifact_extra_and_parent_paths_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self._rewrite_meta(
                fam, lambda m: m["artifact_sha256"].update({"extra.json": "0" * 64}))
            self.assertFalse(replay.load_family(fam)["status"])
            self._rewrite_meta(
                fam, lambda m: m["artifact_sha256"].update(
                    {"../outside.json": "0" * 64}))
            self.assertFalse(replay.load_family(fam)["status"])

    @unittest.skipIf(sys.platform == "win32", "Symlinks require admin privileges on Windows")
    def test_symlinked_artifact_refused(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            target = Path(fam) / "fixed" / "state.json"
            staged = Path(tmp) / "staged-state.json"
            staged.write_bytes(target.read_bytes())
            target.unlink()
            os.symlink(str(staged), str(target))
            self.assertFalse(replay.load_family(fam)["status"])

    def test_refreshed_checksums_do_not_hide_tamper(self):
        from reliable_alerting import replay
        # (a) flipped decision + refreshed sha still fails fresh replay.
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            p = Path(fam) / "fixed" / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[3]["output_state"] = "normal"
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            self._refresh_sha(fam, "fixed/predictions.csv")
            self.assertFalse(replay.load_family(fam)["status"])
        # (b) state after_state flip + refreshed sha still fails.
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            p = Path(fam) / "hysteresis" / "state.json"
            doc = json.loads(p.read_text())
            doc[3]["after_state"] = "normal"
            p.write_text(json.dumps(doc, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n")
            self._refresh_sha(fam, "hysteresis/state.json")
            self.assertFalse(replay.load_family(fam)["status"])
        # (c) policy config threshold tamper + refreshed sha still fails.
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            p = Path(fam) / "fixed" / "policy_config.json"
            doc = json.loads(p.read_text())
            doc["threshold"] = float(doc["threshold"]) + 5.0
            p.write_text(json.dumps(doc, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n")
            self._refresh_sha(fam, "fixed/policy_config.json")
            self.assertFalse(replay.load_family(fam)["status"])

    def test_evaluation_config_id_mismatch_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            self._rewrite_meta(
                fam, lambda m: m.update({"evaluation_config_id": "0" * 64}))
            self.assertFalse(replay.load_family(fam)["status"])


class SidecarTypingTest(unittest.TestCase):
    def _good_state_file(self, tmp):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as outer:
            run = make_source_run(outer)
            high = source_high_of(run)
            scores = score_rows_of(run)
            got = replay.replay_rows(
                scores,
                {"kind": "hysteresis", "low": 0.8 * high, "high": high},
                "c", "r")
            p = str(Path(tmp) / "state.json")
            replay.write_state_json(p, got["state"])
            return p, got["state"]

    def test_bool_start_score_high_low_rejected_not_equal(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            p, state = self._good_state_file(tmp)
            # True == 1 and 1.0 == 1.0 in Python; typed checks must reject.
            for key, bad in (("start_index", True), ("end_index", True),
                             ("availability_end", True), ("score", True),
                             ("high", True), ("low", True),
                             ("judging_threshold", True),
                             ("score", "1.0"), ("high", "1.0")):
                doc = copy.deepcopy(state)
                doc[0][key] = bad
                q = str(Path(tmp) / f"bad-{key}.json")
                with open(q, "w") as fh:
                    fh.write(json.dumps(doc, allow_nan=False) + "\n")
                with self.assertRaises((TypeError, ValueError), msg=key):
                    replay.read_state_json(q)
            # enum + linkage mistypes
            for key, bad in (("before_state", "ALERT"),
                             ("after_state", "bogus"),
                             ("comparator", "greater"),
                             ("policy_kind", "fixed"),
                             ("replay_version", "temporal-replay-v0"),
                             ("config_id", ""), ("run_id", ""),
                             ("window_id", "")):
                doc = copy.deepcopy(state)
                doc[0][key] = bad
                q = str(Path(tmp) / "bad-enum.json")
                with open(q, "w") as fh:
                    fh.write(json.dumps(doc, allow_nan=False) + "\n")
                with self.assertRaises((TypeError, ValueError), msg=key):
                    replay.read_state_json(q)

    def test_state_missing_duplicate_unordered_rejected(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            p, state = self._good_state_file(tmp)
            doc = copy.deepcopy(state)
            del doc[0]["low"]
            q = str(Path(tmp) / "missing.json")
            with open(q, "w") as fh:
                fh.write(json.dumps(doc, allow_nan=False) + "\n")
            with self.assertRaises((TypeError, ValueError)):
                replay.read_state_json(q)
            dup = state + [dict(state[0])]
            q = str(Path(tmp) / "dup.json")
            with open(q, "w") as fh:
                fh.write(json.dumps(dup, allow_nan=False) + "\n")
            with self.assertRaises(ValueError):
                replay.read_state_json(q)
            rev = list(reversed(state))
            q = str(Path(tmp) / "rev.json")
            with open(q, "w") as fh:
                fh.write(json.dumps(rev, allow_nan=False) + "\n")
            with self.assertRaises(ValueError):
                replay.read_state_json(q)
            skewed = copy.deepcopy(state)
            skewed[0]["availability_end"] = skewed[0]["end_index"] + 1
            q = str(Path(tmp) / "skew.json")
            with open(q, "w") as fh:
                fh.write(json.dumps(skewed, allow_nan=False) + "\n")
            with self.assertRaises(ValueError):
                replay.read_state_json(q)


class LowEqualityRoundtripTest(unittest.TestCase):
    def test_pipeline_family_evaluation_at_exact_low(self):
        from reliable_alerting import evaluation_io, replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_low_source_run(tmp)
            high = source_high_of(run)
            low = 0.8 * high
            scores = score_rows_of(run)
            self.assertTrue(any(s["score"] == low for s in scores))
            cfg_p = str(Path(tmp) / "eval.json")
            lab_p = str(Path(tmp) / "labels.json")
            write_json(cfg_p, low_recipe_eval_config())
            write_json(lab_p, low_recipe_labels())
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), cfg_p, lab_p, fam)
            report = replay.load_family(fam)
            self.assertTrue(report["status"], msg=report.get("differences"))
            for name in ("fixed", "hysteresis"):
                rows = replay.load_family_predictions(fam, name)
                self.assertTrue(any(r["score"] == low for r in rows))
                core = evaluation_io.evaluate_saved_predictions(
                    str(Path(fam) / name / "predictions.csv"), lab_p,
                    low_recipe_eval_config())
                persisted = json.loads(
                    (Path(fam) / name / "evaluation.json").read_text())
                self.assertEqual(core, persisted)

    def test_pipeline_family_alert_then_exact_low_holds(self):
        # True pipeline synthetic compute->write->family->evaluate where a
        # >high alert precedes score==low, which retains alert (strict_less).
        from reliable_alerting import evaluation_io, replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_low_source_run(tmp)
            high = source_high_of(run)
            low = 0.8 * high
            cfg_p = str(Path(tmp) / "eval.json")
            lab_p = str(Path(tmp) / "labels.json")
            write_json(cfg_p, low_recipe_eval_config())
            write_json(lab_p, low_recipe_labels())
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), cfg_p, lab_p, fam)
            report = replay.load_family(fam)
            self.assertTrue(report["status"], msg=report.get("differences"))
            fixed_rows = replay.load_family_predictions(fam, "fixed")
            hyst_rows = replay.load_family_predictions(fam, "hysteresis")
            self.assertEqual(
                [r["output_state"] for r in fixed_rows],
                ["alert", "normal", "normal", "normal"])
            self.assertEqual(
                [r["output_state"] for r in hyst_rows],
                ["alert", "alert", "alert", "alert"])
            state = replay.read_state_json(
                str(Path(fam) / "hysteresis" / "state.json"))
            self.assertEqual(state[0]["before_state"], "normal")
            self.assertEqual(state[0]["after_state"], "alert")
            for entry in state[1:]:
                self.assertEqual(entry["before_state"], "alert")
                self.assertEqual(entry["score"], low)
                self.assertEqual(entry["judging_threshold"], low)
                self.assertEqual(entry["comparator"], "strict_less")
                self.assertEqual(entry["after_state"], "alert")
            for name in ("fixed", "hysteresis"):
                core = evaluation_io.evaluate_saved_predictions(
                    str(Path(fam) / name / "predictions.csv"), lab_p,
                    low_recipe_eval_config())
                persisted = json.loads(
                    (Path(fam) / name / "evaluation.json").read_text())
                self.assertEqual(core, persisted)

    def test_sidecar_write_read_exact_at_low_and_exclusive(self):
        from reliable_alerting import evaluation, evaluation_io, replay
        # Alert latch holds exactly at low (strict_less exit): score == low
        # must survive sidecar JSON + predictions CSV bit-for-bit.
        high, low = 1.25, 1.0
        ends = [1, 2, 3, 4, 5, 6, 7]
        vals = [0.5, 1.5, 1.0, 0.5, 1.25, 1.5, 1.0]
        scores = [{"window_id": f"w:{i}", "start_index": e - 1,
                   "end_index": e, "score": v}
                  for i, (e, v) in enumerate(zip(ends, vals))]
        got = replay.replay_rows(
            scores, {"kind": "hysteresis", "low": low, "high": high},
            "cid", "rid")
        self.assertEqual([p["output_state"] for p in got["predictions"]],
                         ["normal", "alert", "alert", "normal",
                          "normal", "alert", "alert"])
        self.assertEqual(got["state"][2]["judging_threshold"], low)
        self.assertEqual(got["state"][2]["score"], low)
        self.assertEqual(got["state"][2]["after_state"], "alert")
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            sp = str(Path(tmp) / "state.json")
            replay.write_state_json(sp, got["state"])
            with self.assertRaises(FileExistsError):
                replay.write_state_json(sp, got["state"])
            back = replay.read_state_json(sp)
            self.assertEqual(back, got["state"])
            cfg = {"schema_version": 1, "time_basis": "sample_index",
                   "horizon": [0, 8], "first_decision": 1,
                   "decision_stride": 1, "window_length": 2}
            lab = {"schema_version": 1, "time_basis": "sample_index",
                   "coverage": [0, 8],
                   "events": [{"event_id": "e0", "start": 2, "stop": 4}]}
            episodes = evaluation.form_episodes(got["predictions"],
                                                copy.deepcopy(cfg))
            core = evaluation.evaluate(got["predictions"], copy.deepcopy(lab),
                                       copy.deepcopy(cfg))
            self.assertEqual(
                [(e["start"], e["stop"]) for e in episodes], [(2, 4), (6, 8)])
            self.assertEqual(core["episodes"], episodes)


class InvarianceTest(unittest.TestCase):
    def test_development_labels_both_policies_invariant(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            alt = {"schema_version": 1, "time_basis": "sample_index",
                   "coverage": [64, 96],
                   "events": [{"event_id": "dev", "start": 64, "stop": 70}]}
            alt_p = str(Path(tmp) / "dev-labels.json")
            write_json(alt_p, alt)
            fa = str(Path(tmp) / "fam-a")
            fb = str(Path(tmp) / "fam-b")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fa)
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              alt_p, fb)
            for name in ("fixed", "hysteresis"):
                # Fresh run_ids differ per family; decisions must not.
                for fname in ("predictions.csv", "policy_config.json"):
                    if fname.endswith(".csv"):
                        with open(Path(fa) / name / fname, newline="") as fh:
                            ra = [{k: v for k, v in r.items() if k != "run_id"}
                                  for r in csv.DictReader(fh)]
                        with open(Path(fb) / name / fname, newline="") as fh:
                            rb = [{k: v for k, v in r.items() if k != "run_id"}
                                  for r in csv.DictReader(fh)]
                        self.assertEqual(ra, rb, msg=f"{name}/{fname}")
                    else:
                        self.assertEqual(
                            (Path(fa) / name / fname).read_bytes(),
                            (Path(fb) / name / fname).read_bytes(),
                            msg=f"{name}/{fname}")
                sa = [{k: v for k, v in e.items() if k != "run_id"}
                      for e in json.loads(
                          (Path(fa) / name / "state.json").read_text())]
                sb = [{k: v for k, v in e.items() if k != "run_id"}
                      for e in json.loads(
                          (Path(fb) / name / "state.json").read_text())]
                self.assertEqual(sa, sb, msg=f"{name}/state.json")
            self.assertTrue(replay.load_family(fa)["status"])
            self.assertTrue(replay.load_family(fb)["status"])

    def test_replay_id_binds_version(self):
        from reliable_alerting import replay
        import hashlib as _hl
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            meta = json.loads((Path(fam) / "family_metadata.json").read_text())
            self.assertEqual(meta["replay_version"], replay.REPLAY_VERSION)
            for name in ("fixed", "hysteresis"):
                entry = meta["policies"][name]
                want = _hl.sha256(
                    f"{entry['config_id']}:{entry['run_id']}:"
                    f"{replay.REPLAY_VERSION}".encode()).hexdigest()
                self.assertEqual(entry["replay_id"], want)
                pmeta = json.loads(
                    (Path(fam) / name / "metadata.json").read_text())
                self.assertEqual(pmeta["replay_id"], want)
                self.assertEqual(pmeta["replay_version"],
                                 replay.REPLAY_VERSION)

    def test_source_collapsed_high_rejected(self):
        from reliable_alerting import replay
        cfg = low_recipe_config()
        cfg["input"] = {"kind": "synthetic_periodic_v1", "length": 32,
                        "pattern": [5, 5, 5, 5], "offsets": []}
        cfg["segments"] = {"source_fit": [0, 8], "calibration": [8, 16],
                           "replay": [16, 32]}
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            trace = pipeline.compute_trace(cfg)
            self.assertEqual(trace["threshold"], 0.0)
            out = str(Path(tmp) / "collapsed-run")
            pipeline.write_output(cfg, trace, out)
            # Matching schedule so the failure is genuinely the collapsed high.
            cfg_p = str(Path(tmp) / "eval.json")
            write_json(cfg_p, {"schema_version": 1,
                               "time_basis": "sample_index",
                               "horizon": [16, 32], "first_decision": 19,
                               "decision_stride": 4, "window_length": 4})
            with self.assertRaises(ValueError):
                replay.run_family(out, str(PROTOCOL), cfg_p,
                                  str(LABELS), str(Path(tmp) / "fam"))
            self.assertFalse((Path(tmp) / "fam").exists())


class SymlinkConfinementTest(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "Symlinks require admin privileges on Windows")
    def test_symlinked_policy_dir_refused(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            staged = str(Path(tmp) / "staged-fixed")
            os.makedirs(staged)
            for fname in ("policy_config.json", "predictions.csv",
                          "state.json", "evaluation.json", "metadata.json"):
                with open(Path(fam, "fixed", fname), "rb") as fh:
                    data = fh.read()
                with open(Path(staged, fname), "wb") as fh:
                    fh.write(data)
            victim = Path(fam) / "fixed"
            backup = Path(tmp) / "fixed-backup"
            os.rename(str(victim), str(backup))
            os.symlink(staged, str(victim))
            try:
                self.assertFalse(replay.load_family(fam)["status"])
            finally:
                os.unlink(str(victim))
                os.rename(str(backup), str(victim))

    @unittest.skipIf(sys.platform == "win32", "Symlinks require admin privileges on Windows")
    def test_symlinked_family_base_refused(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            alias = str(Path(tmp) / "fam-alias")
            os.symlink(fam, alias)
            self.assertFalse(replay.load_family(alias)["status"])

    @unittest.skipIf(sys.platform == "win32", "Symlinks require admin privileges on Windows")
    def test_symlinked_family_metadata_refused(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                              str(LABELS), fam)
            target = Path(fam) / "family_metadata.json"
            staged = Path(tmp) / "staged-meta.json"
            staged.write_bytes(target.read_bytes())
            target.unlink()
            os.symlink(str(staged), str(target))
            self.assertFalse(replay.load_family(fam)["status"])

    @unittest.skipIf(sys.platform == "win32", "Symlinks require admin privileges on Windows")
    def test_run_family_refuses_symlinked_inputs(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            for label, real in (("source_run", run),
                                ("protocol", str(PROTOCOL)),
                                ("evaluation_config", str(EVAL_CONFIG)),
                                ("labels", str(LABELS))):
                link = str(Path(tmp) / f"link-{label}")
                os.symlink(real, link)
                kwargs = {"source_run": run, "protocol_path": str(PROTOCOL),
                          "evaluation_config_path": str(EVAL_CONFIG),
                          "labels_path": str(LABELS)}
                key = {"source_run": "source_run", "protocol": "protocol_path",
                       "evaluation_config": "evaluation_config_path",
                       "labels": "labels_path"}[label]
                kwargs[key] = link
                with self.assertRaises(ValueError, msg=label):
                    replay.run_family(output_dir=str(Path(tmp) / f"fam-{label}"),
                                      **kwargs)
                self.assertFalse((Path(tmp) / f"fam-{label}").exists())


class ResourceScopeTest(unittest.TestCase):
    def test_description_excludes_provenance_and_completion_writes(self):
        from reliable_alerting import replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            res = replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                    str(LABELS), fam)
            meta = res["metadata"]
            # Scope name stays broad (v1); description must be explicit.
            self.assertEqual(meta["resource_scope"], replay.RESOURCE_SCOPE)
            self.assertEqual(meta["resource_description"],
                             replay.RESOURCE_DESCRIPTION)
            low = meta["resource_description"].lower()
            for included in ("validation", "replay", "episode", "label-free",
                             "labels read", "evaluation", "serial", "hash"):
                self.assertIn(included, low, msg=included)
            self.assertIn("excludes", low)
            self.assertIn("provenance", low)
            self.assertIn("completion", low)

    def test_timing_boundary_precedes_provenance_capture(self):
        from reliable_alerting import provenance, replay
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = make_source_run(tmp)
            fam = str(Path(tmp) / "fam")
            marks = {}
            real_cmd = provenance.command_record

            def observing():
                marks["t"] = time.monotonic()
                return real_cmd()

            with mock.patch.object(provenance, "command_record",
                                   side_effect=observing):
                t_start = time.monotonic()
                res = replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG),
                                        str(LABELS), fam)
            self.assertIn("t", marks)
            # Reported elapsed cannot include provenance capture: it was
            # captured strictly before command_record ran.
            self.assertLessEqual(
                res["metadata"]["elapsed_monotonic_seconds"],
                marks["t"] - t_start)


if __name__ == "__main__":
    unittest.main()
