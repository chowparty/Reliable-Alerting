# Phase-I report — canonical LaTeX source

*When Should an Alert Threshold Learn? Admission-Separated Recalibration as a Decision-Time
Action for Time-Series Anomaly Alerting* — B.Tech Project-I (Phase-I) mid-semester report.

This is the tracked, canonical source. It builds a 15-page A4 / 11pt PDF whose numbers all
resolve to the saved study `results/20260929-policy-study-v2` (independently recomputed at
zero mismatches over 99 runs). Wording follows the frozen protocol §10: no "outperforms",
"validated", "generalizes", "state of the art", or policy-winner claim; measured / proved /
implemented / proposed are tagged and kept distinct.

## Files

- `report.tex` — the master file: loads `preamble.tex`, then `\input`s each section and
  the references. It holds no prose of its own.
- `preamble.tex` — packages, page layout, the claim tags (`\Sproved`, `\Smeasured`,
  `\Simplemented`, `\Sproposed`), the page-2 box and the `\aifigure` placeholder macro.
- `sections/` — one file per report section, in reading order: `00-cover`, `01-front`
  (abstract, contents and the seven claims C1–C7), `02-introduction`, `03-motivation`,
  `04-literature`, `05-problem`, `06-methodology`, `07-platform`, `08-results`,
  `09-limitations`, `10-conclusion`. Results subsections open with the claim they support.
- `figures/`
  - `fig-flow.tex` (Figure 1, pipeline and data flow), `fig-concept.tex` (Figure 2,
    admission regimes) and `fig-controller.tex` — hand-authored TikZ diagrams. The report
    does not include `fig-controller.tex`: at page width its labels printed at about 4 pt,
    so Table 3 (the four actions) plus Listing 1 carry the controller instead. The file is
    kept as the diagram source for a future, larger layout.
  - `fig-ratchet.tex`, `fig-scorer-limit.tex`, `fig-synthetic-map.tex`, `fig-tradeoff.tex` —
    **generated** data figures (Figures 3–6; see `generate/`); never hand-edit.
  - `f_replay_pallte.tex` — source palette embedded in generated Figures 4 and 5.
  - `figures-manifest.json` — provenance (inputs + SHA-256, caption, labels) for the generated figures.
  - `ai/` — prompts for optional AI-generated versions of the two schematics (see
    [`figures/ai/README.md`](figures/ai/README.md)). Data figures are never replaced.
- `tables/`
  - `tab-skab.tex` — 11-arm SKAB baseline (report Table 7, `tab:baseline`).
  - `tab-synthetic.tex` — full 8-arm synthetic family; `tab-synthetic-compact.tex` — the
    5-arm view actually shown (Table 8), for the page budget. Both are generated and carry
    identical values under the same summary-equals test.
  - `tab-ablation.tex` — guard-component ablation map (Table 9).
  - `tables-manifest.json` — provenance for the generated tables.
- `references.bib` — bibliography; only allowlisted-platform papers are primary citations;
  SKAB is a dataset; Hu is in press.
- `build.sh` — pdflatex → bibtex → pdflatex ×2 into `build/`.
- `generate/` — reproducible generators (see below).
- `.gitignore` — excludes generated build output.

## Build

```sh
sh build.sh                              # -> build/report.pdf
NO_LOGO=1 sh build.sh                    # optional cover without the logo
AI_PLACEHOLDERS=1 sh build.sh            # draft: prints each schematic's image prompt
```

`build.sh` adds `/Library/TeX/texbin` (where MacTeX and BasicTeX install) to `PATH`;
on Linux `pdflatex` is already on it. To rebuild the report and the slides together,
run every check and refresh `../../deliverables/`, use
`bash scripts/build_deliverables.sh` from the repository root (see
[`../README.md`](../README.md)).

The reviewed build with the logo is committed as `../../deliverables/Phase-I-Report.pdf`.

The report and slides build on BasicTeX (TeX Live's small scheme, which includes the
LaTeX-recommended collection) plus `enumitem`; that is the installation they were
built and checked on. They use no siunitx, cleveref, multirow, makecell, titlesec,
standalone, pgfplots, tcolorbox or libertine.

### The NSUT logo

The team-approved `nsut-logo.png` is stored in this folder and included by default.
`report.tex` uses `\IfFileExists`, so a source-only copy still compiles without it
(the cover then shows a plain text "NSUT logo" mark).

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

- 15 pages (A4, 11pt); cover + page-2 claims through references.
- 0 undefined references / citations; 0 overfull boxes; all fonts embedded.
- No `??` / TODO / TBD / PENDING in the text. The `AI_PLACEHOLDERS=1` draft build is
  longer (17 pages) because it prints the prompts; the submitted build never does.
- One wide table (`tab-skab`, 12 columns × 22 rows) is set at `\scriptsize`; every other
  table is at `\footnotesize` or larger and the body text is 11pt.
