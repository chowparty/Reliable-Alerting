"""test_realstream_leakage.py - Day 3 leakage & causality audits on real data.

Turns the Day-2 one-off audits into saved, re-runnable tests, scoped to
Day 3's comparison pair: the FIXED and ROLLING policies on valve1. (The other
three policies are the Day-4 family; the helpers here are written so Day 4 can
extend POLICIES without rework.)

Each test drives the UNMODIFIED teammate pipeline (reliable_alerting) against
a TEMPORARY copy of the valve1 CSV created outside both repositories, and
asserts:
  - label flip: replacing every anomaly/changepoint label leaves scores,
    decisions, thresholds, and features byte-for-byte identical.
  - future perturbation: changing values inside the replay tail leaves every
    earlier decision (and the fitted scorer + calibration threshold) unchanged.

Nothing is written to result/ (authoritative, tracked) or results/ (generated,
gitignored). Temporary files live in the OS temp dir and are deleted.

Skips cleanly if the valve1 data file or the result configs are absent.
"""
import copy
import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# reliable_alerting imports directly (editable install); no conftest bridge.

from reliable_alerting import pipeline  # noqa: E402

# Reliable-Alerting repo root (three levels up from this test file, then over).
_BTP_ROOT = Path(__file__).resolve().parents[1]
_RA = _BTP_ROOT
_VALVE1 = _RA / "SKAB" / "valve1" / "0.csv"

# All five valve1 policies (Day 5, Task 4). Each maps to its authoritative
# result config (source of truth = result/, singular). The leakage/causality
# invariants below apply to every policy, features included.
POLICIES = ("fixed_threshold", "rolling_threshold", "k_consecutive",
            "m_of_n", "hysteresis")


def _result_config(policy_name):
    return _RA / "result" / "valve1" / policy_name / "config.json"


def _load_config_pointed_at_local(policy_name):
    """Load the authoritative result config and repoint its input path at the
    valve1 file in THIS checkout (the saved config stores an absolute path from
    the machine that produced it)."""
    cfg = json.loads(_result_config(policy_name).read_text(encoding="utf-8"))
    cfg["input"]["path"] = str(_VALVE1)
    return cfg


def _trace_signature(trace):
    """Label-free identity of a trace: per-row score/state/threshold/features
    plus fitted scorer and calibration threshold."""
    rows = [(r["window_id"], r["score"], r["output_state"], r["threshold"],
             tuple(r.get("features", ()))) for r in trace["rows"]]
    return {"rows": rows, "scorer": trace["scorer"], "threshold": trace["threshold"]}


def _write_temp_csv(lines):
    d = tempfile.mkdtemp(prefix="nakul-day3-leak-")
    p = os.path.join(d, "valve1-variant.csv")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return d, p


_SKIP = not (_VALVE1.is_file()
             and all(_result_config(p).is_file() for p in POLICIES))


@unittest.skipIf(_SKIP, "valve1 data or result configs absent")
class LabelFlipInvarianceTest(unittest.TestCase):
    """Flipping every label must not change any decision, score, or feature."""

    @classmethod
    def setUpClass(cls):
        cls.src = _VALVE1.read_text(encoding="utf-8").splitlines()

    def _flipped_lines(self):
        out = [self.src[0]]  # header
        for line in self.src[1:]:
            p = line.split(";")
            # columns: ...;anomaly(9);changepoint(10)
            p[9] = "0.0" if p[9] == "1.0" else "1.0"
            p[10] = "1.0" if p[10] == "0.0" else "0.0"
            out.append(";".join(p))
        return out

    def test_all_policies_invariant_to_label_flip(self):
        flipped = self._flipped_lines()
        d, p = _write_temp_csv(flipped)
        try:
            for name in POLICIES:
                real = pipeline.compute_trace(_load_config_pointed_at_local(name))
                alt_cfg = _load_config_pointed_at_local(name)
                alt_cfg["input"]["path"] = p
                alt = pipeline.compute_trace(alt_cfg)
                self.assertEqual(
                    _trace_signature(real), _trace_signature(alt),
                    f"{name}: label flip changed the trace")
                # explicit feature-value invariance (Day 5, Task 4): the saved
                # median/spread columns must be byte-identical under label flip.
                real_feats = [tuple(r.get("features", ())) for r in real["rows"]]
                alt_feats = [tuple(r.get("features", ())) for r in alt["rows"]]
                self.assertEqual(
                    real_feats, alt_feats,
                    f"{name}: label flip changed a feature value")
        finally:
            os.remove(p); os.rmdir(d)
        self.assertFalse(os.path.exists(d))


@unittest.skipIf(_SKIP, "valve1 data or result configs absent")
class FuturePerturbationCausalityTest(unittest.TestCase):
    """Changing values in the replay tail must not change earlier decisions,
    nor the fitted scorer / calibration threshold."""

    @classmethod
    def setUpClass(cls):
        cls.src = _VALVE1.read_text(encoding="utf-8").splitlines()

    def _perturbed_lines(self, from_data_row, value="999.0"):
        out = [self.src[0]]
        for i, line in enumerate(self.src[1:]):  # i = 0-indexed data row
            p = line.split(";")
            if i >= from_data_row:
                p[3] = value  # Current column
            out.append(";".join(p))
        return out

    def test_earlier_decisions_and_calibration_unchanged(self):
        # valve1 replay is [574,1148); perturb from row 1000 (well inside replay)
        # and also from row 900. Earlier windows and the calibration threshold
        # (fitted on [400,574)) must be identical.
        for cut in (1000, 900):
            lines = self._perturbed_lines(cut)
            d, p = _write_temp_csv(lines)
            try:
                for name in POLICIES:
                    real = pipeline.compute_trace(_load_config_pointed_at_local(name))
                    alt_cfg = _load_config_pointed_at_local(name)
                    alt_cfg["input"]["path"] = p
                    alt = pipeline.compute_trace(alt_cfg)
                    # calibration threshold and scorer unchanged (fit precedes cut)
                    self.assertEqual(real["threshold"], alt["threshold"],
                                     f"{name}: calibration threshold changed (cut {cut})")
                    self.assertEqual(real["scorer"], alt["scorer"],
                                     f"{name}: scorer changed (cut {cut})")
                    # every decision whose window ends strictly before the cut
                    # must be identical
                    def earlier(trace):
                        # include features: a future value must not change any
                        # earlier window's median/spread either (Day 5, Task 4).
                        return [(r["window_id"], r["score"], r["output_state"],
                                 r["threshold"], tuple(r.get("features", ())))
                                for r in trace["rows"] if r["end_index"] < cut]
                    self.assertEqual(earlier(real), earlier(alt),
                                     f"{name}: an earlier decision changed (cut {cut})")
                    self.assertTrue(len(earlier(real)) > 0,
                                    f"{name}: no earlier windows to check at cut {cut}")
            finally:
                os.remove(p); os.rmdir(d)

    def test_window_self_value_change_does_not_alter_its_own_threshold(self):
        """Rolling: a window's own value must not set the cutoff that judges it
        (the cutoff for window t uses history frozen before t)."""
        # Perturb exactly ONE replay window's samples and confirm the threshold
        # recorded on that same window row is unchanged vs the unperturbed run.
        name = "rolling_threshold"
        real = pipeline.compute_trace(_load_config_pointed_at_local(name))
        # choose a mid-replay window and perturb only its 4 samples
        target = real["rows"][20]
        s0, e0 = target["start_index"], target["end_index"]
        lines = [self.src[0]]
        for i, line in enumerate(self.src[1:]):
            p = line.split(";")
            if s0 <= i <= e0:
                p[3] = "999.0"
            lines.append(";".join(p))
        d, p = _write_temp_csv(lines)
        try:
            alt_cfg = _load_config_pointed_at_local(name)
            alt_cfg["input"]["path"] = p
            alt = pipeline.compute_trace(alt_cfg)
            self.assertEqual(
                real["rows"][20]["threshold"], alt["rows"][20]["threshold"],
                "window's own value changed the threshold judging that window")
        finally:
            os.remove(p); os.rmdir(d)


if __name__ == "__main__":
    unittest.main()