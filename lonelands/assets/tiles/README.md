# Map tilesets

The game renders map terrain and entity glyphs from a Dwarf-Fortress-style
CP437 tilesheet (see `lonelands/fonts.py`, `lonelands/tile_glyphs.py`). The
map/HUD prose and the dice tray use the bundled monospace TrueType font; the
native menus render in a proportional font (`lonelands/ui.py`).

## Wanderlust (`wanderlust_16x16.png`) — NOT committed

We use the **Wanderlust** tileset by **Kynsmer** — a 16×16 "subtly shaded ASCII"
CP437 sheet (256×256 px, standard code-page-437 layout). It is **gitignored**
because it ships with no explicit license; each developer downloads their own
copy for local use.

To install it:

1. Download `wanderlust.zip` from the Dwarf Fortress File Depot:
   https://dffd.bay12games.com/file.php?id=10022
2. Inside the archive, take `wanderlust 16x/1 - install/data/art/wanderlust.png`.
3. Save it here as `wanderlust_16x16.png`.

If the file is absent the game still runs — `fonts.py` falls back to rendering
the map glyphs from the bundled TrueType font (the pre-tileset look).

Any 16×16 CP437 sheet in standard layout works as a drop-in replacement under
the same filename.

## Kenney Roguelike sheets (`roguelike_base.png`, `roguelike_chars.png`) — SPIKE

The hidden `--sprites` flag (issue #92, Phase 0 vertical slice) renders Bree from
the **Kenney Roguelike** family instead of the CP437 sheet. Two sheets are used:

- `roguelike_base.png` — terrain, towns, props (Roguelike **Base** Pack).
- `roguelike_chars.png` — the humanoid/monster roster (Roguelike **Characters**
  Pack).

Both are **16×16 tiles with a 1px margin** between them (Kenney's layout, *not*
CP437) — `lonelands/sprites.py` accounts for the margin. They are **CC0** (public
domain, no attribution required; Kenney credited in the README regardless), so
unlike Wanderlust they may be redistributed freely; they are only `*.png`-ignored
here alongside it. Obtain them from the bundled *Kenney Game Assets All-in-1*:

- `Roguelike Base Pack/Spritesheet/roguelikeSheet_transparent.png` → `roguelike_base.png`
- `Roguelike Characters Pack/Spritesheet/roguelikeChar_transparent.png` → `roguelike_chars.png`

With the sheets absent, `--sprites` degrades gracefully to the ASCII map (the
sprite overlay simply draws nothing). Phase 1+ replaces this spike's hard-coded
key table with a data-driven one and force-commits the CC0 sheets.

## Beast sprites (`tiny_dungeon.png`, `custom_beasts.png`)

The Kenney Roguelike sheets carry **no beasts** — only humanoids — so every foe
used to fall back to the one green "orc" humanoid. Two extra sheets give the
non-humanoid roster its own art:

- `tiny_dungeon.png` — Kenney **Tiny Dungeon** (CC0), the one bundled 16×16
  top-down pack with monster tiles. We use the **spider** and the **skeleton**
  (the barrow-wight). Tiny Dungeon draws each creature on a dark rounded "floor
  pad"; our shipped copy has those two tiles flood-filled clear of the pad so
  they sit transparent like the Kenney sprites. Source (raw, padded — the
  runtime fallback): `Tiny Dungeon/Tilemap/tilemap.png`. Gitignored like the
  other CC0 sheets; the fallback path loads the raw pack if it is absent.
- `custom_beasts.png` — **hand-authored** wolf, warg, and boar (packed 16×16 +
  1px margin, tiles 0/1/2), for the canines/boar no bundled top-down pixel pack
  draws. Regenerate with `python gen_custom_beasts.py` — the pixel maps live in
  that script. This is **our own art with no external source**, so unlike the
  other sheets it is **committed** (a `!` exception in `.gitignore`).

Both feed the same tone-grade pipeline in `lonelands/sprites.py`, so beasts read
as somber as the terrain. Foes resolve to a sprite by **creature name** (see
`resolve_entity`), because glyphs collide — the warg and the barrow-wight are
both `W`, and only the name tells a wolf-pack from an undead.
