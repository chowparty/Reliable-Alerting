# Evaluation Streams Manifest

## Day 2 Development Stream: SKAB Valve1
- **Eligibility:** Natural real-world stream with timestamps, unscaled raw metrics, and annotated labels. Order is chronologically preserved.
- **Reference Path:** `SKAB/valve1/0.csv`
- **Field Semantics:** 
  - Time Field: `datetime` (Format: `%Y-%m-%d %H:%M:%S`)
  - Target Value Field: `Current` (Chosen single measurement to represent physical strain/anomaly).
  - Development Label Field: `anomaly`
- **Segment Split Positions:**
  - `source_fit`: 0 to 400
  - `calibration`: 400 to 800
  - `replay`: 800 to 1150

## Day 6 Development Stream: SKAB Valve2
- **Eligibility:** Secondary real-world test stream ensuring algorithmic portability across datasets.
- **Reference Path:** `SKAB/valve2/0.csv`
- **Field Semantics:** 
  - Time Field: `datetime` (Format: `%Y-%m-%d %H:%M:%S`)
  - Target Value Field: `Current` 
  - Development Label Field: `anomaly`
- **Segment Split Positions:**
  - `source_fit`: 0 to 400
  - `calibration`: 400 to 800
  - `replay`: 800 to 1150
