import os
import sys
import uuid
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

# Insert src to PYTHONPATH
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here / "src"))

from reliable_alerting import pipeline
from reliable_alerting import writing
from reliable_alerting import provenance

def peak_allocation():
    _, peak = tracemalloc.get_traced_memory()
    return int(peak)

def run_policy(stream_name, stream_path, length, policy_config):
    kind = policy_config["kind"]
    output_dir = here / "results" / stream_name / kind
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
        
    config = {
        "schema_version": 1,
        "input": {
            "kind": "csv_stream",
            "path": str(stream_path),
            "value_column": "Current",
            "length": length,
            "delimiter": ";"
        },
        "segments": {
            "source_fit": [0, 400],
            "calibration": [400, 800],
            "replay": [800, length]
        },
        "window": {
            "length": 4,
            "stride": 4,
            "anchor": "segment_start",
            "edge_policy": "drop_incomplete",
            "end_index": "inclusive"
        },
        "scoring": {
            "kind": "mean_distance",
            "epsilon": 1e-06,
            "fit_scope": "source_fit",
            "standard_deviation": "population"
        },
        "calibration": {
            "kind": "fixed_quantile",
            "quantile": 0.95,
            "method": "nearest_rank",
            "min_samples": 2,
            "score_segment": "calibration"
        },
        "policy": policy_config,
        "features": [
            {"kind": "rolling_median", "length": 5},
            {"kind": "rolling_spread", "length": 5}
        ],
        "missing_policy": "reject",
        "source_label_use": "none",
        "time_basis": "sample_index",
        "held_out": "not_reserved_or_evaluated"
    }

    print(f"Running {kind} on {stream_name}...")
    t0 = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    tracemalloc.start()
    
    try:
        resolved = pipeline.validate_config(config)
        trace = pipeline.compute_trace(resolved)
        
        cid = trace["config_id"]
        rows = trace["rows"]
        cal_rows = trace["calibration_rows"]
        diagnostics = trace["diagnostics"]
        
        peak = peak_allocation()
        elapsed = time.monotonic() - t0
        run_id = uuid.uuid4().hex
        full_rows = [dict(r, run_id=run_id) for r in rows]
        
        repo = provenance.repo_root()
        metadata = {
            "run_id": run_id,
            "config_id": cid,
            "input_hash": trace.get("input_hash"),
            "started_at": started,
            "started_at_scope": "write_output_entry",
            "intended_day1": pipeline.INTENDED_DAY1,
            "command": provenance.command_record(),
            "environment": provenance.environment_record(),
            "git": provenance.git_record(str(repo)),
            "file_hashes": provenance.file_hashes(repo),
            "resource_scope": pipeline.RESOURCE_SCOPE,
            "elapsed_monotonic_seconds": elapsed,
            "peak_python_allocation_bytes": peak,
        }
        
        writing.write_run(output_dir, full_rows, resolved, metadata, diagnostics, cal_rows)
        print(f"  -> Saved {len(rows)} decision rows for {stream_name}/{kind}")
        
    finally:
        tracemalloc.stop()

def main():
    streams = {
        "valve1": (here / "SKAB" / "valve1" / "0.csv", 1148),
        "valve2": (here / "SKAB" / "valve2" / "0.csv", 1125),
    }

    policies = [
        {"kind": "fixed_threshold", "comparison": "strict_greater"},
        {"kind": "rolling_threshold", "comparison": "strict_greater", "history_length": 10, "admission_rule": "normal_only", "quantile": 0.95},
        {"kind": "k_consecutive", "comparison": "strict_greater", "k": 3},
        {"kind": "m_of_n", "comparison": "strict_greater", "m": 3, "n": 5},
        {"kind": "hysteresis", "comparison": "strict_greater", "low_ratio": 0.8}
    ]

    for sname, (spath, slen) in streams.items():
        for pol in policies:
            run_policy(sname, spath, slen, pol)

if __name__ == "__main__":
    main()
