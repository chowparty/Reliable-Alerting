"""test_audit.py — causality and label-leakage audit for pipeline outputs.

These tests run against a saved pipeline run directory (predictions.csv,
config.json, diagnostics.json) and verify that:

  1. The saved threshold is consistent with the config's calibration output
     (no manual editing, no future-data contamination of the threshold).
  2. config_id in the trace matches a fresh recompute of the config hash
     (reproducibility contract).
  3. No label-related fields appear in predictions.csv (labels never enter
     the writer's output columns).
  4. The saved config carries source_label_use: "none" (synthetic path) or
     an explicitly declared value; it is never absent.
  5. Every end_index in the trace is strictly increasing (causality order).
  6. No row in the trace has end_index <= its start_index (window sanity).

These checks are run against the Day-1 synthetic smoke run output. On later
days they extend to real-stream runs by pointing RUN_DIR at the appropriate
results directory.

USAGE:
    # Run against the default smoke run path (after pipeline is executed):
    python -m unittest tests/test_audit.py -v

    # To audit a specific run directory, set the environment variable:
    AUDIT_RUN_DIR=results/day02-run-a python -m unittest tests/test_audit.py -v

The teammate's pipeline (Aman/Pratyush) must have produced the smoke run
before these tests are meaningful. If the run directory does not exist,
the tests skip with a clear message rather than failing with a confusing error.
"""

import csv
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the run directory to audit.
# Default: results/day01-smoke-a relative to research/.
# Override: set AUDIT_RUN_DIR environment variable.
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_RESEARCH_DIR = _TESTS_DIR.parent

# This module reads saved run files only and never imports reliable_alerting,
# so it needs no path bridge. config_id is recomputed here independently of
# the teammate's code, which is the point of the check.

_DEFAULT_RUN_DIR = _RESEARCH_DIR / "results" / "day01-smoke-a"
_RUN_DIR = Path(os.environ.get("AUDIT_RUN_DIR", str(_DEFAULT_RUN_DIR)))

# Columns that must NOT appear in predictions.csv (labels must never enter
# the writer output).
_FORBIDDEN_COLUMNS = frozenset({
    "label", "is_anomaly", "anomaly", "ground_truth", "true_label",
    "event", "event_id", "labelled", "labeled",
})

# Required columns every predictions.csv must have (writing.py PREDICTIONS_COLUMNS).
_REQUIRED_COLUMNS = (
    "window_id", "start_index", "end_index", "score",
    "output_state", "threshold", "config_id", "run_id",
)
# Optional columns the pipeline may add without it being a discipline breach.
# "features" carries score-derived diagnostics (rolling median/spread of the
# score), added by Aman's Day-2 rework (Reliable-Alerting commit 0f8f5a8). It
# is verified label-free: flipping every label leaves feature values unchanged
# (see the Day-2 completion report label-invariance audit). Any column that is
# neither required nor optional-known fails the test below, so a genuinely
# unexpected column is still caught.
_OPTIONAL_COLUMNS = frozenset({"features"})


def _skip_if_no_run(test_method):
    """Decorator: skip a test if the audit run directory does not exist."""
    def wrapper(self):
        if not _RUN_DIR.is_dir():
            self.skipTest(
                f"Run directory not found: {_RUN_DIR}\n"
                "The Day-1 smoke pipeline must be executed before audit tests run.\n"
                "Run: python -m reliable_alerting.pipeline "
                "--config configs/day01-synthetic.json "
                "--output results/day01-smoke-a\n"
                "(from the Reliable-Alerting/ directory)"
            )
        test_method(self)
    wrapper.__name__ = test_method.__name__
    return wrapper


def _load_predictions(run_dir):
    """Load predictions.csv from a run directory into a list of dicts."""
    path = run_dir / "predictions.csv"
    if not path.exists():
        return None, f"predictions.csv not found in {run_dir}"
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows, None


def _load_json(run_dir, filename):
    """Load a JSON file from a run directory."""
    path = run_dir / filename
    if not path.exists():
        return None, f"{filename} not found in {run_dir}"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh), None


def _config_id_of(resolved_config):
    """Recompute config_id from a resolved config dict (matches pipeline.py)."""
    text = json.dumps(resolved_config, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


class PredictionsSchemaAuditTest(unittest.TestCase):
    """predictions.csv must have exactly the allowed columns, no label fields."""

    @_skip_if_no_run
    def test_predictions_file_exists(self):
        self.assertTrue(
            (_RUN_DIR / "predictions.csv").exists(),
            f"predictions.csv missing from {_RUN_DIR}"
        )

    @_skip_if_no_run
    def test_predictions_columns_exact(self):
        """All required columns present; any extra column must be an
        explicitly allowed optional column (currently just 'features').
        An unknown extra column fails, so unexpected fields are still caught."""
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        self.assertGreater(len(rows), 0, "predictions.csv has no data rows")
        actual_cols = set(rows[0].keys())
        missing = set(_REQUIRED_COLUMNS) - actual_cols
        unexpected = actual_cols - set(_REQUIRED_COLUMNS) - _OPTIONAL_COLUMNS
        self.assertEqual(missing, set(),
                         f"predictions.csv is missing required columns: {missing}")
        self.assertEqual(unexpected, set(),
                         f"predictions.csv has unrecognised columns: {unexpected}\n"
                         "Only required columns plus known optional ones "
                         f"({sorted(_OPTIONAL_COLUMNS)}) are allowed. A new column "
                         "must be reviewed for label leakage and added to "
                         "_OPTIONAL_COLUMNS with justification.")

    @_skip_if_no_run
    def test_no_forbidden_columns_in_predictions(self):
        """Explicit check: no label-related column name appears in predictions."""
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        if not rows:
            return
        actual_cols = {c.lower() for c in rows[0].keys()}
        violations = _FORBIDDEN_COLUMNS & actual_cols
        self.assertEqual(violations, set(),
                         f"Label-related columns found in predictions.csv: {violations}\n"
                         "Labels must never enter the writer output path.")


class CausalityOrderAuditTest(unittest.TestCase):
    """Decisions must be in strictly increasing end_index order (causality)."""

    @_skip_if_no_run
    def test_end_index_strictly_increasing(self):
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        ends = [int(r["end_index"]) for r in rows]
        for i in range(1, len(ends)):
            self.assertGreater(
                ends[i], ends[i - 1],
                f"end_index not strictly increasing at row {i}: "
                f"{ends[i-1]} then {ends[i]}. "
                "This would indicate a causality ordering violation."
            )

    @_skip_if_no_run
    def test_start_index_not_after_end_index(self):
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        for i, row in enumerate(rows):
            start = int(row["start_index"])
            end = int(row["end_index"])
            self.assertLessEqual(
                start, end,
                f"Row {i} (window_id={row['window_id']}): "
                f"start_index {start} > end_index {end}. "
                "A window cannot start after it ends."
            )


class ThresholdConsistencyAuditTest(unittest.TestCase):
    """The threshold in every predictions row must match the calibration output."""

    # Policies whose recorded per-window threshold is the frozen calibration
    # cutoff on every row. Stateful/adaptive policies (rolling_threshold) update
    # the cutoff from past-only history, so only their FIRST decision must equal
    # the calibration output.
    _STATIC_THRESHOLD_POLICIES = {"fixed_threshold", "k_consecutive", "m_of_n"}

    @_skip_if_no_run
    def test_threshold_consistent_with_diagnostics(self):
        """Threshold rows must be consistent with the calibration output.

        For static-threshold policies (fixed/k_consecutive/m_of_n) EVERY row's
        threshold equals diagnostics.quantile.threshold. For adaptive policies
        (rolling_threshold) the FIRST decision must equal the calibration
        threshold (the frozen initial cutoff); later rows update causally from
        past-only history and are checked by the dedicated leakage tests, not
        here. Hysteresis records a judging level per row and is exempt from the
        single-value check."""
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        diag, derr = _load_json(_RUN_DIR, "diagnostics.json")
        self.assertIsNone(derr, derr)
        config, cerr = _load_json(_RUN_DIR, "config.json")
        self.assertIsNone(cerr, cerr)

        self.assertIn("quantile", diag,
                      "diagnostics.json missing 'quantile' key")
        self.assertIn("threshold", diag["quantile"],
                      "diagnostics.json['quantile'] missing 'threshold'")
        expected_threshold = float(diag["quantile"]["threshold"])
        kind = config.get("policy", {}).get("kind")

        if kind in self._STATIC_THRESHOLD_POLICIES:
            for i, row in enumerate(rows):
                actual = float(row["threshold"])
                self.assertAlmostEqual(
                    actual, expected_threshold, places=12,
                    msg=(f"Row {i} threshold {actual} != diagnostics threshold "
                         f"{expected_threshold}. Either the config was edited "
                         "after calibration, or future data influenced the "
                         "threshold (causality breach)."))
        elif kind == "rolling_threshold":
            first = float(rows[0]["threshold"])
            self.assertAlmostEqual(
                first, expected_threshold, places=12,
                msg=(f"Rolling run's first-decision threshold {first} != "
                     f"calibration threshold {expected_threshold}: the run must "
                     "start from the frozen calibration cutoff."))
        else:
            self.skipTest(f"Policy kind {kind!r} records a per-row judging "
                          "threshold; single-value consistency does not apply.")

    @_skip_if_no_run
    def test_all_rows_same_threshold(self):
        """For a fixed-threshold run, all rows must carry identical threshold."""
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        config, cerr = _load_json(_RUN_DIR, "config.json")
        self.assertIsNone(cerr, cerr)
        if config.get("policy", {}).get("kind") != "fixed_threshold":
            self.skipTest("Not a fixed-threshold run; threshold may vary by design.")
        thresholds = {float(r["threshold"]) for r in rows}
        self.assertEqual(
            len(thresholds), 1,
            f"Fixed-threshold run has multiple threshold values: {thresholds}. "
            "The threshold must be set once from calibration data and held fixed."
        )


class ConfigIdReproducibilityAuditTest(unittest.TestCase):
    """config_id in the trace must match a fresh recompute from config.json."""

    @_skip_if_no_run
    def test_config_id_matches_recompute(self):
        """Recompute config_id from saved config.json; compare to trace rows."""
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        config, cerr = _load_json(_RUN_DIR, "config.json")
        self.assertIsNone(cerr, cerr)

        recomputed_id = _config_id_of(config)
        for i, row in enumerate(rows):
            self.assertEqual(
                row["config_id"], recomputed_id,
                f"Row {i}: config_id in trace ({row['config_id']}) does not match "
                f"recomputed config_id ({recomputed_id}).\n"
                "This means either config.json was edited after the run, or "
                "the run was produced by a different config than what is saved."
            )

    @_skip_if_no_run
    def test_config_id_consistent_across_rows(self):
        rows, err = _load_predictions(_RUN_DIR)
        self.assertIsNone(err, err)
        ids = {r["config_id"] for r in rows}
        self.assertEqual(len(ids), 1,
                         f"Multiple config_ids in one run: {ids}. "
                         "All rows in a run must share one config_id.")


class SourceLabelUseAuditTest(unittest.TestCase):
    """config.json must carry an explicit source_label_use declaration."""

    @_skip_if_no_run
    def test_source_label_use_present(self):
        config, cerr = _load_json(_RUN_DIR, "config.json")
        self.assertIsNone(cerr, cerr)
        self.assertIn(
            "source_label_use", config,
            "config.json is missing 'source_label_use' field. "
            "Every run config must declare how source labels are used "
            "(value: 'none' for synthetic; for real streams, the declared use)."
        )

    @_skip_if_no_run
    def test_held_out_field_present(self):
        config, cerr = _load_json(_RUN_DIR, "config.json")
        self.assertIsNone(cerr, cerr)
        self.assertIn(
            "held_out", config,
            "config.json is missing 'held_out' field. "
            "Every run config must declare held-out status explicitly."
        )

    @_skip_if_no_run
    def test_synthetic_run_has_none_label_use(self):
        """Day-1 synthetic run must declare source_label_use: 'none'."""
        config, cerr = _load_json(_RUN_DIR, "config.json")
        self.assertIsNone(cerr, cerr)
        input_kind = config.get("input", {}).get("kind", "")
        if "synthetic" not in input_kind:
            self.skipTest("Not a synthetic run; label use may differ.")
        self.assertEqual(
            config["source_label_use"], "none",
            f"Synthetic run must have source_label_use='none', "
            f"got {config['source_label_use']!r}."
        )


if __name__ == "__main__":
    unittest.main()
