# Search log

All entries dated **2026-09-29 (Asia/Kolkata)**. This log records the **fresh** searches
and verifications run in the P2-finish pass, on top of the prior proceedings/publisher
search logs already in `proceedings-notes.md` and `publisher-notes.md` (not repeated here).
Cutoff for "published" status: **29 September 2026**.

**Boundary statement.** This is a **practical, bounded** search targeted at defending one
specific direction (a four-action decision-time policy on a common score trace), not a
universal or exhaustive survey. A blocked/paywalled page is recorded as an access result,
never as evidence a paper lacks a feature. Primary evidence is only from the seven
allowlisted platforms; arXiv / SSRN / author pages / Semantic Scholar / vldb.org are
discovery or version checks.

## Verifications of already-listed records (metadata / access)

| Platform | Action / query | Result | Kept? |
|---|---|---|---|
| ACM DL | fetch `dl.acm.org/doi/10.1145/3576841.3585931` (CODiT conf.) | HTTP 403; metadata via Crossref | already listed; corrected "Sethi" -> Kaur et al., pp. 120-131, 8 authors |
| ACM DL | fetch `dl.acm.org/doi/10.1145/3648005` (CODiT journal) | HTTP 403; Crossref: Kaur/Yang/Sokolsky/Lee, TCPS 8(4), pp. 1-27, 2024-10 | already listed; page range corrected (pp. 1-27, not "Article 46"); read-scope downgraded to abstract-only |
| Crossref (metadata check) | `api.crossref.org/works/{10.1145/3648005, 10.1145/3576841.3585931, 10.1016/j.knosys.2026.115380, 10.1016/j.knosys.2026.116530, 10.1016/j.eswa.2026.134305, 10.1016/j.knosys.2026.116716}` | authors/venue/pages/dates confirmed | metadata only |
| doi.org (redirect check) | resolve DDADE/ADAPTS/Hu/Altay DOIs | 302 -> linkinghub.elsevier.com PIIs: DDADE=`S0950705126001231`, ADAPTS=`S0950705126012566`, Hu=`S0957417426032112`, Altay=`S0950705126014425` | DDADE official URL fixed from non-allowlisted `doi.org` to verified ScienceDirect PII |
| ScienceDirect | fetch DDADE PII `S0950705126001231` | HTTP 400 (runtime block) — not evidence of absence | access result only |
| PMLR | fetch `proceedings.mlr.press/v267/shah25c.html` + PDF | **HTTP 200** (previously blocked); official BibTeX + pp. 54167-54185 verified | SEAD upgraded to official full-text; PDF cached |
| NeurIPS | fetch `.../dc48c738...-Abstract-Conference.html` (Perini & Davis) | open; abstract + DOI 10.52202/075280-3052 verified | already listed |

## Fresh discovery searches (deepen coverage)

| Platform | Exact query | Filters | Hits screened | Kept |
|---|---|---|---|---|
| Web (allowlist filter) | `selective prediction abstention streaming time series anomaly detection defer 2024 2025 proceedings` | 2023-2026 | ~10 (all arXiv/blog) | none closer than Sun/Perini; discovery-only |
| Web | `alert budget anomaly detection operational workload episodes evaluation time series 2024 2025` | 2023-2026 | ~10 (arXiv/researcher.life/MDPI/blogs) | none allowlisted; "Alarm-Budgeted Event-Level Eval (SWaT/WADI)" and "Open Challenges in TSAD" noted as arXiv discovery only |
| Web -> PMLR/NeurIPS | `conformal anomaly detection online threshold proceedings.mlr.press OR neurips.cc 2024 2025` | allowlisted only | ~12 | **KEPT: Hennhöfer et al., nonconform, PMLR 329:613-632 (2026)** — added |
| Web -> Springer/ACM | `VUS volume under surface TSB-UAD PVLDB Paparrizos dl.acm.org anomaly detection accuracy` | allowlisted only | ~11 | **KEPT: Boniol et al., VUS, The VLDB Journal 34:32 (2025)** (link.springer.com) — added; PVLDB v15 version is on vldb.org (not allowlisted) so not used as primary |
| PMLR | verify `proceedings.mlr.press/v329/hennhofer26a.html` | — | 1 | citation + abstract verified |
| SpringerLink | verify `link.springer.com/article/10.1007/s00778-025-00907-x` (VUS VLDBJ) | — | 1 | VoR 2025-03-27, vol. 34 art. 32, 10 authors verified |

## Backward/forward citation follow-up (closest three)

- From **Sun 2024** / **Perini & Davis 2023** / **SEAD 2025**: the FITNESS (Sankararaman 2022), online-FDR (Rebjock 2021) and D3M (Nguyen 2025) neighbours were already captured in `proceedings-rows.csv`; no *closer* allowlisted policy paper surfaced than the eight in `closest-work.md`.
- The VUS VLDBJ reference list surfaced the Tatbul 2018 and TSB-UAD lineage already held; nothing new closer to our policy layer.

## Saturation (bounded)

Repeated allowlisted queries on abstention/defer, alert-budget/workload, conformal online
thresholding, and VUS/benchmark evaluation returned either records already in the ledger or
non-allowlisted discovery hits. Two genuinely new allowlisted papers were added (nonconform;
VUS VLDBJ). No single allowlisted record was found that holds one score trace fixed and
competes alert/hold/defer/recalibrate **policies** on it with coverage + workload reporting.
**This is saturation of the targeted query families on the allowlisted platforms, not a
universal absence claim.**

## Tooling note
No browser-automation tool was available for this search. All work used web search and
page fetches, shell
(curl for DOI redirects + Crossref metadata + SHA-256 + pdftotext/pdflatex/bibtex from
`/Library/TeX/texbin`), and file tools.
