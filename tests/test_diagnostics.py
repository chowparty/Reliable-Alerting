"""Day-05 provisional diagnostic: trailing-median-gap-v1 (Pratyush support only).

Why: current-inclusive last-3 score median minus frozen calibration median
(score units, no divide, one setting) as a decision-time diagnostic aid.
PROVISIONAL: not an Aman deliverable, not a quality claim.
"""
import copy
import csv
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from reliable_alerting import pipeline  # noqa: E402

DIAG_CONFIG = REPO / "configs" / "day05-diagnostic.json"


def base_diag_config():
    return {
        "schema_version": 1,
        "diagnostic_id": "trailing-median-gap-v1",
        "trailing_window": 3,
        "warmup_count": 2,
        "reference": {
            "segment": "calibration",
            "statistic": "median",
            "fit_scope": "calibration_scores",
        },
        "score_unit": "score",
        "normalize": False,
        "time_basis": "sample_index",
        "provisional": True,
        "provisional_owner": "pratyush",
        "notes": "PROVISIONAL Pratyush support only; not an Aman deliverable.",
    }


def make_rows(scores, start=64, length=4):
    rows = []
    for i, s in enumerate(scores):
        st = start + i * length
        en = st + length - 1
        rows.append({
            "window_id": f"replay:{st}:{en}",
            "start_index": st,
            "end_index": en,
            "score": float(s),
        })
    return rows


def make_calibration(scores, start=32, length=4):
    return make_rows(scores, start=start, length=length)


def base_source_run(tmp, name="diag-source-run"):
    cfg = {
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
        "window": {"length": 4, "stride": 4, "anchor": "segment_start",
                   "edge_policy": "drop_incomplete", "end_index": "inclusive"},
        "scoring": {"kind": "mean_distance", "epsilon": 1e-6,
                    "fit_scope": "source_fit", "standard_deviation": "population"},
        "calibration": {"kind": "fixed_quantile", "quantile": 0.95,
                        "method": "nearest_rank", "min_samples": 2,
                        "score_segment": "calibration"},
        "policy": {"kind": "fixed_threshold", "comparison": "strict_greater"},
        "missing_policy": "reject",
        "source_label_use": "none",
        "time_basis": "sample_index",
        "held_out": "not_reserved_or_evaluated",
    }
    trace = pipeline.compute_trace(cfg)
    out = str(Path(tmp) / name)
    pipeline.write_output(cfg, trace, out)
    return out


class ApiLabelFreeTest(unittest.TestCase):
    def test_public_api_is_label_free(self):
        from reliable_alerting import diagnostics
        for fn in ("compute_features", "verify_features", "run_diagnostic",
                   "load_diagnostic"):
            self.assertTrue(hasattr(diagnostics, fn), msg=fn)
            params = inspect.signature(getattr(diagnostics, fn)).parameters
            for bad in ("label", "labels", "y_true"):
                self.assertNotIn(bad, params, msg=f"{fn}:{bad}")

    def test_labels_key_in_rows_rejected(self):
        from reliable_alerting import diagnostics
        scores = make_rows([1.0, 2.0, 3.0, 4.0])
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        bad = copy.deepcopy(scores)
        bad[0]["labels"] = [0]
        with self.assertRaises((TypeError, ValueError)):
            diagnostics.compute_features(bad, cal, base_diag_config())


class KnownMediansTest(unittest.TestCase):
    def test_hand_median_minus_reference(self):
        from reliable_alerting import diagnostics
        # calibration [1,2,3,4] -> sorted median (2+3)/2 = 2.5
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0, 4.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        self.assertEqual(doc["reference"]["median"], 2.5)
        self.assertEqual(doc["reference"]["count"], 4)
        rows = doc["rows"]
        self.assertIsNone(rows[0]["feature"])
        self.assertIsNone(rows[1]["feature"])
        # median(0,10,2)=2 -> 2-2.5=-0.5
        self.assertEqual(rows[2]["trailing_median"], 2.0)
        self.assertAlmostEqual(rows[2]["feature"], -0.5)
        # median(10,2,8)=8 -> 5.5
        self.assertEqual(rows[3]["trailing_median"], 8.0)
        self.assertAlmostEqual(rows[3]["feature"], 5.5)
        # median(2,8,4)=4 -> 1.5
        self.assertEqual(rows[4]["trailing_median"], 4.0)
        self.assertAlmostEqual(rows[4]["feature"], 1.5)

    def test_constant_zero_spread_ties(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([5.0, 5.0, 5.0, 5.0])
        scores = make_rows([5.0, 5.0, 5.0, 5.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        self.assertEqual(doc["reference"]["median"], 5.0)
        self.assertIsNone(doc["rows"][0]["feature"])
        self.assertIsNone(doc["rows"][1]["feature"])
        self.assertEqual(doc["rows"][2]["feature"], 0.0)
        self.assertEqual(doc["rows"][3]["feature"], 0.0)

    def test_odd_calibration_median(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([3.0, 1.0, 2.0])
        scores = make_rows([0.0, 0.0, 9.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        self.assertEqual(doc["reference"]["median"], 2.0)
        self.assertEqual(doc["rows"][2]["trailing_median"], 0.0)
        self.assertAlmostEqual(doc["rows"][2]["feature"], -2.0)


class StartupWarmupTest(unittest.TestCase):
    def test_first_two_null_third_ready(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        scores = make_rows([7.0, 1.0, 5.0, 9.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        self.assertTrue(doc["rows"][0]["warmup"])
        self.assertTrue(doc["rows"][1]["warmup"])
        self.assertFalse(doc["rows"][2]["warmup"])
        self.assertIsNone(doc["rows"][0]["trailing_median"])
        self.assertIsNone(doc["rows"][1]["trailing_median"])
        self.assertIsNotNone(doc["rows"][2]["trailing_median"])

    def test_warmup_has_explicit_readiness_reason(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        scores = make_rows([7.0, 1.0, 5.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        for i, row in enumerate(doc["rows"]):
            reason = row.get("readiness_reason")
            self.assertIsInstance(reason, str)
            self.assertTrue(reason.strip(), msg=f"row {i} empty reason")
            if row["warmup"]:
                self.assertIn("warmup", reason.lower(), msg=f"row {i}")
            else:
                self.assertIn("ready", reason.lower(), msg=f"row {i}")
        # tampered reason must fail verification
        import copy as _copy
        tampered = _copy.deepcopy(doc)
        tampered["rows"][0]["readiness_reason"] = "ready"
        cfg = base_diag_config()
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])

    def test_document_records_inclusion_reset_and_reference_bounds(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        self.assertEqual(doc.get("inclusion"), "current_inclusive")
        self.assertEqual(doc.get("reset"), "independent_call")
        ref = doc["reference"]
        self.assertEqual(ref["bounds"], [cal[0]["start_index"],
                                         cal[-1]["end_index"]])
        self.assertEqual(ref["window_length"], 4)
        # tamper must fail
        import copy as _copy
        cfg = base_diag_config()
        tampered = _copy.deepcopy(doc)
        tampered["inclusion"] = "other"
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        tampered = _copy.deepcopy(doc)
        tampered["reference"]["bounds"] = [0, 1]
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])

    def test_empty_rejected(self):
        from reliable_alerting import diagnostics
        with self.assertRaises(ValueError):
            diagnostics.compute_features([], make_calibration([1.0, 2.0]),
                                         base_diag_config())

    def test_short_all_warmup(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0])
        for n in (1, 2):
            scores = make_rows([3.0] * n)
            doc = diagnostics.compute_features(scores, cal, base_diag_config())
            self.assertEqual(len(doc["rows"]), n)
            for r in doc["rows"]:
                self.assertIsNone(r["feature"])
                self.assertTrue(r["warmup"])

    def test_availability_end_equals_end(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        scores = make_rows([1.0, 2.0, 3.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        for s, r in zip(scores, doc["rows"]):
            self.assertEqual(r["availability_end"], s["end_index"])
            self.assertEqual(r["window_id"], s["window_id"])
            self.assertEqual(r["start_index"], s["start_index"])
            self.assertEqual(r["end_index"], s["end_index"])


class PrefixInvarianceTest(unittest.TestCase):
    def test_prefix_stable_under_future(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0, 4.0, 6.0])
        full = diagnostics.compute_features(scores, cal, base_diag_config())
        prefix = diagnostics.compute_features(scores[:4], cal, base_diag_config())
        self.assertEqual([r["feature"] for r in full["rows"][:4]],
                         [r["feature"] for r in prefix["rows"]])

    def test_future_mutation_leaves_prefix(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0])
        mutated = copy.deepcopy(scores)
        mutated[-1] = dict(mutated[-1], score=999.0)
        a = diagnostics.compute_features(scores, cal, base_diag_config())
        b = diagnostics.compute_features(mutated, cal, base_diag_config())
        self.assertEqual(a["rows"][2], b["rows"][2])
        self.assertNotEqual(a["rows"][3]["feature"], b["rows"][3]["feature"])


class ResetSegmentsTest(unittest.TestCase):
    def test_independent_calls_reset(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        seg_a = make_rows([9.0, 9.0, 9.0], start=64)
        seg_b = make_rows([0.0, 0.0, 0.0], start=80)
        a = diagnostics.compute_features(seg_a, cal, base_diag_config())
        b = diagnostics.compute_features(seg_b, cal, base_diag_config())
        # second segment must warm up again, not carry trailing state
        self.assertIsNone(b["rows"][0]["feature"])
        self.assertIsNone(b["rows"][1]["feature"])
        self.assertAlmostEqual(b["rows"][2]["feature"], 0.0 - 2.0)
        self.assertAlmostEqual(a["rows"][2]["feature"], 9.0 - 2.0)


class ValidationTest(unittest.TestCase):
    def test_gaps_duplicate_unordered_rejected(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        good = make_rows([1.0, 2.0, 3.0])
        cfg = base_diag_config()
        # gap: skip one window
        gapped = [good[0], dict(good[1], start_index=good[1]["start_index"] + 4,
                                end_index=good[1]["end_index"] + 4,
                                window_id="replay:99:102")]
        with self.assertRaises(ValueError):
            diagnostics.compute_features(gapped, cal, cfg)
        # duplicate
        with self.assertRaises(ValueError):
            diagnostics.compute_features(good + [dict(good[0])], cal, cfg)
        # unordered
        with self.assertRaises(ValueError):
            diagnostics.compute_features(list(reversed(good)), cal, cfg)
        # overlapping (stride != length)
        overlap = copy.deepcopy(good)
        overlap[1] = dict(overlap[1], start_index=overlap[0]["start_index"] + 2,
                          end_index=overlap[0]["end_index"] + 2,
                          window_id="replay:66:69")
        with self.assertRaises(ValueError):
            diagnostics.compute_features(overlap, cal, cfg)

    def test_malformed_nonfinite_bool_rejected(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        cfg = base_diag_config()
        good = make_rows([1.0, 2.0, 3.0])
        for mutate in (
            lambda r: {k: v for k, v in r[0].items() if k != "score"},
            lambda r: dict(r[0], score=float("nan")),
            lambda r: dict(r[0], score=float("inf")),
            lambda r: dict(r[0], score=True),
            lambda r: dict(r[0], start_index=True),
            lambda r: dict(r[0], score="1.0"),
            lambda r: dict(r[0], extra=1),
        ):
            bad = copy.deepcopy(good)
            mutated_first = mutate(copy.deepcopy(good))
            if isinstance(mutated_first, dict):
                bad[0] = mutated_first
            else:
                bad[0] = mutated_first
            with self.assertRaises((TypeError, ValueError), msg=str(mutated_first)):
                diagnostics.compute_features(bad, cal, cfg)

    def test_misalignment_length_mismatch_rejected(self):
        from reliable_alerting import diagnostics
        scores = make_rows([1.0, 2.0, 3.0], length=4)
        cal = make_calibration([1.0, 2.0, 3.0], length=2)
        with self.assertRaises(ValueError):
            diagnostics.compute_features(scores, cal, base_diag_config())

    def test_irregular_stride_rejected(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        rows = make_rows([1.0, 2.0, 3.0])
        rows[2] = dict(rows[2], start_index=rows[2]["start_index"] + 1,
                       end_index=rows[2]["end_index"] + 1,
                       window_id="replay:73:76")
        with self.assertRaises(ValueError):
            diagnostics.compute_features(rows, cal, base_diag_config())

    def test_calibration_must_precede_scores_disjoint(self):
        from reliable_alerting import diagnostics
        cfg = base_diag_config()
        scores = make_rows([1.0, 2.0, 3.0], start=64)
        # overlapping identical bounds
        with self.assertRaises(ValueError):
            diagnostics.compute_features(
                scores, make_rows([1.0, 2.0, 3.0], start=64), cfg)
        # calibration after scores
        with self.assertRaises(ValueError):
            diagnostics.compute_features(
                scores, make_rows([1.0, 2.0, 3.0], start=100), cfg)
        # interleaved overlap (shares one window boundary region)
        with self.assertRaises(ValueError):
            diagnostics.compute_features(
                scores, make_rows([1.0, 2.0, 3.0], start=68), cfg)

    def test_verify_rejects_coerced_numeric_types(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0])
        cfg = base_diag_config()
        doc = diagnostics.compute_features(scores, cal, cfg)
        # numeric-string trailing_median must not verify
        tampered = copy.deepcopy(doc)
        tampered["rows"][2]["trailing_median"] = "2.0"
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        # bool contributing_count must not verify (True == 1 in Python)
        tampered = copy.deepcopy(doc)
        tampered["rows"][0]["contributing_count"] = True
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        # float index must not verify (64.0 == 64 in Python)
        tampered = copy.deepcopy(doc)
        tampered["rows"][2]["contributing_start_index"] = float(
            tampered["rows"][2]["contributing_start_index"])
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        # float decision_count / score_bounds / reference count must not verify
        tampered = copy.deepcopy(doc)
        tampered["decision_count"] = float(len(scores))
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        tampered = copy.deepcopy(doc)
        tampered["score_bounds"] = [float(scores[0]["start_index"]),
                                    scores[-1]["end_index"]]
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        tampered = copy.deepcopy(doc)
        tampered["reference"]["count"] = float(len(cal))
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        # float_equal itself must reject strings
        self.assertFalse(diagnostics._float_equal("2.0", 2.0))
        self.assertFalse(diagnostics._float_equal(2.0, "2.0"))

    def test_verify_rejects_nested_extra_keys(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0])
        cfg = base_diag_config()
        doc = diagnostics.compute_features(scores, cal, cfg)
        tampered = copy.deepcopy(doc)
        tampered["reference"]["extra"] = "x"
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        tampered = copy.deepcopy(doc)
        tampered["source_identities"]["extra"] = "x"
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])

    def test_nonfinite_feature_rejected(self):
        from reliable_alerting import diagnostics
        scores = make_rows([1e308, 1e308, 1e308], start=64)
        cal = make_calibration([-1e308, -1e308], start=32)
        with self.assertRaises(ValueError):
            diagnostics.compute_features(scores, cal, base_diag_config())

    def test_scores_csv_rejects_float_index(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            p = Path(tmp) / "scores.csv"
            with open(p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["window_id", "start_index", "end_index", "score"])
                w.writerow(["replay:64:67", "64.0", "67", "1.0"])
            with self.assertRaises((TypeError, ValueError)):
                diagnostics._parse_scores_csv(str(p))


class ResourceTimingTest(unittest.TestCase):
    def test_description_and_scopes_match_timed_region(self):
        from reliable_alerting import diagnostics
        # timed region ends at verification, before provenance + file writes
        self.assertIn("excludes provenance", diagnostics.RESOURCE_DESCRIPTION)
        self.assertNotIn("label-free file creation/writes;",
                         diagnostics.RESOURCE_DESCRIPTION)
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-timing")
            res = diagnostics.run_diagnostic(run, cfg_p, out)
            meta = res["metadata"]
            self.assertEqual(meta["started_at_scope"], "diagnostics_entry")
            # must not claim exit: persistence happens after finished_at
            self.assertNotEqual(meta["finished_at_scope"], "diagnostics_exit")
            self.assertIn("verif", meta["finished_at_scope"])
            self.assertIn("excludes provenance",
                          meta["resource_description"])
            self.assertGreaterEqual(meta["elapsed_monotonic_seconds"], 0)


class TamperTest(unittest.TestCase):
    def test_verify_detects_row_and_reference_tamper(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0, 4.0])
        scores = make_rows([0.0, 10.0, 2.0, 8.0])
        cfg = base_diag_config()
        doc = diagnostics.compute_features(scores, cal, cfg)
        ok = diagnostics.verify_features(doc, scores, cal, cfg)
        self.assertTrue(ok["status"], msg=ok.get("differences"))
        tampered = copy.deepcopy(doc)
        tampered["rows"][2]["feature"] += 1.0
        bad = diagnostics.verify_features(tampered, scores, cal, cfg)
        self.assertFalse(bad["status"])
        tampered2 = copy.deepcopy(doc)
        tampered2["reference"]["median"] += 1.0
        bad2 = diagnostics.verify_features(tampered2, scores, cal, cfg)
        self.assertFalse(bad2["status"])
        # score tamper
        bad_scores = copy.deepcopy(scores)
        bad_scores[2] = dict(bad_scores[2], score=999.0)
        bad3 = diagnostics.verify_features(doc, bad_scores, cal, cfg)
        self.assertFalse(bad3["status"])

    def test_verify_detects_metadata_config_tamper(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        scores = make_rows([1.0, 2.0, 3.0])
        cfg = base_diag_config()
        doc = diagnostics.compute_features(scores, cal, cfg)
        tampered = copy.deepcopy(doc)
        tampered["diagnostic_config_id"] = "0" * 64
        self.assertFalse(diagnostics.verify_features(
            tampered, scores, cal, cfg)["status"])
        other = base_diag_config()
        other["trailing_window"] = 5
        # config validation itself must reject non-3 setting
        with self.assertRaises((TypeError, ValueError)):
            diagnostics.compute_features(scores, cal, other)
        self.assertFalse(diagnostics.verify_features(
            doc, scores, cal, other)["status"])

    def test_independent_recomputation_not_production(self):
        from reliable_alerting import diagnostics
        import inspect as _inspect
        src = _inspect.getsource(diagnostics.verify_features)
        # independent path must sort; must not delegate to compute_features
        self.assertIn("sorted", src)
        self.assertNotIn("compute_features(", src)


class StrictJsonIdentitiesTest(unittest.TestCase):
    def test_config_and_score_identities_exact(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        scores = make_rows([1.0, 2.0, 3.0])
        cfg = base_diag_config()
        a = diagnostics.compute_features(scores, cal, cfg)
        b = diagnostics.compute_features(copy.deepcopy(scores),
                                         copy.deepcopy(cal),
                                         copy.deepcopy(cfg))
        self.assertEqual(a["diagnostic_config_id"], b["diagnostic_config_id"])
        self.assertEqual(a["score_identity"], b["score_identity"])
        self.assertEqual(a["reference_identity"], b["reference_identity"])
        self.assertEqual(a, b)

    def test_strict_json_roundtrip_and_dup_nonfinite(self):
        from reliable_alerting import diagnostics
        cal = make_calibration([1.0, 2.0, 3.0])
        scores = make_rows([1.0, 2.0, 3.0])
        doc = diagnostics.compute_features(scores, cal, base_diag_config())
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            p = str(Path(tmp) / "diag.json")
            diagnostics.write_diagnostic(p, doc)
            back = diagnostics.read_diagnostic(p)
            self.assertEqual(back, doc)
            with self.assertRaises(FileExistsError):
                diagnostics.write_diagnostic(p, doc)
            dup = Path(tmp) / "dup.json"
            dup.write_text('{"a": 1, "a": 2}')
            with self.assertRaises(ValueError):
                diagnostics.read_diagnostic(str(dup))
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"a": NaN}')
            with self.assertRaises(ValueError):
                diagnostics.read_diagnostic(str(bad))


class CliPersistenceTest(unittest.TestCase):
    def test_run_and_load_roundtrip(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            res = diagnostics.run_diagnostic(run, cfg_p, out)
            self.assertTrue((Path(out) / "diagnostic.json").is_file())
            self.assertTrue((Path(out) / "verification.json").is_file())
            self.assertTrue((Path(out) / "metadata.json").is_file())
            report = diagnostics.load_diagnostic(out)
            self.assertTrue(report["status"], msg=report.get("differences"))
            # cross-check against source run
            report2 = diagnostics.load_diagnostic(out, source_run=run)
            self.assertTrue(report2["status"], msg=report2.get("differences"))
            meta = json.loads((Path(out) / "metadata.json").read_text())
            for k in ("command", "environment", "git", "file_hashes",
                      "resource_scope", "started_at", "finished_at",
                      "diagnostic_id", "diagnostic_config_id"):
                self.assertIn(k, meta, msg=k)
            # No labels joined: no label keys/hashes/events in metadata or
            # document; file_hashes legitimately lists the repo whitelist
            # (which includes a labels fixture path) and the resource
            # description documents the label-free scope.
            for bad in ("labels", "label_file_sha256", "semantic_label_sha256",
                        "events", "event_recall", "episode_precision"):
                self.assertNotIn(bad, meta, msg=bad)
            self.assertIn("label-free", meta["resource_description"])
            doc = json.loads((Path(out) / "diagnostic.json").read_text())
            self.assertNotIn("label", json.dumps(doc).lower())
            self.assertEqual(res["output"], out)

    def test_load_rejects_source_config_tamper_extra_file_metadata(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            # tampered source_config must fail
            saved = (Path(out) / "source_config.json").read_text()
            tampered_cfg = json.loads(saved)
            tampered_cfg["window"] = {"length": 999, "stride": 4,
                                      "anchor": "segment_start",
                                      "edge_policy": "drop_incomplete",
                                      "end_index": "inclusive"}
            (Path(out) / "source_config.json").write_text(
                json.dumps(tampered_cfg, sort_keys=True, indent=2) + "\n")
            bad = diagnostics.load_diagnostic(out)
            self.assertFalse(bad["status"])
            # restore then extra file must fail
            (Path(out) / "source_config.json").write_text(saved)
            (Path(out) / "evil.txt").write_text("x")
            bad2 = diagnostics.load_diagnostic(out)
            self.assertFalse(bad2["status"])
            (Path(out) / "evil.txt").unlink()
            # metadata decision_count tamper must fail
            meta = json.loads((Path(out) / "metadata.json").read_text())
            meta["decision_count"] = 999
            (Path(out) / "metadata.json").write_text(
                json.dumps(meta, sort_keys=True, indent=2) + "\n")
            bad3 = diagnostics.load_diagnostic(out)
            self.assertFalse(bad3["status"])

    def test_load_rejects_shallow_provenance_bad_hash_shape(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            good = json.loads((Path(out) / "metadata.json").read_text())
            # shallow command / git / environment must fail
            for key, bad_val in (
                ("command", {"shell": "x"}),
                ("git", {"head": "abc"}),
                ("environment", {"x": 1}),
                ("file_hashes", {"a": "zzz"}),
            ):
                m = json.loads(json.dumps(good))
                m[key] = bad_val
                (Path(out) / "metadata.json").write_text(
                    json.dumps(m, sort_keys=True, indent=2) + "\n")
                bad = diagnostics.load_diagnostic(out)
                self.assertFalse(bad["status"], msg=key)
            # deleted file_hashes must fail
            m = json.loads(json.dumps(good))
            del m["file_hashes"]
            (Path(out) / "metadata.json").write_text(
                json.dumps(m, sort_keys=True, indent=2) + "\n")
            self.assertFalse(diagnostics.load_diagnostic(out)["status"])
            # deleting ONE file_hashes key must fail (exact frozen keys)
            m = json.loads(json.dumps(good))
            del m["file_hashes"][next(iter(m["file_hashes"]))]
            (Path(out) / "metadata.json").write_text(
                json.dumps(m, sort_keys=True, indent=2) + "\n")
            single = diagnostics.load_diagnostic(out)
            self.assertFalse(single["status"])
            (Path(out) / "metadata.json").write_text(
                json.dumps(good, sort_keys=True, indent=2) + "\n")

    def test_resource_scope_names_verification_excluding_output(self):
        from reliable_alerting import diagnostics
        self.assertEqual(
            diagnostics.RESOURCE_SCOPE,
            "saved_run_validation_recompute_diagnostic_verification_excluding_output")
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            res = diagnostics.run_diagnostic(run, cfg_p, out)
            self.assertEqual(
                res["metadata"]["resource_scope"],
                "saved_run_validation_recompute_diagnostic_verification_excluding_output")
            rep = diagnostics.load_diagnostic(out)
            self.assertTrue(rep["status"], msg=rep.get("differences"))

    def test_load_file_form_runs_same_artifact_checks(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            file_form = str(Path(out) / "diagnostic.json")
            ok = diagnostics.load_diagnostic(file_form)
            self.assertTrue(ok["status"], msg=ok.get("differences"))
            (Path(out) / "evil.txt").write_text("x")
            bad = diagnostics.load_diagnostic(file_form)
            self.assertFalse(bad["status"])
            (Path(out) / "evil.txt").unlink()
            ok2 = diagnostics.load_diagnostic(file_form)
            self.assertTrue(ok2["status"], msg=ok2.get("differences"))

    def test_load_rejects_nonstring_nested_provenance_elements(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            good = json.loads((Path(out) / "metadata.json").read_text())
            mutations = (
                ("argv ints", {"command": dict(
                    good["command"], argv=[1, 2, None])}),
                ("orig_argv ints", {"command": dict(
                    good["command"], orig_argv=["x", 5])}),
                ("shell int", {"command": dict(good["command"], shell=7)}),
                ("distributions ints", {"environment": dict(
                    good["environment"], distributions=[1, 2])}),
                ("hostname int", {"environment": dict(
                    good["environment"], hostname=9)}),
                ("git branch int", {"git": dict(good["git"], branch=3)}),
            )
            for label, mut in mutations:
                m = json.loads(json.dumps(good))
                m.update(mut)
                (Path(out) / "metadata.json").write_text(
                    json.dumps(m, sort_keys=True, indent=2) + "\n")
                bad = diagnostics.load_diagnostic(out)
                self.assertFalse(bad["status"], msg=label)
            (Path(out) / "metadata.json").write_text(
                json.dumps(good, sort_keys=True, indent=2) + "\n")

    def test_load_rejects_strict_timestamps_counts_alloc(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            good = json.loads((Path(out) / "metadata.json").read_text())
            cases = (
                {"started_at": "not-a-time"},
                {"finished_at": ""},
                {"started_at_scope": "wrong"},
                {"finished_at_scope": "diagnostics_exit"},
                {"decision_count": "8"},
                {"elapsed_monotonic_seconds": "fast"},
                {"peak_python_allocation_bytes": "unmeasured"},
                {"peak_python_allocation_bytes": -1},
                {"allocation_note": "measured 5"},
            )
            for mut in cases:
                m = json.loads(json.dumps(good))
                m.update(mut)
                (Path(out) / "metadata.json").write_text(
                    json.dumps(m, sort_keys=True, indent=2) + "\n")
                bad = diagnostics.load_diagnostic(out)
                self.assertFalse(bad["status"], msg=mut)
            (Path(out) / "metadata.json").write_text(
                json.dumps(good, sort_keys=True, indent=2) + "\n")

    def test_load_rejects_subdirectory_and_parent_symlink(self):
        from reliable_alerting import diagnostics
        import os as _os
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            sub = Path(out) / "extra_dir"
            sub.mkdir()
            (sub / "x.json").write_text("{}")
            bad = diagnostics.load_diagnostic(out)
            self.assertFalse(bad["status"])
            import shutil as _shutil
            _shutil.rmtree(sub)
            # parent symlink: real dir reached via symlinked parent
            real_parent = Path(tmp) / "realparent"
            real_parent.mkdir()
            inner = real_parent / "inner"
            inner.mkdir()
            # build under real paths, then load via symlinked parent
            run2 = base_source_run(str(inner), name="src2")
            cfg2 = str(inner / "c.json")
            Path(cfg2).write_text(json.dumps(base_diag_config(),
                                             sort_keys=True, indent=2) + "\n")
            real_out = str(inner / "d2")
            diagnostics.run_diagnostic(run2, cfg2, real_out)
            link_parent = str(Path(tmp) / "linkparent")
            _os.symlink(real_parent, link_parent)
            via_parent = str(Path(link_parent) / "inner" / "d2")
            bad2 = diagnostics.load_diagnostic(via_parent)
            self.assertFalse(bad2["status"])
            self.assertTrue(any("symlink" in d.lower()
                                for d in bad2["differences"]))

    def test_load_symlinked_artifact_refused_before_read(self):
        from reliable_alerting import diagnostics
        import os as _os
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-out")
            diagnostics.run_diagnostic(run, cfg_p, out)
            target = Path(out) / "config.json"
            saved = target.read_text()
            target.unlink()
            _os.symlink("/etc/hosts", target)
            bad = diagnostics.load_diagnostic(out)
            self.assertFalse(bad["status"])
            self.assertTrue(any("symlink refused" in d.lower()
                                for d in bad["differences"]))

    def test_run_refuses_symlinked_source_artifact(self):
        from reliable_alerting import diagnostics
        import os as _os
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            pred = Path(run) / "predictions.csv"
            saved = pred.read_bytes()
            pred.unlink()
            _os.symlink("/etc/hosts", pred)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            with self.assertRaisesRegex(ValueError, "symlink refused"):
                diagnostics.run_diagnostic(
                    run, cfg_p, str(Path(tmp) / "diag-out2"))

    def test_cli_and_no_overwrite(self):
        from reliable_alerting import diagnostics
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            run = base_source_run(tmp)
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(base_diag_config(), sort_keys=True,
                                    indent=2, allow_nan=False) + "\n")
            out = str(Path(tmp) / "diag-cli")
            import os as _os
            env = dict(_os.environ)
            env["PYTHONPATH"] = str(REPO / "src") + _os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.diagnostics",
                 "--run", run, "--config", cfg_p, "--output", out],
                cwd=str(REPO), capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            report = diagnostics.load_diagnostic(out)
            self.assertTrue(report["status"], msg=report.get("differences"))
            before = sorted(p.name for p in Path(out).iterdir())
            proc2 = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.diagnostics",
                 "--run", run, "--config", cfg_p, "--output", out],
                cwd=str(REPO), capture_output=True, text=True, env=env)
            self.assertNotEqual(proc2.returncode, 0)
            self.assertEqual(sorted(p.name for p in Path(out).iterdir()), before)

    def test_whitelist_covers_new_files(self):
        from reliable_alerting import provenance
        for rel in ("src/reliable_alerting/diagnostics.py",
                    "tests/test_diagnostics.py",
                    "tests/test_diagnostic_evidence.py",
                    "configs/day05-diagnostic.json"):
            self.assertIn(rel, provenance.WHITELIST)
            self.assertTrue((REPO / rel).is_file(), msg=rel)

    def test_saved_config_matches_shipped(self):
        shipped = json.loads(DIAG_CONFIG.read_text())
        self.assertEqual(shipped, base_diag_config())


if __name__ == "__main__":
    unittest.main()
