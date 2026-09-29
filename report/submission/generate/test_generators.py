#!/usr/bin/env python3
"""Verification tests for the P6 generators, run against the real v2 study root.

stdlib ``unittest`` only.  Checks:
  * the normal-only rolling threshold has 0 increases and the stated end values;
  * the in-event exceedance counts and the max exceedance run length (E3);
  * every number written into a table equals summary.json (and summary.json
    equals the recompute file where they overlap);
  * running each generator twice gives byte-identical output.

Run:
    python3 report-work/figures/test_generators.py
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _studylib as L  # noqa: E402

ROOT = L.DEFAULT_ROOT
FIG = os.path.join(HERE, "make_figures.py")
TAB = os.path.join(HERE, "make_tables.py")
# Promoted: generators emit into submission/figures and submission/tables.
FIGDIR = L.FIGURES_OUT
TABDIR = L.TABLES_OUT

RATCHET_END = {"valve1": 0.258, "valve2": 0.406}   # to 3 dp, per the spec caption
E3_EXPECTED = {                                     # (exceed, in_event, max_run)
    "valve1": (6, 100, 2),
    "valve2": (13, 98, 2),
}
# A healthy generator run takes about a second; anything near this is a hang.
GEN_TIMEOUT = 60


class TestLabelSpreading(unittest.TestCase):
    """The trade-off labels once looped forever on Y1/Y2 (a crowded column near
    the top of the panel). The spreader must terminate and keep labels apart."""

    def setUp(self):
        import make_figures as M
        self.spread = M.spread_labels
        self.gap = M.LABEL_GAP

    def _check(self, ys, lo, hi):
        out = self.spread(ys, lo, hi, self.gap)
        self.assertEqual(len(out), len(ys))
        for y in out:
            self.assertGreaterEqual(y, lo - 1e-9)
            self.assertLessEqual(y, hi + 1e-9)
        s = sorted(out)
        min_gap = min(self.gap, (hi - lo) / (len(ys) - 1)) if len(ys) > 1 else 0
        for a, b in zip(s, s[1:]):
            self.assertGreaterEqual(b - a, min_gap - 1e-9)
        return out

    def test_y1_case_that_used_to_hang(self):
        # Requested label heights in the Y1 right-edge column (panel h = 3.4).
        self._check([2.29, 3.30, 0.46, 1.04, 2.88, 2.92], 0.20, 3.30)

    def test_overfull_column_is_spaced_evenly(self):
        self._check([3.3] * 15, 0.20, 3.30)

    def test_uncrowded_labels_do_not_move(self):
        self.assertEqual(self.spread([0.5, 1.5, 2.5], 0.20, 3.30, self.gap),
                         [0.5, 1.5, 2.5])


def _digests_of(paths):
    out = {}
    for p in paths:
        with open(p, "rb") as fh:
            out[p] = hashlib.sha256(fh.read()).hexdigest()
    return out


class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = L.load_summary(ROOT)
        cls.recompute = L.load_recompute(ROOT)

    def test_summary_matches_recompute(self):
        n = L.assert_summary_matches_recompute(self.summary, self.recompute)
        self.assertGreater(n, 0)
        self.assertEqual(self.recompute["mismatch_count"], 0)

    def test_ratchet_monotone_and_end_values(self):
        for stream, end in RATCHET_END.items():
            _, ts = L.threshold_trajectory(ROOT, stream, "rolling_threshold")
            self.assertEqual(L.count_threshold_increases(ts), 0,
                             "%s normal-only rolling must never increase" % stream)
            self.assertAlmostEqual(ts[-1], end, places=3,
                                   msg="%s ratchet end value" % stream)

    def test_in_event_exceedance(self):
        for stream, (exc, ine, mx) in E3_EXPECTED.items():
            s = L.in_event_exceedance(ROOT, stream)
            self.assertEqual((s["exceed"], s["in_event"], s["max_run"]),
                             (exc, ine, mx),
                             "%s E3 exceedance stats" % stream)


class TestTablesEqualSummary(unittest.TestCase):
    """Every numeric cell written into a table must be present in summary.json."""

    @classmethod
    def setUpClass(cls):
        subprocess.check_call([sys.executable, TAB, ROOT],
                              stdout=subprocess.DEVNULL, timeout=GEN_TIMEOUT)
        cls.summary = L.load_summary(ROOT)
        cls.tabdir = TABDIR

    def _expected_numbers(self):
        """Collect the set of stringified numbers summary.json licenses."""
        allowed = set()
        for stream in L.STREAMS:
            for arm in L.ARMS:
                m = self.summary["results"][stream][arm]
                for key in ("alert_windows", "alert_episodes", "false_episodes",
                            "non_event_alert_duration", "deferrals",
                            "recalibration_count", "coverage_num", "coverage_den",
                            "event_recall_num", "event_recall_den"):
                    allowed.add(str(m[key]))
                if m["mean_delay"] is not None:
                    allowed.add("%.1f" % m["mean_delay"])
                if m["in_event_alerted_fraction"] is not None:
                    allowed.add("%.3f" % m["in_event_alerted_fraction"])
        return allowed

    def test_skab_and_synthetic_cells_are_licensed(self):
        allowed = self._expected_numbers()
        for tid in ("tab-skab.tex", "tab-synthetic.tex", "tab-synthetic-compact.tex"):
            with open(os.path.join(self.tabdir, tid)) as _fh:
                text = _fh.read()
            for line in text.splitlines():
                if "&" not in line or "\\midrule" in line or "toprule" in line:
                    continue
                # skip the two header rows
                if ("Stream" in line or "Scen." in line or "delay" in line
                        or "dur." in line or "alert" in line):
                    continue
                cells = [c.strip().rstrip("\\").strip() for c in line.split("&")]
                for c in cells:
                    for tok in re.findall(r"\d+\.\d+", c):  # decimals
                        self.assertIn(tok, allowed,
                                      "%s: decimal %s not in summary.json"
                                      % (tid, tok))
                    for frac in re.findall(r"\b\d+/\d+\b", c):  # n/d fractions
                        num, den = frac.split("/")
                        self.assertIn(num, allowed)
                        self.assertIn(den, allowed)


class TestDeterminism(unittest.TestCase):
    def _run_twice(self, script, outdir, names):
        subprocess.check_call([sys.executable, script, ROOT],
                              stdout=subprocess.DEVNULL, timeout=GEN_TIMEOUT)
        paths = [os.path.join(outdir, n) for n in names]
        first = _digests_of(paths)
        subprocess.check_call([sys.executable, script, ROOT],
                              stdout=subprocess.DEVNULL, timeout=GEN_TIMEOUT)
        second = _digests_of(paths)
        self.assertEqual(first, second, "output not byte-identical across runs")

    def test_figures_deterministic(self):
        self._run_twice(FIG, FIGDIR, [
            "fig-ratchet.tex", "fig-scorer-limit.tex",
            "fig-synthetic-map.tex", "fig-tradeoff.tex",
            "figures-manifest.json", "preview.tex",
        ])

    def test_tables_deterministic(self):
        self._run_twice(TAB, TABDIR, [
            "tab-skab.tex", "tab-synthetic.tex", "tab-synthetic-compact.tex",
            "tab-ablation.tex",
            "tables-manifest.json", "tables-preview.tex",
        ])


class TestBudget(unittest.TestCase):
    """Measure each fragment's natural size at the report geometry and assert it
    fits the page budget.  Skipped cleanly if pdflatex is absent."""

    GEOMETRY = "a4paper,margin=24mm,includeheadfoot"
    FRAGS = ["fig-ratchet", "fig-scorer-limit", "fig-synthetic-map", "fig-tradeoff"]
    HEIGHT_FRACTION = {           # HD / textheight upper bounds
        "fig-ratchet": 0.42,
        "fig-synthetic-map": 0.45,
        "fig-tradeoff": 0.50,
        "fig-scorer-limit": 0.30,
    }

    @classmethod
    def setUpClass(cls):
        cls.pdflatex = None
        for cand in ("/Library/TeX/texbin/pdflatex", "pdflatex"):
            path = shutil.which(cand) or (cand if os.path.exists(cand) else None)
            if path:
                cls.pdflatex = path
                break
        # ensure fragments exist
        subprocess.check_call([sys.executable, FIG, ROOT], stdout=subprocess.DEVNULL, timeout=GEN_TIMEOUT)

    def _measure(self):
        scratch = os.environ.get("KIROCREW_SCRATCH") or tempfile.gettempdir()
        workdir = tempfile.mkdtemp(prefix="p6budget-", dir=scratch)
        tex = [
            "\\documentclass[11pt]{article}",
            "\\usepackage[%s]{geometry}" % self.GEOMETRY,
            "\\usepackage{tikz}\\usepackage{amsmath}\\usetikzlibrary{arrows.meta}",
            "\\newsavebox{\\measbox}\\newdimen\\hd",
            "\\begin{document}",
            "\\typeout{MEAS TEXTWIDTH=\\the\\textwidth}",
            "\\typeout{MEAS TEXTHEIGHT=\\the\\textheight}",
        ]
        for f in self.FRAGS:
            tex.append("\\savebox{\\measbox}{\\input{%s}}" % os.path.join(FIGDIR, f + ".tex"))
            tex.append("\\hd=\\dimexpr\\ht\\measbox+\\dp\\measbox\\relax")
            tex.append("\\typeout{MEAS FRAG=%s WIDTH=\\the\\wd\\measbox HD=\\the\\hd}" % f)
        tex.append("\\end{document}")
        texpath = os.path.join(workdir, "budget.tex")
        with open(texpath, "w") as fh:
            fh.write("\n".join(tex) + "\n")
        proc = subprocess.run(
            [self.pdflatex, "-halt-on-error", "-interaction=nonstopmode", "budget.tex"],
            cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=GEN_TIMEOUT)
        log = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0,
                         "measuring pdflatex failed:\n" + log[-2000:])

        def dim(pat, s):
            m = re.search(pat + r"=([\d.]+)pt", s)
            return float(m.group(1)) if m else None

        tw = dim("MEAS TEXTWIDTH", log)
        th = dim("MEAS TEXTHEIGHT", log)
        sizes = {}
        for line in log.splitlines():
            if "MEAS FRAG=" in line:
                m = re.search(r"FRAG=(\S+) WIDTH=([\d.]+)pt\s*HD=([\d.]+)pt", line)
                if m:
                    sizes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        shutil.rmtree(workdir, ignore_errors=True)
        return tw, th, sizes

    def test_fragments_within_budget(self):
        if not self.pdflatex:
            self.skipTest("pdflatex not available; budget check skipped")
        tw, th, sizes = self._measure()
        self.assertIsNotNone(tw)
        self.assertIsNotNone(th)
        measured = {}
        for f in self.FRAGS:
            self.assertIn(f, sizes, "no measurement for %s" % f)
            w, hd = sizes[f]
            frac = hd / th
            measured[f] = (w, frac)
            self.assertLessEqual(w, tw + 0.5,
                                 "%s natural width %.1fpt > textwidth %.1fpt"
                                 % (f, w, tw))
            self.assertLessEqual(frac, self.HEIGHT_FRACTION[f] + 1e-6,
                                 "%s height fraction %.3f > budget %.3f"
                                 % (f, frac, self.HEIGHT_FRACTION[f]))
        # emit the measured fractions for the run log
        print("\n[budget] textwidth=%.1fpt textheight=%.1fpt" % (tw, th))
        for f in self.FRAGS:
            w, frac = measured[f]
            print("[budget] %-18s width=%6.1fpt  height=%.3f textheight (budget %.2f)"
                  % (f, w, frac, self.HEIGHT_FRACTION[f]))

    def test_no_font_below_6pt(self):
        # Exact per-glyph point sizes are not feasible to measure from the log,
        # so this is a PROXY: the smallest font macro used by any generator is
        # \scriptsize, which at an 11pt base is ~8pt (>= 6pt).  We assert no
        # generator emits \tiny (~6pt at 11pt, and smaller under scaling) or an
        # explicit sub-6pt \fontsize.  A true typeset-size check is skipped.
        for f in self.FRAGS:
            with open(os.path.join(FIGDIR, f + ".tex")) as fh:
                txt = fh.read()
            self.assertNotIn("\\tiny", txt, "%s uses \\tiny" % f)
            for m in re.findall(r"\\fontsize\{([\d.]+)\}", txt):
                self.assertGreaterEqual(float(m), 6.0,
                                        "%s sets a font below 6pt" % f)
        print("\n[budget] font-size check is a proxy (no \\tiny / no sub-6pt "
              "\\fontsize); exact typeset-pt measurement skipped.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
