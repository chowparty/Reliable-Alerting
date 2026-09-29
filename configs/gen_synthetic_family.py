#!/usr/bin/env python3
"""Generate the Y1-Y7 synthetic-family configs, labels, and evaluation config.

Frozen protocol section 6. Deterministic; standard library only. Writes JSON
with sorted keys so reruns are byte-identical. Run:

    .venv/bin/python configs/gen_synthetic_family.py

Output (under research/configs/):
    policy-study-Y{1..7}.json          run config (input + segments + window +
                                       scoring + calibration; policy filled by
                                       the runner per arm)
    policy-study-Y{1..7}-labels.json   labelled events (half-open), by construction
    policy-study-synthetic-evaluation.json   shared evaluation schedule

The runner substitutes each arm's "policy" block into the run config; the base
config here carries a placeholder fixed_threshold policy so the file validates
on its own.
"""
import json
from pathlib import Path

PATTERN = [9, 10, 11, 10, 10, 11, 12, 11, 8, 9, 10, 9, 10, 10, 10, 10]
LENGTH = 1600
SOURCE_FIT = [0, 400]
CALIBRATION = [400, 560]
REPLAY = [560, 1600]
WINDOW = 4
STRIDE = 4
FAULT_OFFSET = 6.0

_CONFIG_DIR = Path(__file__).resolve().parent


def spiky_fault_offsets(a, b):
    """+6.0 on alternating aligned 4-sample windows over [a, b).

    Blocks are [a, a+4), [a+4, a+8), ...; the fault is added on blocks 0, 2,
    4, ... (every other block), which raises the block median on those windows
    and leaves the ones between untouched -- the 'spiky' shape of section 6.
    """
    offsets = []
    block = 0
    start = a
    while start < b:
        stop = min(start + WINDOW, b)
        if block % 2 == 0:
            offsets.append({"start": start, "stop": stop, "offset": FAULT_OFFSET})
        start += WINDOW
        block += 1
    return offsets


def step(a, b, amount):
    return [{"start": a, "stop": b, "offset": float(amount)}]


def ramp(start_at, step_every, increment, target, stop):
    """+increment added at start_at, start_at+step_every, ... until +target,
    held to stop. Modelled as cumulative half-open step offsets."""
    offsets = []
    cum = 0.0
    t = start_at
    # Each tick raises the level by `increment` from that tick to `stop`.
    while cum + increment <= target + 1e-9:
        offsets.append({"start": t, "stop": stop, "offset": float(increment)})
        cum += increment
        t += step_every
    return offsets


# Scenario definitions (offsets, labelled events as inclusive-of-construction
# half-open ranges). Y1/Y2/Y6 have no events.
def scenarios():
    out = {}

    # Y1 benign step: +2.0 on [800,1600); no events.
    out["Y1"] = (step(800, 1600, 2.0), [])

    # Y2 benign ramp: +0.25 at each of 800,810,...,870 until +2.0, held to 1600.
    out["Y2"] = (ramp(800, 10, 0.25, 2.0, 1600), [])

    # Y3 step then fault: Y1 + spiky fault on [1200,1300); event [1200,1300).
    out["Y3"] = (step(800, 1600, 2.0) + spiky_fault_offsets(1200, 1300),
                 [("Y3-fault-0", 1200, 1300)])

    # Y4 fault shaped like a step: +2.0 on [800,1600); event [800,1600) (H4).
    out["Y4"] = (step(800, 1600, 2.0), [("Y4-fault-0", 800, 1600)])

    # Y5 spiky fault only: spiky fault on [800,900); event [800,900).
    out["Y5"] = (spiky_fault_offsets(800, 900), [("Y5-fault-0", 800, 900)])

    # Y6 step beyond cap: +5.0 on [800,1600); no events.
    out["Y6"] = (step(800, 1600, 5.0), [])

    # Y7 temporary step, return, fault: +2.0 on [800,1100); spiky fault on
    # [1300,1400); event [1300,1400).
    out["Y7"] = (step(800, 1100, 2.0) + spiky_fault_offsets(1300, 1400),
                 [("Y7-fault-0", 1300, 1400)])

    return out


def base_config(offsets):
    return {
        "schema_version": 1,
        "input": {"kind": "synthetic_periodic_v1", "length": LENGTH,
                  "pattern": [float(x) for x in PATTERN], "offsets": offsets},
        "segments": {"source_fit": SOURCE_FIT, "calibration": CALIBRATION,
                     "replay": REPLAY},
        "window": {"length": WINDOW, "stride": STRIDE, "anchor": "segment_start",
                   "edge_policy": "drop_incomplete", "end_index": "inclusive"},
        "scoring": {"kind": "mean_distance", "epsilon": 1e-06,
                    "fit_scope": "source_fit", "standard_deviation": "population"},
        "calibration": {"kind": "fixed_quantile", "quantile": 0.95,
                        "method": "nearest_rank", "min_samples": 2,
                        "score_segment": "calibration"},
        # Placeholder policy so the file validates standalone; the runner
        # substitutes each arm's policy block.
        "policy": {"kind": "fixed_threshold", "comparison": "strict_greater"},
        "missing_policy": "reject", "source_label_use": "none",
        "time_basis": "sample_index", "held_out": "not_reserved_or_evaluated",
    }


def labels_doc(events):
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "coverage": [REPLAY[0], REPLAY[1]],
        "events": [{"event_id": eid, "start": s, "stop": e} for (eid, s, e) in events],
    }


def eval_config():
    first = REPLAY[0] + WINDOW - 1  # 563
    return {
        "schema_version": 1,
        "time_basis": "sample_index",
        "horizon": [REPLAY[0], REPLAY[1]],
        "first_decision": first,
        "decision_stride": STRIDE,
        "window_length": WINDOW,
    }


def _write(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2, allow_nan=False)
        fh.write("\n")


def main():
    scen = scenarios()
    for name, (offsets, events) in scen.items():
        _write(_CONFIG_DIR / f"policy-study-{name}.json", base_config(offsets))
        _write(_CONFIG_DIR / f"policy-study-{name}-labels.json", labels_doc(events))
    _write(_CONFIG_DIR / "policy-study-synthetic-evaluation.json", eval_config())
    print(f"wrote {len(scen)} scenario configs + labels + 1 evaluation config")


if __name__ == "__main__":
    main()
