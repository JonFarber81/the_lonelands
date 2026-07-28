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
