"""audit.py - code-level label-discipline checks (Nakul, Day 3).

Static, import-and-inspect checks that no runtime component accepts a label
input. This complements the data-level audits in test_audit.py (which inspect
saved run outputs) and the behavioural checks in test_verification.py /
test_metric_cases.py. Here we look at the teammate code itself: the scorer,
the decision policies, the label-free trace builder, and the loader.

Read-only: this module imports reliable_alerting components and inspects their
signatures and source; it never runs the pipeline and never touches result/,
results/, or any data file. It is exercised by tests/test_audit_code.py.
"""
import inspect

# Substrings that would indicate a label/ground-truth input sneaking into a
# runtime signature. Matched case-insensitively against parameter names.
LABEL_PARAM_MARKERS = (
    "label", "labels", "anomaly", "ground_truth", "groundtruth",
    "y_true", "target", "is_anomaly",
)


def _param_names(func):
    return list(inspect.signature(func).parameters.keys())


def signature_has_no_label_param(func):
    """Return (ok, offending_params) for a callable's parameter names."""
    names = _param_names(func)
    bad = [n for n in names
           if any(m in n.lower() for m in LABEL_PARAM_MARKERS)]
    return (not bad), bad


def audit_runtime_label_freedom():
    """Inspect every runtime component and report label-parameter freedom.

    Returns a dict: {qualified_name: {"params": [...], "ok": bool,
    "offending": [...]}}. Covers the scorer (fit + score), all five decision
    policies' constructors and decide(), the label-free trace builder
    compute_trace, and the CSV loader.
    """
    from reliable_alerting import scoring, policy, pipeline, loading

    targets = {
        "scoring.MeanDistanceScorer.fit": scoring.MeanDistanceScorer.fit,
        "scoring.MeanDistanceScorer.score": scoring.MeanDistanceScorer.score,
        "policy.FixedThresholdPolicy.__init__": policy.FixedThresholdPolicy.__init__,
        "policy.FixedThresholdPolicy.decide": policy.FixedThresholdPolicy.decide,
        "policy.RollingThresholdPolicy.__init__": policy.RollingThresholdPolicy.__init__,
        "policy.RollingThresholdPolicy.decide": policy.RollingThresholdPolicy.decide,
        "policy.KConsecutivePolicy.__init__": policy.KConsecutivePolicy.__init__,
        "policy.KConsecutivePolicy.decide": policy.KConsecutivePolicy.decide,
        "policy.MOfNPolicy.__init__": policy.MOfNPolicy.__init__,
        "policy.MOfNPolicy.decide": policy.MOfNPolicy.decide,
        "policy.HysteresisPolicy.__init__": policy.HysteresisPolicy.__init__,
        "policy.HysteresisPolicy.decide": policy.HysteresisPolicy.decide,
        "pipeline.compute_trace": pipeline.compute_trace,
        "loading.load_csv_stream": loading.load_csv_stream,
        "loading.load_values": loading.load_values,
    }
    report = {}
    for name, func in targets.items():
        ok, offending = signature_has_no_label_param(func)
        report[name] = {"params": _param_names(func), "ok": ok,
                        "offending": offending}
    return report


def loader_returns_only_value_column():
    """Confirm load_csv_stream's source reads a single value column, not labels.

    Static-source check: the function body must reference the value_column
    parameter and must NOT reference an 'anomaly'/'label' column literal. This
    is a guard against a future edit that starts reading the label column.
    Returns (ok, reason).
    """
    from reliable_alerting import loading
    src = inspect.getsource(loading.load_csv_stream)
    lowered = src.lower()
    # It must use the value_column parameter to select data.
    uses_value_column = "value_column" in src
    # It must not hard-read a label-like column.
    reads_label = ('"anomaly"' in lowered or "'anomaly'" in lowered
                   or '"label"' in lowered or "'label'" in lowered)
    if not uses_value_column:
        return False, "load_csv_stream does not reference value_column"
    if reads_label:
        return False, "load_csv_stream references a label-like column literal"
    return True, "reads only the configured value_column; no label column literal"

def recompute_median_feature_from_scores(rows):
    """Feature spot-check: recompute the rolling-median feature column from the
    saved SCORE sequence and compare it to the saved features[0] column.

    `rows` is a list of dicts each carrying at least "score" (float) and
    "features" (a two-element [median, spread] list, as stored in a saved
    predictions.csv). We drive the SAME teammate component the pipeline used
    (diagnostics_features.RollingMedianFeature, length 5, causal) over the
    scores in row order and confirm every recomputed value matches the saved
    median to a tight tolerance.

    This is a diagnostics-feature integrity check, not a scoring/label check:
    it proves the persisted median column is exactly what the declared causal
    feature produces from the recorded scores, with no hidden inputs.

    Returns (ok, n_checked, first_mismatch) where first_mismatch is None on
    success or a dict describing the first disagreeing row.
    """
    from reliable_alerting import diagnostics_features

    feat = diagnostics_features.RollingMedianFeature(5)
    n = 0
    for i, r in enumerate(rows):
        recomputed = feat.update(r["score"])
        saved = r["features"][0]
        n += 1
        if abs(recomputed - saved) > 1e-9:
            return False, n, {"index": i, "recomputed": recomputed,
                              "saved": saved, "score": r["score"]}
    return True, n, None
