# Stealth, awareness, and the ambush gate

## Status

accepted

## Context

The Hidden Path is named for stealth, and three channels already carried a
**Stealth** number — Silent Tread's `stealth_bonus` on perk Nodes, the
`stealth_bonus` on equippables (the *gleaming* affix), and the character sheet's
promise that *Wits* governs stealth — but **nothing consumed any of it**. Enemy
"spotting" was purely the player's FOV: `HostileEnemy` chased whenever its own
tile fell in the player's visible map. There was no perception, no awareness
state, and no way to *strike from the shadows* except the abstract "opening blow"
ambush. We wanted a real sneak layer: a stance you toggle, foes that can fail to
notice you, and a big payoff for the unseen strike.

## Decision

**A global sneak stance with per-enemy awareness.** One key (`s`) toggles a free
sneak **stance** (no turn cost — it is a stance, not an action). While sneaking,
each hostile and beast independently decides whether it notices you; townsfolk
are exempt. An enemy carries an **awareness** state that can rise *and* fall.

**Detection is deterministic, not rolled.** Each enemy has a base **perception**
radius (hostiles 8, beasts 4); your **Stealth** score (`Wits mod + Silent Tread
+ gear stealth_bonus`, no floor — negative Stealth is allowed) subtracts from it:
`effective perception = base − Stealth`, and it only fires with line of sight. We
chose deterministic over per-turn checks so the player can *read the board and
plan a route*; it also makes Silent Tread legible (each rank pulls enemy vision
in by 2 tiles). There is **no adjacency floor** — a sufficiently stealthy Ranger
can stand next to a foe unseen. This is deliberate: an adjacency floor would make
the melee sneak-kill unreachable, gutting the whole payoff.

**De-escalation via timed decay.** Losing line of sight or slipping outside the
effective perception radius does not instantly reset awareness. The enemy hunts
your **last-known** tile for `max(2, 5 − Stealth)` turns (better sneaks shake
pursuers faster), then falls back to idle. Re-detection resets the timer.

**Stealth is the gate for Ambush.** Ambush (advantage + bonus damage, keyed by
Deathblow's +6, etc.) now requires the target to be **Unaware** — the free
"strike a *fresh* foe" opener is removed. Striking an unaware foe reuses the
existing ambush machinery (it primes a sure ambush), so the entire Silent Tread →
Ambush → Deathblow trunk pays off through the stealth layer with no new combat
math, and — because you can re-hide — ambush becomes *repeatable* within a fight
rather than a one-shot opener. Attacking always alerts the struck target and any
enemy with line of sight to the fight; witnesses out of sight stay oblivious (a
noise radius is a deliberate future extension).

**v1 cost is narrowed senses.** Sneaking cuts the player's FOV radius by roughly
a third (20→13 outdoors, 8→5 indoors) — a real trade-off with no change to the
strict 1:1 turn loop. True **half-speed** movement (a sneak-step yields a tick,
so pursuers close on a crouched Ranger) is the intended primary cost and is
deferred to a follow-up ADR, because it requires changing the turn loop.

## Considered alternatives

- **Per-turn stealth checks** (dice) instead of a deterministic radius — rejected
  for legibility; a planned sneak should not be undone by a bad roll.
- **Keep the fresh-opener ambush alongside stealth** — rejected; it left stealth
  without a distinct identity. Making Unaware the sole gate (plus primed actives)
  means "Ambush" literally means *unseen*. **Primed** ambushes (Shadowstep,
  Vanish) still bypass awareness by design — they spend an active to manufacture
  a sure ambush against any foe.
- **Half-speed as the v1 cost** — the best mechanic, but it forces a turn-loop
  change we did not want to bundle into the first cut; deferred, not dropped.
- **Instant de-escalation** — rejected as amnesiac and making escape trivial.

## Consequences

- Existing `resolve_ambush` behaviour and its tests change: the `fresh + owns-node`
  path is replaced by an `Unaware` (or primed) gate.
- Enemies gain an awareness state + last-known tile; `SkittishBeast`'s existing
  `distance <= 4` folds into the perception model.
- The UI must surface the state — a HUD sneak indicator and `!`/`?` markers for
  Alerted/Searching foes — in **both** ASCII and sprite modes, or the
  deterministic model feels as random as dice.
