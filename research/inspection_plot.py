"""inspection_plot.py - Day 5 hand-inspection plots (Pratyush stand-in).

Why this exists: the existing evidence.render_figure refuses any run whose
threshold varies over time ("varying thresholds not supported for figure"),
so it cannot plot the rolling_threshold policy, and it plots no threshold
TRACE, no episodes, and no labelled-event span. Day 5 hand-inspection needs
to read each policy's saved trace against the score, the threshold trace, the
alert episodes, and the labelled event. This module adds the smallest reusable
capability to do that, for all five valve1 policy traces (fixed thresholds and
the varying rolling threshold alike).

Conventions match evidence.render_figure: plain stdlib SVG (no dependencies),
xml.escape on text, point markers (no interpolated score line), a dashed
threshold drawn as a stepwise trace, refuse-overwrite output (mode "x").

Read-only: reads saved predictions.csv + a labels/event span; writes one SVG.
It never runs a policy, never modifies traces, thresholds, or evaluations.
"""
import csv
from pathlib import Path
from xml.sax.saxutils import escape


def load_prediction_rows(predictions_csv):
    """Read a saved predictions.csv (8 base columns, optional 'features').

    Returns rows as dicts with parsed numeric fields. Accepts the trailing
    'features' column but does not require or parse it (Day 5 hand-inspection
    plots score/threshold/decisions, not feature values)."""
    p = Path(predictions_csv)
    rows = []
    with open(p, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"window_id", "start_index", "end_index", "score",
                    "output_state", "threshold", "config_id", "run_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"predictions.csv missing columns: {sorted(missing)}")
        for r in reader:
            rows.append({
                "window_id": r["window_id"],
                "start_index": int(r["start_index"]),
                "end_index": int(r["end_index"]),
                "score": float(r["score"]),
                "output_state": r["output_state"],
                "threshold": float(r["threshold"]),
            })
    if not rows:
        raise ValueError("predictions.csv has no data rows")
    return rows


def alert_episodes(rows):
    """Group adjacent 'alert' decisions into (start_end_index, stop_end_index)
    episodes keyed on decision end_index. Mirrors the evaluator's rule
    (adjacent alerts merge; normal/defer break) but on the decision grid, for
    plotting only -- not an evaluation."""
    episodes = []
    run_start = None
    prev_end = None
    for r in rows:
        if r["output_state"] == "alert":
            if run_start is None:
                run_start = r["end_index"]
            prev_end = r["end_index"]
        else:
            if run_start is not None:
                episodes.append((run_start, prev_end))
                run_start = None
    if run_start is not None:
        episodes.append((run_start, prev_end))
    return episodes


def render_inspection_figure(predictions_csv, output_svg, event_spans=(),
                             policy_label=None):
    """Plot one saved policy trace for Day 5 hand-inspection.

    Draws: score points (blue=normal, red=alert) at each decision end_index;
    a STEPWISE threshold trace (handles varying thresholds, e.g. rolling);
    shaded alert-episode bands; and shaded labelled-event span(s). event_spans
    is an iterable of [start, stop) sample-index pairs (e.g. [(574, 975)]).

    Writes plain SVG with refuse-overwrite (mode 'x'). Returns the path.
    """
    rows = load_prediction_rows(predictions_csv)
    xs = [r["end_index"] for r in rows]
    ys = [r["score"] for r in rows]
    thrs = [r["threshold"] for r in rows]
    varying = len(set(thrs)) != 1

    width, height = 720, 440
    left, right, top, bottom = 60, 20, 54, 78
    plot_w = width - left - right
    plot_h = height - top - bottom

    # x-domain covers decisions and any event span so events are visible.
    x_candidates = list(xs)
    for a, b in event_spans:
        x_candidates.extend([a, b])
    x_min, x_max = min(x_candidates), max(x_candidates)
    if x_max == x_min:
        x_min -= 1
        x_max += 1
    y_lo = min(min(ys), min(thrs))
    y_hi = max(max(ys), max(thrs))
    if y_hi == y_lo:
        y_lo -= 1.0
        y_hi += 1.0
    else:
        pad = (y_hi - y_lo) * 0.1 or 1.0
        y_lo -= pad
        y_hi += pad

    def _cx(x):
        return left + (x - x_min) / (x_max - x_min) * plot_w

    def _cy(y):
        return top + plot_h - (y - y_lo) / (y_hi - y_lo) * plot_h

    if len(set(xs)) <= 10:
        x_ticks = sorted(set(xs))
    else:
        x_ticks = [int(round(x_min + (x_max - x_min) * i / 5)) for i in range(6)]
    y_ticks = [y_lo + (y_hi - y_lo) * i / 4 for i in range(5)]

    label = policy_label or Path(predictions_csv).parent.name
    title = f"valve1 {label} - Day 5 inspection: score, threshold trace, episodes, event"

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">')
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{width // 2}" y="24" text-anchor="middle" font-size="13">{escape(title)}</text>')

    # labelled event span(s) - light band behind everything
    for a, b in event_spans:
        xa, xb = _cx(a), _cx(b)
        parts.append(
            f'<rect x="{xa:.2f}" y="{top}" width="{max(0.0, xb - xa):.2f}" height="{plot_h}" '
            f'fill="orange" fill-opacity="0.15"><title>{escape(f"labelled event [{a},{b})")}</title></rect>')

    # alert-episode bands (grey), on the forward decision grid
    for (s, e) in alert_episodes(rows):
        # episode spans decisions s..e (inclusive end_index); shade to next tick
        xa = _cx(s)
        xb = _cx(e)
        parts.append(
            f'<rect x="{xa:.2f}" y="{top}" width="{max(2.0, xb - xa):.2f}" height="{plot_h}" '
            f'fill="red" fill-opacity="0.08"><title>{escape(f"alert episode ends {s}..{e}")}</title></rect>')

    # axes
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="black"/>')
    parts.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="black"/>')
    parts.append(
        f'<text x="12" y="{top + plot_h // 2}" font-size="11" transform="rotate(-90 12,{top + plot_h // 2})">score</text>')
    parts.append(
        f'<text x="{left + plot_w // 2}" y="{height - 12}" text-anchor="middle" font-size="11">end_index (sample_index)</text>')
    for xt in x_ticks:
        cx = _cx(xt)
        parts.append(
            f'<line x1="{cx:.2f}" y1="{top + plot_h}" x2="{cx:.2f}" y2="{top + plot_h + 5}" stroke="black"/>')
        parts.append(
            f'<text x="{cx:.2f}" y="{top + plot_h + 18}" text-anchor="middle" font-size="10">{escape(str(xt))}</text>')
    for yt in y_ticks:
        cy = _cy(yt)
        parts.append(
            f'<line x1="{left - 5}" y1="{cy:.2f}" x2="{left}" y2="{cy:.2f}" stroke="black"/>')
        parts.append(
            f'<text x="{left - 8}" y="{cy + 3:.2f}" text-anchor="end" font-size="10">{escape(f"{yt:.3g}")}</text>')

    # STEPWISE threshold trace: each decision's threshold held across its
    # forward interval [end_index, next end_index). This is the key capability
    # the existing plotter lacks -- it renders the rolling policy's varying
    # cutoff honestly, with no interpolation and no backdating.
    seg_pts = []
    for i, r in enumerate(rows):
        x_start = r["end_index"]
        x_stop = rows[i + 1]["end_index"] if i + 1 < len(rows) else x_max
        ty = _cy(r["threshold"])
        seg_pts.append((_cx(x_start), ty, _cx(x_stop), ty))
    for j, (x1, y1, x2, y2) in enumerate(seg_pts):
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="green" stroke-dasharray="6,4" stroke-width="1.5"/>')
        # vertical connector between successive threshold levels (step)
        if j + 1 < len(seg_pts):
            nx1, ny1, _, _ = seg_pts[j + 1]
            if abs(ny1 - y2) > 0.01:
                parts.append(
                    f'<line x1="{x2:.2f}" y1="{y2:.2f}" x2="{nx1:.2f}" y2="{ny1:.2f}" '
                    f'stroke="green" stroke-dasharray="2,3" stroke-width="1"/>')
    thr_note = "threshold trace (varying)" if varying else f"threshold {rows[0]['threshold']:.4g} (fixed)"

    # score points: blue normal, red alert (no connecting line)
    for r in rows:
        cx = _cx(r['end_index'])
        cy = _cy(r['score'])
        fill = 'red' if r['output_state'] == 'alert' else 'blue'
        tip = '{wid} end={end} score={score:.4g} thr={thr:.4g} {state}'.format(
            wid=r['window_id'], end=r['end_index'], score=r['score'],
            thr=r['threshold'], state=r['output_state'])
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="3.5" fill="{fill}">'
            f'<title>{escape(tip)}</title>'
            '</circle>')

    # captions
    parts.append(
        f'<text x="{left}" y="{height - 46}" font-size="10">{escape("source=" + str(predictions_csv))}</text>')
    parts.append(
        f'<text x="{left}" y="{height - 32}" font-size="10">{escape(thr_note + "; orange band = labelled event; grey/red band = alert episode")}</text>')

    # legend
    lx = left + plot_w - 150
    ly = top + 12
    parts.append(f'<circle cx="{lx}" cy="{ly}" r="4" fill="blue"/>')
    parts.append(f'<text x="{lx + 8}" y="{ly + 4}" font-size="10">normal</text>')
    parts.append(f'<circle cx="{lx + 62}" cy="{ly}" r="4" fill="red"/>')
    parts.append(f'<text x="{lx + 70}" y="{ly + 4}" font-size="10">alert</text>')
    parts.append(
        f'<line x1="{lx}" y1="{ly + 16}" x2="{lx + 20}" y2="{ly + 16}" stroke="green" stroke-dasharray="6,4"/>')
    parts.append(f'<text x="{lx + 26}" y="{ly + 20}" font-size="10">threshold</text>')
    parts.append("</svg>")

    text = "\n".join(parts) + "\n"
    with open(output_svg, "x", encoding="utf-8") as fh:
        fh.write(text)
    return str(output_svg)