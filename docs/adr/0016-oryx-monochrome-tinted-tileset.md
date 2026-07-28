# Oryx monochrome-mask tileset as the tinted play field

## Status

Accepted. **Supersedes ADR-0015** (ASCII-only play field). Revives the *ambition*
of ADR-0013 (a sprite play field) but on a **different technical basis** — Oryx's
art is monochrome masks, tinted exactly like text, not the pre-coloured Kenney
tiles ADR-0013 assumed. Re-extends the ADR-0001 glyph-baking seam to the map.

## Context

ADR-0015 committed the game to a classic ASCII look and deleted the sprite path,
concluding "the sprite ambition is dropped, not deferred." That was decided
2026-07-27. It is **deliberately reversed here**: the right tileset (a licensed
Oryx *Ultimate Roguelike 2.0* set) has since landed, and a look we're excited to
ship is now within cheap reach. We say that plainly rather than pretend 0015
never happened.

Two facts reshape the decision away from ADR-0013's model:

1. **The Oryx sheets are monochrome white masks, shaped by alpha, built to be
   engine-tinted** — verified: not one coloured pixel across `Monsters`,
   `Avatar`, `Terrain`, `Items`, `Interface_Portraits`, even `Backgrounds`. This
   is the *opposite* of the pre-coloured Kenney art ADR-0013 was built around,
   whose load-bearing rule was "a colourful sprite must **not** be re-tinted by
   fg colour" (forcing two-layer compositing and a separate sprite identity).
   Here, a tile *wants* to be tinted per-cell — the same operation
   `fonts.py:GlyphAtlas` already performs on every letter.

2. **The art is a paid, licensed product we own, and must never enter the source
   tree.** A bare `git clone` must still run. So ASCII is not "the game" (as 0015
   held) nor a throwaway toggle (as 0013 had it) — it is the **guaranteed
   baseline** that every clone falls back to, present forever by licensing
   necessity.

## Decision

Adopt the Oryx set as the **default play-field look wherever the licensed art is
present**, rendered as **single-hue-per-entity tinted silhouettes** (an
illuminated-woodcut look, not a full-colour RPG). Concretely:

1. **A sprite is a glyph whose bitmap is an Oryx silhouette.** Each source tile
   is sliced from its sheet, baked into a per-key surface, and **tinted per-cell
   by the drawable's existing foreground colour** through the ADR-0001/0010
   atlas seam. No two-layer compositing; no separate sprite colour. Glyph and
   sprite **share one `(char/sprite-key, fg)`**.

2. **Full parity, both paths first-class, forever.** Every drawable carries an
   ASCII glyph **and** a sprite key; a missing sprite key is a bug. Because the
   two share a colour, this is near-free bookkeeping, not ADR-0013's double
   identity.

3. **Auto-detect default, ASCII toggle.** On boot the game looks for the sheets
   at a known local path (`LONELANDS_TILES` or the configured location).
   **Present → sprites; absent → ASCII.** A toggle forces ASCII either way
   (parity testing, accessibility, preference). The lever flips from ADR-0013:
   opt *out* of sprites, not in. No hidden off-by-default limb.

4. **Square map cell.** The map cell moves from 24×30 to **square** so
   silhouettes render with no letterbox and no stretch; the HUD/sidebar/log
   reflow to match (single shared grid retained, per ADR-0010). Each Oryx source
   tile — whose native size **varies per sheet** (creatures ~16, terrain ~24,
   portraits ~48; detect per-sheet at load) — is scaled to the square game cell.

5. **Keep and extend the palette.** `color.py`'s existing earthy Middle-earth
   palette *is* the sprite palette; it is not repainted. Silhouette shape now
   disambiguates entities that share a tint (goblin/orc/archer; wight/warg), so
   the palette can tighten rather than grow. The hero takes a **Dúnedain
   steel-grey** signature tint on a fixed hooded-Ranger-with-bow silhouette, so
   he reads apart from the green orc-kin and the lettered crowd.

6. **Curated hybrid coverage; four bespoke tiles.** Oryx renders everything it
   does well (the hostile roster, dungeon terrain, items). Four Middle-earth
   surface shapes Oryx cannot do justice are **bespoke 24-square tiles via the
   ADR-0001 seam** — the **hobbit-hole, the Prancing Pony, signposts, and
   barrow-mounds** — each tracked as an issue, none a blocker (all keep an ASCII
   glyph, so nothing is ever blank).

7. **First cut is system-complete, not a region slice.** One pass maps *all*
   terrain, *every* entity in `content.py`, *all* item glyphs, and the hero — so
   everywhere walkable today renders in tiles. No per-region slice (the shape
   that rotted under ADR-0013). Done = every existing drawable has a sprite key;
   the bespoke four are issues, not gates.

Deferred, each an issue, in order: **dialog portraits** (first follow-up),
**projectile FX**, **region-entry/title backgrounds**, **equipment paper-doll**.
Plus a **bundling/distribution** step that packs the licensed art into
distributable builds (the only sanctioned way the art ships).

## Consequences

- The rendering stack stays a **single tinted-glyph path**: ASCII and sprites
  differ only in which bitmap a key resolves to, both tinted per-cell. The
  ADR-0013 "glyph *and* sprite colour" maintenance tax does **not** return —
  only a sprite-key per drawable does.
- The game's look is a cohesive monochrome-tint woodcut, arguably *more* Tolkien
  than a candy-coloured set — but it is **not** the full-colour RPG of ADR-0013's
  mockups. That is the intended aesthetic, chosen with eyes open.
- The licensed sheets are **gitignored and never committed**; clones render
  ASCII, bundled builds render sprites. Repo and running game diverge *by
  design*, resolved for players by the bundling step.
- If the monochrome tint ever proves too austere, going full-colour would be a
  *fresh* decision requiring a different (pre-coloured) set and ADR-0013's
  compositing — this ADR does not leave that wired up.
- ADR-0009's "glyph" now implies a paired sprite key; new lettered/authored NPCs
  pick a sprite key alongside their race letter or `@`.
