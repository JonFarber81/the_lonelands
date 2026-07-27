# NPC map glyphs: letter the wandering crowd by race, reserve `@` for principals

## Context

Every friendly on the map was drawn as `@` — the player, all hand-authored NPCs
(questgivers, merchants, fixed bystanders), and the whole generated tavern crowd
— differing only by colour. Hostile creatures already carry distinct beast
letters (`g o s w W b q`, see `content.py`), but a Bree street or the Prancing
Pony common room rendered as an undifferentiated sea of `@`, hardest to parse
exactly where the folk are thickest (the wandering patron crowd). Glyphs are
single printable-ASCII codepoints backed by the tileset (ADR-0001,
`tile_glyphs.graphic_cp`), so a letter per race is free to render.

## Decision

Split friendlies along **generated-wandering vs hand-authored**, not
functional-vs-bystander:

- **Generated wandering Bystanders** (the patron crowd minted by
  `story/patrons.py`) are **lettered by race** — `m` man, `h` hobbit, `d` dwarf —
  so a roomful reads at a glance.
- **The player and every hand-authored NPC** — questgivers, merchants, and
  *fixed* bystanders alike (Butterbur, Halbarad, Bill Ferny, the hamlet
  flavour-folk) — keep the roguelike **`@`**, reserving that glyph for the folk
  you seek out by a specific place and name.

`@` therefore means "a specific individual standing here," not "advances the
game" — which is why the colour-only innkeeper Butterbur keeps `@` while an
anonymous drifting Bree-man becomes `m`. Signposts remain `?`.

`story/_helpers.RACE_GLYPHS` is the **single source of truth**: a patron kind
declares its `race` and derives its glyph from the map; a new lettered NPC draws
its glyph from there by race, and a new race (elf, orc-friend, …) adds exactly
one entry. Chosen letters stay printable ASCII and must not collide with the
beast letters in `content.py`.

## Consequences

- The crowd reads by kind without a legend; `@` stays meaningful as "a named
  figure worth walking up to."
- New NPCs must choose a side. A wandering/anonymous member of a crowd is
  lettered from `RACE_GLYPHS`; a hand-placed, sought-out figure is `@`. Adding a
  race is one line in `RACE_GLYPHS`, referenced by name everywhere — never a
  hardcoded letter at a call site.
- A glyph is fixed at creation and **never changes as an NPC moves**. "Wandering"
  names a *kind* of NPC (the generated patron crowd, which happens to carry the
  `IdleWanderer` AI), not a motion state: a patron is stamped with its race letter
  once and keeps it whether it is mid-stride or standing still. Two *different*
  NPCs of the same race can differ (a hand-placed hobbit `@`, a crowd hobbit `h`),
  but no single NPC ever flips between them.
- The glyph lives on the entity (`Entity.char`) and survives save-pickle and
  `spawn` deepcopy; savegames made before this decision keep whatever glyph they
  stored, which is cosmetic only.
- Fixed hamlet flavour-bystanders (Nib Sandheaver, Mattock Mugwort, the pedlar,
  the coppicer) stay `@` under this rule — they are hand-placed individuals, not
  crowd. If we later want their race shown too, the deliberate follow-up is to
  move them onto `RACE_GLYPHS` at their call sites; the registry already supports
  it. This is the one boundary to revisit if the split ever feels wrong.
