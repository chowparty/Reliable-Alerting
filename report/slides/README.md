# Slide deck

One source, `deck.md`, builds two decks: `deck.pdf` (beamer, for presenting) and
`deck.pptx` (PowerPoint, editable). The deck has 15 slides: a title, two foundation
slides for listeners new to the area (how alerting works; why a threshold has to learn,
and from what), then the direction, its defence, the evidence and the next experiment.
Each content slide carries its speaker notes in a `::: notes` block, which the
PowerPoint file keeps as presenter notes (about nine minutes in all).

To change a slide and re-render, follow [`../README.md`](../README.md); it has the
writing rules for `deck.md` and the one command that builds and checks everything.

## Build

```sh
bash build.sh            # renders figures, then deck.pdf and deck.pptx
python3 check_numbers.py # every number on a slide must appear in the report
NO_LOGO=1 bash build.sh  # title slide without the NSUT logo (public copy)
```

Needs pandoc 3, pdflatex, Ghostscript and poppler (`pdftoppm`). `build.sh` calls
`make_figure_pngs.sh`, which renders the TikZ figures into `figures/`: the report's
diagrams and data figures from `../submission/figures/`, and the slide-only diagrams
from `diagrams/`. A reviewed AI image saved as `ai/<name>.png` beside a diagram's
source replaces its TikZ render, in the slides as in the report. The PDF is built in
`.work/`, and `.work/deck.log` keeps the LaTeX log: an `Overfull` line there means
something runs off a slide.

## Files

- `deck.md`: slides and speaker notes. Slide titles state each slide's takeaway.
- `diagrams/`: slide-only schematics, `fig-basics.tex` (slide 2, how alerting works)
  and `fig-dilemma.tex` (slide 3, three ways a threshold can learn), with their
  AI-image prompts in `diagrams/ai/`. Both are marked as schematics, not data.
- `beamer-preamble.tex`: the PDF theme (navy and one accent, quiet footer, evidence tags).
- `reference.pptx`: the PowerPoint theme (same palette, left-aligned bold titles).
- `tags.lua`: renders `[MEASURED]{.tag}` as a shaded chip in the PDF and as bold
  `[MEASURED]` in PowerPoint.
- `check_numbers.py`: the number check against `../submission/sections/` and the
  generated tables.

Writing rule for `deck.md`: keep text before a table or image on the same slide.
Pandoc's PowerPoint writer starts a new slide for text placed after one.
