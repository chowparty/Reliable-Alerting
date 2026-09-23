"""Day-04 family evidence utilities: compare, table, figure (stdlib unittest).

Why: two replay policies over one frozen score trace must be comparable,
tabulatable, and plottable from saved family artifacts only. All temps
stay inside the repo results dir (git-ignored); no artifacts committed.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
SRC_ENV = dict(os.environ, PYTHONPATH=str(REPO / "src") +
               (os.pathsep + os.environ["PYTHONPATH"]
                if os.environ.get("PYTHONPATH") else ""))
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


def make_family(tmp, name="fam", run_name="source-run"):
    from reliable_alerting import replay
    run = make_source_run(tmp, run_name)
    fam = str(Path(tmp) / name)
    replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG), str(LABELS), fam)
    return fam


def hold_config():
    """Variant with a mid offset so hysteresis holds one window at high."""
    cfg = base_config()
    cfg["input"]["offsets"] = [
        {"start": 72, "stop": 80, "offset": 2},
        {"start": 80, "stop": 84, "offset": 1.0},
        {"start": 88, "stop": 96, "offset": -3},
    ]
    return cfg


def make_hold_family(tmp, name="fam-hold", run_name="source-hold"):
    from reliable_alerting import replay
    cfg = hold_config()
    trace = pipeline.compute_trace(cfg)
    run = str(Path(tmp) / run_name)
    pipeline.write_output(cfg, trace, run)
    fam = str(Path(tmp) / name)
    replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG), str(LABELS), fam)
    return fam


class CompareFamiliesTest(unittest.TestCase):
    def test_equal_fresh_runs_despite_provenance_hashes(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            a = make_family(tmp, "fam-a", "run-a")
            b = make_family(tmp, "fam-b", "run-b")
            rep = evidence.compare_families(a, b)
            self.assertTrue(rep["status"], msg=rep.get("differences"))
            self.assertTrue(rep["scientific_equal"])
            # provenance doc hashes vary (fresh run_ids inside files) yet pass
            meta_a = json.loads((Path(a) / "family_metadata.json").read_text())
            meta_b = json.loads((Path(b) / "family_metadata.json").read_text())
            self.assertNotEqual(meta_a["family_id"], meta_b["family_id"])
            self.assertNotEqual(meta_a["artifact_sha256"],
                                meta_b["artifact_sha256"])
            # varying ids reported, not claimed byte-identical
            blob = json.dumps(rep)
            self.assertNotIn("byte-identical", blob.lower())
            self.assertNotIn("byte identical", blob.lower())
            self.assertIn("family_ids", rep)

    def test_write_comparison_no_overwrite(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            a = make_family(tmp, "fam-a", "run-a")
            b = make_family(tmp, "fam-b", "run-b")
            out = str(Path(tmp) / "comparison.json")
            evidence.write_family_comparison(a, b, out)
            before = Path(out).read_text()
            with self.assertRaises(FileExistsError):
                evidence.write_family_comparison(a, b, out)
            self.assertEqual(Path(out).read_text(), before)

    def test_same_score_state_mismatch_rejected(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            a = make_family(tmp, "fam-a", "run-a")
            b = make_family(tmp, "fam-b", "run-b")
            # same scores, tampered judging threshold in state -> reject
            p = Path(b) / "hysteresis" / "state.json"
            doc = json.loads(p.read_text())
            doc[0]["judging_threshold"] = float(doc[0]["judging_threshold"]) + 5.0
            p.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_families(a, b)
            self.assertFalse(rep["status"])
            self.assertFalse(rep["scientific_equal"])

    def test_same_score_predictions_mismatch_rejected(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            a = make_family(tmp, "fam-a", "run-a")
            b = make_family(tmp, "fam-b", "run-b")
            p = Path(b) / "fixed" / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[0]["output_state"] = ("alert"
                                       if rows[0]["output_state"] == "normal"
                                       else "normal")
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            rep = evidence.compare_families(a, b)
            self.assertFalse(rep["status"])


class FamilyTableTest(unittest.TestCase):
    def test_table_rows_annotations_and_feasible(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_family(tmp)
            table = evidence.family_table(fam)
            self.assertIn("policies", table)
            # all attempted settings retained: both policies present
            self.assertEqual(sorted(table["policies"].keys()),
                             ["fixed", "hysteresis"])
            for name, row in table["policies"].items():
                for key in ("decision_count", "alerted_window_count",
                            "decision_coverage", "alert_episode_rate",
                            "alert_episode_rate_per_1000_decisions",
                            "total_alert_duration", "non_event_alert_duration",
                            "warmup_duration", "event_recall",
                            "episode_precision", "false_alert_episodes",
                            "resource_scope", "policy_replay_seconds",
                            "feasible", "annotations"):
                    self.assertIn(key, row, msg=f"{name}.{key}")
                # denominators present, sample-index units explicit
                self.assertIn("denominator", row["decision_coverage"])
                self.assertIn("denominator", row["event_recall"])
                self.assertIn("denominator", row["episode_precision"])
                self.assertEqual(row["total_alert_duration"]["unit"],
                                 "sample_index")
                self.assertEqual(row["non_event_alert_duration"]["unit"],
                                 "sample_index")
                # coverage floor + rate tolerance from protocol, not rejected
                self.assertIsInstance(row["feasible"], bool)
                # annotations traced to ids
                ann = row["annotations"]
                for key in ("largest_delay_recalled_event",
                            "first_missed_event", "first_false_episode",
                            "longest_non_event_alert_episode"):
                    self.assertIn(key, ann, msg=key)
                self.assertIn("source_paths", row)
            # no authoritative operating-record claim
            blob = json.dumps(table).lower()
            self.assertNotIn("authoritative", blob)
            self.assertNotIn("nakul", blob)
            # annotation ids agree with saved evaluation matches/episodes
            fixed_eval = json.loads(
                (Path(fam) / "fixed" / "evaluation.json").read_text())
            ann = table["policies"]["fixed"]["annotations"]
            recalled = [m for m in fixed_eval["matches"] if m["recalled"]]
            if recalled:
                want = max(recalled, key=lambda m: (m["delay"], m["event_id"]))
                # tie-break: first by sorted id among max delay
                top = max(m["delay"] for m in recalled)
                cands = sorted(m["event_id"] for m in recalled
                               if m["delay"] == top)
                self.assertEqual(ann["largest_delay_recalled_event"]["event_id"],
                                 cands[0])
                self.assertEqual(ann["largest_delay_recalled_event"]["delay"],
                                 top)
            missed = sorted(m["event_id"] for m in fixed_eval["matches"]
                            if not m["recalled"])
            if missed:
                self.assertEqual(ann["first_missed_event"]["event_id"],
                                 missed[0])
            else:
                self.assertIsNone(ann["first_missed_event"])

    def test_table_tamper_refuses_and_no_overwrite(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_family(tmp)
            out = str(Path(tmp) / "table.json")
            evidence.write_family_table(fam, out)
            before = Path(out).read_text()
            with self.assertRaises(FileExistsError):
                evidence.write_family_table(fam, out)
            self.assertEqual(Path(out).read_text(), before)
            # tampered predictions -> table refuses
            p = Path(fam) / "fixed" / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[1]["output_state"] = ("alert"
                                       if rows[1]["output_state"] == "normal"
                                       else "normal")
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError):
                evidence.family_table(fam)
            with self.assertRaises(ValueError):
                evidence.write_family_table(
                    fam, str(Path(tmp) / "table2.json"))
            self.assertFalse((Path(tmp) / "table2.json").exists())


class FamilyFigureTest(unittest.TestCase):
    def test_figure_parses_and_episodes_match_saved_bounds(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_family(tmp)
            table = evidence.family_table(fam)
            svg_p = str(Path(tmp) / "family.svg")
            evidence.render_family_figure(fam, svg_p)
            tree = ET.parse(svg_p)
            root = tree.getroot()
            blob = Path(svg_p).read_text()
            low = blob.lower()
            self.assertIn("synthetic engineering check", low)
            self.assertIn("fixed", low)
            self.assertIn("hysteresis", low)
            self.assertNotIn("rolling", low)
            # episode annotations agree with saved bounds per policy
            titles = [t.text or "" for t in root.iter()
                      if str(t.tag).endswith("title")]
            for name in ("fixed", "hysteresis"):
                saved = json.loads(
                    (Path(fam) / name / "evaluation.json").read_text())
                for ep in saved["episodes"]:
                    tag = f"{ep['episode_id']} [{ep['start']}, {ep['stop']})"
                    self.assertIn(tag, titles, msg=f"{name} {tag}")
            # deterministic annotations match the table
            for name in ("fixed", "hysteresis"):
                ann = table["policies"][name]["annotations"]
                largest = ann["largest_delay_recalled_event"]
                if largest is not None:
                    self.assertIn(largest["event_id"], blob)
                longest = ann["longest_non_event_alert_episode"]
                if longest is not None:
                    self.assertIn(longest["episode_id"], blob)
            # source path traced
            self.assertIn("source_scores.csv", blob)

    def test_figure_tamper_refuses_and_no_overwrite(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_family(tmp)
            svg_p = str(Path(tmp) / "family.svg")
            evidence.render_family_figure(fam, svg_p)
            before = Path(svg_p).read_text()
            with self.assertRaises(FileExistsError):
                evidence.render_family_figure(fam, svg_p)
            self.assertEqual(Path(svg_p).read_text(), before)
            p = Path(fam) / "hysteresis" / "state.json"
            doc = json.loads(p.read_text())
            doc[0]["comparator"] = ("strict_less"
                                    if doc[0]["comparator"] == "strict_greater"
                                    else "strict_greater")
            p.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
            with self.assertRaises(ValueError):
                evidence.render_family_figure(
                    fam, str(Path(tmp) / "other.svg"))
            self.assertFalse(Path(tmp, "other.svg").exists())


class TableDeferralTest(unittest.TestCase):
    def test_deferral_rate_exact_zero_of_8(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_family(tmp)
            table = evidence.family_table(fam)
            for name in ("fixed", "hysteresis"):
                row = table["policies"][name]
                saved = json.loads(
                    (Path(fam) / name / "evaluation.json").read_text())
                self.assertEqual(row["deferral_rate"],
                                 saved["metrics"]["deferral_rate"])
                self.assertEqual(row["deferral_rate"]["numerator"], 0)
                self.assertEqual(row["deferral_rate"]["denominator"],
                                 row["decision_count"])
                self.assertEqual(row["deferral_rate"]["denominator"], 8)


class AnnotationWindowTraceTest(unittest.TestCase):
    def _check(self, fam):
        from reliable_alerting import evidence
        table = evidence.family_table(fam)
        for name in ("fixed", "hysteresis"):
            row = table["policies"][name]
            ann = row["annotations"]
            with open(Path(fam) / name / "predictions.csv",
                       newline="") as fh:
                preds = {r["window_id"]: r for r in csv.DictReader(fh)}
            state = {e["window_id"]: e for e in json.loads(
                (Path(fam) / name / "state.json").read_text())}
            alert_ids = {w for w, r in preds.items()
                         if r["output_state"] == "alert"}
            largest = ann["largest_delay_recalled_event"]
            if largest is not None:
                self.assertEqual(largest["matching_episode_ids"],
                                 [m for m in
                                  largest["matching_episode_ids"]])
                for wid in largest["matching_alert_window_ids"]:
                    self.assertIn(wid, alert_ids, msg=wid)
                    self.assertEqual(state[wid]["after_state"], "alert")
            missed = ann["first_missed_event"]
            if missed is not None:
                self.assertTrue(missed["normal_window_ids"])
                for wid in missed["normal_window_ids"]:
                    self.assertEqual(preds[wid]["output_state"], "normal")
                self.assertEqual(
                    sorted(int(preds[w]["end_index"])
                           for w in missed["normal_window_ids"]),
                    sorted(missed["normal_ends"]))
            for key in ("first_false_episode",
                        "longest_non_event_alert_episode"):
                entry = ann[key]
                if entry is not None:
                    self.assertTrue(entry["alert_window_ids"])
                    for wid in entry["alert_window_ids"]:
                        self.assertIn(wid, alert_ids, msg=f"{key}:{wid}")
                        self.assertEqual(state[wid]["after_state"],
                                         "alert")

    def test_standard_fixture_annotations_trace_windows(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_family(tmp)
            self._check(fam)
            from reliable_alerting import evidence
            table = evidence.family_table(fam)
            largest = (table["policies"]["fixed"]["annotations"]
                       ["largest_delay_recalled_event"])
            # episode-0 covers forward [79, 83): only window ending at 79
            self.assertEqual(largest["matching_episode_ids"], ["episode-0"])
            self.assertEqual(largest["matching_alert_window_ids"],
                             ["replay:76:79"])

    def test_hold_fixture_annotations_trace_windows(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_hold_family(tmp)
            self._check(fam)
            from reliable_alerting import evidence
            table = evidence.family_table(fam)
            held = (table["policies"]["hysteresis"]["annotations"]
                    ["held_on_windows"])
            # latch holds through both mid windows scoring at high
            self.assertEqual(held, ["replay:80:83", "replay:84:87"])


class HeldIntervalHelperTest(unittest.TestCase):
    def test_hand_spike_then_low_forward_intervals(self):
        from reliable_alerting import evidence
        rows = [
            {"window_id": "w0", "end_index": 3},
            {"window_id": "w1", "end_index": 7},
            {"window_id": "w2", "end_index": 11},
            {"window_id": "w3", "end_index": 15},
        ]
        self.assertEqual(
            evidence._held_forward_intervals(["w1"], rows, 16),
            [{"window_id": "w1", "start": 7, "stop": 11}])
        # last window runs to the horizon
        self.assertEqual(
            evidence._held_forward_intervals(["w3"], rows, 16),
            [{"window_id": "w3", "start": 15, "stop": 16}])
        self.assertEqual(
            evidence._held_forward_intervals(["w1", "w3"], rows, 16),
            [{"window_id": "w1", "start": 7, "stop": 11},
             {"window_id": "w3", "start": 15, "stop": 16}])
        self.assertEqual(
            evidence._held_forward_intervals([], rows, 16), [])


class FamilyFigureGeometryTest(unittest.TestCase):
    def _texts(self, svg_p):
        tree = ET.parse(svg_p)
        root = tree.getroot()
        w = float(root.get("width"))
        h = float(root.get("height"))
        texts = [e for e in root.iter() if str(e.tag).endswith("text")]
        return w, h, texts, root

    def test_all_text_inside_canvas_and_wrapped(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_hold_family(tmp)
            svg_p = str(Path(tmp) / "family.svg")
            evidence.render_family_figure(fam, svg_p)
            w, h, texts, _ = self._texts(svg_p)
            self.assertGreaterEqual(len(texts), 8)
            for t in texts:
                x = float(t.get("x"))
                y = float(t.get("y"))
                self.assertGreaterEqual(x, 0, msg=t.text)
                self.assertLessEqual(x, w, msg=t.text)
                self.assertGreaterEqual(y, 0, msg=t.text)
                self.assertLessEqual(y, h, msg=t.text)
                for line in (t.text or "").splitlines():
                    self.assertLessEqual(len(line), 80, msg=line)

    def test_held_forward_intervals_drawn_with_window_ids(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_hold_family(tmp)
            table = evidence.family_table(fam)
            held = (table["policies"]["hysteresis"]["annotations"]
                    ["held_on_intervals"])
            self.assertTrue(held)
            svg_p = str(Path(tmp) / "family.svg")
            evidence.render_family_figure(fam, svg_p)
            _, _, _, root = self._texts(svg_p)
            titles = [t.text or "" for t in root.iter()
                      if str(t.tag).endswith("title")]
            rects = [e for e in root.iter()
                     if str(e.tag).endswith("rect")]
            for iv in held:
                tag = (f"held-on {iv['window_id']} "
                       f"[{iv['start']}, {iv['stop']})")
                self.assertIn(tag, titles, msg=tag)
                x1 = 60 + (iv["start"] - 64) / (96 - 64) * 600
                x2 = 60 + (iv["stop"] - 64) / (96 - 64) * 600
                match = [r for r in rects
                         if abs(float(r.get("x")) - x1) < 1.0
                         and abs(float(r.get("width")) - (x2 - x1)) < 1.0
                         and (r.get("stroke") == "orange"
                              or r.get("fill") == "orange")]
                self.assertTrue(match, msg=tag)

    def test_horizon_and_warmup_cover_all_lanes(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            fam = make_hold_family(tmp)
            svg_p = str(Path(tmp) / "family.svg")
            evidence.render_family_figure(fam, svg_p)
            _, _, _, root = self._texts(svg_p)
            rects = [e for e in root.iter()
                     if str(e.tag).endswith("rect")]
            outlines = [r for r in rects
                        if r.get("fill") == "none" and r.get("stroke") == "black"]
            self.assertTrue(outlines)
            # hyst lane rects (red) must sit inside the horizon outline
            reds = [r for r in rects if r.get("fill") == "red"]
            self.assertTrue(reds)
            lane_bottom = max(float(r.get("y")) + float(r.get("height"))
                              for r in reds)
            tops = [float(r.get("y")) + float(r.get("height"))
                    for r in outlines]
            self.assertTrue(any(b >= lane_bottom for b in tops))


class FamilyCliTest(unittest.TestCase):
    def test_cli_compare_table_figure(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            a = make_family(tmp, "fam-a", "run-a")
            b = make_family(tmp, "fam-b", "run-b")
            out_c = str(Path(tmp) / "comparison.json")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "compare-families", a, b, "--output", out_c],
                cwd=str(REPO), capture_output=True, text=True, env=SRC_ENV)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(json.loads(Path(out_c).read_text())["status"])
            out_t = str(Path(tmp) / "table.json")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "family-table", a, "--output", out_t],
                cwd=str(REPO), capture_output=True, text=True, env=SRC_ENV)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(Path(out_t).is_file())
            out_f = str(Path(tmp) / "family.svg")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "family-figure", a, "--output", out_f],
                cwd=str(REPO), capture_output=True, text=True, env=SRC_ENV)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(Path(out_f).is_file())


if __name__ == "__main__":
    unittest.main()
