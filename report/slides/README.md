# Slide deck

One source, `deck.md`, builds two decks: `deck.pdf` (beamer, for presenting) and
`deck.pptx` (PowerPoint, editable). Each content slide carries 45–60 seconds of speaker
notes in its `::: notes` block, which the PowerPoint file keeps as presenter notes.

## Build

```sh
bash build.sh            # renders figures, then deck.pdf and deck.pptx
python3 check_numbers.py # every number on a slide must appear in the report
NO_LOGO=1 bash build.sh  # title slide without the NSUT logo (public copy)
```

Needs pandoc 3, pdflatex (TeX Live basic), Ghostscript and poppler (`pdftoppm`).
`build.sh` calls `make_figure_pngs.sh`, which renders the report's TikZ figures from
`../submission/figures/` into `figures/`. A reviewed AI image in
`../submission/figures/ai/` replaces its TikZ figure here as it does in the report.

## Files

- `deck.md`: slides and speaker notes. Slide titles state each slide's takeaway.
- `beamer-preamble.tex`: the PDF theme (navy and one accent, quiet footer, evidence tags).
- `reference.pptx`: the PowerPoint theme (same palette, left-aligned bold titles).
- `tags.lua`: renders `[MEASURED]{.tag}` as a shaded chip in the PDF and as bold
  `[MEASURED]` in PowerPoint.
- `check_numbers.py`: the number check against `../submission/sections/` and the
  generated tables.

Writing rule for `deck.md`: keep text before a table or image on the same slide.
Pandoc's PowerPoint writer starts a new slide for text placed after one.
