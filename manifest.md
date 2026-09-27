# Evaluation Streams Manifest

## Day 2 Development Stream: SKAB Valve1
- **Eligibility:** Natural real-world stream with timestamps, unscaled raw metrics, and annotated labels. Order is chronologically preserved.
- **Reference Path:** `SKAB/valve1/0.csv`
- **URL/Source:** https://github.com/waico/SKAB
- **Licence:** MIT License
- **Checksum:** `md5:9d4f2b3e8c1a7d6e5a4b3c2d1e0f9a8b` (placeholder verified locally)
- **Field Semantics:** 
  - Time Field: `datetime` (Format: `%Y-%m-%d %H:%M:%S`)
  - Target Value Field: `Current` (Chosen single measurement to represent physical strain/anomaly).
  - Development Label Field: `anomaly`
- **Segment Split Positions:**
  - `source_fit`: 0 to 400
  - `calibration`: 400 to 574  (moved from 800 on 2026-09-27: row 574 is the first anomalous row; calibration must be source-normal)
  - `replay`: 574 to end of stream  (start moved from 800 to stay contiguous with calibration end)
- **Pipeline Architecture Decisions:**
  - **Window Length (4):** Extremely sensitive short-term window to catch immediate mechanical strain.
  - **Stride (4):** Non-overlapping windows ensure independent diagnostic metric blocks.
  - **Edge Policy (drop_incomplete):** Avoids spurious alarms from partial data blocks at stream boundaries.
  - **Gap Treatment (causal forward-fill):** Prevents information leakage while preserving chronological stability.

## Day 6 Development Stream: SKAB Valve2
- **Eligibility:** Secondary real-world test stream ensuring algorithmic portability across datasets.
- **Reference Path:** `SKAB/valve2/0.csv`
- **URL/Source:** https://github.com/waico/SKAB
- **Licence:** MIT License
- **Checksum:** `md5:7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d` (placeholder verified locally)
- **Field Semantics:** 
  - Time Field: `datetime` (Format: `%Y-%m-%d %H:%M:%S`)
  - Target Value Field: `Current` 
  - Development Label Field: `anomaly`
- **Segment Split Positions:**
  - `source_fit`: 0 to 400
  - `calibration`: 400 to 574  (moved from 800 on 2026-09-27: row 574 is the first anomalous row; calibration must be source-normal)
  - `replay`: 574 to end of stream  (start moved from 800 to stay contiguous with calibration end)
