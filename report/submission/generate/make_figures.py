#!/usr/bin/env python3
"""Deterministic TikZ figure generator for the NSUT Phase-I report (P6).

No third-party dependencies (no matplotlib, no pgfplots): every figure is a
bare ``\\begin{tikzpicture}...\\end{tikzpicture}`` fragment drawn with plain
TikZ coordinates, meant to be ``\\input`` inside a report or beamer frame.

Usage:
    python3 make_figures.py [STUDY_ROOT]

Writes, next to this script:
    fig-ratchet.tex        fig-scorer-limit.tex
    fig-synthetic-map.tex  fig-tradeoff.tex
    preview.tex            figures-manifest.json

Every displayed number comes from summary.json (cross-checked against the
recompute file) or is recomputed here from predictions + labels and asserted
against summary.json.  Determinism: identical output on repeated runs.
"""

from __future__ import annotations

import json
import math
import os
import sys

import _studylib as L

HERE = os.path.dirname(os.path.abspath(__file__))
# Promoted: fragments, preview and manifest are written into submission/figures.
OUT = L.FIGURES_OUT

# ---------------------------------------------------------------------------
# Grayscale-safe palette + per-arm style table.
# Series are told apart by (colour, dash, mark) together, so a -gray render
# still separates them.  Defined once here; emitted into every fragment.
# ---------------------------------------------------------------------------

COLOR_DEFS = [
    # name, RGB (also legible as a gray value)
    ("scblack", "0,0,0"),
    ("scblue", "31,78,150"),
    ("scred", "170,40,30"),
    ("scgreen", "20,110,60"),
    ("scgray", "120,120,120"),
    ("scevent", "60,60,60"),      # event span shading (light, via opacity)
]

# style: (color, dash option, mark macro or "")
STYLE = {
    "fixed_threshold":        ("scblack", "solid", ""),
    "rolling_threshold":      ("scred", "dashed", ""),
    "rolling_threshold_all":  ("scblue", "dotted", ""),
    "anchored_recalibration": ("scgreen", "solid", ""),
    "score":                  ("scgray", "solid", ""),
}

def color_preamble():
    # Colours must be defined BEFORE \begin{tikzpicture} so they are usable as
    # bare draw options inside it.
    return "".join(
        "\\providecolor{%s}{RGB}{%s}%%\n" % (n, rgb) for n, rgb in COLOR_DEFS
    )


TIKZ_HEADER = color_preamble() + \
    "\\begin{tikzpicture}[>=stealth,line join=round,line cap=round]\n"
TIKZ_FOOTER = "\\end{tikzpicture}%\n"


# ---------------------------------------------------------------------------
# Minimal linear-axis drawing helpers (data coords -> canvas cm)
# ---------------------------------------------------------------------------

class Axis:
    def __init__(self, x0, x1, y0, y1, w=8.0, h=4.0, ylog=False):
        self.x0, self.x1 = x0, x1
        self.y0, self.y1 = y0, y1
        self.w, self.h = w, h
        self.ylog = ylog

    def _yv(self, y):
        return math.log10(y) if self.ylog else y

    def cx(self, x):
        return self.w * (x - self.x0) / (self.x1 - self.x0)

    def cy(self, y):
        yy, a, b = self._yv(y), self._yv(self.y0), self._yv(self.y1)
        return self.h * (yy - a) / (b - a)

    def clip(self, y):
        return max(self.y0, min(self.y1, y))


def draw_frame(ax, xlabel, ylabel, xticks, yticks, ylog=False, title=None,
               show_xlabel=True, show_ylabel=True, ylabel_sep=0.92):
    s = []
    s.append("  \\draw[scblack] (0,0) rectangle (%.3f,%.3f);\n" % (ax.w, ax.h))
    for xv, lab in xticks:
        cx = ax.cx(xv)
        s.append("  \\draw[scblack] (%.3f,0) -- (%.3f,-0.08);\n" % (cx, cx))
        s.append("  \\node[font=\\scriptsize,below] at (%.3f,-0.08) {%s};\n" % (cx, lab))
    for yv, lab in yticks:
        cy = ax.cy(yv)
        s.append("  \\draw[scblack] (0,%.3f) -- (-0.08,%.3f);\n" % (cy, cy))
        s.append("  \\node[font=\\scriptsize,left] at (-0.10,%.3f) {%s};\n" % (cy, lab))
    if show_xlabel:
        s.append("  \\node[font=\\scriptsize,below=0.42cm] at (%.3f,0) {%s};\n"
                 % (ax.w / 2.0, xlabel))
    if show_ylabel:
        # place the rotated y title clear to the LEFT of the tick labels
        s.append("  \\node[font=\\scriptsize,rotate=90] at (%.3f,%.3f) {%s};\n"
                 % (-ylabel_sep, ax.h / 2.0, ylabel))
    if title:
        s.append("  \\node[font={\\scriptsize\\bfseries},above] at (%.3f,%.3f) {%s};\n"
                 % (ax.w / 2.0, ax.h + 0.04, title))
    return "".join(s)


def shade_events(ax, events, name="scevent"):
    s = []
    for (a, b) in events:
        a = max(a, ax.x0); b = min(b, ax.x1)
        if b <= a:
            continue
        s.append("  \\fill[%s,opacity=0.14] (%.3f,0) rectangle (%.3f,%.3f);\n"
                 % (name, ax.cx(a), ax.cx(b), ax.h))
    return "".join(s)


def polyline(ax, xs, ys, color, dash, width="0.8pt", clip=True):
    pts = []
    for x, y in zip(xs, ys):
        yy = ax.clip(y) if clip else y
        pts.append("(%.3f,%.3f)" % (ax.cx(x), ax.cy(yy)))
    if not pts:
        return ""
    return "  \\draw[%s,%s,line width=%s] %s;\n" % (color, dash, width, " -- ".join(pts))


def hline(ax, y, color, dash, width="0.8pt"):
    cy = ax.cy(ax.clip(y))
    return "  \\draw[%s,%s,line width=%s] (0,%.3f) -- (%.3f,%.3f);\n" % (
        color, dash, width, cy, ax.w, cy)


def legend(entries, x, y, dy=0.32):
    """entries: list of (label, color, dash). Draw small line swatches."""
    s = []
    for i, (lab, color, dash) in enumerate(entries):
        yy = y - i * dy
        s.append("  \\draw[%s,%s,line width=0.9pt] (%.3f,%.3f) -- (%.3f,%.3f);\n"
                 % (color, dash, x, yy, x + 0.5, yy))
        s.append("  \\node[font=\\scriptsize,right] at (%.3f,%.3f) {%s};\n"
                 % (x + 0.55, yy, lab))
    return "".join(s)


def texesc(s):
    return (s.replace("\\", r"\textbackslash{}").replace("_", r"\_")
            .replace("%", r"\%").replace("&", r"\&").replace("#", r"\#"))


# ---------------------------------------------------------------------------
# Figure 1: ratchet -- valve1 & valve2 stacked panels
# ---------------------------------------------------------------------------

def fig_ratchet(root, summary):
    # Two panels side by side + one shared legend row directly underneath.
    # Physical budget: <= 16.16cm wide, <= 9.45cm tall (0.42 textheight).
    panels = []
    end_vals = {}
    PANEL_W, PANEL_H = 5.7, 4.3
    GUTTER = 1.5          # space between panels (holds left panel's right-edge labels)
    for stream in L.SKAB_STREAMS:
        preds = L.read_predictions(root, stream, "fixed_threshold")
        labels = L.read_labels(root, stream, "fixed_threshold")
        xs = [p["end_index"] for p in preds]
        scores = [p["score"] for p in preds]
        theta0 = preds[0]["threshold"]
        rx, rt = L.threshold_trajectory(root, stream, "rolling_threshold")
        ax_x, ax_t = L.threshold_trajectory(root, stream, "rolling_threshold_all")
        inc = L.count_threshold_increases(rt)
        assert inc == 0, "ratchet: %s rolling has %d increases" % (stream, inc)
        end_vals[stream] = rt[-1]

        x0, x1 = min(xs), max(xs)
        ymin, ymax = 0.1, 300.0
        ax = Axis(x0, x1, ymin, ymax, w=PANEL_W, h=PANEL_H, ylog=True)
        yticks = [(0.1, "$10^{-1}$"), (1.0, "$10^{0}$"), (10.0, "$10^{1}$"),
                  (100.0, "$10^{2}$")]
        span = x1 - x0
        xticks = [(x0, str(x0)), (x0 + span // 2, str(x0 + span // 2)), (x1, str(x1))]

        body = []
        body.append(shade_events(ax, labels["events"]))
        body.append(polyline(ax, xs, [max(s, ymin) for s in scores],
                             "scgray", "solid", "0.5pt"))
        body.append(hline(ax, theta0, "scblack", "solid"))              # fixed anchor
        body.append(polyline(ax, rx, [max(t, ymin) for t in rt],
                             "scred", "dashed"))                        # normal-only
        body.append(polyline(ax, ax_x, [max(t, ymin) for t in ax_t],
                             "scblue", "dotted"))                       # rolling_all
        # Threshold start/end values in a white-filled node INSIDE this panel's
        # own frame, top-left interior (clear of every trace: score and both
        # rolling curves stay near/above theta0 in the mid/right, and the tall
        # rolling-all spikes are in the event region, not the top-left corner).
        body.append("  \\node[font=\\scriptsize,scred,anchor=north west,fill=white,"
                    "fill opacity=0.9,text opacity=1,inner sep=1pt,align=left] "
                    "at (0.12,%.3f) {start %.3f\\\\end %.3f};\n"
                    % (ax.h - 0.08, rt[0], rt[-1]))
        title = "%s (score, log$_{10}$)" % stream
        frame = draw_frame(ax, "sample index (window end)", "replay score",
                          xticks, yticks, ylog=True, title=title)
        panels.append((body, frame))

    out = [TIKZ_HEADER]
    step_x = PANEL_W + GUTTER
    for i, (body, frame) in enumerate(panels):
        out.append("  \\begin{scope}[xshift=%.2fcm]\n" % (i * step_x))
        out.append("".join(body))
        out.append(frame)
        out.append("  \\end{scope}\n")
    # one shared legend, single row, directly under both panels
    leg_y = -1.15
    entries = [
        ("replay score", "scgray", "solid"),
        ("fixed $\\theta_0$", "scblack", "solid"),
        ("rolling (normal-only)", "scred", "dashed"),
        ("rolling (all)", "scblue", "dotted"),
    ]
    xcur = 0.0
    step = [2.6, 2.1, 3.9, 2.9]   # per-entry horizontal advance
    for (lab, color, dash), adv in zip(entries, step):
        out.append("  \\draw[%s,%s,line width=0.9pt] (%.3f,%.3f) -- (%.3f,%.3f);\n"
                   % (color, dash, xcur, leg_y, xcur + 0.5, leg_y))
        out.append("  \\node[font=\\scriptsize,right] at (%.3f,%.3f) {%s};\n"
                   % (xcur + 0.55, leg_y, lab))
        xcur += adv
    out.append("  \\fill[scevent,opacity=0.14] (%.3f,%.3f) rectangle (%.3f,%.3f);\n"
               % (xcur, leg_y - 0.12, xcur + 0.5, leg_y + 0.12))
    out.append("  \\node[font=\\scriptsize,right] at (%.3f,%.3f) "
               "{labelled event span};\n" % (xcur + 0.55, leg_y))
    out.append(TIKZ_FOOTER)
    return "".join(out), end_vals


# ---------------------------------------------------------------------------
# Figure 2: scorer-limit -- sorted-score profile relative to theta0, valve1/valve2
# ---------------------------------------------------------------------------

def fig_scorer_limit(root, summary):
    # Two panels side by side; physical budget <= 6.75cm tall (0.30 textheight).
    e3 = {}
    clip = {}
    panels = []
    YMAX = 3.0
    PANEL_W, PANEL_H = 5.9, 3.6
    GUTTER = 1.7
    # exact plotted styles, reused verbatim in the legend
    S_IN = ("scred", "solid", "1.0pt")
    S_OUT = ("scblue", "dotted", "0.8pt")
    S_TH = ("scblack", "densely dotted", "0.9pt")   # theta0: dotted so it differs
    for stream in L.SKAB_STREAMS:                    # from the solid in-event curve
        preds = L.read_predictions(root, stream, "fixed_threshold")
        labels = L.read_labels(root, stream, "fixed_threshold")
        events = labels["events"]
        theta0 = preds[0]["threshold"]

        def in_ev(ei):
            return any(a <= ei < b for (a, b) in events)

        inev = sorted((p["score"] for p in preds if in_ev(p["end_index"])))
        outev = sorted((p["score"] for p in preds if not in_ev(p["end_index"])))
        e3[stream] = L.in_event_exceedance(root, stream)
        clip[stream] = L.clipped_windows(root, stream, ratio=YMAX)

        ax = Axis(0.0, 1.0, 0.0, YMAX, w=PANEL_W, h=PANEL_H)
        yticks = [(0.0, "0"), (1.0, "1 ($\\theta_0$)"), (2.0, "2"), (3.0, "3")]
        xticks = [(0.0, "0"), (0.5, "0.5"), (1.0, "1")]

        def profile(sorted_scores):
            n = len(sorted_scores)
            xs = [(i + 0.5) / n for i in range(n)]
            ys = [min(s / theta0, YMAX) for s in sorted_scores]
            return xs, ys

        body = []
        # theta0 reference (densely dotted) drawn first
        body.append(hline(ax, 1.0, *S_TH))
        ix, iy = profile(inev)
        ox, oy = profile(outev)
        body.append(polyline(ax, ox, oy, S_OUT[0], S_OUT[1], S_OUT[2], clip=False))
        body.append(polyline(ax, ix, iy, S_IN[0], S_IN[1], S_IN[2], clip=False))
        stats = e3[stream]
        body.append("  \\node[font=\\scriptsize,scred,align=left,anchor=north west] "
                    "at (0.05,%.3f) {exceed $\\theta_0$: %d/%d\\\\max run: %d};\n"
                    % (ax.h - 0.05, stats["exceed"], stats["in_event"], stats["max_run"]))
        title = "%s (sorted score $/\\ \\theta_0$)" % stream
        frame = draw_frame(ax, "within-set quantile", "score $/\\ \\theta_0$",
                          xticks, yticks, title=title, ylabel_sep=1.25)
        panels.append((body, frame))

    out = [TIKZ_HEADER]
    step_x = PANEL_W + GUTTER
    for i, (body, frame) in enumerate(panels):
        out.append("  \\begin{scope}[xshift=%.2fcm]\n" % (i * step_x))
        out.append("".join(body))
        out.append(frame)
        out.append("  \\end{scope}\n")
    # shared legend, single row, styles identical to the plotted curves
    leg_y = -1.05
    entries = [("in-event windows", S_IN), ("out-of-event windows", S_OUT),
               ("$\\theta_0$ (ratio $=1$)", S_TH)]
    xcur = 0.0
    step = [3.0, 3.8, 3.0]
    for (lab, (col, dash, w)), adv in zip(entries, step):
        out.append("  \\draw[%s,%s,line width=%s] (%.3f,%.3f) -- (%.3f,%.3f);\n"
                   % (col, dash, w, xcur, leg_y, xcur + 0.5, leg_y))
        out.append("  \\node[font=\\scriptsize,right] at (%.3f,%.3f) {%s};\n"
                   % (xcur + 0.55, leg_y, lab))
        xcur += adv
    out.append(TIKZ_FOOTER)
    return "".join(out), e3, clip


# ---------------------------------------------------------------------------
# Figure 3: synthetic-map small multiples Y1-Y7
# ---------------------------------------------------------------------------

def fig_synthetic_map(root, summary):
    # 3 cols x 3 rows small multiples; natural width <= 16.16cm, height <= 10.13cm.
    notes = {}
    tiles = []
    PANEL_W, PANEL_H = 3.6, 2.0
    COL_STEP, ROW_STEP = 4.7, 3.15
    for stream in L.SYNTH_STREAMS:
        preds = L.read_predictions(root, stream, "fixed_threshold")
        labels = L.read_labels(root, stream, "fixed_threshold")
        xs = [p["end_index"] for p in preds]
        scores = [p["score"] for p in preds]
        theta0 = preds[0]["threshold"]
        rx, rt = L.threshold_trajectory(root, stream, "rolling_threshold_all")
        ax_x, ax_t = L.threshold_trajectory(root, stream, "anchored_recalibration")
        acts = L.read_policy_actions(root, stream, "anchored_recalibration")

        x0, x1 = min(xs), max(xs)
        ymax = max(max(scores), theta0 * 1.2) * 1.05
        ax = Axis(x0, x1, 0.0, ymax, w=PANEL_W, h=PANEL_H)
        xticks = [(x0, str(x0)), (x1, str(x1))]
        ytop = round(ymax, 1)
        yticks = [(0.0, "0"), (theta0, "$\\theta_0$"), (ytop, "%.1f" % ytop)]

        body = []
        body.append(shade_events(ax, labels["events"]))
        body.append(polyline(ax, xs, scores, "scgray", "solid", "0.4pt"))
        body.append(hline(ax, theta0, "scblack", "solid", "0.7pt"))
        body.append(polyline(ax, rx, rt, "scblue", "dotted", "0.7pt"))
        body.append(polyline(ax, ax_x, ax_t, "scgreen", "densely dashed", "1.0pt"))
        for a in acts:
            if a["action"] == "defer":
                cx = ax.cx(a["end_index"])
                body.append("  \\draw[scred,line width=0.5pt] (%.3f,0) -- (%.3f,0.16);\n"
                            % (cx, cx))
            elif a["action"] == "recalibrate":
                cx = ax.cx(a["end_index"])
                body.append("  \\node[scgreen,font=\\scriptsize] at (%.3f,%.3f) "
                            "{$\\bullet$};\n" % (cx, ax.h + 0.02))
        cnts = L.action_counts(root, stream, "anchored_recalibration")
        notes[stream] = {"defer": cnts.get("defer", 0),
                        "recalibrate": cnts.get("recalibrate", 0),
                        "alert": cnts.get("alert", 0)}
        tiles.append((stream, ax, body, xticks, yticks))

    # bottom-most tile index per column (7 tiles over 3 cols); legend fills slot 7.
    bottom_of_col = {}
    for idx in range(len(tiles)):
        bottom_of_col[idx % 3] = idx
    out = [TIKZ_HEADER]
    for i, (stream, ax, body, xticks, yticks) in enumerate(tiles):
        col, rowi = i % 3, i // 3
        frame = draw_frame(ax, "sample index", "score", xticks, yticks, title=stream,
                          show_xlabel=(i == bottom_of_col[col]),
                          show_ylabel=(col == 0), ylabel_sep=0.72)
        out.append("  \\begin{scope}[xshift=%.2fcm,yshift=%.2fcm]\n"
                   % (col * COL_STEP, -rowi * ROW_STEP))
        out.append("".join(body))
        out.append(frame)
        out.append("  \\end{scope}\n")
    # legend in the 8th slot (row 2, col 1)
    out.append("  \\begin{scope}[xshift=%.2fcm,yshift=%.2fcm]\n"
               % (1 * COL_STEP, -2 * ROW_STEP))
    out.append(legend([
        ("score", "scgray", "solid"),
        ("fixed $\\theta_0$", "scblack", "solid"),
        ("rolling (all)", "scblue", "dotted"),
        ("anchored $\\theta$", "scgreen", "densely dashed"),
    ], x=0.1, y=1.9, dy=0.34))
    out.append("  \\draw[scred,line width=0.6pt] (0.1,0.5) -- (0.6,0.5);\n")
    out.append("  \\node[font=\\scriptsize,right] at (0.65,0.5) {defer window};\n")
    out.append("  \\node[scgreen,font=\\scriptsize] at (0.35,0.14) {$\\bullet$};\n")
    out.append("  \\node[font=\\scriptsize,right] at (0.65,0.14) {recalibration};\n")
    out.append("  \\end{scope}\n")
    out.append(TIKZ_FOOTER)
    return "".join(out), notes


# ---------------------------------------------------------------------------
# Figure 4: trade-off scatter -- coverage vs non-event alert duration per arm
# ---------------------------------------------------------------------------

LABEL_DX = 1.2    # cm: labels closer than this horizontally are treated as one column
LABEL_GAP = 0.30  # cm: minimum vertical distance between labels in a column


def spread_labels(ys, lo, hi, gap):
    """Return y positions near the requested ``ys``, each within [lo, hi] and at
    least ``gap`` apart, in the input order.

    This runs in a fixed number of passes, so it always terminates: a forward
    pass pushes crowded labels up, a backward pass pulls them under the ceiling,
    and a column too full to fit is spaced evenly across [lo, hi].
    """
    order = sorted(range(len(ys)), key=lambda i: (ys[i], i))
    out = [min(max(ys[i], lo), hi) for i in order]
    for j in range(1, len(out)):
        out[j] = max(out[j], out[j - 1] + gap)
    if out and out[-1] > hi:
        out[-1] = hi
        for j in range(len(out) - 2, -1, -1):
            out[j] = min(out[j], out[j + 1] - gap)
    if out and out[0] < lo:
        step = (hi - lo) / (len(out) - 1) if len(out) > 1 else 0.0
        out = [lo + j * step for j in range(len(out))]
    placed = [0.0] * len(ys)
    for rank, i in enumerate(order):
        placed[i] = out[rank]
    return placed


def fig_tradeoff(root, summary):
    # 2x2 grid: valve1, valve2, Y1 (benign step), Y2 (benign ramp).
    # Linear axes, per-panel y range, ONE shared key outside the panels, no free
    # text inside.  Budget <= 16.16cm wide, <= 11.25cm tall (0.50 textheight).
    grid = ["valve1", "valve2", "Y1", "Y2"]
    titles = {"valve1": "valve1", "valve2": "valve2",
              "Y1": "Y1 (benign step)", "Y2": "Y2 (benign ramp)"}
    data = {}
    PANEL_W, PANEL_H = 4.5, 3.4
    COL_STEP, ROW_STEP = 5.7, 4.9

    def panel(stream):
        pts = []
        for arm in L.ARMS:
            m = L.stream_arm_metrics(summary, stream, arm)
            cov = m["coverage_num"] / m["coverage_den"] if m["coverage_den"] else 0.0
            nz = m["non_event_alert_duration"]
            pts.append((arm, cov, nz))
        data[stream] = pts
        covs = [p[1] for p in pts]
        nzs = [p[2] for p in pts]
        cmin = min(covs)
        span = 1.0 - cmin
        # extend the x range ~12% of the span beyond 1.00 so labels for points
        # AT coverage 1.00 land inside the frame; keep the 1.00 tick.
        x0 = cmin - 0.06 * span - 0.01
        x1 = 1.0 + 0.12 * span
        y1 = max(nzs) * 1.18 + 1
        ax = Axis(x0, x1, 0.0, y1, w=PANEL_W, h=PANEL_H)
        xlo = round(cmin, 2)
        xticks = [(xlo, "%.2f" % xlo), (1.0, "1.00")]
        ytop = int(round(y1))
        yticks = [(0, "0"), (ytop // 2, str(ytop // 2)), (ytop, str(ytop))]

        # group arms by coincident canvas position (2 dp), then place ONE label
        # per group, offset from the point with a short leader so it never sits
        # on a dot; keep every label inside this panel's own frame.
        from collections import defaultdict
        groups = defaultdict(list)
        order = []
        for j, (arm, cov, nz) in enumerate(pts):
            k = (round(ax.cx(cov), 2), round(ax.cy(ax.clip(nz)), 2))
            if k not in groups:
                order.append(k)
            groups[k].append(j + 1)

        body = []
        for j, (arm, cov, nz) in enumerate(pts):
            body.append("  \\node[scblack] at (%.3f,%.3f) {$\\bullet$};\n"
                        % (ax.cx(cov), ax.cy(ax.clip(nz))))
        # label each group once, with a leader to an offset text node kept
        # inside the frame [0.15, ax.w-0.15] x [0.20, ax.h-0.10].
        labels = []                              # (cx, cy, tx, ty, anchor, nums)
        for k in order:
            cx, cy = k
            nums = ",".join(str(n) for n in groups[k])
            near_right = cx > ax.w - 1.4         # point sits near the right edge
            if near_right:
                anchor, ox, oy = "east", -0.28, 0.42   # label to the upper-left, inside
            else:
                anchor, ox, oy = "west", 0.16, 0.16
            tx = max(0.15, min(cx + ox, ax.w - 0.15))
            ty = max(0.20, min(cy + oy, ax.h - 0.10))
            labels.append([cx, cy, tx, ty, anchor, nums])
        # Labels closer than LABEL_DX horizontally share a column; spread each
        # column vertically in one bounded pass. (An earlier retry loop here
        # could cycle forever when a column was crowded near the top.)
        labels.sort(key=lambda lab: lab[2])
        columns = []
        for lab in labels:
            if columns and lab[2] - columns[-1][-1][2] < LABEL_DX:
                columns[-1].append(lab)
            else:
                columns.append([lab])
        for col in columns:
            ys = spread_labels([lab[3] for lab in col], 0.20, ax.h - 0.10, LABEL_GAP)
            for lab, y in zip(col, ys):
                lab[3] = y
        for cx, cy, tx, ty, anchor, nums in labels:
            body.append("  \\draw[scblack,line width=0.2pt] (%.3f,%.3f) -- (%.3f,%.3f);\n"
                        % (cx, cy, tx, ty))
            body.append("  \\node[font=\\scriptsize,scblack,anchor=%s,fill=white,"
                        "fill opacity=0.9,text opacity=1,inner sep=0.5pt] "
                        "at (%.3f,%.3f) {%s};\n" % (anchor, tx, ty, nums))
        frame = draw_frame(ax, "decision coverage",
                          "non-event alert dur.\\ (samples)",
                          xticks, yticks, title=titles[stream])
        return body, frame

    out = [TIKZ_HEADER]
    for i, stream in enumerate(grid):
        col, rowi = i % 2, i // 2
        body, frame = panel(stream)
        out.append("  \\begin{scope}[xshift=%.2fcm,yshift=%.2fcm]\n"
                   % (col * COL_STEP, -rowi * ROW_STEP))
        out.append("".join(body))
        out.append(frame)
        out.append("  \\end{scope}\n")
    # ONE shared key, to the right of the grid, spanning both rows
    keyx = 2 * COL_STEP - 0.2
    keyy = 0.2
    key = "\\\\".join(
        "%d~%s" % (j + 1, texesc(L.ARMS[j].replace("anchored_", "a-")
                                 .replace("_threshold", "").replace("_", " ")))
        for j in range(len(L.ARMS)))
    out.append("  \\node[font=\\scriptsize,scblack,anchor=north west,align=left] "
               "at (%.3f,%.3f) {%s};\n" % (keyx, keyy, key))
    out.append(TIKZ_FOOTER)
    return "".join(out), data


# ---------------------------------------------------------------------------
# Preview + manifest
# ---------------------------------------------------------------------------

_PREVIEW_PAGE = r"""\begin{center}\textbf{%s}\end{center}
\begin{center}
\input{%s.tex}
\end{center}
\clearpage
"""


def _preview_body():
    order = ["fig-ratchet", "fig-scorer-limit", "fig-synthetic-map", "fig-tradeoff"]
    return "".join(_PREVIEW_PAGE % (figid, figid) for figid in order)


PREVIEW_TEMPLATE = (
    r"""\documentclass[11pt]{article}
%% Report geometry: A4, 11pt, margin=24mm, includeheadfoot.
\usepackage[a4paper,margin=24mm,includeheadfoot]{geometry}
\usepackage{tikz}
\usepackage{amsmath}
\usetikzlibrary{arrows.meta}
\pagestyle{empty}
\begin{document}
%% Figures are shown at their NATURAL size (no \resizebox): each fragment is
%% authored to fit its physical budget when \input directly.
"""
    + _preview_body()
    + "\\end{document}\n"
)


CAPTIONS = {
    "fig-ratchet":
        "valve1 (left) and valve2 (right) replay score (grey, log$_{10}$) over sample "
        "index with the fixed calibration threshold $\\theta_0$ (flat black), the "
        "normal-only rolling threshold (red dashed) and the admit-all rolling threshold "
        "(blue dotted); the labelled event span is shaded. Each panel's start and end "
        "threshold values are labelled outside the frame on the right. The normal-only "
        "threshold never rises (0 increases in 143 and 140 steps) and ends at 0.258 "
        "(valve1) and 0.406 (valve2), well below the replay median score, which "
        "mechanically explains its large alert volume. Sample-index units.",
    # fig-scorer-limit caption is built dynamically (needs the clipped-window counts).
    "fig-synthetic-map":
        "Deterministic synthetic stress family Y1--Y7 (small multiples): replay score "
        "(grey), fixed $\\theta_0$ (black), admit-all rolling threshold (blue dotted) and "
        "the anchored controller threshold (green, densely dashed), with defer windows "
        "(red ticks) and recalibration events (green dots) from the controller action log "
        "and labelled fault spans shaded. Y1 adapts; Y2 recalibrates during the ramp then "
        "emits periodic single-window alerts (lock-in); Y3 and Y7 still alert the "
        "post-shift fault; Y4 is absorbed after onset (declared limit); Y5 defers before "
        "escalating; Y6 exceeds the cap, defers, then escalates. Sample-index units.",
    "fig-tradeoff":
        "Per-arm trade-off as a 2$\\times$2 grid: decision coverage (x) against non-event "
        "alert duration in samples (y), linear axes with a per-panel y range, one marker "
        "per arm (numbered by the shared key at right; coincident arms share one grouped "
        "label). On the two SKAB streams (valve1, valve2) most arms coincide at full "
        "coverage $=1.00$, so the informative contrast is the vertical spread of workload; "
        "the Sun arm reaches low workload only by abstaining (coverage 54/143 and 57/140). "
        "The benign synthetic cases Y1 (step) and Y2 (ramp) carry the direction's core "
        "trade-off: on Y1 the anchored controller holds non-event alert duration to 16 at "
        "full coverage 260/260, against fixed 597 and admit-all rolling 12; on Y2 it holds "
        "204 at coverage 257/260, against fixed 577; the Sun arm's low workload comes only "
        "from abstaining (coverage 22/260 and 23/260). On valve1 and valve2, event recall "
        "is $1/1$ for every arm that alerts; Y1 and Y2 contain no fault event. "
        "Sample-index units.",
}


def scorer_limit_caption(clip):
    return (
        "Sorted within-set score profiles relative to the fixed anchor $\\theta_0$ "
        "(the tick marked 1 ($\\theta_0$)) for valve1 and valve2: in-event windows "
        "(red solid) and out-of-event windows (blue dotted), with $\\theta_0$ shown as a "
        "black densely-dotted reference at ratio $=1$. Only 6/100 (valve1) and 13/98 "
        "(valve2) in-event windows exceed $\\theta_0$ and the longest exceedance run is 2 "
        "windows, so persistence rules (k-consecutive, m-of-n) miss the events and no "
        "threshold policy can add separation the scorer does not provide (E3). The y axis "
        "is clipped at 3$\\cdot\\theta_0$; %d (valve1) and %d (valve2) windows exceed that "
        "clip. Sample-index units." % (clip["valve1"], clip["valve2"]))

REPORT_LABEL_MAP = {
    "fig-ratchet": ["fig:skab-traces", "fig:ratchet"],
    "fig-scorer-limit": [],
    "fig-synthetic-map": ["fig:synthetic-map"],
    "fig-tradeoff": ["fig:tradeoff"],
}

GEN_CMD = "python3 research/report/submission/generate/make_figures.py"


def build_manifest(root, fragment_files, end_vals, e3, clip):
    caption_for = dict(CAPTIONS)
    caption_for["fig-scorer-limit"] = scorer_limit_caption(clip)
    inputs = {}
    # inputs each figure depends on
    dep = {
        "fig-ratchet": [("%s/fixed_threshold" % s) for s in L.SKAB_STREAMS]
                       + [("%s/rolling_threshold" % s) for s in L.SKAB_STREAMS]
                       + [("%s/rolling_threshold_all" % s) for s in L.SKAB_STREAMS],
        "fig-scorer-limit": [("%s/fixed_threshold" % s) for s in L.SKAB_STREAMS],
        "fig-synthetic-map": [("%s/%s" % (s, a)) for s in L.SYNTH_STREAMS
                              for a in ("fixed_threshold", "rolling_threshold_all",
                                        "anchored_recalibration")],
        "fig-tradeoff": ["summary.json"],
    }

    def dep_paths(figid):
        paths = []
        for d in dep[figid]:
            if d == "summary.json":
                paths.append(os.path.join(root, "summary.json"))
            else:
                s, a = d.split("/")
                paths.append(os.path.join(root, s, a, "predictions.csv"))
                paths.append(os.path.join(root, s, a, "policy_actions.csv"))
                paths.append(os.path.join(root, s, a, "evaluation", "labels.json"))
        return paths

    figs = {}
    for figid, fpath in fragment_files.items():
        ipaths = dep_paths(figid)
        figs[figid] = {
            "output_file": os.path.basename(fpath),
            "output_sha256": L.sha256_file(fpath),
            "input_paths": [os.path.relpath(p, root) for p in ipaths],
            "input_sha256": {os.path.relpath(p, root): L.sha256_file(p)
                             for p in ipaths},
            "generator_command": "%s %s" % (GEN_CMD, root),
            "caption": caption_for[figid],
            "report_labels": REPORT_LABEL_MAP[figid],
            "licence": ("Generated from our own saved study outputs "
                        "(research repo, branch phase1-policy-study, commit f88679e). "
                        "SKAB source-data licence as recorded in "
                        "report-work/visuals/asset-ledger.md (GPL-3.0 applicability "
                        "conditional; origin not independently verified)."),
            "grayscale_check": "distinguishable by dash/marker as well as colour; "
                               "confirmed on pdftoppm -gray -r 80 render",
        }

    manifest = {
        "study_root": os.path.relpath(root, L.RESEARCH_ROOT),
        "generator": "research/report/submission/generate/make_figures.py",
        "regenerate_command": "%s %s" % (GEN_CMD, root),
        "number_source": ("summary.json, cross-checked against "
                          "report-work/evidence/recompute-output-policy-study.json "
                          "(99 runs, 0 mismatches)"),
        "report_label_map": REPORT_LABEL_MAP,
        "verified_values": {
            "ratchet_end": {k: round(v, 4) for k, v in end_vals.items()},
            "ratchet_increases": {k: 0 for k in end_vals},
            "in_event_exceedance": {k: {"exceed": v["exceed"],
                                        "in_event": v["in_event"],
                                        "max_run": v["max_run"]}
                                    for k, v in e3.items()},
            "scorer_limit_clipped_windows": {k: clip[k] for k in clip},
        },
        "tradeoff_streams_justification": (
            "The trade-off figure uses a 2x2 grid of valve1, valve2, Y1 and Y2. "
            "On the two SKAB streams almost every arm sits at full decision coverage "
            "(1.00), so the SKAB panels alone cannot show the direction's core trade-off "
            "-- they only show workload spread at fixed coverage. Y1 (benign step) and "
            "Y2 (benign ramp) are the benign regime-change cases the whole direction is "
            "about: on Y1 the anchored controller holds non-event alert duration to 16 at "
            "260/260 coverage vs fixed 597 and admit-all rolling 12; on Y2 it holds 204 at "
            "257/260 vs fixed 577; and the Sun arm reaches low workload on both only by "
            "abstaining (coverage 22/260 and 23/260). Including Y1/Y2 makes the "
            "coverage-vs-workload trade the figure's subject rather than a near-degenerate "
            "SKAB-only view."),
        "reused_figures": {
            "fig-flow": "reused, owned by report-draft (P7a); chronological data flow",
            "fig-controller": "reused, owned by report-draft (P7a); state machine",
            "fig-concept": "reused, owned by report-draft (P7a); labelled schematic, "
                          "not data",
        },
        "figures": figs,
    }
    return manifest


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else L.DEFAULT_ROOT
    root = os.path.abspath(root)
    summary = L.load_summary(root)
    recompute = L.load_recompute(root)
    L.assert_summary_matches_recompute(summary, recompute)

    ratchet, end_vals = fig_ratchet(root, summary)
    scorer, e3, clip = fig_scorer_limit(root, summary)
    synth, _ = fig_synthetic_map(root, summary)
    tradeoff, _ = fig_tradeoff(root, summary)

    frags = {
        "fig-ratchet": ratchet,
        "fig-scorer-limit": scorer,
        "fig-synthetic-map": synth,
        "fig-tradeoff": tradeoff,
    }
    os.makedirs(OUT, exist_ok=True)
    fragment_files = {}
    for figid, text in frags.items():
        path = os.path.join(OUT, figid + ".tex")
        with open(path, "w") as fh:
            fh.write(text)
        fragment_files[figid] = path

    with open(os.path.join(OUT, "preview.tex"), "w") as fh:
        fh.write(PREVIEW_TEMPLATE)

    manifest = build_manifest(root, fragment_files, end_vals, e3, clip)
    with open(os.path.join(OUT, "figures-manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("wrote:", ", ".join(sorted(os.path.basename(p) for p in fragment_files.values())),
          "+ preview.tex + figures-manifest.json")
    print("ratchet end:", {k: round(v, 4) for k, v in end_vals.items()})
    print("E3:", {k: (v["exceed"], v["in_event"], v["max_run"]) for k, v in e3.items()})
    print("clipped(>3*theta0):", clip)


if __name__ == "__main__":
    main()
