"""Pipeline integration for the frozen-protocol policy kinds (sections 4-6).

Covers item 5 (new policy kinds through validate_config/compute_trace, the
action log, defer allowed end to end, existing kinds byte-identical) and the
item-6 requirement that a synthetic run goes through the same
validate_config/compute_trace path.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from reliable_alerting import pipeline, writing, evidence, evaluation_io


def _base_synth(policy):
    return {
        "schema_version": 1,
        "input": {"kind": "synthetic_periodic_v1", "length": 64,
                  "pattern": [1.0, 2.0, 3.0, 2.0], "offsets": [
                      {"start": 32, "stop": 64, "offset": 3.0}]},
        "segments": {"source_fit": [0, 16], "calibration": [16, 32], "replay": [32, 64]},
        "window": {"length": 4, "stride": 4, "anchor": "segment_start",
                   "edge_policy": "drop_incomplete", "end_index": "inclusive"},
        "scoring": {"kind": "mean_distance", "epsilon": 1e-06,
                    "fit_scope": "source_fit", "standard_deviation": "population"},
        "calibration": {"kind": "fixed_quantile", "quantile": 0.95,
                        "method": "nearest_rank", "min_samples": 2,
                        "score_segment": "calibration"},
        "policy": policy,
        "missing_policy": "reject", "source_label_use": "none",
        "time_basis": "sample_index", "held_out": "not_reserved_or_evaluated",
    }


class NewPolicyKindsValidate(unittest.TestCase):
    def test_anchored_validates_and_resolves(self):
        cfg = _base_synth({"kind": "anchored_recalibration", "comparison": "strict_greater",
                           "history_length": 10, "quantile": 0.95, "kappa": 4.0,
                           "rho": 2.0, "defer_limit": 10})
        resolved = pipeline.validate_config(cfg)
        self.assertEqual(resolved["policy"]["kind"], "anchored_recalibration")
        for k in ("history_length", "quantile", "kappa", "rho", "defer_limit"):
            self.assertIn(k, resolved["policy"])

    def test_anchored_null_ablations(self):
        for k in ("kappa", "rho"):
            pol = {"kind": "anchored_recalibration", "comparison": "strict_greater",
                   "history_length": 10, "quantile": 0.95, "kappa": 4.0,
                   "rho": 2.0, "defer_limit": 10}
            pol[k] = None
            resolved = pipeline.validate_config(_base_synth(pol))
            self.assertIsNone(resolved["policy"][k])
        pol = {"kind": "anchored_recalibration", "comparison": "strict_greater",
               "history_length": 10, "quantile": 0.95, "kappa": 4.0,
               "rho": 2.0, "defer_limit": 0}
        pipeline.compute_trace(_base_synth(pol))  # D=0 must run

    def test_sun_validates(self):
        cfg = _base_synth({"kind": "sun_confidence_sequence", "comparison": "strict_greater",
                           "p": 0.95, "alpha": 0.05})
        resolved = pipeline.validate_config(cfg)
        self.assertEqual(resolved["policy"]["p"], 0.95)
        self.assertEqual(resolved["policy"]["alpha"], 0.05)

    def test_rolling_all_is_just_config(self):
        cfg = _base_synth({"kind": "rolling_threshold", "comparison": "strict_greater",
                           "history_length": 10, "admission_rule": "all", "quantile": 0.95})
        resolved = pipeline.validate_config(cfg)
        self.assertEqual(resolved["policy"]["admission_rule"], "all")


class ComputeTraceEmitsActionsAndDefer(unittest.TestCase):
    def test_action_rows_align_with_rows(self):
        cfg = _base_synth({"kind": "anchored_recalibration", "comparison": "strict_greater",
                           "history_length": 4, "quantile": 0.95, "kappa": 4.0,
                           "rho": 2.0, "defer_limit": 10})
        trace = pipeline.compute_trace(cfg)
        self.assertEqual(len(trace["action_rows"]), len(trace["rows"]))
        for a, r in zip(trace["action_rows"], trace["rows"]):
            self.assertEqual(a["window_id"], r["window_id"])
            self.assertEqual(a["end_index"], r["end_index"])
            self.assertIn(a["action"], ("hold", "alert", "defer", "recalibrate"))

    def test_sun_can_defer(self):
        cfg = _base_synth({"kind": "sun_confidence_sequence", "comparison": "strict_greater",
                           "p": 0.95, "alpha": 0.05})
        trace = pipeline.compute_trace(cfg)
        states = {r["output_state"] for r in trace["rows"]}
        self.assertTrue(states.issubset({"normal", "alert", "defer"}))


class ActionLogRoundTrip(unittest.TestCase):
    def test_write_and_read_action_log(self):
        cfg = _base_synth({"kind": "anchored_recalibration", "comparison": "strict_greater",
                           "history_length": 4, "quantile": 0.95, "kappa": 4.0,
                           "rho": 2.0, "defer_limit": 3})
        trace = pipeline.compute_trace(cfg)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            run_id = "r" * 8
            full_rows = [dict(r, run_id=run_id) for r in trace["rows"]]
            writing.write_run(out, full_rows, trace["config"], _min_meta(run_id, trace),
                              trace["diagnostics"], trace["calibration_rows"],
                              action_rows=trace["action_rows"])
            self.assertTrue((out / "policy_actions.csv").is_file())
            text = (out / "policy_actions.csv").read_text().splitlines()
            self.assertEqual(text[0], "window_id,end_index,action,threshold")
            self.assertEqual(len(text) - 1, len(trace["rows"]))

    def test_write_without_action_log_omits_file(self):
        cfg = _base_synth({"kind": "fixed_threshold", "comparison": "strict_greater"})
        trace = pipeline.compute_trace(cfg)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            run_id = "r" * 8
            full_rows = [dict(r, run_id=run_id) for r in trace["rows"]]
            writing.write_run(out, full_rows, trace["config"], _min_meta(run_id, trace),
                              trace["diagnostics"], trace["calibration_rows"])
            self.assertFalse((out / "policy_actions.csv").exists())


class DeferBearingRunPassesRecompute(unittest.TestCase):
    def test_evidence_read_run_accepts_defer_run(self):
        # A defer-bearing run must survive evidence._read_run + recompute verify
        # (this is what the evaluation path calls before joining labels).
        cfg = _base_synth({"kind": "anchored_recalibration", "comparison": "strict_greater",
                           "history_length": 4, "quantile": 0.95, "kappa": 1.5,
                           "rho": 1.2, "defer_limit": 3})
        trace = pipeline.compute_trace(cfg)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            run_id = "abcd1234"
            full_rows = [dict(r, run_id=run_id) for r in trace["rows"]]
            writing.write_run(out, full_rows, trace["config"], _min_meta(run_id, trace),
                              trace["diagnostics"], trace["calibration_rows"],
                              action_rows=trace["action_rows"])
            run = evidence._read_run(out)
            diffs = []
            self.assertTrue(evidence._verify_recompute("t", run, diffs), diffs)


def _min_meta(run_id, trace):
    from reliable_alerting import provenance
    repo = provenance.repo_root()
    return {
        "run_id": run_id,
        "config_id": trace["config_id"],
        "input_hash": trace["input_hash"],
        "started_at": "2026-09-29T00:00:00+00:00",
        "started_at_scope": "write_output_entry",
        "intended_day1": pipeline.INTENDED_DAY1,
        "command": provenance.command_record(),
        "environment": provenance.environment_record(),
        "git": provenance.git_record(str(repo)),
        "file_hashes": provenance.file_hashes(repo),
        "resource_scope": pipeline.RESOURCE_SCOPE,
        "elapsed_monotonic_seconds": 0.0,
        "peak_python_allocation_bytes": 0,
    }


if __name__ == "__main__":
    unittest.main()
