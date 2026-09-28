"""Day-05 saved diagnostic evidence integration (stdlib unittest).

Why: join the verified trailing-median-gap diagnostic with the validated
family from saved artifacts only. Descriptive comparison only; no
modelling/significance/candidate selection; no future prediction.
All temps stay inside the repo results dir (git-ignored).
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
DIAG_SHIPPED = REPO / "configs" / "day05-diagnostic.json"

ABSENT = "None observed in this evaluated scope"


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


def make_family_and_diagnostic(tmp):
    from reliable_alerting import diagnostics, replay
    run = make_source_run(tmp, "source-run")
    fam = str(Path(tmp) / "fam")
    replay.run_family(run, str(PROTOCOL), str(EVAL_CONFIG), str(LABELS), fam)
    cfg_p = str(Path(tmp) / "diag-config.json")
    shipped = json.loads(DIAG_SHIPPED.read_text())
    with open(cfg_p, "w") as fh:
        fh.write(json.dumps(shipped, sort_keys=True, indent=2, allow_nan=False) + "\n")
    diag = str(Path(tmp) / "diag")
    diagnostics.run_diagnostic(run, cfg_p, diag)
    return diag, fam


class DiagnosticTableApiTest(unittest.TestCase):
    def test_table_joins_validated_artifacts(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            table = evidence.diagnostic_table(diag, fam)
            self.assertEqual(sorted(table["policies"].keys()), ["fixed", "hysteresis"])
            self.assertIn("diagnostic_config_id", table)
            self.assertIn("family_id", table)
            self.assertTrue(table["linkage"]["scores_equal"])
            self.assertTrue(table["linkage"]["calibration_equal"])
            self.assertTrue(table["linkage"]["source_config_equal"])
            for name in ("fixed", "hysteresis"):
                self.assertIn("per_row", table["policies"][name])
                self.assertIn("cases", table["policies"][name])

    def test_table_verifies_features_first(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            doc = json.loads((Path(diag) / "diagnostic.json").read_text())
            doc["rows"][2]["feature"] = float(doc["rows"][2]["feature"] or 0.0) + 5.0
            (Path(diag) / "diagnostic.json").write_text(
                json.dumps(doc, sort_keys=True, indent=2) + "\n")
            with self.assertRaises(ValueError):
                evidence.diagnostic_table(diag, fam)

    def test_table_rejects_score_mismatch_without_hash_compare(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            p = Path(fam) / "source_scores.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[0]["score"] = repr(float(rows[0]["score"]) + 1.0)
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError):
                evidence.diagnostic_table(diag, fam)

    def test_write_table_exclusive(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            out = str(Path(tmp) / "diag-table.json")
            evidence.write_diagnostic_table(diag, fam, out)
            before = Path(out).read_text()
            with self.assertRaises(FileExistsError):
                evidence.write_diagnostic_table(diag, fam, out)
            self.assertEqual(Path(out).read_text(), before)


class DiagnosticTableCasesTest(unittest.TestCase):
    def test_deterministic_cases_per_policy(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            table = evidence.diagnostic_table(diag, fam)
            for name in ("fixed", "hysteresis"):
                cases = table["policies"][name]["cases"]
                for key in ("first_false_episode", "largest_delay_recalled_event",
                            "first_missed_event", "longest_non_event_alert_episode",
                            "misleading_feature_example"):
                    self.assertIn(key, cases, msg=f"{name}.{key}")
                    val = cases[key]
                    self.assertTrue(
                        isinstance(val, dict) or val == ABSENT,
                        msg=f"{name}.{key}:{val!r}")
                # largest delay tie-break first by sorted event id
                saved = json.loads((Path(fam) / name / "evaluation.json").read_text())
                recalled = [m for m in saved["matches"] if m["recalled"]]
                largest = cases["largest_delay_recalled_event"]
                if recalled:
                    top = max(m["delay"] for m in recalled)
                    cands = sorted(m["event_id"] for m in recalled if m["delay"] == top)
                    self.assertIsInstance(largest, dict)
                    self.assertEqual(largest["event_id"], cands[0])
                    self.assertEqual(largest["delay"], top)
                    # tied rows preserved
                    if len(cands) > 1:
                        self.assertIn("tied_event_ids", largest)
                        self.assertEqual(sorted(largest["tied_event_ids"]), cands)
                missed = sorted(m["event_id"] for m in saved["matches"]
                                if not m["recalled"])
                first_miss = cases["first_missed_event"]
                if missed:
                    self.assertIsInstance(first_miss, dict)
                    self.assertEqual(first_miss["event_id"], missed[0])
                else:
                    self.assertEqual(first_miss, ABSENT)
                longest = cases["longest_non_event_alert_episode"]
                if saved["episodes"]:
                    self.assertIsInstance(longest, dict)
                    self.assertIn("non_event_duration", longest)
                    self.assertIn("episode_id", longest)

    def test_per_row_descriptive_fields(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            table = evidence.diagnostic_table(diag, fam)
            high = float(json.loads((Path(fam) / "family_metadata.json").read_text())["threshold_high"])
            for name in ("fixed", "hysteresis"):
                rows = table["policies"][name]["per_row"]
                self.assertEqual(len(rows), 8)
                for r in rows:
                    for key in ("window_id", "start_index", "end_index",
                                "availability_end", "score", "judging_threshold",
                                "margin", "threshold_high", "margin_high",
                                "recent_exceedance_rate",
                                "output_state", "before_state", "after_state",
                                "comparator", "feature", "warmup"):
                        self.assertIn(key, r, msg=key)
                    self.assertAlmostEqual(r["margin"],
                                           r["score"] - r["judging_threshold"])
                    self.assertAlmostEqual(r["margin_high"],
                                           r["score"] - r["threshold_high"])
                    self.assertEqual(r["threshold_high"], high)
                    self.assertGreaterEqual(r["recent_exceedance_rate"], 0.0)
                    self.assertLessEqual(r["recent_exceedance_rate"], 1.0)
                    if r["warmup"]:
                        self.assertIsNone(r["feature"])
                    # state matches saved sidecar after_state
                    state = {e["window_id"]: e for e in json.loads(
                        (Path(fam) / name / "state.json").read_text())}
                    self.assertEqual(r["output_state"],
                                     state[r["window_id"]]["after_state"])
                    self.assertEqual(r["after_state"],
                                     state[r["window_id"]]["after_state"])
                    self.assertEqual(r["before_state"],
                                     state[r["window_id"]]["before_state"])
                    self.assertEqual(r["comparator"],
                                     state[r["window_id"]]["comparator"])
                    self.assertEqual(r["judging_threshold"],
                                     float(state[r["window_id"]]["judging_threshold"]))
            blob = json.dumps(table).lower()
            self.assertNotIn("significance", blob)
            self.assertNotIn("candidate selection", blob)
            self.assertNotIn("future prediction", blob)

    def test_recent_exceedance_uses_frozen_high_exact_windows(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            table = evidence.diagnostic_table(diag, fam)
            high = float(json.loads((Path(fam) / "family_metadata.json").read_text())["threshold_high"])
            # trio windows in order from diagnostic rows
            doc = json.loads((Path(diag) / "diagnostic.json").read_text())
            ids = [r["window_id"] for r in doc["rows"]]
            trio_at = {}
            all_scores = [float(r["score"]) for r in doc["rows"]]
            for i, wid in enumerate(ids):
                trio = all_scores[max(0, i - 2): i + 1]
                trio_at[wid] = trio
            for name in ("fixed", "hysteresis"):
                by_id = {r["window_id"]: r for r in table["policies"][name]["per_row"]}
                # 80:83 trio [1.069.., 2.138.., 0.0] -> 1/3 strictly above HIGH
                r1 = by_id["replay:80:83"]
                self.assertAlmostEqual(r1["recent_exceedance_rate"], 1.0 / 3.0)
                self.assertAlmostEqual(r1["margin_high"], r1["score"] - high)
                self.assertAlmostEqual(r1["margin"], r1["score"] - r1["judging_threshold"])
                # 92:95 trio [1.069.., 4.276.., 3.207..] -> 2/3 strictly above HIGH
                r2 = by_id["replay:92:95"]
                self.assertAlmostEqual(r2["recent_exceedance_rate"], 2.0 / 3.0)
                self.assertAlmostEqual(r2["margin_high"], r2["score"] - high)
                # both policies share the frozen-HIGH rate on the same trio
            self.assertAlmostEqual(
                table["policies"]["fixed"]["per_row"][4]["recent_exceedance_rate"],
                table["policies"]["hysteresis"]["per_row"][4]["recent_exceedance_rate"])
            # rate recomputed independently from frozen HIGH trio
            for wid in ("replay:80:83", "replay:92:95"):
                trio = trio_at[wid]
                want = sum(1 for s in trio if s > high) / len(trio)
                for name in ("fixed", "hysteresis"):
                    got = {r["window_id"]: r for r in table["policies"][name]["per_row"]}[wid]["recent_exceedance_rate"]
                    self.assertAlmostEqual(got, want, msg=f"{name} {wid}")

    def test_misleading_is_sign_gap_vs_frozen_high_exact(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            table = evidence.diagnostic_table(diag, fam)
            high = float(json.loads((Path(fam) / "family_metadata.json").read_text())["threshold_high"])
            for name in ("fixed", "hysteresis"):
                cases = table["policies"][name]["cases"]
                mis = cases["misleading_feature_example"]
                by_id = {r["window_id"]: r for r in table["policies"][name]["per_row"]}
                # explicit definition: ready feature>0 with current score<=HIGH,
                # or feature<=0 with current score>HIGH (strict_greater exceedance)
                if isinstance(mis, dict):
                    feat = float(mis["feature"])
                    exceeds = float(mis["score"]) > high
                    self.assertTrue((feat > 0 and not exceeds) or (feat <= 0 and exceeds),
                                    msg=f"{name} {mis!r}")
                    self.assertEqual(mis["threshold_high"], high)
                    self.assertIn("exceeds_high", mis)
                    # first such ready window in order
                    doc = json.loads((Path(diag) / "diagnostic.json").read_text())
                    first = None
                    for drow in doc["rows"]:
                        if drow.get("warmup") or drow.get("feature") is None:
                            continue
                        f = float(drow["feature"])
                        s = float(drow["score"])
                        if (f > 0 and not (s > high)) or (f <= 0 and (s > high)):
                            first = drow["window_id"]
                            break
                    self.assertEqual(mis["window_id"], first)
                # exact spot checks: 80:83 is positive-gap with no exceedance
                r1 = by_id["replay:80:83"]
                self.assertGreater(float(r1["feature"]), 0.0)
                self.assertFalse(float(r1["score"]) > high)
                # 92:95 agrees (positive gap with exceedance) so not misleading
                r2 = by_id["replay:92:95"]
                self.assertGreater(float(r2["feature"]), 0.0)
                self.assertTrue(float(r2["score"]) > high)


class DiagnosticWarmupTest(unittest.TestCase):
    def test_warmup_separate_from_full_decisions(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            table = evidence.diagnostic_table(diag, fam)
            warm = table["warmup"]
            self.assertEqual(warm["warmup_count"], 2)
            self.assertEqual(warm["decision_count"], 8)
            self.assertEqual(warm["ready_count"], 6)
            self.assertEqual(len(warm["warmup_window_ids"]), 2)
            self.assertEqual(len(warm["ready_window_ids"]), 6)
            for name in ("fixed", "hysteresis"):
                rows = table["policies"][name]["per_row"]
                self.assertTrue(rows[0]["warmup"])
                self.assertTrue(rows[1]["warmup"])
                self.assertFalse(rows[2]["warmup"])
                self.assertIsNone(rows[0]["feature"])
                self.assertIsNone(rows[1]["feature"])
                self.assertIsNotNone(rows[2]["feature"])


class DiagnosticFigureTest(unittest.TestCase):
    def test_figure_parses_geometry_and_ids(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            svg_p = str(Path(tmp) / "diag.svg")
            evidence.render_diagnostic_plot(diag, fam, svg_p)
            tree = ET.parse(svg_p)
            root = tree.getroot()
            w, h = float(root.get("width")), float(root.get("height"))
            blob = Path(svg_p).read_text()
            low = blob.lower()
            self.assertIn("synthetic", low)
            self.assertIn("sample_index", low)
            self.assertIn("horizon", low)
            self.assertIn("warmup", low)
            # source IDs annotated
            table = evidence.diagnostic_table(diag, fam)
            self.assertIn(table["diagnostic_config_id"], blob)
            self.assertIn(table["family_id"], blob)
            self.assertIn("source_scores.csv", blob)
            # episode + event annotations present per saved bounds
            titles = [t.text or "" for t in root.iter()
                      if str(t.tag).endswith("title")]
            for name in ("fixed", "hysteresis"):
                saved = json.loads((Path(fam) / name / "evaluation.json").read_text())
                for ep in saved["episodes"]:
                    tag = f"{ep['episode_id']} [{ep['start']}, {ep['stop']})"
                    self.assertIn(tag, titles, msg=f"{name} {tag}")
            # actual judging values at window ends present
            state = json.loads((Path(fam) / "fixed" / "state.json").read_text())
            for e in state:
                self.assertIn(e["window_id"], blob)
            # geometry: all text inside canvas by estimated extents
            texts = [e for e in root.iter() if str(e.tag).endswith("text")]
            self.assertGreaterEqual(len(texts), 8)
            for t in texts:
                x, y = float(t.get("x")), float(t.get("y"))
                size = float(t.get("font-size", "10"))
                anchor = (t.get("text-anchor") or "start").strip().lower()
                est_w = len(t.text or "") * size * 0.6
                self.assertGreaterEqual(y, 0, msg=t.text)
                self.assertLessEqual(y, h, msg=t.text)
                if anchor == "middle":
                    self.assertGreaterEqual(x - est_w / 2, -1.0, msg=t.text)
                    self.assertLessEqual(x + est_w / 2, w + 1.0, msg=t.text)
                elif anchor == "end":
                    self.assertGreaterEqual(x - est_w, -1.0, msg=t.text)
                    self.assertLessEqual(x, w + 1.0, msg=t.text)
                else:
                    self.assertGreaterEqual(x, -1.0, msg=t.text)
                    self.assertLessEqual(x + est_w, w + 1.0, msg=t.text)
            # long absolute footer paths are wrapped so extents fit canvas
            paths = [t.text or "" for t in texts if (t.text or "").startswith(
                ("source=", "diagnostic="))]
            self.assertTrue(paths)
            for line in paths:
                self.assertLessEqual(len(line), 100, msg=line)

    def test_figure_tamper_refuses_and_no_overwrite(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            svg_p = str(Path(tmp) / "diag.svg")
            evidence.render_diagnostic_plot(diag, fam, svg_p)
            before = Path(svg_p).read_text()
            with self.assertRaises(FileExistsError):
                evidence.render_diagnostic_plot(diag, fam, svg_p)
            self.assertEqual(Path(svg_p).read_text(), before)
            p = Path(fam) / "fixed" / "predictions.csv"
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            rows[0]["output_state"] = ("alert" if rows[0]["output_state"] == "normal"
                                       else "normal")
            with open(p, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError):
                evidence.render_diagnostic_plot(diag, fam, str(Path(tmp) / "o.svg"))


class DiagnosticFeaturePanelTest(unittest.TestCase):
    FORMULA = ("median(last 3 scores, current-inclusive)"
               " - calibration median; score units")

    def _render(self, tmp):
        from reliable_alerting import evidence
        diag, fam = make_family_and_diagnostic(tmp)
        svg_p = str(Path(tmp) / "diag.svg")
        evidence.render_diagnostic_plot(diag, fam, svg_p)
        tree = ET.parse(svg_p)
        return diag, fam, svg_p, tree.getroot()

    def test_feature_panel_exact_coordinates_and_linkage(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam, svg_p, root = self._render(tmp)
            doc = json.loads((Path(diag) / "diagnostic.json").read_text())
            table = __import__("reliable_alerting.evidence",
                                fromlist=["diagnostic_table"]).diagnostic_table(
                                    diag, fam)
            circles = [e for e in root.iter()
                       if str(e.tag).endswith("circle")]
            # score-panel blue circles keyed by window end
            score_cx = {}
            for c in circles:
                if c.get("fill") != "blue":
                    continue
                for t in c:
                    if str(t.tag).endswith("title") and "score=" in (t.text or ""):
                        for tok in (t.text or "").split():
                            if tok.startswith("end="):
                                score_cx[(t.text or "").split()[0]] = float(
                                    c.get("cx"))
            feat_circles = [c for c in circles if c.get("fill") == "green"]
            ready = [r for r in doc["rows"] if not r.get("warmup")]
            self.assertEqual(len(feat_circles), len(ready),
                             msg="one plotted feature marker per ready window")
            seen = {}
            for c in feat_circles:
                title = "".join(t.text or "" for t in c
                                if str(t.tag).endswith("title"))
                wid = title.split()[0]
                seen[wid] = (float(c.get("cx")), float(c.get("cy")), title)
            for r in ready:
                self.assertIn(r["window_id"], seen, msg=r["window_id"])
                cx, cy, title = seen[r["window_id"]]
                # same availability_end x as the score marker
                self.assertAlmostEqual(cx, score_cx[r["window_id"]], places=2,
                                       msg=r["window_id"])
                self.assertIn(repr(float(r["feature"])), title)
                # table linkage: same feature value as saved diagnostic
                got = {x["window_id"]: x for x in
                       table["policies"]["fixed"]["per_row"]}[r["window_id"]]
                self.assertAlmostEqual(got["feature"], float(r["feature"]))

    def test_zero_line_formula_and_warmup_null(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam, svg_p, root = self._render(tmp)
            blob = Path(svg_p).read_text()
            self.assertIn(self.FORMULA, blob)
            titles = [t.text or "" for t in root.iter()
                      if str(t.tag).endswith("title")]
            self.assertTrue(any("feature=0" in t or "zero" in t.lower()
                                for t in titles),
                            msg="zero/reference line annotated")
            doc = json.loads((Path(diag) / "diagnostic.json").read_text())
            warm = [r["window_id"] for r in doc["rows"] if r.get("warmup")]
            self.assertEqual(len(warm), 2)
            green_titles = " ".join(
                t.text or "" for t in root.iter()
                if str(t.tag).endswith("title") and "feat=" in (t.text or ""))
            for wid in warm:
                self.assertNotIn(wid, green_titles, msg=f"warmup {wid} plotted")
            # readiness lane still distinguishes warmup vs ready
            self.assertIn("warmup", blob.lower())

    def test_threshold_legend_separate_no_overlap(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam, svg_p, root = self._render(tmp)
            texts = [e for e in root.iter() if str(e.tag).endswith("text")]
            highs = [e for e in texts if (e.text or "").startswith("high ")]
            lows = [e for e in texts if (e.text or "").startswith("low ")]
            self.assertTrue(highs and lows)
            for h in highs:
                for lo in lows:
                    self.assertGreaterEqual(
                        abs(float(h.get("y")) - float(lo.get("y"))), 12.0,
                        msg="high/low legend labels overlap")
            blob = Path(svg_p).read_text().lower()
            self.assertIn("connector", blob)

    def test_time_ticks_cover_decision_ends(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam, svg_p, root = self._render(tmp)
            doc = json.loads((Path(diag) / "diagnostic.json").read_text())
            ends = [str(r["end_index"]) for r in doc["rows"]]
            tick_texts = [ (e.text or "").strip() for e in root.iter()
                           if str(e.tag).endswith("text")]
            for end in ends:
                self.assertIn(end, tick_texts, msg=f"tick {end}")
            self.assertGreaterEqual(len([t for t in tick_texts
                                         if t in ends]), len(ends))


class CompareDiagnosticsTest(unittest.TestCase):
    def test_equal_diagnostics_pass_provenance_separate(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            from reliable_alerting import diagnostics
            run = make_source_run(tmp, "source-run")
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(json.loads(DIAG_SHIPPED.read_text()),
                                    sort_keys=True, indent=2, allow_nan=False) + "\n")
            a = str(Path(tmp) / "diag-a")
            b = str(Path(tmp) / "diag-b")
            diagnostics.run_diagnostic(run, cfg_p, a)
            diagnostics.run_diagnostic(run, cfg_p, b)
            rep = evidence.compare_diagnostics(a, b)
            self.assertTrue(rep["status"], msg=rep.get("differences"))
            self.assertTrue(rep["scientific_equal"])
            blob = json.dumps(rep).lower()
            self.assertNotIn("byte-identical", blob)
            # metadata timestamps/paths/timing reported separately
            self.assertIn("varying_metadata", rep)
            meta_a = json.loads((Path(a) / "metadata.json").read_text())
            meta_b = json.loads((Path(b) / "metadata.json").read_text())
            self.assertNotEqual(meta_a["started_at"], meta_b["started_at"])

    def test_tampered_feature_fails(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            from reliable_alerting import diagnostics
            run = make_source_run(tmp, "source-run")
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(json.loads(DIAG_SHIPPED.read_text()),
                                    sort_keys=True, indent=2, allow_nan=False) + "\n")
            a = str(Path(tmp) / "diag-a")
            b = str(Path(tmp) / "diag-b")
            diagnostics.run_diagnostic(run, cfg_p, a)
            diagnostics.run_diagnostic(run, cfg_p, b)
            doc = json.loads((Path(b) / "diagnostic.json").read_text())
            doc["rows"][3]["feature"] = float(doc["rows"][3]["feature"] or 0.0) + 1.0
            (Path(b) / "diagnostic.json").write_text(
                json.dumps(doc, sort_keys=True, indent=2) + "\n")
            rep = evidence.compare_diagnostics(a, b)
            self.assertFalse(rep["status"])
            self.assertFalse(rep["scientific_equal"])

    def test_write_comparison_exclusive(self):
        from reliable_alerting import evidence
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            from reliable_alerting import diagnostics
            run = make_source_run(tmp, "source-run")
            cfg_p = str(Path(tmp) / "diag-config.json")
            with open(cfg_p, "w") as fh:
                fh.write(json.dumps(json.loads(DIAG_SHIPPED.read_text()),
                                    sort_keys=True, indent=2, allow_nan=False) + "\n")
            a = str(Path(tmp) / "diag-a")
            b = str(Path(tmp) / "diag-b")
            diagnostics.run_diagnostic(run, cfg_p, a)
            diagnostics.run_diagnostic(run, cfg_p, b)
            out = str(Path(tmp) / "cmp.json")
            evidence.write_diagnostic_comparison(a, b, out)
            before = Path(out).read_text()
            with self.assertRaises(FileExistsError):
                evidence.write_diagnostic_comparison(a, b, out)
            self.assertEqual(Path(out).read_text(), before)


class DiagnosticCliTest(unittest.TestCase):
    def test_cli_table_plot_compare(self):
        with tempfile.TemporaryDirectory(dir=str(RESULTS)) as tmp:
            diag, fam = make_family_and_diagnostic(tmp)
            out_t = str(Path(tmp) / "table.json")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "diagnostic-table", "--diagnostic", diag, "--family", fam,
                 "--output", out_t],
                cwd=str(REPO), capture_output=True, text=True, env=SRC_ENV)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(Path(out_t).is_file())
            out_f = str(Path(tmp) / "plot.svg")
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "diagnostic-plot", "--diagnostic", diag, "--family", fam,
                 "--output", out_f],
                cwd=str(REPO), capture_output=True, text=True, env=SRC_ENV)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(Path(out_f).is_file())
            out_c = str(Path(tmp) / "cmp.json")
            import shutil as _shutil
            _shutil.copytree(diag, str(Path(tmp) / "diag-b"))
            proc = subprocess.run(
                [sys.executable, "-m", "reliable_alerting.evidence",
                 "compare-diagnostics", diag, str(Path(tmp) / "diag-b"),
                 "--output", out_c],
                cwd=str(REPO), capture_output=True, text=True, env=SRC_ENV)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertTrue(Path(out_c).is_file())


if __name__ == "__main__":
    unittest.main()
