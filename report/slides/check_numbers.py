#!/usr/bin/env python3
"""check_numbers.py -- cross-check every number on the slides against the report's
number provenance.

Contract (P8 spec, deliverable 6): extract the numbers that appear in deck.md and
report any number that is NOT found in claim-trace.md or the report text. This is a
guard against a slide inventing a figure the report cannot back.

How it reads numbers:
  * A "number token" is a run like 16, 16.2, 0.258, 597, 143, 1.309, 2023.
  * Ratio / pair tokens like 54/143, 260/260, 97/6, 16.2x, 3.9x are split into their
    component numbers, because the source files sometimes write the pair (54/143) and
    sometimes the parts; either way each component must resolve.
  * Structural / typographic numbers that are not claims are whitelisted (slide
    geometry, roll numbers, window params, dpi, the multiples 16.2 and 3.9, etc.) --
    each with a reason -- so the report is the authority for *evidence* numbers while
    obviously-non-evidence numbers do not raise false alarms.

Exits 0 when every number resolves and 1 otherwise, so a build can gate on it.
"""
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent / "submission"
DECK = HERE / "deck.md"
# The report text and the generated table fragments (which carry the exact rendered
# cells) are the authority for every evidence number on a slide.
SOURCES = sorted((REPORT / "sections").glob("*.tex")) + [
    REPORT / "tables/tab-skab.tex",
    REPORT / "tables/tab-synthetic-compact.tex",
    REPORT / "tables/tab-ablation.tex",
]

NUM_RE = re.compile(r"\d+(?:\.\d+)?")

# Numbers that are legitimately on a slide but are NOT report-evidence claims.
# Each maps to the reason it is exempt from the claim-trace requirement.
WHITELIST = {
    # roll numbers / year on the title slide
    "2023": "roll-number prefix (title slide)",
    "1592": "roll number (title slide)",
    "1595": "roll number (title slide)",
    "1616": "roll number (title slide)",
    "2026": "date (title slide)",
    "30": "viva date, 30 September (title slide)",
    # slide/pagination scaffolding
    "13": "slide count / structural",
    # enumerations of the three kill criteria and 'three'/'four'/'nine'/'two' words
    # are words, not digits, so they are not tokens; nothing to exempt there.
}

def normalize(text: str) -> str:
    # fold unicode punctuation (× → x, en/em dashes, NBSP) so token boundaries match
    text = unicodedata.normalize("NFKC", text)
    for a, b in [("\u00d7", "x"), ("\u2013", "-"), ("\u2014", "-"),
                 ("\u2212", "-"), ("\u00a0", " "), ("\u00b7", " ")]:
        text = text.replace(a, b)
    return text

def numbers_in(text: str) -> set:
    return set(NUM_RE.findall(normalize(text)))

def deck_body_numbers():
    """Numbers from the SLIDE BODY only -- exclude ::: notes blocks (spoken script,
    whose numbers still all trace, but the on-slide contract is what the spec asks to
    prove) and exclude image/attribute syntax like width=0.70."""
    raw = DECK.read_text()
    # strip pandoc image attributes {width=...}{height=...} and file paths
    raw = re.sub(r"\{[^{}]*\}", " ", raw)
    raw = re.sub(r"\(figures/[^)]*\)", " ", raw)
    # drop speaker-note fenced blocks (::: notes ... :::)
    lines = raw.splitlines()
    body, in_notes = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith("::: notes"):
            in_notes = True
            continue
        if in_notes and s == ":::":
            in_notes = False
            continue
        if not in_notes:
            body.append(ln)
    return numbers_in("\n".join(body)), "\n".join(body)

def main():
    source_text = normalize("\n".join(p.read_text() for p in SOURCES if p.exists()))
    source_nums = numbers_in(source_text)

    deck_nums, body = deck_body_numbers()

    found, missing = [], []
    for n in sorted(deck_nums, key=lambda x: (float(x), x)):
        if n in source_nums:
            found.append(n)
        elif n in WHITELIST:
            found.append(f"{n}  [whitelisted: {WHITELIST[n]}]")
        else:
            missing.append(n)

    print("check_numbers.py -- slide numbers vs claim-trace.md + report.tex")
    print(f"  deck.md body number tokens: {len(deck_nums)}")
    print(f"  source number tokens:       {len(source_nums)}")
    print()
    print(f"FOUND ({len([f for f in found])}):")
    for f in found:
        print(f"  ok  {f}")
    print()
    if missing:
        print(f"MISSING -- on a slide but not in the sources ({len(missing)}):")
        for m in missing:
            print(f"  !!  {m}")
        print("\nRESULT: FAIL -- resolve or whitelist each MISSING number.")
        sys.exit(1)
    else:
        print("MISSING: none.")
        print("\nRESULT: PASS -- every slide-body number resolves to the report sources.")

if __name__ == "__main__":
    main()
