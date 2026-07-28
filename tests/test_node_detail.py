"""The pure "what a point buys" framing shown on the Paths detail strip
(:func:`lonelands.perks.buy_summary`). Engine-free, so it unit-tests without a
display — the render wiring in ``input_handlers`` only positions the string."""
from __future__ import annotations

from lonelands import perks


def _passive(max_rank=3, cost=1):
    return perks.Node("n", "long_watch", "trunk", "Steady Endurance",
                      "…", cost=cost, tier=1, max_rank=max_rank)


def _active(cost=1):
    return perks.Node("a", "long_watch", "trunk", "Second Wind", "…",
                      cost=cost, tier=1, max_rank=1,
                      active=perks.ActiveSpec("Second Wind", "heal"))


def test_pathless_chooser_shows_only_the_price():
    node = _passive()
    assert perks.buy_summary(node, 0, committed=False, buyable=False) == "1pp"


def test_a_capstone_price_reads_two_points():
    cap = _passive(cost=2)
    assert perks.buy_summary(cap, 0, committed=False, buyable=False) == "2pp"


def test_a_first_buy_reads_buy_and_the_cost():
    node = _passive()
    assert perks.buy_summary(node, 0, committed=True, buyable=True) == "buy · 1pp"


def test_a_rank_up_shows_the_current_to_next_rank():
    node = _passive()
    assert perks.buy_summary(node, 1, committed=True, buyable=True) == "rank 1→2 · 1pp"


def test_an_exhausted_passive_reads_maxed():
    node = _passive(max_rank=3)
    assert perks.buy_summary(node, 3, committed=True, buyable=False) == "maxed"


def test_a_learned_active_reads_learned_not_maxed():
    node = _active()
    assert perks.buy_summary(node, 1, committed=True, buyable=False) == "learned"


def test_a_gated_node_shows_the_locked_reason():
    node = _passive()
    assert perks.buy_summary(node, 0, committed=True, buyable=False,
                             locked_reason="need 6 in Path") == "need 6 in Path"
