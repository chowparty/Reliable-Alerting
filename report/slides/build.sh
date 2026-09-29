#!/usr/bin/env bash
# build.sh -- one slide source (deck.md), two outputs.
#   deck.pdf  : pandoc -t beamer (16:9, custom theme in beamer-preamble.tex)
#   deck.pptx : pandoc -t pptx   (editable; colours and fonts from reference.pptx)
# Figures are rendered first from the report's TikZ sources (make_figure_pngs.sh).
# NO_LOGO=1 leaves the NSUT logo off the title slide (public repository copy).
#
# Hang guard: this macOS host has no `timeout`; every render runs under perl alarm.
set -euo pipefail

cd "$(dirname "$0")"
PATH="/Library/TeX/texbin:$PATH"; export PATH
guard() { perl -e 'alarm shift; exec @ARGV' 180 "$@"; }

bash make_figure_pngs.sh >/dev/null

logo=()
if [ -f figures/nsut-logo.png ]; then
  logo=(-V titlegraphic=figures/nsut-logo.png -V titlegraphicoptions=height=13mm)
fi

guard pandoc deck.md \
  -t beamer --slide-level=1 \
  -V aspectratio=169 -V fontsize=10pt \
  -H beamer-preamble.tex \
  --lua-filter=tags.lua \
  "${logo[@]}" \
  --pdf-engine=pdflatex \
  -o deck.pdf

guard pandoc deck.md \
  -t pptx --slide-level=1 \
  --reference-doc=reference.pptx \
  --lua-filter=tags.lua \
  -o deck.pptx

echo "built: deck.pdf deck.pptx"
