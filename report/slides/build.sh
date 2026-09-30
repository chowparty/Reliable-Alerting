#!/usr/bin/env bash
# build.sh -- one slide source (deck.md), two outputs.
#   deck.pdf  : pandoc -t beamer (16:9, custom theme in beamer-preamble.tex), then
#               pdflatex twice; the LaTeX log is kept in .work/deck.log so overfull
#               (text off the slide) warnings can be checked
#   deck.pptx : pandoc -t pptx   (editable; colours and fonts from reference.pptx)
# Figures are rendered first from the TikZ sources (make_figure_pngs.sh).
# NO_LOGO=1 leaves the NSUT logo off the title slide.
#
# Hang guard: macOS has no `timeout`; every render runs under a perl alarm.
# Works with the bash 3.2 that ships with macOS as well as newer versions.
set -euo pipefail

cd "$(dirname "$0")"
PATH="/Library/TeX/texbin:$PATH"; export PATH
# A fixed timestamp makes the PDF and PPTX byte-identical when nothing changed.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1790706600}"   # 2026-09-30 00:00 IST
guard() { perl -e 'alarm shift; exec @ARGV' 180 "$@"; }

bash make_figure_pngs.sh >/dev/null

logo=()
if [ -f figures/nsut-logo.png ]; then
  logo=(-V titlegraphic=figures/nsut-logo.png -V titlegraphicoptions=height=13mm)
fi

mkdir -p .work
guard pandoc deck.md \
  -s -t beamer --slide-level=1 \
  -V aspectratio=169 -V fontsize=10pt \
  -H beamer-preamble.tex \
  --lua-filter=tags.lua \
  ${logo[@]+"${logo[@]}"} \
  -o .work/deck.tex

# Two passes, so the "n / total" slide numbers in the footer resolve.
for pass in 1 2; do
  guard pdflatex -interaction=nonstopmode -halt-on-error \
    -output-directory=.work .work/deck.tex >/dev/null \
    || { echo "pdflatex failed; see .work/deck.log" >&2; exit 1; }
done
cp .work/deck.pdf deck.pdf

guard pandoc deck.md \
  -t pptx --slide-level=1 \
  --reference-doc=reference.pptx \
  --lua-filter=tags.lua \
  -o deck.pptx

if [ -f figures/nsut-logo.png ]; then
  guard python3 add_title_logo.py deck.pptx figures/nsut-logo.png
fi

echo "built: deck.pdf deck.pptx (LaTeX log: .work/deck.log)"
