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
