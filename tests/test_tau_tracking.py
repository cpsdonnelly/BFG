"""Tau Tracking Systems (Tau faction rules): any Tau vessel within 10cm of a
ship with tracking systems (20cm for the Custodian / Orbital City) re-rolls
missed turret attacks and ignores the right shift for gunnery beyond 30cm."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.ordnance import turret_dice, turret_reroll, turret_kill_p
from src.combat import get_column_shifts


def test_catalog_reads_tracking_systems_from_the_notes():
    rules = {n: [r for r in find_ship_class(n).special_rules if r.startswith("tracking")]
             for n in ("Messenger Starship", "Custodian Battleship", "Tau Orbital City",
                       "Hero Starship", "Protector Cruiser")}
    assert rules == {"Messenger Starship": ["tracking_systems_10"],
                     "Custodian Battleship": ["tracking_systems_20"],
                     "Tau Orbital City": ["tracking_systems_20"],
                     "Hero Starship": [], "Protector Cruiser": []}


def _scene(dist):
    src = make_ship(id="m", player=1, x=0.0, y=0.0, faction="tau_kororvesh",
                    special_rules=["tracking_systems_10"])
    tau = make_ship(id="t", player=1, x=dist, y=0.0, faction="tau_kororvesh", turrets=2)
    navy = make_ship(id="n", player=1, x=0.0, y=dist, faction="imperial_navy_gothic", turrets=2)
    return make_gs([src, tau, navy])


def test_turret_misses_rerolled_only_for_tau_in_range():
    gs = _scene(8.0)
    tau, navy = gs.get_ship_by_id("t"), gs.get_ship_by_id("n")
    assert turret_reroll(tau, gs) and not turret_reroll(navy, gs)
    dice = DiceStub([2, 5, 4])                       # a miss and a hit, the miss re-rolled
    assert sorted(turret_dice(dice, tau, 2, 4, "t", gs)) == [4, 5] and dice._idx == 3
    assert abs(turret_kill_p(tau, 4, gs) - 0.75) < 1e-12
    assert not turret_reroll(_scene(12.0).get_ship_by_id("t"), _scene(12.0))


def test_no_long_range_shift_near_tracking_systems():
    gs = _scene(8.0)
    tau = gs.get_ship_by_id("t")
    far = make_ship(id="e", player=2, x=8.0, y=40.0)
    navy = gs.get_ship_by_id("n")
    ships = gs.ships + [far.to_dict()]
    assert get_column_shifts(tau, far, [], [], ships) == 0     # 40cm: shift cancelled
    assert get_column_shifts(navy, far, [], [], ships) == 1    # not a Tau vessel
