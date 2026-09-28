import tempfile
import unittest
import csv
import json
from pathlib import Path

import run_real_streams


class RealRunnerSafetyTest(unittest.TestCase):
    def test_valve2_calibration_ends_before_first_anomaly(self):
        stream_path, length, calibration_end = run_real_streams.STREAMS["valve2"]
        with open(run_real_streams.here / stream_path, newline="") as fh:
            labels = [row["anomaly"] for row in csv.DictReader(fh, delimiter=";")]
        self.assertEqual(length, len(labels))
        self.assertTrue(all(float(x) == 0 for x in labels[400:calibration_end]))
        self.assertEqual(float(labels[calibration_end]), 1.0)
        event = json.loads((run_real_streams.here / "configs/day04-valve2-labels.json").read_text())["events"][0]
        self.assertTrue(all(float(x) == 1.0 for x in labels[event["start"]:event["stop"]]))
        self.assertEqual(float(labels[event["stop"]]), 0.0)
        with tempfile.TemporaryDirectory() as tmp:
            run_real_streams.run_policy(
                "valve2", stream_path, length,
                {"kind": "fixed_threshold", "comparison": "strict_greater"},
                output_root=Path(tmp),
            )
            config = json.loads((Path(tmp) / "valve2" / "fixed_threshold" / "config.json").read_text())
            self.assertEqual(config["segments"]["calibration"], [400, calibration_end])
            self.assertEqual(config["segments"]["replay"], [calibration_end, length])

    def test_existing_run_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "valve1" / "fixed_threshold"
            output.mkdir(parents=True)
            marker = output / "marker"
            marker.write_text("preserve")
            with self.assertRaises(FileExistsError):
                run_real_streams.run_policy(
                    "valve1", "SKAB/valve1/0.csv", 1148,
                    {"kind": "fixed_threshold", "comparison": "strict_greater"},
                    output_root=Path(tmp),
                )
            self.assertEqual(marker.read_text(), "preserve")
