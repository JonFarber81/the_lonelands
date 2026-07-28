# Oryx tileset — drawable → sprite mapping

Companion to **ADR-0016**. The complete first-cut (system-complete) map of every
current drawable to an Oryx *Ultimate Roguelike 2.0* silhouette.

**How to read this.** Every drawable keeps its ASCII glyph (unchanged) and gains
a **sprite key** resolving to a source tile. The silhouette is **tinted per-cell
by the drawable's existing foreground colour** (from `color.py` / the entity's
`color`) — glyph and sprite share that one colour. Source-tile size **varies per
sheet** (creatures ~16 px, terrain ~24, portraits ~48) and must be detected
per-sheet at load, then scaled to the square game cell.

Sheet coordinates below are **semantic** (sheet + descriptor), not pixel
row/col — those get pinned when the atlas loader lands and the per-sheet grid is
detected. `★ BESPOKE` = draw in-code via the ADR-0001 seam; Oryx has no adequate
tile (all four keep their ASCII glyph as fallback).

## Terrain (`tile_types.py`, 16 tiles)

| tile | glyph | tint (fg) | → Oryx |
|---|---|---|---|
| floor | `.` | floor_light | Terrain — dungeon flagstone floor |
| wall | `#` | wall_light | Terrain — cracked stone wall |
| rubble | `%` | stone brown | Terrain — rubble / debris |
| down_stairs | `>` | pale gold | Terrain — stairs descending |
| up_stairs | `<` | pale gold | Terrain — stairs ascending |
| door | `+` | wood brown | Terrain — arched wooden door |
| grass | `"` | grass_light | Terrain — grass tuft |
| grass_low | `,` | grass_light | Terrain — low ground scatter |
| tree | `T` | tree_light | Terrain_Objects — tree |
| water | `~` | water_light | Terrain — water / waves |
| road | `.` | road_light | Terrain — dirt path |
| bridge | `=` | wood brown | Terrain — bridge planks |
| hill | `n` | stone tan | Terrain — hill / rise |
| cobble | `.` | stone grey | Terrain — cobblestone |
| building_wall | `#` | timber tan | Terrain — timber/plaster wall (best-fit; **the Prancing Pony** is the ★ bespoke exception) |
| ruin_entrance | `>` | pale gold | Terrain — ruined archway / gate |

Plus map props that ride the NPC machinery:
- **Signpost** `?` (`_helpers.make_signpost`, SIGNPOST_COLOR) → **★ BESPOKE — wooden signpost**
- **Snare** `^` (Hidden Path, `snare_c`) → Items/FX — laid trap / snare

## Player & entities (`content.py`)

| entity | glyph | tint | → Oryx |
|---|---|---|---|
| **Player** (Greycloak / Tarandir) | `@` | **Dúnedain steel-grey** (new signature tint) | Avatar — hooded ranger, bow in hand (**★ bespoke fallback** if no Avatar figure reads as a bowman) |
| cave-goblin | `g` | orc_c green | Monsters — small goblin |
| orc soldier | `o` | orc_c green | Monsters — orc warrior |
| orc bowman | `o` | olive green | Monsters — orc archer (bow) |
| great spider | `s` | beast_c | Monsters — giant spider |
| barrow-wight | `W` | undead_c corpse-grey | Monsters — wraith / barrow-spectre |
| grey wolf | `w` | wolf_c | Monsters — wolf |
| warg | `W` | wolf_c | Monsters — large wolf / warg |
| footpad | `b` | orc_c | Monsters — hooded human rogue |
| highwayman | `b` | tan | Monsters — armed human brigand |
| wild boar | `q` | earthy brown | Monsters — boar |

## NPCs (`story/`)

Sprites parallel the ADR-0009 glyph split. Add a `RACE_SPRITES` beside
`RACE_GLYPHS` as the single source of truth for the lettered crowd.

| NPC class | glyph | tint | → Oryx |
|---|---|---|---|
| wandering Bree-man | `m` | warm tan | Avatar/Monsters — townsman silhouette |
| wandering hobbit | `h` | ochre | Avatar/Monsters — shorter halfling silhouette |
| wandering dwarf | `d` | steel | Avatar/Monsters — stout bearded silhouette |
| fixed/authored NPCs (Butterbur, Ferny, the Ranger, gatekeeper, hamlet folk) | `@` | per-NPC | Avatar/Monsters — standing-figure silhouette, tinted per NPC (portraits are the deferred dialog upgrade, not the map glyph) |

## Items (`content.py`) → `Items` sheet

| item(s) | glyph | → Oryx (Items) |
|---|---|---|
| bow | `}` | bow |
| melee weapons (sword/spear/blade variants) | `/` `\|` etc. | matching blade/haft |
| woodwright's felling-axe | `/` | axe |
| arrows / ammo | `\` | arrows / quiver |
| Ranger's leathers | `[` | leather armour |
| corslet of mail · Mail of the Last Watch | `[` | mail hauberk |
| buckler | `)` | shield / buckler |
| reinforced hood | `^` | hood / helm |
| Grey Mantle of Lórien | `(` | cloak |
| star of the Dúnedain · leaf-brooch of green · star-brooch of Arnor | `*` | brooch / star gem / amulet |
| athelas leaves · healing herbs | `*` | herb / leaf |
| waybread | `%` | bread / ration |
| draught of the Dúnedain | `!` | potion / flask |
| Southlinch pipe-weed | `%` | pouch / pipe |
| spider-silk | `~` | silk skein / thread |
| coins / gold | `$` | coin stack |

## The four bespoke tiles (issues, not blockers)

1. **Hobbit-hole** — the Shire/Staddle round green door; Oryx has no cozy
   halfling dwelling.
2. **The Prancing Pony** — Bree's inn, the social hub; the generic timber wall
   won't carry it.
3. **Signpost** — the wayfinding post the player bumps to read.
4. **Barrow-mound** — Tyrn Gorthad's grave-mounds (Oryx gravestones are the
   nearest miss, but a mound is a distinct shape).
