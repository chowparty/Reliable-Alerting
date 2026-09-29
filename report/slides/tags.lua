-- tags.lua -- render evidence tags written as [MEASURED]{.tag} in deck.md.
-- Beamer gets the shaded \evtag chip defined in beamer-preamble.tex; PowerPoint,
-- which has no such macro, gets the same word in bold brackets.
function Span(el)
  if not el.classes:includes("tag") then
    return nil
  end
  local word = pandoc.utils.stringify(el)
  if FORMAT:match("beamer") or FORMAT:match("latex") then
    return pandoc.RawInline("latex", "\\evtag{" .. word .. "}")
  end
  return pandoc.Strong({ pandoc.Str("[" .. word .. "]") })
end
