# Phase-I report — canonical LaTeX source

*When Should an Alert Threshold Learn? Admission-Separated Recalibration as a Decision-Time
Action for Time-Series Anomaly Alerting* — B.Tech Project-I (Phase-I) mid-semester report.

This is the tracked, canonical source. It builds a 15-page A4 / 11pt PDF whose numbers all
resolve to the saved study `results/20260929-policy-study-v2` (independently recomputed at
zero mismatches over 99 runs). Wording follows the frozen protocol §10: no "outperforms",
"validated", "generalizes", "state of the art", or policy-winner claim; measured / proved /
implemented / proposed are tagged and kept distinct.

## Files

- `report.tex` — the report.
- `figures/`
  - `fig-flow.tex`, `fig-controller.tex`, `fig-concept.tex` — hand-authored TikZ diagrams
    (data flow, controller state machine, admission-regime schematic). The report does not
    include `fig-controller.tex`: at page width its labels printed at about 4 pt, so Table 2
    (the four actions) plus Listing 1 carry the controller instead. The file is kept as the
    diagram source for a future, larger layout.
  - `fig-ratchet.tex`, `fig-scorer-limit.tex`, `fig-synthetic-map.tex`, `fig-tradeoff.tex` —
    **generated** data figures (see `generate/`); never hand-edit.
  - `figures-manifest.json` — provenance (inputs + SHA-256, caption, labels) for the generated figures.
- `tables/`
  - `tab-skab.tex` — 11-arm SKAB baseline (report Table 6, `tab:baseline`).
  - `tab-synthetic.tex` — full 8-arm synthetic family; `tab-synthetic-compact.tex` — the
    5-arm view actually shown (Table 7), for the page budget. Both are generated and carry
    identical values under the same summary-equals test.
  - `tab-ablation.tex` — guard-component ablation map (Table 8).
  - `tables-manifest.json` — provenance for the generated tables.
- `references.bib` — bibliography; only allowlisted-platform papers are primary citations;
  SKAB is a dataset; Hu is in press.
- `build.sh` — pdflatex → bibtex → pdflatex ×2 into `build/`.
- `generate/` — reproducible generators (see below).
- `.gitignore` — excludes `build/` and `nsut-logo.png`.

## Build

```sh
export PATH=/Library/TeX/texbin:$PATH   # TeX Live 2026 basic
sh build.sh                              # -> build/report.pdf
```

The install is TeX Live *basic*; the report uses only packages present in it (no siunitx,
cleveref, multirow, makecell, titlesec, standalone, pgfplots, tcolorbox, libertine).

### The NSUT logo

The logo's reuse rights are unresolved and this repo is public, so the logo is **not
committed** (`.gitignore` excludes `nsut-logo.png`). `build.sh` copies it in from
`report-work/visuals/nsut-page1-000.png` when that file is present beside the checkout, and
`report.tex` uses `\IfFileExists`, so the source still compiles without it (the cover then
shows a plain text "NSUT logo" mark). The final submitted PDF includes the logo.

## Reproducing the numbers from the repo alone

The figures and tables are generated, and the generators live in `generate/`:

```sh
# study root defaults to results/20260929-policy-study-v2 (regenerate it if absent:
#   .venv/bin/python run_policy_study.py --output-root results/20260929-policy-study-v2)
python3 generate/make_figures.py     # -> figures/*.tex + figures-manifest.json
python3 generate/make_tables.py      # -> tables/*.tex  + tables-manifest.json
python3 generate/test_generators.py  # ratchet/E3 checks, cells==summary.json, determinism, budget
```

`generate/` is a behaviour-identical promotion of `report-work/{figures,tables}` with the
study root resolved relative to the research repo and outputs written into `figures/` and
`tables/`. When the review pack `report-work/evidence/recompute-output-policy-study.json` is
present beside the checkout, `test_generators.py` also cross-checks every value against it
(99 runs, 0 mismatches); when it is absent the cross-check is skipped and the tests still run
against the study's own `summary.json`. Never hand-edit a generated fragment — change the
generator and re-run.

## QA (as built)

- 15 pages (A4, 11pt); cover + contents through references.
- 0 undefined references / citations; 0 overfull boxes > 1pt; all fonts embedded.
- No `??` / TODO / TBD / PENDING / placeholder in the text.
- One wide table (`tab-skab`, 12 columns × 22 rows) is set at `\scriptsize`; every other
  table is at `\footnotesize` or larger and the body text is 11pt.
