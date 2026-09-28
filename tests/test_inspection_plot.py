"""test_inspection_plot.py - tests for research/inspection_plot.py (Nakul, Day 5 prereq).

Covers the smallest reusable score+threshold-trace plotting capability built
as a Pratyush stand-in (the existing evidence.render_figure refuses varying
thresholds, so it cannot plot rolling_threshold).

Verifies: row loading (base 8 cols + optional 'features'); missing-column
rejection; empty-file rejection; alert-episode grouping; refuse-overwrite
output; that a labelled event span is rendered; and that the emitted SVG is
well-formed XML for BOTH a fixed-threshold trace and the varying (rolling)
threshold trace -- the case the existing plotter rejects.

Integration checks against saved valve1 traces skip cleanly if absent.
"""
import sys
import tempfile
import unittest
import xml.dom.minidom as minidom
from pathlib import Path

# reliable_alerting imports directly (editable install). Add the sibling
# research/ folder so the Nakul module below resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "research"))

import inspection_plot as ip  # noqa: E402

_BTP_ROOT = Path(__file__).resolve().parents[1]
_VALVE1 = _BTP_ROOT / "result" / "valve1"
_EVENT_SPAN = (574, 975)

_HEADER = ("window_id,start_index,end_index,score,output_state,"
           "threshold,config_id,run_id")


def _write_csv(dirpath, rows, header=_HEADER):
    p = Path(dirpath) / "predictions.csv"
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")
    return p


# Minimal synthetic rows: end_index climbing, mix of alert/normal.
# columns: window_id,start_index,end_index,score,output_state,threshold,config_id,run_id
_FIXED_ROWS = [
    ("w0", 0, 4, 0.5, "normal", 1.0, "c", "r"),
    ("w1", 4, 8, 1.2, "alert", 1.0, "c", "r"),
    ("w2", 8, 12, 1.3, "alert", 1.0, "c", "r"),
    ("w3", 12, 16, 0.4, "normal", 1.0, "c", "r"),
]
# varying threshold (rolling-like): threshold changes across rows
_VARYING_ROWS = [
    ("w0", 0, 4, 0.5, "normal", 0.9, "c", "r"),
    ("w1", 4, 8, 1.2, "alert", 1.1, "c", "r"),
    ("w2", 8, 12, 1.0, "normal", 1.3, "c", "r"),
    ("w3", 12, 16, 1.6, "alert", 1.25, "c", "r"),
]


class TestLoadPredictionRows(unittest.TestCase):
    def test_loads_base_columns(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, _FIXED_ROWS)
            rows = ip.load_prediction_rows(p)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["end_index"], 4)
        self.assertAlmostEqual(rows[1]["score"], 1.2)
        self.assertEqual(rows[1]["output_state"], "alert")

    def test_accepts_optional_features_column(self):
        header = _HEADER + ",features"
        rows = [r + ('{"m":0.1}',) for r in _FIXED_ROWS]
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, rows, header=header)
            loaded = ip.load_prediction_rows(p)
        self.assertEqual(len(loaded), 4)

    def test_rejects_missing_column(self):
        bad_header = "window_id,start_index,end_index,score,output_state,config_id,run_id"
        rows = [("w0", 0, 4, 0.5, "normal", "c", "r")]
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, rows, header=bad_header)
            with self.assertRaises(ValueError):
                ip.load_prediction_rows(p)

    def test_rejects_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, [])
            with self.assertRaises(ValueError):
                ip.load_prediction_rows(p)


class TestAlertEpisodes(unittest.TestCase):
    def test_groups_adjacent_alerts(self):
        rows = [
            {"end_index": 4, "output_state": "normal"},
            {"end_index": 8, "output_state": "alert"},
            {"end_index": 12, "output_state": "alert"},
            {"end_index": 16, "output_state": "normal"},
            {"end_index": 20, "output_state": "alert"},
        ]
        eps = ip.alert_episodes(rows)
        self.assertEqual(eps, [(8, 12), (20, 20)])

    def test_trailing_alert_closes(self):
        rows = [
            {"end_index": 4, "output_state": "normal"},
            {"end_index": 8, "output_state": "alert"},
        ]
        self.assertEqual(ip.alert_episodes(rows), [(8, 8)])

    def test_no_alerts(self):
        rows = [{"end_index": 4, "output_state": "normal"}]
        self.assertEqual(ip.alert_episodes(rows), [])


class TestRenderFixedThreshold(unittest.TestCase):
    def test_renders_wellformed_svg_with_event(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, _FIXED_ROWS)
            out = Path(d) / "fig.svg"
            ip.render_inspection_figure(p, out, event_spans=[_EVENT_SPAN],
                                        policy_label="fixed_threshold")
            text = out.read_text(encoding="utf-8")
        minidom.parseString(text)  # raises if not well-formed
        self.assertIn("labelled event [574,975)", text)
        self.assertIn("fixed", text)

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, _FIXED_ROWS)
            out = Path(d) / "fig.svg"
            ip.render_inspection_figure(p, out)
            with self.assertRaises(FileExistsError):
                ip.render_inspection_figure(p, out)


class TestRenderVaryingThreshold(unittest.TestCase):
    """The case the existing plotter rejects outright."""

    def test_renders_wellformed_svg(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_csv(d, _VARYING_ROWS)
            out = Path(d) / "fig.svg"
            ip.render_inspection_figure(p, out, event_spans=[_EVENT_SPAN],
                                        policy_label="rolling_threshold")
            text = out.read_text(encoding="utf-8")
        minidom.parseString(text)
        self.assertIn("threshold trace (varying)", text)


class TestSavedValve1Traces(unittest.TestCase):
    """Integration: render each real saved valve1 trace, if present."""

    def _policies(self):
        if not _VALVE1.is_dir():
            return []
        return [d.name for d in _VALVE1.iterdir()
                if (d / "predictions.csv").is_file()]

    def test_all_present_traces_render(self):
        policies = self._policies()
        if not policies:
            self.skipTest("valve1 saved traces not present")
        for pol in policies:
            src = _VALVE1 / pol / "predictions.csv"
            with tempfile.TemporaryDirectory() as d:
                out = Path(d) / f"{pol}.svg"
                ip.render_inspection_figure(src, out,
                                            event_spans=[_EVENT_SPAN],
                                            policy_label=pol)
                minidom.parseString(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()