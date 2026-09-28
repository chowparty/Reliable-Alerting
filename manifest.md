# Development stream manifest (checked 28 September 2026)

Both files are the tracked public SKAB streams from <https://github.com/waico/SKAB>. The SHA-256 values below were computed from the files in this checkout with `shasum -a 256`. They identify these exact local bytes; the upstream download and licence have not been independently reverified in this audit. The CSV delimiter is `;`, the ordered time field is `datetime`, the measured field is `Current`, and `anomaly` is used **offline** to check development split eligibility and to evaluate saved predictions. Runtime scoring receives only `Current`; `source_label_use: none` describes the runtime API, not how these development boundaries were chosen.

| Development stream | Tracked file | Rows | SHA-256 | Source fit | Calibration | Replay | Labelled event |
|---|---|---:|---|---|---|---|---|
| valve1 | `SKAB/valve1/0.csv` | 1148 | `14ea55a5987f2074f3c9851f3963e3308c8668eeeca2249fc3de6491cb7e1b74` | `[0,400)` | `[400,574)` | `[574,1148)` | `[574,975)` |
| valve2 | `SKAB/valve2/0.csv` | 1125 | `893e9f555603657ed871d00975e1154a3139daca523118daabdb18c9b0124a6c` | `[0,400)` | `[400,562)` | `[562,1125)` | `[562,956)` |

The first anomaly is at row 574 in valve1 and row 562 in valve2. Both calibration segments are source-normal under the supplied `anomaly` labels. The previous valve2 runs in `result/valve2/` used calibration `[400,574)`, which includes twelve anomalous rows; those results must not support the corrected development comparison. The split correction was made after inspecting **development** labels. It is not an untouched or prospectively selected test.

The runner in `run_real_streams.py` uses length 4, stride 4, segment-anchored non-overlapping windows, drops incomplete tails, fits a mean-distance scorer on source fit, and sets a nearest-rank 0.95 calibration quantile. It declares `missing_policy: reject`; the CSV loader now rejects missing `Current` values. Both current files have zero blank `Current` cells. The five policies and their settings are in the runner. Each output uses its own source-fit and calibration history.

No held-out stream was reserved by name before outcome inspection. No authoritative operating-point freeze or independent pre-held-out audit is recorded. Valve1 and valve2 are development streams. Do not describe either as held-out; preserve the held-out target for a later prospective freeze and audit.
