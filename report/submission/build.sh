#!/bin/sh
# Build report.tex into build/ with pdflatex -> bibtex -> pdflatex x2.
# TeX Live 2026 basic must be on PATH: export PATH=/Library/TeX/texbin:$PATH
#
# The NSUT logo is NOT committed (reuse rights unresolved; the repo is public).
# This script copies it in from the report-work visuals pack WHEN that pack is
# present beside the checkout, so the final PDF carries the logo. report.tex uses
# \IfFileExists, so the source still compiles (with a plain text cover mark)
# without it. build/ is git-ignored; generated files are never hand-edited.
set -eu

sub_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$sub_dir"
export PATH=/Library/TeX/texbin:$PATH
mkdir -p build

# Bring the cover logo in from the review pack if it is available; harmless if not.
logo_src="$sub_dir/../../../report-work/visuals/nsut-page1-000.png"
if [ -f "$logo_src" ] && [ ! -f "$sub_dir/nsut-logo.png" ]; then
  cp "$logo_src" "$sub_dir/nsut-logo.png"
fi

# Generated build files live under build/ and are never hand-edited.
rm -f build/report.aux build/report.bbl build/report.blg \
      build/report.log build/report.out build/report.pdf build/report.toc

# bibtex needs the .bib and the figure/table fragments reachable from build/.
# Fragments are \input by relative path from report.tex; run pdflatex with the
# source directory as the working dir and build/ as the output directory.
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build report.tex
( cd build && BIBINPUTS="$sub_dir:" bibtex report )
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build report.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build report.tex

echo "built $sub_dir/build/report.pdf"
