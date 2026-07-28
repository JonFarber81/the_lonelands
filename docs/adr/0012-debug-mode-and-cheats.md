---
status: accepted
---

# Debug mode and cheats

Testing a change — a new Region's layout, a shop flow, a level-up gain, a
combat edge case — currently means *playing there*: walking across the
overworld, surviving to the right level, finding an enemy. That is slow and
non-deterministic, and there is no way to reach a state directly. We are adding
a **debug mode**: an off-by-default developer switch that unlocks a small set of
**cheats** for reaching and inspecting game states quickly. This is a testing
affordance only — it is never part of a real playthrough and nothing about it
touches the save format.

## Decisions

- **Debug mode is a runtime flag from `--debug`, never a saved fact.** `main.py`
  gains `argparse` (its first CLI surface) and a single `--debug` flag, off by
  default. The flag lives only for the life of the process. It is **not**
  serialized: a save made under `--debug` is an ordinary save, and reloading it
  without `--debug` yields an ordinary (possibly over-powered) game. *Rejected:*
  an env var (invisible) and persisting a debug bit into the save (dirties the
  save format for a testing-only concern).

- **One door: the F12 Debug menu.** With `--debug` set, **`F12`** opens a
  **Debug menu** overlay — built on the existing native-overlay pattern
  (`on_render_native`), the same machinery as the other menus. Without
  `--debug`, `F12` is inert and the menu does not exist. A single discoverable
  entry point means adding a cheat is one more menu row, not a hunt for a free
  key. *Rejected:* raw per-cheat keybinds (undiscoverable, key-space pollution)
  and a typed console (more surface than the cheat set warrants).

- **Six cheats, chosen for reuse across testing flows.** The menu offers:
  - **God mode** — a **toggle**: the hero takes **no damage** and is **never
    weary** (carry-load ignored for weariness). Combat rolls are otherwise
    normal — god *protects*, it does not auto-win, so you can still miss. Resets
    to **off** on load.
  - **Gain a level** — banks exactly `xp_to_next`, producing one clean level-up
    with every normal gain (Endurance, to-hit, Path point) via the ordinary
    advancement path.
  - **Teleport** — opens the **Overworld Map** in a pick-a-Region mode; confirm
    a cell and land on that Region's **Surface** arrival point. **Region-to-
    Region and Surface-only** — reaching a deeper Level still uses stairs.
  - **Heal fully** — restore Endurance to its maximum.
  - **Full map reveal** — clear fog on the current **local map**.
  - **Kill all visible enemies** — remove **every** hostile on the current local
    map, not only those in the hero's FOV, so the Region reliably clears for
    flow-testing.

  *Deferred:* add-gold, spawn-item, set-a-specific-stat, spawn-a-specific-enemy,
  freeze-time — more surface, less reuse; add when a concrete test needs one.

- **Only ordinary consequences persist.** Nothing debug-specific is written to
  the save. God mode is transient (re-toggle after a reload); permanent world
  changes a cheat causes — a granted level, killed enemies, revealed fog — are
  real game state and survive the save like anything else.

- **Minimal, honest indication.** While `--debug` is active a small `[DEBUG]`
  marker sits in a sidebar corner, with a `GOD` flag beside it while god mode is
  on, so a debug session is never mistaken for a real one. Every cheat also
  prints a **Chronicle** line (`God mode ON`, `Teleported to Weathertop`,
  `+1 level`) as a log of what was done.

## Consequences

- `main.py` gains `argparse` and threads a `debug` boolean into the game
  (setup/engine), the first CLI argument surface — a natural home for later
  flags (`--seed`, `--start-region`).
- `input_handlers.py` gains the `F12` Debug-menu handler (gated on the runtime
  flag) and the teleport-via-Overworld-Map pick mode; `god_mode` becomes a
  transient hero/engine flag consulted by `fighter.take_damage` and the
  weariness check, and is **not** serialized by `savegame.py`.
- `hud.py` renders the `[DEBUG]`/`GOD` marker.
- Cheat actions reuse existing machinery wherever possible — `add_xp`,
  `fighter.heal`, the fog/FOV reveal, the Overworld Map picker — rather than new
  bespoke systems.
- **CONTEXT.md** gains a short **Development & tooling** section defining
  **Debug mode**, the **Debug menu**, **god mode**, and the **cheat** vocabulary.
