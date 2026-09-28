"""test_verification.py - tests for research/verification.py.

Three groups:
  1. Hand cases on tiny temp CSVs with known answers.
  2. Held-out guard: label-reading checks refuse reserved files BEFORE any
     file access, and the reserved list stays in sync with data/manifest.md.
  3. Regression checks pinning the Day-2 verified facts for the development
     stream SKAB/valve1/0.csv (checksum, ordering, source-normal segment).
     These skip if the teammate repo's data file is absent.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

# reliable_alerting is importable directly (editable install); no conftest
# bridge needed. Add the sibling research/ folder so `import verification`
# resolves to Reliable-Alerting/research/verification.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "research"))

import verification as v  # noqa: E402

_MANIFEST = _REPO_ROOT / "manifest.md"
_VALVE1 = _REPO_ROOT / "SKAB" / "valve1" / "0.csv"
# Recorded in data/manifest.md on 2026-09-27 (working-tree bytes, CRLF checkout).
_VALVE1_SHA256 = "90f70a75cf359e5e7b0fffa0644fdbac6733a71510e7891b6d0427effd750cb6"

_HEADER = "datetime;Current;anomaly"


def _write_csv(lines):
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="nakul-verif-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join([_HEADER] + lines) + "\n")
    return path


class HandCaseTest(unittest.TestCase):
    def setUp(self):
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            os.remove(p)

    def _csv(self, lines):
        p = _write_csv(lines)
        self.paths.append(p)
        return p

    def test_label_runs_half_open(self):
        p = self._csv([
            "2020-01-01 00:00:00;1.0;0.0",
            "2020-01-01 00:00:01;1.0;1.0",
            "2020-01-01 00:00:02;1.0;1.0",
            "2020-01-01 00:00:03;1.0;0.0",
            "2020-01-01 00:00:04;1.0;1",
        ])
        self.assertEqual(v.label_runs(p), [(1, 3), (4, 5)])

    def test_segment_label_counts_clip_runs(self):
        runs = [(1, 3), (4, 5)]
        counts = v.segment_label_counts(runs, {"a": (0, 2), "b": (2, 5)})
        self.assertEqual(counts, {"a": 1, "b": 2})

    def test_non_binary_label_rejected(self):
        p = self._csv(["2020-01-01 00:00:00;1.0;2.0"])
        with self.assertRaises(ValueError):
            v.label_runs(p)

    def test_timestamp_report_order_and_cadence(self):
        p = self._csv([
            "2020-01-01 00:00:00;1.0;0",
            "2020-01-01 00:00:01;1.0;0",
            "2020-01-01 00:00:03;1.0;0",
            "2020-01-01 00:00:03;1.0;0",
        ])
        rep = v.timestamp_report(v.read_rows(p))
        self.assertEqual(rep["rows"], 4)
        self.assertEqual(rep["delta_histogram"], {0.0: 1, 1.0: 1, 2.0: 1})
        self.assertEqual(len(rep["violations"]), 1)
        self.assertEqual(rep["violations"][0][0], 3)

    def test_missing_cells(self):
        p = self._csv([
            "2020-01-01 00:00:00;1.0;0",
            "2020-01-01 00:00:01; ;0",
            "2020-01-01 00:00:02;;0",
        ])
        self.assertEqual(v.missing_cells(v.read_rows(p), "Current"), [1, 2])

    def test_checksum_matches_hashlib(self):
        import hashlib
        p = self._csv(["2020-01-01 00:00:00;1.0;0"])
        with open(p, "rb") as fh:
            self.assertEqual(v.file_sha256(p), hashlib.sha256(fh.read()).hexdigest())


class HeldOutGuardTest(unittest.TestCase):
    def test_reserved_spellings_detected(self):
        for p in ("SKAB/other/21.csv", "SKAB\\other\\21.csv",
                  "C:/x/Reliable-Alerting/SKAB/other/21.csv",
                  r"C:\x\Reliable-Alerting\SKAB\OTHER\21.CSV"):
            self.assertTrue(v.is_reserved(p), p)

    def test_non_reserved_not_detected(self):
        for p in ("SKAB/valve1/0.csv", "SKAB/other/12.csv", "SKAB/other/121.csv"):
            self.assertFalse(v.is_reserved(p), p)

    def test_label_runs_refuses_before_opening(self):
        # Path does not exist: a ReservedHeldOutError (not FileNotFoundError)
        # proves the refusal happens before any file access.
        missing = str(Path(tempfile.gettempdir()) / "no-such" / "SKAB" / "other" / "21.csv")
        with self.assertRaises(v.ReservedHeldOutError):
            v.label_runs(missing)

    def test_reserved_list_matches_manifest(self):
        text = _MANIFEST.read_text(encoding="utf-8-sig")
        status = re.search(r"\*\*Current status: RESERVED\W+(\S+?)\*\*", text)
        self.assertIsNotNone(status, "manifest has no 'Current status: RESERVED' line")
        self.assertEqual((status.group(1),), v.RESERVED_HELD_OUT)


@unittest.skipUnless(_VALVE1.is_file(), f"development stream file absent: {_VALVE1}")
class Valve1VerifiedFactsTest(unittest.TestCase):
    """Pins the Day-2 verification of the development stream."""

    @classmethod
    def setUpClass(cls):
        cls.rows = v.read_rows(_VALVE1)

    def test_checksum_matches_manifest(self):
        self.assertEqual(v.file_sha256(_VALVE1), _VALVE1_SHA256)
        self.assertIn(_VALVE1_SHA256, _MANIFEST.read_text(encoding="utf-8-sig"))

    def test_row_count(self):
        self.assertEqual(len(self.rows), 1148)

    def test_timestamps_strictly_increasing(self):
        rep = v.timestamp_report(self.rows)
        self.assertEqual(rep["violations"], [])
        self.assertEqual(rep["delta_histogram"], {1.0: 1095, 2.0: 52})

    def test_no_missing_current(self):
        self.assertEqual(v.missing_cells(self.rows, "Current"), [])

    def test_source_fit_is_source_normal(self):
        runs = v.label_runs(_VALVE1)
        # Corrected split (2026-09-27): calibration moved [400,800) -> [400,574)
        # so the calibration pool is now source-normal. Row 574 is the first
        # anomalous row (anomaly run [574,975)); the whole run now falls in replay.
        counts = v.segment_label_counts(
            runs, {"source_fit": (0, 400), "calibration": (400, 574), "replay": (574, 1148)})
        self.assertEqual(runs, [(574, 975)])
        self.assertEqual(counts["source_fit"], 0)
        # The point of the fix: calibration segment is now anomaly-free.
        self.assertEqual(counts["calibration"], 0)
        self.assertEqual(counts["replay"], 401)
        self.assertEqual(counts, {"source_fit": 0, "calibration": 0, "replay": 401})


if __name__ == "__main__":
    unittest.main()