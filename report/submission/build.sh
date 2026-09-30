#!/bin/sh
# Build report.tex into build/ with pdflatex -> bibtex -> pdflatex x2.
# Needs pdflatex and bibtex on PATH (macOS MacTeX/BasicTeX installs them under
# /Library/TeX/texbin, which is added below; on Linux they are already on PATH).
#
# The NSUT logo is stored beside report.tex and included in the cover by default.
# build/ is git-ignored; generated files are never hand-edited.
set -eu

sub_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$sub_dir"
export PATH=/Library/TeX/texbin:$PATH
# A fixed timestamp makes the PDF byte-identical when nothing changed.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1790706600}"   # 2026-09-30 00:00 IST
mkdir -p build

# Generated build files live under build/ and are never hand-edited.
rm -f build/report.aux build/report.bbl build/report.blg \
      build/report.log build/report.out build/report.pdf build/report.toc

# Build switches (environment variables, both off by default):
#   NO_LOGO=1          cover shows a plain "NSUT logo" mark
#   AI_PLACEHOLDERS=1  print each schematic's AI-image generation prompt under it
flags=""
[ "${NO_LOGO:-0}" = 1 ] && flags="$flags\\def\\ReportNoLogo{}"
[ "${AI_PLACEHOLDERS:-0}" = 1 ] && flags="$flags\\def\\ReportAIPrompts{}"

# bibtex needs the .bib and the figure/table fragments reachable from build/.
# Fragments are \input by relative path from report.tex; run pdflatex with the
# source directory as the working dir and build/ as the output directory.
latex() {
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build \
    -jobname=report "$flags\\input{report.tex}"
}
latex
( cd build && BIBINPUTS="$sub_dir:" bibtex report )
latex
latex

echo "built $sub_dir/build/report.pdf"
