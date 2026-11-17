"""Alternate activation core (To do 13): the notes' check values for the
edge-share formula, a Monte Carlo of the bag, initiative and the band table."""
import random
from tests.conftest import make_ship, make_gs
from src.activation import (edge_share, Bag, units, initiative, fleet_mean, edge, band,
                            fixed_order, AAConfig, Unit)

CHECKS = [((5, 6), 0, False, 0.00), ((5, 6), 1, False, 0.14), ((5, 6), 2, False, 0.25),
          ((5, 6), 3, False, 0.33), ((5, 6), 0, True, 0.20), ((5, 6), 1, True, 0.33),
          ((5, 6), 3, True, 0.50), ((10, 12), 5, False, 0.31), ((15, 18), 8, False, 0.33)]


def test_edge_share_check_values():
    for (ne, ni), k, choice, want in CHECKS:
        assert abs(edge_share(ne, ni, k, choice) - want) < 0.006, ((ne, ni), k, choice)


def _mc(ne, ni, k, choice, n=20000, seed=1):
    rng = random.Random(seed)
    first = 0
    for _ in range(n):
        bag = Bag({1: ne, 2: ni}, {1: k}, rng=rng)
        order = []
        if choice:
            bag.take_first(1)
            order.append(1)
        while not bag.empty():
            p = bag.draw()
            if bag.activate(p):
                order.append(p)
        seen_i = 0
        for p in order:          # each edge unit precedes the opponents not yet seen
            if p == 1:
                first += ni - seen_i
            else:
                seen_i += 1
    return 2 * first / (n * ne * ni) - 1


def test_bag_monte_carlo_matches_the_formula():
    for (ne, ni), k, choice, want in CHECKS[:7]:
        assert abs(_mc(ne, ni, k, choice) - want) < 0.02, ((ne, ni), k, choice)


def test_initiative_units_and_bands():
    ships = [make_ship(id="c", player=1, leadership=8, hits_max=8),
             make_ship(id="e1", player=1, ship_type="escort", squadron_id="sq", leadership=7,
                       hits_max=1),
             make_ship(id="e2", player=1, ship_type="escort", squadron_id="sq", leadership=7,
                       hits_max=1),
             make_ship(id="b", player=2, leadership=7, hits_max=12)]
    gs = make_gs(ships)
    us = units(gs, 1)
    assert sorted(initiative(u) for u in us) == [10, 15]      # 8-8+10, 7-2+10
    assert fleet_mean(us) == 12.5
    assert edge(gs) == (1, 7.5)
    assert band(0.4, 5) == (False, 0) and band(1.0, 5) == (True, 0)
    assert band(2.0, 5) == (True, 2) and band(3.0, 5) == (True, 3)
    cfg = AAConfig(bands=[(1.0, True, None)])
    assert band(0.6, 5, cfg) == (False, 0)


def test_fixed_order_shooting_high_first_movement_inverse():
    a = Unit(1, ["a"], 9, 6)      # 13
    b = Unit(2, ["b"], 7, 8)      # 9
    c = Unit(2, ["c"], 8, 6)      # 12
    shoot = [u.key for u in fixed_order([a, b, c], "shooting", abfg=False)]
    assert shoot == ["a", "c", "b"]
    assert [u.key for u in fixed_order([a, b, c], "movement", abfg=False)] == ["b", "c", "a"]
