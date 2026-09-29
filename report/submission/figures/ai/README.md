# AI-image placeholders

Two report figures are schematics, not data, and could look better as generated
images. Each has a prompt file here, and the prompt text is the single source.

| Figure | Prompt | Fallback used today |
|---|---|---|
| Figure 1, pipeline and data flow | `fig-flow.prompt.txt` | `../fig-flow.tex` (TikZ) |
| Figure 2, admission-regime schematic | `fig-concept.prompt.txt` | `../fig-concept.tex` (TikZ) |

The data figures (ratchet, scorer limit, synthetic map, trade-off) are generated from
the saved study results and must never be replaced by generated images.

The two slide-only schematics (slides 2 and 3) keep their prompts beside their sources
in `../../../slides/diagrams/ai/`, and follow the same rules.

## How it works

`report.tex` places these figures with `\aifigure{<name>}{<fallback>}`:

- If `figures/ai/<name>.png` exists, the report uses it.
- Otherwise it draws the TikZ fallback, which is what the submitted report shows.
- `AI_PLACEHOLDERS=1 sh build.sh` also prints each prompt, verbatim, in a box under its
  figure, so a draft shows exactly what to generate.

## Using a generated image

1. Paste the prompt file's text into the image generator.
2. Check the result against the TikZ source line by line: every box, label, arrow
   direction and the dashed "labels joined offline only" edge must match. Generators
   often misspell or invent text; reject any image with a wrong or extra label.
3. Save the accepted image as `figures/ai/<name>.png` and rebuild. Delete the PNG to
   return to the TikZ figure.
