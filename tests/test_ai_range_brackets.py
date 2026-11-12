"""Firepower by range bracket (CLAUDE.md To do 8 f, owner): fleet vs fleet and
ship vs ship, measured on the real Gunnery table, so the AI can fight in the
bracket where its guns beat the enemy's."""
import math
from tests.conftest import make_gs
from src.models import Ship
from src.ship_catalog import find_ship_class
from src.ai_hazards import (bracket_matchup, fleet_bracket_table, best_bracket,
                            past_shields, nova_expected_hits, RANGE_BRACKETS)


def _ship(name, player, i=0):
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"{name[:4]}{player}{i}")
    d.update(leadership=8)
    return Ship.from_dict(d)


def _winning(matchup):
    return [br for br, ours, theirs in matchup if ours > theirs]


def test_merchant_outguns_a_lunar_only_at_30_45():
    """Owner's example: a Tau Merchant (6 battery points of 45cm railguns, all
    bearing forward) out-guns a Lunar (30cm broadsides and lances) at 30-45cm
    but not at 0-30cm."""
    m = bracket_matchup(_ship("Merchant Starship", 1), _ship("Lunar Class Cruiser", 2))
    assert _winning(m) == [(30.0, 45.0)]


def test_chaos_long_guns_hold_30_to_60_against_lunars():
    """Murder: 45cm batteries and 60cm prow lances; the Lunar can't reply past 30cm."""
    m = bracket_matchup(_ship("Murder Class Cruiser", 1), _ship("Lunar Class Cruiser", 2))
    assert _winning(m) == [(30.0, 45.0), (45.0, 60.0)]


def test_nova_cannon_is_the_artillery_bracket():
    """60-150cm is artillery: the Dominator's Nova Cannon (30cm minimum) is the
    only gun on either side that reaches it."""
    m = dict((br, (o, t)) for br, o, t in
             bracket_matchup(_ship("Dominator Class Cruiser", 1), _ship("Lunar Class Cruiser", 2)))
    assert m[(60.0, 150.0)][0] > 0 and m[(60.0, 150.0)][1] == 0
    lunar = _ship("Lunar Class Cruiser", 2)
    assert nova_expected_hits(20.0, lunar) == 0.0 and nova_expected_hits(200.0, lunar) == 0.0
    # a direct hit (1 in 3) is D6; further away the scatter grows, so less
    assert nova_expected_hits(40.0, lunar) > nova_expected_hits(100.0, lunar) > 3.5 / 3


def test_past_shields_counts_the_good_rolls():
    """Shields stop the first hits, but a ship averaging below its target's
    shields still gets some through: E[max(0, H - s)] for a Poisson H."""
    assert past_shields(3.0, 0) == 3.0
    lam, s = 1.0, 2
    exact = sum(max(0, k - s) * math.exp(-lam) * lam ** k / math.factorial(k)
                for k in range(40))
    assert abs(past_shields(lam, s) - exact) < 1e-9
    assert 0 < past_shields(1.0, 2) < max(0.0, 1.0 - 2) + 0.2


def test_fleet_table_and_best_bracket():
    """Three Merchants against two Lunars: the fleet's best bracket is 30-45cm
    (the Lunars can't reply), though up close the Lunars win."""
    gs = make_gs([_ship("Merchant Starship", 1, i) for i in range(3)]
                 + [_ship("Lunar Class Cruiser", 2, i) for i in range(2)])
    table = fleet_bracket_table(gs, 1)
    assert [br for br, _o, _t in table] == list(RANGE_BRACKETS)
    assert best_bracket(table) == (30.0, 45.0)
    close = table[0]
    assert close[2] > close[1]
