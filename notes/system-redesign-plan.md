# System redesign — phased build plan

Implements ADR 0005 (own system: a d20 core, perk-Paths, legible loot). Uses the
CONTEXT.md vocabulary (Check, Attribute, Path, Perk, Soak, Bleed, Affix…).

**Principle: the game stays runnable and win-able after every phase.** Each phase
is a self-contained slice (one PR, or a small handful) that leaves `main`
playable. Phases 1→2→3 are the spine and go in order; 4 and 5 can run in parallel
once 2 lands; 6 sits on top of 5.

**Progress:** Phases 1–4 have **landed** on `main`; Phases 5–6 remain.

---

## Phase 1 — d20 resolution + combat spine  ✅ **landed**
*The riskiest core swap; do it first and tune the feel before building on it.*

- `dice.py`: replace the Feat+Success pool with **Check** — `d20 + modifier vs
  TN`; `roll_check(mod, tn, advantage=0)` (2d20 keep high/low), `is_crit`
  (nat 20), `is_fumble` (nat 1). Keep `set_seed`.
- `fighter.py`: **Attack roll** `d20 + attack_bonus vs Defence`; on hit roll
  **damage − soak**; a **Critical** adds bonus damage; drop the Parry/Piercing
  Blow/Protection/Wound chain. Add a **Bleed** status (damage-over-time), applied
  by crits/heavy foes. Foe fields become `attack_bonus`, `damage` (dice),
  `defence`, `soak`.
- `hero.py`: `test_skill`/`test_attribute` → a single `check(mod, tn, …)`.
- `render_functions.py` / dice-tray: render a d20 line (die + bonus + total vs TN,
  damage, CRIT/FUMBLE) instead of feat+success glyphs.
- `content.py`: convert every foe to the new fields; convert the hero's temporary
  attack bonus.
- Tests: rewrite `test_dice.py`, `test_combat.py`.

## Phase 2 — new character model (attributes, single HP, curve)  ✅ **landed**
- `tor.py` → rename/replace: **Brawn · Wits · Will**; delete `SKILL_GROUPS`,
  `ALL_SKILLS`, `PROFICIENCIES`. (Rename the module off `tor` too.)
- `hero.py`: attributes drive checks & derived combat numbers; **single Endurance
  HP** (already the pool — just remove the Wound death-track); delete Hope,
  Shadow, Valour, Wisdom, skills, proficiencies. Add the **Level** curve: XP
  thresholds, `+HP` per level, periodic `+to-hit`, and **perk points** every few
  levels.
- `input_handlers.py`: rewrite `CharacterScreenHandler` for the new sheet.
- Tests: `test_tor.py` (→ new name), hero/level tests.

## Phase 3 — XP from kills *(small; folds near Phase 2)*  ✅ **landed**
- `fighter.die()`: grant `xp_reward` for **all** foes; keep loot resolution.
- `content.py`: assign `xp_reward` across foes; tune the curve so levels land
  **frequently** in normal play. Supersedes ADR 0004's no-XP rule.
- Tests: kill→XP→level.

## Phase 4 — Paths & perks *(largest content phase; needs Phase 2)*  ✅ **landed**
- New `perks.py`: a **Path**/**Perk** data model — per-perk cost, in-Path
  prerequisites, capstone gating, and an **effect hook** (passive modifiers +
  active abilities on charges/cooldowns).
- Author the five Paths, ~3–4 perks each to start: **Long Watch, Swift Wrath, Far
  Shot, Hidden Path, Kindled Heart**.
- Wire effect hooks into `fighter.py`/`hero.py` (to-hit, Defence, soak, on-hit,
  on-kill, low-HP triggers; cooldown/charge bookkeeping).
- `input_handlers.py`: replace `AdvancementHandler` with a **Path/perk** buy UI.
- Tests: prereq/capstone gating, a passive and an active perk end-to-end.

## Phase 5 — equipment overhaul (stats + named Uniques) *(needs Phase 1)*
- `equipment_types.py`: add an **ACCESSORY** slot.
- `equippable.py`: split armour into **soak** (heavy) vs **+Defence** (light +
  shields); add weapon **property** (pierce / bonus-vs-type); add accessory
  pluses (+attribute, +stealth, Path synergy, ability charges).
- `content.py`: convert existing gear; author a starter set of **named Uniques**.
- `components/equipment.py`: aggregate the new bonuses.
- Tests: equip/aggregate, a Unique, an accessory plus.

## Phase 6 — affix generator (procedural loot) *(needs Phase 5)*
- New `affixes.py`: **prefix**/**suffix** pools, a **rarity** roll (Plain/Fine/
  Rare), name assembly (`a keen longsword of warding`), full stat line **visible
  on pickup** (no ID).
- Integrate generation into loot tables / shop stock.
- Tests: generation determinism (seeded), name assembly, rarity distribution.

---

## Dependency map

```
1 ─→ 2 ─→ 3
     └─→ 4
1 ─→ 5 ─→ 6
```

Suggested PR/issue granularity: one issue per phase, splitting Phase 4 (model vs
the five Paths' content) and Phase 6 (pools vs integration) if they run large.
