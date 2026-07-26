# Ranged combat: bows, arrows, and lock-on targeting

The d20 combat core (ADR 0005) shipped melee-only: bumping a foe swings the
weapon in the `weapon` slot. The scaffolding for ranged was authored ahead of
time — a dedicated `ranged` equipment slot, an `Equippable.ranged` flag, the Far
Shot Path with `ranged_bonus`/`ranged_damage_bonus` perk fields — but **nothing
read it** (marked `TODO(ranged)`). This ADR records the design that brings it to
life as a distinct style of fighting, not a reskinned melee attack.

## Decisions

- **A Shot is a parallel attack path, keyed off Wits.** Ranged reuses the d20
  core (`d20 + bonus vs Defence`, Crit on a natural 20, Fumble on a 1) but
  composes its bonus from **Wits** (not Brawn), the shared level to-hit, the Far
  Shot perk fields, and the bow's `+hit`. Melee's `Fighter.attack_bonus`/`damage`
  keep reading only the `weapon` slot; ranged gets its own derived numbers off the
  `ranged` slot. A Shot's Critical hits and adds damage but opens **no Bleed** —
  Bleed stays a melee/heavy-foe signature, so the two styles *feel* different.

- **Bow and melee weapon are wielded at once; the action picks the weapon.**
  The `ranged` slot is independent of `weapon`, so both stay equipped. Bump =
  melee; `f` = ranged. No swap step — the melee-vs-ranged decision is live every
  turn. *Rejected:* one active weapon at a time (a mid-fight swap dance for no
  gain).

- **Lock-on targeting.** `f` enters a firing mode with the **nearest visible foe**
  pre-selected; `Tab`/move-keys cycle visible foes; `f`/`Enter` looses; `Esc`
  cancels. A target must be in **FOV with a clear line**. *Rejected:* a fixed
  directional shot (blind to off-axis foes, against the "lock onto nearest"
  instinct) and a free look-cursor (more keystrokes, no benefit here). There is no
  prior targeting UI in the game — this is the first, and a future "look" mode can
  reuse it.

- **Range matters: a per-bow effective range, then falloff.** Each bow carries an
  `effective_range` (shortbow 4, longbow 6); within it a Shot takes no penalty,
  beyond it accuracy drops **−1 per 3 tiles**, folded into the roll. A Shot with a
  foe **adjacent** is at **Disadvantage**. Together these give a bow a short-to-
  medium **sweet spot** — bad point-blank, best at range, a gamble at extreme
  range (FOV reaches 20 tiles outdoors). This finally gives the Far Shot Path
  literal meaning: its flat bonuses offset the falloff and the Deadeye capstone
  ("no range is too far") extends reliable reach. *Rejected:* a single global
  effective range (bows should differ) and no falloff at all (a 20-tile headshot
  at full accuracy is absurd). No hard range cap — FOV is the cap.

- **Arrows are a finite, partly-recoverable resource.** A Shot spends one **Arrow**
  (a consumable Stack); an empty quiver refuses to fire. This is the counterweight
  that keeps ranged from being a strict upgrade over melee — infinite free ranged
  damage would flatten the choice. **50%** of spent arrows are recoverable (drop
  on the target tile, picked up with `g`); the recovery rate is a deliberate future
  perk lever. *Rejected:* no ammo (ranged becomes strictly better than melee) and
  full recovery (no economy). Uses existing machinery — the Stack/inventory model,
  the shop (a Bree fletcher stocks arrows + the longbow), and loot tables.

- **Ambush applies to a Shot, via a shared helper.** The Hidden Path ambush
  (advantage + bonus damage on the opening strike against a fresh foe) is lifted
  out of `MeleeAction` into a helper both attack flows call. Ambush is a *Hidden
  Path* mechanic, not a melee one — the unseen shaft from the treeline is its
  purest form — and letting Far Shot + Hidden Path combine honours the "blend
  freely across Paths" promise.

## Scope

Player-only for this cut. **Enemy archers** (foes that shoot, needing kiting AI)
are a deliberate fast-follow, not part of v1.

## Consequences

- A second combat code path (ranged) now parallels melee. The two must be kept in
  step for shared concerns (Crit, level to-hit, ambush) — hence the shared ambush
  helper rather than duplicated logic.
- An **Arrow** is both a Stack in the pack *and* a droppable ground item; the loot
  and pickup systems already handle both, so no new machinery — but it is the first
  item that lives in both worlds routinely.
- `effective_range` becomes a new bow stat that affixes/Uniques can push (a bow
  *of the far mark*), and the range falloff becomes a natural target for a future
  Far Shot "reduce falloff" perk field.
