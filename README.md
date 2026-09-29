# When Should an Alert Threshold Learn?

Our research studies alert thresholds that learn from recent data. A threshold that
learns only from windows it already judged normal can only fall, which floods the
operator with alerts. Learning from every window lets a sustained fault become the new
normal. We treat recalibration as one guarded decision-time action (alongside alert,
hold and defer), whose data is chosen neither by the threshold itself nor
unconditionally, and we compare every policy on one common score trace. This is the
Phase-I (B.Tech Project-I, NSUT) stage: a proved mechanism, development measurements
on two SKAB streams and a synthetic stress family, and a predeclared experiment that can
refute the direction. No held-out result is claimed.

## Start here: the deliverables

| File | What it is |
|---|---|
| [`deliverables/Phase-I-Report.pdf`](deliverables/Phase-I-Report.pdf) | The 15-page Phase-I report |
| [`deliverables/Phase-I-Slides.pdf`](deliverables/Phase-I-Slides.pdf) | The 14-slide viva deck, for presenting |
| [`deliverables/Phase-I-Slides.pptx`](deliverables/Phase-I-Slides.pptx) | The same deck, editable, with speaker notes |
| [`deliverables/SHA256SUMS`](deliverables/SHA256SUMS) | Checksums of the three files |

The repository copies are built without the NSUT logo, whose reuse rights are
unresolved; the printed submission carries it.

### How to follow them

1. **Read report page 2.** It states the direction and its seven claims C1–C7, each
   tagged PROVED, MEASURED, IMPLEMENTED or PROPOSED. Every later section points back
   to one of these claims.
2. **Check the defence.** Section 3 of the report (Table 2) and slide 4 answer "isn't
   this just X?" for the nine closest papers. Section 8 and slide 12 give the strongest
   case against us.
3. **Follow one number to its source.** Every table and data figure is generated from
   the saved study results by [`report/submission/generate/`](report/submission/generate/),
   and a test asserts each cell equals the saved value. The slide check
   ([`report/slides/check_numbers.py`](report/slides/check_numbers.py)) fails if a slide
   shows a number the report does not.
4. **Present.** Slides carry 45–60 s of speaker notes each; the deck runs ten minutes.
   Slide titles state each slide's takeaway, so the titles alone tell the story.

## Reproduce everything

Requires Python 3.12 (standard library only), and for the documents TeX Live (basic),
pandoc 3, Ghostscript and poppler.

```sh
# 1. Set up the package
python3.12 -m venv .venv && source .venv/bin/activate
python -m pip install -e .

# 2. Run the policy study: 11 arms on valve1, valve2 and synthetic cases Y1-Y7.
#    Writers refuse an existing output folder, so pick a fresh name under results/.
python configs/gen_synthetic_family.py
python run_policy_study.py --output-root results/20260929-policy-study-v2

# 3. Check it independently (re-derives every metric; exit 0 = zero mismatches)
python3 scripts/recompute_evaluations.py --all-arms results/20260929-policy-study-v2

# 4. Tests: the research suite, then the figure/table generators
python -m unittest discover -s tests -q
python -m unittest report/submission/generate/test_generators.py

# 5. Documents
sh report/submission/build.sh        # report -> report/submission/build/report.pdf
bash report/slides/build.sh          # slides -> report/slides/deck.pdf, deck.pptx
python3 report/slides/check_numbers.py
```

`NO_LOGO=1` builds either document without the logo. `AI_PLACEHOLDERS=1 sh
report/submission/build.sh` prints, under each schematic figure, the prompt for an
optional AI-generated replacement; see
[`report/submission/figures/ai/README.md`](report/submission/figures/ai/README.md).
Data figures are never replaced.

## Repository layout

```text
deliverables/         final report and slides (built copies, checksummed)
report/
  submission/         report source: sections/, figures/, tables/, generate/, build.sh
  slides/             slide source: deck.md, theme, build.sh, check_numbers.py
  literature/         paper ledger, search log, closest-work analysis
  evidence-index.md   where each piece of evidence lives
src/reliable_alerting/  loaders, chronological splits, scorer, calibration,
                        policies, replay, offline evaluation, provenance
tests/                unittest suite
configs/              run, label and evaluation configs; synthetic family generator
research/             team audit, verification and plotting helpers (tested in tests/)
scripts/              independent metric recompute
run_policy_study.py   policy-study runner (all arms, all streams)
run_real_streams.py   corrected baseline runner (valve1, valve2)
run_tests.py          full test suite with a verbose log in test_results.log (ignored)
pyproject.toml        package metadata (standard library only)
opencode.json         optional tooling config, see docs/tooling.md
SKAB/                 the SKAB CSV files used, with the manifest's hashes
manifest.md           data provenance, split boundaries, reserved stream
result/               superseded Day-04 baseline outputs, kept as history
docs/                 policy-study guide, development history, optional tooling
plan/                 historical day-by-day plan
AGENTS.md             team working rules and scientific-integrity rules
```

`results/` (plural) holds local run outputs and is git-ignored; regenerate it with
the commands above.

## Scientific-integrity notes

- The two SKAB streams are development data. Dataset origin and licence are not
  independently verified, so every result is development-only.
- `SKAB/other/21.csv` is named reserved in [`manifest.md`](manifest.md), but the
  authority and recipe for that reservation are disputed. It was never opened and no
  claim rests on it.
- Labels are never read at runtime: predictions and the action log are saved first,
  and episodes are formed before labels are joined.
- All policies replay identical score traces, so ranking metrics such as VUS-PR are
  identical by construction and are not used to compare policies.

## More detail

- [`docs/policy-study.md`](docs/policy-study.md): the arms, the controller's
  parameters, and which run is current.
- [`docs/history.md`](docs/history.md): dated development sections from 19–28
  September, with their exact commands. Historical; it does not govern current claims.
- [`docs/tooling.md`](docs/tooling.md): the optional `opencode.json` tooling config.
- [`report/submission/README.md`](report/submission/README.md) and
  [`report/slides/README.md`](report/slides/README.md): document build details.
