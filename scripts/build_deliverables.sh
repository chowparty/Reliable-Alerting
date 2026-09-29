#!/usr/bin/env bash
# build_deliverables.sh -- rebuild the report and the slides, check both, and refresh
# deliverables/ (the reviewed PDFs, the PPTX and SHA256SUMS).
#
#   bash scripts/build_deliverables.sh              build, check, refresh deliverables/
#   bash scripts/build_deliverables.sh --check      build and check only; deliverables/
#                                                   is left untouched
#   bash scripts/build_deliverables.sh --regenerate first regenerate the data figures and
#                                                   tables from results/ (needs the study
#                                                   run; see README "Reproduce everything")
#
# Any failed check stops the script with a FAIL line; nothing is copied after a failure.
# The public copies are built without the NSUT logo (NO_LOGO=1, the default here); run
# with NO_LOGO=0 to build a local, with-logo copy. Page previews for a visual check are
# written to report/submission/build/preview/ and report/slides/.work/preview/.
#
# Works with the bash 3.2 that ships with macOS and with newer bash on Linux.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
PATH="/Library/TeX/texbin:$PATH"; export PATH
# Fixed timestamp: an unchanged source rebuilds to byte-identical files.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1790706600}"   # 2026-09-30 00:00 IST
export NO_LOGO="${NO_LOGO:-1}"

mode=copy; regenerate=0
for arg in "$@"; do
  case "$arg" in
    --check) mode=check ;;
    --regenerate) regenerate=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
ok()   { printf '   ok  %s\n' "$*"; }
guard() { perl -e 'alarm shift; exec @ARGV' "$@"; }   # guard <seconds> <cmd...>

step "Tools"
missing=""
for tool in python3 perl pdflatex bibtex pandoc gs pdftoppm pdfinfo pdffonts pdftotext; do
  command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
[ -z "$missing" ] || fail "missing tools:$missing (see report/README.md, Setup)"
ok "all found"

study="results/20260929-policy-study-v2"
if [ "$regenerate" = 1 ]; then
  step "Regenerate data figures and tables from $study"
  [ -d "$study" ] || fail "$study not found; run the policy study first"
  guard 300 python3 report/submission/generate/make_figures.py >/dev/null
  guard 300 python3 report/submission/generate/make_tables.py >/dev/null
  ok "figures/ and tables/ fragments rewritten"
fi

step "Generator tests"
if [ -d "$study" ]; then
  guard 600 python3 report/submission/generate/test_generators.py >/dev/null 2>&1 \
    || fail "generator tests; run: python3 report/submission/generate/test_generators.py"
  ok "every generated cell equals the saved study results"
else
  echo "   skip  $study not present (generated fragments are committed, so text-only"
  echo "         edits do not need it)"
fi

step "Report"
sub=report/submission
mkdir -p "$sub/build"
guard 600 sh "$sub/build.sh" >"$sub/build/console.txt" 2>&1 \
  || fail "report build; see $sub/build/report.log"
log="$sub/build/report.log"; pdf="$sub/build/report.pdf"
if grep -Eq "(Reference|Citation) .* undefined|There were undefined" "$log"; then
  grep -E "(Reference|Citation) .* undefined" "$log" | head -5 >&2
  fail "undefined references or citations in the report"
fi
if grep -q "^Overfull" "$log"; then
  grep -A1 "^Overfull" "$log" | head -8 >&2
  fail "text runs past the margin in the report (Overfull box; the line numbers above point into the source)"
fi
pages=$(pdfinfo "$pdf" | awk '/^Pages:/ {print $2}')
[ "$pages" -ge 10 ] && [ "$pages" -le 15 ] || fail "report has $pages pages; the Guidelines require 10-15"
hits=$(pdftotext "$pdf" - | grep -nE '\?\?|TODO|TBD|PENDING' || true)
[ -z "$hits" ] || { printf '%s\n' "$hits" | head -3 >&2; fail "placeholder text (?? / TODO / TBD / PENDING) in the report"; }
if pdffonts "$pdf" | awk 'NR>2 && $(NF-4)!="yes"' | grep -q .; then
  fail "a font is not embedded in the report"
fi
ok "$pages pages, no undefined references, no overfull lines, all fonts embedded"

step "Slides"
sl=report/slides
guard 900 bash "$sl/build.sh" >"$sl/.build.log" 2>&1 || fail "slide build; see $sl/.build.log"
if grep -q "^Overfull" "$sl/.work/deck.log"; then
  grep "^Overfull" "$sl/.work/deck.log" | head -5 >&2
  fail "slide content runs off the slide (Overfull box in $sl/.work/deck.log; line numbers point into $sl/.work/deck.tex)"
fi
slides=$(pdfinfo "$sl/deck.pdf" | awk '/^Pages:/ {print $2}')
[ "$slides" -ge 10 ] && [ "$slides" -le 15 ] || fail "deck has $slides slides; the Guidelines require 10-15"
counts=$(python3 -c '
import re, sys, zipfile
names = zipfile.ZipFile(sys.argv[1]).namelist()
count = lambda pat: sum(1 for n in names if re.fullmatch(pat, n))
print(count(r"ppt/slides/slide\d+\.xml"), count(r"ppt/notesSlides/notesSlide\d+\.xml"))
' "$sl/deck.pptx")
pptx_slides=${counts% *}; pptx_notes=${counts#* }
[ "$pptx_slides" = "$slides" ] || fail "PPTX has $pptx_slides slides but the PDF has $slides (text placed after a table or image starts a new PPTX slide; see $sl/README.md)"
[ "$pptx_notes" -ge $((slides - 1)) ] || fail "only $pptx_notes of $((slides - 1)) content slides have speaker notes"
python3 "$sl/check_numbers.py" >"$sl/.work/check_numbers.txt" \
  || { grep -A20 "^MISSING" "$sl/.work/check_numbers.txt" >&2; fail "a slide shows a number the report does not"; }
ok "$slides slides in PDF and PPTX, $pptx_notes with speaker notes, nothing off the slides, every number traced"

step "Previews for a visual check"
rm -rf "$sub/build/preview" "$sl/.work/preview"
mkdir -p "$sub/build/preview" "$sl/.work/preview"
guard 300 pdftoppm -r 60 -png "$pdf" "$sub/build/preview/page"
guard 300 pdftoppm -r 80 -png "$sl/deck.pdf" "$sl/.work/preview/slide"
ok "$sub/build/preview/ and $sl/.work/preview/ (look at every page before committing)"

if [ "$mode" = check ]; then
  step "Checks passed; deliverables/ left unchanged (--check)"
  exit 0
fi

step "Refresh deliverables/"
[ "$NO_LOGO" = 1 ] || fail "deliverables/ holds only logo-free copies; rerun without NO_LOGO=0"
cp "$pdf" deliverables/Phase-I-Report.pdf
cp "$sl/deck.pdf" deliverables/Phase-I-Slides.pdf
cp "$sl/deck.pptx" deliverables/Phase-I-Slides.pptx
python3 - <<'PY'
import hashlib, pathlib
out = pathlib.Path("deliverables")
names = ["Phase-I-Report.pdf", "Phase-I-Slides.pdf", "Phase-I-Slides.pptx"]
lines = [f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}" for n in names]
(out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
PY
ok "copied and checksummed"
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  changed=$(git status --short -- deliverables)
  if [ -n "$changed" ]; then printf '%s\n' "$changed"; else echo "   (identical to the committed copies)"; fi
fi
