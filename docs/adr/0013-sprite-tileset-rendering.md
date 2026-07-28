# Full-colour sprite tileset for the play field, with an ASCII toggle

## Status

**Superseded by ADR-0015 (ASCII-only play field).** Only Phase 0 (the hidden
`--sprites` vertical slice) ever shipped; the game has since committed to a
classic ASCII look, and both the sprite path and the CP437 map tilesheet
described below have been removed. Kept for the record of what was tried.

## Context

The play field has always been drawn as coloured glyphs. ADR-0001 baked custom
glyphs into a tileset; ADR-0010 moved windowing/render/input to pygame, where
`fonts.py:GlyphAtlas` bakes one surface per codepoint and `tile_glyphs.py`
already routes map/entity glyphs through a **separate** Private-Use codepoint
block (`graphic_cp`). Today those graphic codepoints resolve to a **CP437
tilesheet cell, baked white and tinted per-cell by the entity/terrain fg
colour** — the "deluxe ASCII" look in `screenshots/bree_cla_sprites.png`.

We have a large CC0 art library (Kenney Game Assets, `2D assets/`) with
purpose-built top-down sets — **Roguelike Base + Characters + Dungeon** (16×16),
plus Tiny Dungeon/Town and Micro Roguelike. We want the shippable game to read
as a full-colour top-down RPG (see `screenshots/mockup_bree_roguelike.png`,
`mockup_barrow_roguelike.png`, `mockup_shire_roguelike.png`, composed from the
real Roguelike tiles) while keeping the classic ASCII look available.

Full colour breaks the load-bearing assumption of the current path: a colourful
sprite must **not** be re-tinted by an entity's fg colour, and "one glyph per
cell" cannot show a creature standing *on* a floor.

## Decision

Add a **Sprite mode** to the play field as the default, with **ASCII mode**
retained behind a toggle. Concretely:

1. **Full-colour tiles, no fg tint.** Sprite mode draws bundled 16×16 tile-sheet
   art at its own colour. The per-cell white-bake-and-tint path stays for ASCII
   mode and for the retained CP437 fallback, but sprite tiles bypass it.
2. **Roguelike family is the backbone.** Kenney **Roguelike Base + Characters +
   Dungeon** provide terrain, towns, dungeons, and the humanoid/monster roster;
   other packs are cherry-picked only where they match its 16×16 top-down idiom.
   Only the sheets actually used are vendored into `lonelands/assets/tiles/`
   (CC0 — no attribution required; Kenney credited in the README regardless).
3. **Two-layer compositing.** A map cell is a **Terrain layer** (ground) plus an
   **Entity layer** (creature/item) drawn over it with transparency. This
   extends the `Console` beyond today's single `(ch, fg, bg)` per cell — the map
   grid carries a terrain sprite-key and an ordered stack of entity sprite-keys.
4. **Sprite key, distinct from the ASCII glyph.** Each drawable (tile type and
   entity) gains an explicit **sprite key**; a data-driven table maps sprite key
   → sheet coordinate. Keys are *not* derived from the ASCII `char`, because many
   entities share a char (every orc is `o`). The **race** crowd (ADR-0009)
   carries a sprite key beside its race-letter; the toggle simply chooses which
   identity to draw.
5. **Square 16×16 map cells.** The map moves from 16×20 to square cells so
   sprites render pixel-perfect (no letterbox, no stretch); the map viewport and
   the HUD/log grid are re-proportioned. The chrome (native pygame per ADR-0010)
   is unaffected.
6. **FOV by dimming, not palette-swap.** Lit tiles draw full-bright; remembered
   tiles draw the *same* sprite darkened; unseen stay black — replacing ASCII
   mode's separate light/dark glyph colours.

## Consequences

- The seams from ADR-0001/0010 hold: the codepoint/atlas contract and the
  `Console` shim are still where art meets the game. The change is *additive* —
  a second layer and a sprite-key resolver — so ASCII mode and the CP437 path
  keep working, and the toggle is a genuine A/B, not a rewrite.
- Maintaining both paths is the standing cost: every new drawable needs a glyph
  *and* a sprite key, and layout must survive a cell-geometry change. The payoff
  is accessibility, art-independence, and a truthful fallback while sprite
  coverage is still filling in.
- **Coverage is not free, and the Roguelike pack has gaps.** The mockups are
  honest about this: Bree and the Barrow-downs deep compose convincingly from
  stock tiles, but **the Shire's hobbit-holes have no adequate stock tile** and
  are the clearest case where bespoke pixel art is required (ADR-0001's
  glyph-baking seam is the model for adding it). The plan sequences a thin
  in-engine vertical slice first, then coverage cluster-by-cluster, so gaps
  surface early against the ASCII fallback rather than blocking the whole swap.
- The bundled sheets add ~120 KB to the repo; CC0 keeps licensing a non-issue.
