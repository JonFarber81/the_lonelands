# Wandering threats: a three-kind band blend, and roads made safer

Wandering threats are now grouped into three **kinds** — **Brigand**, **Wild
animal**, **Monster** — and each **band** is a *blend* of them rather than one
flat beast table, so the danger gradient reads by composition and not just count:
Free is animals-and-a-lone-footpad, Wild is brigands-and-animals with monsters
*rare*, Dark/Perilous are monster country. This fixes great spiders and orcs
turning up on Bree's doorstep, which came from Wild band listing monsters
outright.

Roads are made safer by a **radius-4 keep-away buffer**: wild animals and
monsters do not spawn within it, in every band. **Brigands are the deliberate
exception** — they are biased *toward* the road, because highwaymen work where
the travellers are. So the road trades the danger of beasts for the danger of
ambush; it is safer, and in the Dark only *safer*, never *safe*. A future reader
will see brigands hugging the very tiles other threats avoid and may read it as a
bug — it is intentional.

## Considered options

- **Whole-Region spawn discount for road cells** (rejected): a road on the far
  side of a Region would magically calm the whole cell, which reads oddly. The
  spatial buffer is honest — safety follows the road, tile by tile.
- **No monsters in Wild at all** (rejected): crisper as a rule, but it makes the
  wilds feel tame and gamey. Keeping monsters rare-but-present preserves the
  Middle-earth mood that the wild is never truly safe.
- **Re-drawing the band map around Bree** (deferred): the tables + buffer do the
  work without lore-fudging the geography; a band-map pass can come later if the
  doorstep still feels off.
