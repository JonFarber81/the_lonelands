# Loot drops and a coin-driven economy on item Value

Routine foes gave no reward at all: they grant no experience (by design —
advancement is the quests' job), and until now coins were literally unearnable
(the purse started at 15 and could only ever be *spent* at Bree's buy-only shop).
We add a **material** reward loop — foes drop **loot** (coins into the purse,
trade-goods onto the corpse tile) which the hero hauls back to Bree and **sells**
— and in doing so establish how prices work across the whole game.

## Decisions

- **Prices live on the item, as one `Value`.** Every item carries a base worth in
  coins; `Value == 0` means "not sellable". A merchant **sells** an item to the
  hero at its Value and **buys** it back at `floor(Value × SELL_FRACTION)` (a
  single global constant, 0.5) — so he always pays less than he charges. This
  **replaces** the parallel price list that lived in the shop's `stock` tuples:
  Halbarad's stock becomes item references, and every merchant derives both
  directions from Value. *Rejected:* explicit per-item `buy_price`/`sell_price`
  (two authored numbers per item, a second drift source) — an optional per-item
  override can be added later if one item ever needs a bespoke spread.
- **Coins are purse-only; trade-goods are items.** A slain humanoid adds coins
  straight to the purse (money is never a floor entity). A slain beast drops a
  **pelt**/curio onto its corpse tile, taken with the existing pickup action —
  reusing `spawn()` + `PickupAction` and preserving the "stop and skin the wolf,
  or leave it" choice. *Rejected:* auto-adding drops to inventory (bypasses the
  capacity check and removes the choice).
- **Loot is template-driven.** Each creature carries a **loot table** resolved in
  the non-player branch of `Fighter.die()`; a creature drops the same table
  wherever it dies. Encounter *pacing* is already handled upstream by which
  creatures spawn where (`monsters_for_depth`, `BAND_BEASTS`), so danger and
  reward gradients align for free without threading location into `die()`.
- **A loot table is one-or-more independent weighted rolls**, each including a
  "nothing" slice; a single kill may resolve several (coins *and* a trophy). This
  mirrors the existing `(template, weight)` idiom in `content.py`.
- **Fungible items stack; equipment never does.** Trade-goods and consumables
  carry a `stackable` flag (fungible, no per-instance state) and occupy one slot
  as a counted stack; equipment (distinct instances with equipped state) stays
  one-per-slot. This is a real extension to the inventory model (a `quantity`
  concept, merge-on-pickup, `×N` rendering, sell-from-stack).
- **One merchant, a Buy/Sell toggle.** Halbarad's `ShopHandler` grows a sell mode
  listing the hero's `Value > 0` items (Enter sells one, Shift+Enter the stack),
  rather than adding a dedicated furrier NPC. A specialised buyer is deferred
  flavour.

## Consequences

- `Item` gains a `Value` field and a `stackable` flag; `Inventory` gains stacking
  (merge, count, split-on-sell). The shop's `stock` stops carrying prices.
- Every existing item needs a Value assigned; the current shop prices seed the
  gear/consumable Values so buy prices are unchanged.
- New trade-good templates (wolf-pelt, warg-pelt, spider-silk, orc-trophy,
  wolf-fang) and per-creature loot tables live beside the `_beast` definitions in
  `content.py`. The barrow-wight keeps its XP and additionally drops a grave-hoard
  of coins.

## Status

Accepted; not yet implemented (build spec: issue #31). Terms recorded in
`CONTEXT.md` (Trade & loot).
