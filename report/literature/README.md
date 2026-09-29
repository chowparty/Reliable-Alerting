# report-work/literature — reading ledger and closest-work defense

Phase-I literature review for our research direction: a **decision-time action policy
(alert / hold / defer / recalibrate) on a common frozen anomaly-score trace**, evaluated
on SKAB dev streams with chronological, label-free splits and workload/coverage reporting.

All primary citations come from the seven allowlisted platforms (IEEE Xplore, ACM DL,
SpringerLink, ScienceDirect, NeurIPS Proceedings, PMLR, ACL Anthology). arXiv / SSRN /
author pages / Semantic Scholar / vldb.org are discovery or version checks only. A
blocked page is never treated as evidence a paper lacks a feature.

## Files

| File | What it is |
|---|---|
| `closest-work.md` | **The most important file.** Adversarial "isn't this just X?" matrix over the 8 closest threats (DDADE, ADAPTS, CDDIA, Sun 2024, Perini & Davis, SEAD, Dynamic-XY, Hu) plus neighbours; per-component occupation table; synthesis; a reusable honest-scope sentence for the viva. |
| `ledger.csv` | **Generated.** Merged, de-duplicated reading ledger (34 records). Do not hand-edit — regenerate from the source rows. |
| `assemble_ledger.py` | Merges the three source-row CSVs into `ledger.csv`, de-duplicating on DOI/venue id and enforcing allowlisted official hosts. |
| `validate_ledger.py` | **stdlib** validator: (1) CSV parses + header, (2) DOI uniqueness, (3) every official URL allowlisted, (4) declared local-PDF SHA-256 well-formed and matches a file on disk. |
| `base-rows.csv` / `base-notes.md` | 11 seed papers (6 with local full-text PDFs + SHA-256), with reading notes. |
| `proceedings-rows.csv` / `proceedings-notes.md` | NeurIPS / PMLR / ACL slice (now incl. `hennhofer26a`). |
| `publisher-rows.csv` / `publisher-notes.md` | IEEE / ACM / Springer / Elsevier slice (now incl. `springer-vus-2025`). |
| `references.bib` | Every paper the report may cite. Allowlisted papers only as `@article`/`@inproceedings`; SKAB as `@misc`. Fields verified against official records (2026-09-29). |
| `search-log.md` | Dated (2026-09-29) log of this pass's searches/verifications + bounded saturation record. |
| `library-request.md` | Genuinely blocked high-relevance full texts, why they matter, and routes tried. |
| `pdf-cache-index.md` | Every lawful local PDF: path, source URL, version, licence, SHA-256, pages. |
| `pdf-cache/` | Lawfully obtained PDFs downloaded by this task (currently `shah25c-sead.pdf`). |

## Regenerate / validate

```sh
cd report-work/literature
python3 assemble_ledger.py      # -> writes ledger.csv (prints "Wrote N unique records")
python3 validate_ledger.py      # exit 0 = all hard checks pass
```

Validate the bib parses (pdflatex + bibtex; on macOS TeX Live they live in
`/Library/TeX/texbin`, which may need adding to PATH). Do it in a scratch dir, not here:

```sh
export PATH="/Library/TeX/texbin:$PATH"     # if the tools are not already on PATH
cd "$(mktemp -d)"                             # any scratch dir
cp <lit>/references.bib .
printf '\\documentclass{article}\\begin{document}\n' > bibstub.tex
# \nocite{*} pulls in every key:
printf '\\nocite{*}\\bibliographystyle{plain}\\bibliography{references}\\end{document}\n' >> bibstub.tex
pdflatex -interaction=nonstopmode bibstub.tex
bibtex bibstub                                # expect no error messages
pdflatex -interaction=nonstopmode bibstub.tex && pdflatex -interaction=nonstopmode bibstub.tex
```

## Editorial conventions
- `read_scope` is `abstract-only` when only the official abstract/metadata (or a non-official preview) was seen; it is a full/targeted read only when an official or lawfully-cached PDF section was actually read.
- Non-allowlisted URLs must never appear in `official_record_url` (check 3 enforces this).
- Version/date conflicts (Navarro Hydra/Orthus; Hu in-press; Altay after-cutoff; CODiT journal page range) are recorded in the row, never silently resolved.
- New lawful PDFs go in `pdf-cache/` and get a row in `pdf-cache-index.md`; paywalls are never bypassed.

## Last run (2026-09-29)
`assemble_ledger.py` -> "Wrote 34 unique records" (exit 0).
`validate_ledger.py` -> checks 1-4 OK, "All hard checks passed." (exit 0).
`references.bib` -> pdflatex + bibtex: bibtex exit 0, 0 errors/warnings, 29 bibitems, no undefined citations.
