# Changing the report or the slides

This folder holds everything needed to edit the Phase-I report and the viva deck and
to re-render them: the sources, the figure and table generators, the build scripts and
the checks. One command rebuilds both documents, checks them and refreshes the copies
in [`../deliverables/`](../deliverables/).

```text
 report/submission/sections/*.tex ─┐
 report/submission/figures/*.tex  ─┼─> report/submission/build.sh ─> report.pdf ─┐
 report/submission/tables/*.tex   ─┘                                              │
                                                                                  ├─> checks ─> deliverables/
 report/slides/deck.md ─┐                                                         │
 TikZ figures (shared) ─┴────────> report/slides/build.sh ─> deck.pdf, deck.pptx ─┘

 results/<study run> ──(--regenerate)──> submission/generate/*.py ──> data figures and tables
```

## Setup, once

You need Python 3 (standard library only), a TeX Live 2026 or newer installation,
pandoc 3, Ghostscript and poppler.

- **macOS:** `brew install pandoc ghostscript poppler`, plus MacTeX
  (`brew install --cask mactex-no-gui`), which contains every LaTeX package used.
  BasicTeX (`brew install --cask basictex`) is much smaller and is what the documents
  were built on; it needs one extra package, `sudo tlmgr install enumitem`. If a build
  ever reports `File 'x.sty' not found`, install `x` the same way.
- **Ubuntu or Debian:** `sudo apt install texlive-latex-recommended texlive-latex-extra
  texlive-fonts-recommended texlive-pictures pandoc ghostscript poppler-utils`. Check
  `pandoc --version`: if it is older than 3, install the current `.deb` from
  [pandoc's releases](https://github.com/jgm/pandoc/releases).
- **Windows:** use WSL (Ubuntu) and follow the Ubuntu line. The scripts need `bash`
  and `perl`, which WSL provides.

The scripts work with the bash 3.2 that ships with macOS and with newer versions.

## Where to make a change

| I want to… | Edit | Notes |
|---|---|---|
| Fix wording in the report | `submission/sections/NN-*.tex` | One file per section, in reading order |
| Change the title, team or supervisor | `submission/sections/00-cover.tex` and the header of `slides/deck.md` | Keep the two identical |
| Change a claim C1–C7 | `submission/sections/01-front.tex` and the "Our direction" slide in `slides/deck.md` | The report and the deck must state the same claims with the same tags |
| Add or fix a reference | `submission/references.bib`, then `\citep{key}` in the text | Primary citations only from the seven platforms in [`../AGENTS.md`](../AGENTS.md); record the paper in `literature/ledger.csv` |
| Change a number, a table or a data figure | Never the `.tex` fragment: change the study or `submission/generate/*.py`, then rebuild with `--regenerate` | The fragments are generated from `results/` and tested cell by cell |
| Redraw a diagram | `submission/figures/fig-flow.tex` or `fig-concept.tex` (report and slides), or `slides/diagrams/*.tex` (slides only) | Hand-drawn TikZ on a millimetre grid; see the comment at the top of each file |
| Change the Figure 4–5 colours | `submission/figures/f_replay_pallte.tex`, then rebuild with `--regenerate` | The generator embeds this palette in the report figures and slide PNGs |
| Use an AI-generated image for a diagram | Save the reviewed PNG as `ai/<name>.png` beside the diagram's source | Prompts: [`submission/figures/ai/`](submission/figures/ai/README.md) and `slides/diagrams/ai/`. Data figures are never replaced |
| Edit a slide or its speaker notes | `slides/deck.md` | Rules below |
| Change the look of the slides | `slides/beamer-preamble.tex` (PDF) and `slides/reference.pptx` (PowerPoint) | Keep the two palettes matched |

### Writing rules for `deck.md`

- Each `#` heading starts one slide, and the heading is the slide's takeaway.
- Speaker notes go in a `::: notes` block at the end of the slide.
- Put text **before** a table or an image. PowerPoint starts a new slide for text placed
  after one, and the check then fails because the PDF and PPTX counts differ.
- Evidence tags are written `[MEASURED]{.tag}` (also PROVED, IMPLEMENTED, PROPOSED).
- Size images in percent (`{width=86%}`). Pandoc ignores `\textheight`-style sizes.
- Every number on a slide must already appear in the report. The check fails
  otherwise, so change the report first.

## Rebuild and check

From the repository root:

```sh
bash scripts/build_deliverables.sh --check   # build both and run every check
bash scripts/build_deliverables.sh           # the same, then refresh deliverables/
```

A run takes under a minute. It stops at the first failed check with a `FAIL:` line
saying what is wrong and where. It checks:

- **Report:** 10–15 pages (the Guidelines), no undefined references or citations, no
  line running past the margin, no `??`/TODO/TBD/PENDING, all fonts embedded.
- **Slides:** 10–15 slides, nothing running off a slide, the PDF and PPTX have the same
  slides, every content slide has speaker notes, and every number traces to the report
  (`slides/check_numbers.py`).
- **Generated figures and tables:** every cell equals the saved study results. This
  runs when `results/20260929-policy-study-v2` is present; text-only edits do not need it.

The checks cannot see two labels colliding inside a figure, so look at the previews
before committing. They are one PNG per page in `submission/build/preview/` and
`slides/.work/preview/`. Build dates are fixed, so rebuilding an unchanged source
reproduces the committed files byte for byte, and `git status` shows exactly which
deliverables your change touched.

### The NSUT logo

The team-approved logo is stored at `submission/nsut-logo.png`. The standard build
includes it on the report cover and the PDF and PowerPoint title slides. Set
`NO_LOGO=1` only when a logo-free local render is needed.

## Worked example: fix a sentence on a slide and publish it

```sh
# 1. edit report/slides/deck.md
bash scripts/build_deliverables.sh --check           # 2. build and check
open report/slides/.work/preview/slide-06.png        # 3. look at the slide (xdg-open on Linux)
bash scripts/build_deliverables.sh                   # 4. refresh deliverables/
git add report/slides/deck.md deliverables/          # 5. stage exact paths only
git commit -m "docs(slides): clarify the closest-work slide" \
           -m "Rewords the lead sentence so the bounded-search caveat reads first."
git push origin <your-branch>
```

Commit subjects follow Conventional Commits (`docs(report): …`, `fix(slides): …`) with a
plain-language body, and carry no AI or co-author trailers (see
[`../AGENTS.md`](../AGENTS.md)).

## Rules that keep the work honest

- Do not hand-edit generated files: `submission/figures/fig-ratchet.tex`,
  `fig-scorer-limit.tex`, `fig-synthetic-map.tex`, `fig-tradeoff.tex`, everything in
  `submission/tables/`, both `*-manifest.json`, and anything under `build/` or `.work/`.
- Keep measured, proved, implemented and proposed statements tagged and distinct. Do not
  write "outperforms", "validated", "generalizes" or "state of the art"; no policy is
  claimed to win.
- Never open `SKAB/other/21.csv`. It is named reserved in [`../manifest.md`](../manifest.md).
- A slide may simplify the report, but it may not say more than the report does.
