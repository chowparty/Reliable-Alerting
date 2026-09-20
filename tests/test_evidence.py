"""Evidence utilities: run comparison and saved-trace SVG figure (stdlib unittest)."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
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


def _write_hand_csv(path, rows):
    header = ["window_id", "start_index", "end_index", "score",
              "output_state", "threshold", "config_id", "run_id"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([r[k] for k in header])


def _hand_rows():
    return [
        {"window_id": "seg:0:1", "start_index": 0, "end_index": 1,
         "score": 0.5, "output_state": "normal", "threshold": 1.0,
         "config_id": "cfg123", "run_id": "run1"},
        {"window_id": "seg:2:3", "start_index": 2, "end_index": 3,
         "score": 2.5, "output_state": "alert", "threshold": 1.0,
         "config_id": "cfg123", "run_id": "run1"},
        # tie: score == threshold -> normal
        {"window_id": "seg:4:5", "start_index": 4, "end_index": 5,
         "score": 1.0, "output_state": "normal", "threshold": 1.0,
         "config_id": "cfg123", "run_id": "run1"},
    ]


class FigureTest(unittest.TestCase):
    def test_hand_csv_end_index_circles_labels_ties(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            csv_p = str(Path(tmp) / "predictions.csv")
            svg_p = str(Path(tmp) / "score.svg")
            _write_hand_csv(csv_p, _hand_rows())
            evidence.render_figure(csv_p, svg_p)
            self.assertTrue(Path(svg_p).is_file())
            tree = ET.parse(svg_p)
            root = tree.getroot()
            circles = [e for e in root.iter() if str(e.tag).endswith("circle")]
            # legend adds 2 swatches without <title>; data points carry window_id titles
            data = [c for c in circles
                    if any(str(t.tag).endswith("title") and t.text and "seg:" in t.text
                           for t in c)]
            self.assertEqual(len(data), 3)
            circles = data
            fills = sorted([c.get("fill") for c in circles])
            self.assertEqual(fills, ["blue", "blue", "red"])
            xs = [float(c.get("cx")) for c in circles]
            self.assertEqual(xs, sorted(xs))
            # end_index plotted: larger end_index -> larger cx
            self.assertLess(xs[0], xs[1])
            self.assertLess(xs[1], xs[2])
            blob = Path(svg_p).read_text()
            for wid in ("seg:0:1", "seg:2:3", "seg:4:5"):
                self.assertIn(wid, blob)
            low = blob.lower()
            self.assertIn("synthetic", low)
            self.assertIn("no quality claim", low)
            self.assertIn("cfg123", blob)
            self.assertIn("predictions.csv", blob)
            # threshold dashed line present
            self.assertIn("stroke-dasharray", blob)

    def test_figure_rejects_bad_schema_and_nonfinite(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            bad_p = str(Path(tmp) / "bad.csv")
            with open(bad_p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["window_id", "start_index", "end_index", "score",
                            "output_state", "threshold", "config_id", "run_id"])
                w.writerow(["seg:0:1", 0, 1, "nan", "normal", 1.0, "c", "r"])
            with self.assertRaises((TypeError, ValueError)):
                evidence.render_figure(bad_p, str(Path(tmp) / "o.svg"))
            missing_p = str(Path(tmp) / "missing.csv")
            with open(missing_p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["window_id", "start_index", "end_index", "score"])
                w.writerow(["seg:0:1", 0, 1, 0.5])
            with self.assertRaises((TypeError, ValueError)):
                evidence.render_figure(missing_p, str(Path(tmp) / "o2.svg"))

    def test_figure_existing_output_preserved(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            csv_p = str(Path(tmp) / "predictions.csv")
            svg_p = str(Path(tmp) / "score.svg")
            _write_hand_csv(csv_p, _hand_rows())
            evidence.render_figure(csv_p, svg_p)
            before = Path(svg_p).read_text()
            with self.assertRaises(FileExistsError):
                evidence.render_figure(csv_p, svg_p)
            self.assertEqual(Path(svg_p).read_text(), before)

    def test_figure_rejects_varying_thresholds_no_output(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            rows = _hand_rows()
            rows[1] = dict(rows[1], threshold=9.0, output_state="normal",
                           score=2.5)
            csv_p = str(Path(tmp) / "predictions.csv")
            svg_p = str(Path(tmp) / "score.svg")
            _write_hand_csv(csv_p, rows)
            with self.assertRaises(ValueError):
                evidence.render_figure(csv_p, svg_p)
            self.assertFalse(Path(svg_p).exists())

    def test_figure_legend_and_wrapped_caption(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            csv_p = str(Path(tmp) / "predictions.csv")
            svg_p = str(Path(tmp) / "score.svg")
            _write_hand_csv(csv_p, _hand_rows())
            evidence.render_figure(csv_p, svg_p)
            blob = Path(svg_p).read_text().lower()
            self.assertIn("normal", blob)
            self.assertIn("alert", blob)
            tree = ET.parse(svg_p)
            root = tree.getroot()
            texts = [e for e in root.iter() if str(e.tag).endswith("text")]
            self.assertGreaterEqual(len(texts), 4)
            blob_raw = Path(svg_p).read_text()
            self.assertIn("cfg123", blob_raw)
            # config id and source path on separate lines (not one long clipped line)
            lines_with_cfg = [e for e in texts if e.text and "cfg123" in (e.text or "")]
            lines_with_src = [e for e in texts if e.text and "predictions.csv" in (e.text or "")]
            self.assertTrue(lines_with_cfg)
            self.assertTrue(lines_with_src)
            self.assertNotEqual(lines_with_cfg[0], lines_with_src[0] if lines_with_src else None)

    def test_parse_int_simple(self):
        from reliable_alerting import evidence
        self.assertEqual(evidence._parse_int("001", "x"), 1)
        self.assertEqual(evidence._parse_int("+2", "x"), 2)
        self.assertEqual(evidence._parse_int(3, "x"), 3)
        with self.assertRaises(ValueError):
            evidence._parse_int("1.0", "x")
        with self.assertRaises(ValueError):
            evidence._parse_int("abc", "x")


class CompareTest(unittest.TestCase):
    def _two_runs(self, tmp):
        cfg = base_config()
        t1 = pipeline.compute_trace(cfg)
        t2 = pipeline.compute_trace(cfg)
        a = str(Path(tmp) / "run-a")
        b = str(Path(tmp) / "run-b")
        pipeline.write_output(cfg, t1, a)
        pipeline.write_output(cfg, t2, b)
        return a, b

    def test_differing_run_ids_pass_same_substantive(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            rep = evidence.compare_runs(a, b)
            self.assertTrue(rep["status"])
            self.assertNotEqual(rep["run_ids"]["a"], rep["run_ids"]["b"])
            self.assertEqual(rep["row_counts"]["a"], rep["row_counts"]["b"])
            self.assertGreater(rep["row_counts"]["a"], 0)

    def test_differing_score_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            # mutate one score in b, keep output_state consistent
            p = Path(b) / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            thr = float(rows[0]["threshold"])
            rows[0]["score"] = repr(thr + 5.0)
            rows[0]["output_state"] = "alert"
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])

    def test_differing_threshold_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            p = Path(b) / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            # raise threshold above all scores -> all normal
            for r in rows:
                s = float(r["score"])
                r["threshold"] = repr(s + 10.0)
                r["output_state"] = "normal"
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])

    def test_differing_config_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            with open(Path(b) / "config.json") as fh:
                cfg = json.load(fh)
            cfg["calibration"] = dict(cfg["calibration"])
            cfg["calibration"]["quantile"] = 0.5
            with open(Path(b) / "config.json", "w") as fh:
                fh.write(json.dumps(cfg, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])

    def test_differing_boundary_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            p = Path(b) / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[0]["window_id"] = "replay:999:999"
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])

    def test_existing_output_preserved(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            out = str(Path(tmp) / "comparison.json")
            evidence.write_comparison(a, b, out)
            before = Path(out).read_text()
            with self.assertRaises(FileExistsError):
                evidence.write_comparison(a, b, out)
            self.assertEqual(Path(out).read_text(), before)

    def test_resource_scope_mismatch_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            with open(Path(b) / "metadata.json") as fh:
                meta = json.load(fh)
            meta["resource_scope"] = "tampered_scope"
            with open(Path(b) / "metadata.json", "w") as fh:
                fh.write(json.dumps(meta, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])

    def test_missing_metadata_fields_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            with open(Path(b) / "metadata.json") as fh:
                meta = json.load(fh)
            del meta["resource_scope"]
            with open(Path(b) / "metadata.json", "w") as fh:
                fh.write(json.dumps(meta, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])

    def test_both_runs_same_invalid_fails_recompute(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            # identical tamper in BOTH runs: cross-run equal but invalid vs recompute
            for run in (a, b):
                with open(Path(run) / "diagnostics.json") as fh:
                    diag = json.load(fh)
                diag["alert_count"] = int(diag.get("alert_count", 0)) + 100
                with open(Path(run) / "diagnostics.json", "w") as fh:
                    fh.write(json.dumps(diag, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_runs(a, b)
            self.assertFalse(rep["status"])
            self.assertTrue(any("recomput" in d.lower() or "diagnostic" in d.lower()
                                for d in rep["differences"]))

    def test_git_branch_status_recorded_varying(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            with open(Path(b) / "metadata.json") as fh:
                meta = json.load(fh)
            meta["git"] = dict(meta["git"])
            meta["git"]["branch"] = "tampered-branch"
            meta["git"]["status_porcelain"] = "tampered-status"
            with open(Path(b) / "metadata.json", "w") as fh:
                fh.write(json.dumps(meta, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_runs(a, b)
            # branch/status differ: recorded as varying, head still equal so pass
            self.assertTrue(rep["status"])
            self.assertIn("git_branch", rep["varying_metadata"])
            self.assertIn("git_status", rep["varying_metadata"])

    def test_report_requires_valid_provenance(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            rep = evidence.compare_runs(a, b)
            self.assertTrue(rep["status"])
            self.assertTrue(rep.get("source_hashes_match_current"))
            self.assertTrue(rep.get("metadata_keys_valid"))
            self.assertTrue(rep.get("recompute_match"))

    def test_cli_compare_and_figure(self):
        with tempfile.TemporaryDirectory(dir=str(REPO)) as tmp:
            a, b = self._two_runs(tmp)
            out = str(Path(tmp) / "comparison.json")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "compare", a, b, "--output", out],
                cwd=str(REPO), capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(Path(out).is_file())
            with open(out) as fh:
                rep = json.load(fh)
            self.assertTrue(rep["status"])
            svg = str(Path(tmp) / "score.svg")
            csv_p = str(Path(a) / "predictions.csv")
            proc2 = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "figure", csv_p, "--output", svg],
                cwd=str(REPO), capture_output=True, text=True,
            )
            self.assertEqual(proc2.returncode, 0, msg=proc2.stderr[-2000:])
            self.assertTrue(Path(svg).is_file())


if __name__ == "__main__":
    unittest.main()
