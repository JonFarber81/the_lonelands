# Context & Ubiquitous Language

The shared vocabulary of The Lonelands. Terms here are the canonical names —
use them in code, comments, UI copy, and conversation. This file is a glossary,
not a spec: it defines *what words mean*, never *how things are built*.

## The One Ring dice

- **Test** — a single roll resolving an action: one Feat die plus zero or more
  Success dice, summed and compared to a Target Number.
- **Feat die** — the d12 rolled on every Test. Two faces are magic:
  - **Eye of Sauron** — the 11 face. Counts as 0 and invites ill fortune.
  - **Gandalf rune** — the 12 face. An automatic success regardless of TN.
- **Success die** — a d6. A Test rolls one per point of skill/proficiency
  **rank**. Its 6 face is special:
  - **Tengwar** — the rune on a Success die's 6 face; a great-success marker.
    "Tengwar count" is how many 6s a Test rolled.
- **Target Number (TN)** — the value a Test's total must reach to succeed.
- **Rank** — the number of Success dice a Test rolls.

## Test outcomes

- **Success / failure** — total meets the TN (or the Gandalf rune shows).
- **Great success** — a success carrying at least one Tengwar (or the Gandalf
  rune).
- **Extraordinary success** — a success carrying two or more Tengwar.

## Conditions on a Test

- **Favoured / ill-favoured** — roll two Feat dice, keep the higher / lower.
- **Weary** — Success dice showing 1–3 count as 0.

## Presentation

- **Dice tray** — the fixed, single-row panel pinned to the top of the
  bottom-left (log) pane. It shows the player's **latest** Test rendered as
  die-face glyphs: the Feat die, each Success die, the total vs the TN, and the
  outcome. It only ever reflects the *player's* rolls, never an enemy's. The
  scrolling **message log** beneath it carries pure narrative prose with no dice
  math — the tray is the sole home for the numbers.
