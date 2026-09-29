#!/usr/bin/env bash
# make_figure_pngs.sh
# Compile each TikZ fragment from the report standalone, one fragment per page,
# then rasterize at 220 dpi into figures/. Both decks embed these PNGs.
#
# Page sizing: the spec's \setbox0\hbox{\input{...}} + \pdfpagewidth=\wd0 primitive
# under-measures fragments whose TikZ nodes are placed to the right of / below the
# picture origin (fig-flow's Sun arm overflows the measured hbox and clips). So we
# ship each fragment onto a large fixed page, then compute the TRUE ink bounding box
# with ghostscript's bbox device and set it as the PDF CropBox, giving a tight page
# sized to exactly one fragment with a thin uniform margin. pdftoppm then rasterizes
# that crop.
#
# Hang guard: this macOS host has no `timeout`. Every latex / gs / pdftoppm call is
# wrapped in `perl -e 'alarm shift; exec @ARGV' 180 ...`.
set -euo pipefail

SLIDES="$(cd "$(dirname "$0")" && pwd)"
FIGSRC="$SLIDES/../submission/figures"
OUT="$SLIDES/figures"
WORK="$SLIDES/.work/figbuild"
PATH="/Library/TeX/texbin:$PATH"; export PATH

# The report's diagrams and data figures, plus the slide-only diagrams in diagrams/.
# Each entry is "<source folder>:<figure name>".
DIAGRAMS="$SLIDES/diagrams"
FIGS=("$FIGSRC:fig-flow" "$FIGSRC:fig-concept" "$FIGSRC:fig-ratchet"
      "$FIGSRC:fig-scorer-limit" "$FIGSRC:fig-synthetic-map" "$FIGSRC:fig-tradeoff"
      "$DIAGRAMS:fig-basics" "$DIAGRAMS:fig-dilemma")

guard() { perl -e 'alarm shift; exec @ARGV' 180 "$@"; }

rm -rf "$WORK"; mkdir -p "$WORK" "$OUT"

for entry in "${FIGS[@]}"; do
  dir="${entry%:*}"; fig="${entry##*:}"
  # A reviewed AI image for a schematic (see ../submission/figures/ai/README.md)
  # replaces the TikZ render, exactly as it does in the report.
  if [ -f "$dir/ai/$fig.png" ]; then
    cp "$dir/ai/$fig.png" "$OUT/$fig.png"; echo ">> $fig: using AI image"; continue
  fi
  src="$dir/$fig.tex"
  [ -f "$src" ] || { echo "MISSING: $src" >&2; exit 1; }
  wrap="$WORK/$fig.tex"

  # Ship the fragment onto a large page (no measurement trick, so nothing clips).
  cat > "$wrap" <<TEXEOF
\\documentclass[11pt]{article}
\\usepackage[T1]{fontenc}
\\usepackage{lmodern}
\\usepackage{amsmath,amssymb}
\\usepackage{xcolor}
\\usepackage{tikz}
\\usetikzlibrary{arrows.meta, positioning, calc, shapes.geometric, arrows}
\\providecommand{\\providecolor}[3]{\\definecolor{#1}{#2}{#3}}
\\pdfpagewidth=1600pt \\pdfpageheight=1200pt
\\usepackage[left=20pt,top=20pt,paperwidth=1600pt,paperheight=1200pt]{geometry}
\\pagestyle{empty}
\\setlength{\\parindent}{0pt}
\\begin{document}
\\noindent\\input{$src}
\\end{document}
TEXEOF

  echo ">> compiling $fig"
  ( cd "$WORK" && guard pdflatex -interaction=nonstopmode -halt-on-error \
      -output-directory "$WORK" "$wrap" >/dev/null )

  # True ink bounding box (points), from ghostscript.
  echo ">> cropping $fig to bounding box"
  bbox=$(guard gs -q -dBATCH -dNOPAUSE -sDEVICE=bbox "$WORK/$fig.pdf" 2>&1 \
           | grep '%%BoundingBox:' | head -1)
  read -r _ x0 y0 x1 y1 <<<"$bbox"
  m=6   # uniform margin in pt
  cx0=$((x0 - m)); cy0=$((y0 - m)); cx1=$((x1 + m)); cy1=$((y1 + m))
  # Re-emit a PDF whose page is exactly the padded bounding box.
  guard gs -q -o "$WORK/$fig-crop.pdf" -sDEVICE=pdfwrite \
      -dDEVICEWIDTHPOINTS=$((cx1 - cx0)) -dDEVICEHEIGHTPOINTS=$((cy1 - cy0)) \
      -dFIXEDMEDIA \
      -c "<</PageOffset [$(( -cx0 )) $(( -cy0 ))]>> setpagedevice" \
      -f "$WORK/$fig.pdf"

  echo ">> rasterizing $fig at 220 dpi"
  guard pdftoppm -r 220 -png -singlefile "$WORK/$fig-crop.pdf" "$OUT/$fig"
done

# Cover logo: copied from the report folder when present, unless NO_LOGO=1.
rm -f "$OUT/nsut-logo.png"
if [ "${NO_LOGO:-0}" != 1 ] && [ -f "$FIGSRC/../nsut-logo.png" ]; then
  cp "$FIGSRC/../nsut-logo.png" "$OUT/nsut-logo.png"
fi

echo "== figure PNGs written to $OUT =="
ls -la "$OUT"/*.png
