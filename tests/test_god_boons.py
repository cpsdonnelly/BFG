"""Chaos god-fleet boons (To do 4): Veil of Lust, Siren's Summon, Miasma of
Pestilence (gunnery), Plague Arks."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import get_column_shifts
from src.fleet_lists import option_allowed


def test_veil_and_miasma_shifts():
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    veil = make_ship(id="v", player=2, x=20.0, y=0.0, special_rules=["veil_of_lust"])
    plain = make_ship(id="p", player=2, x=20.0, y=0.0)
    assert get_column_shifts(a, veil, []) == get_column_shifts(a, plain, []) + 1
    close = make_ship(id="c", player=2, x=10.0, y=0.0, special_rules=["miasma"])
    assert get_column_shifts(a, close, []) == 0          # no left shift within 15cm


def test_sirens_summon_blocks_orders_nearby():
    from src.movement import do_command_check
    siren = make_ship(id="s", player=2, x=10.0, y=0.0, special_rules=["sirens_summon"])
    me = make_ship(id="m", player=1, x=0.0, y=0.0, leadership=10)
    gs = make_gs([me, siren])
    assert not do_command_check(me, "lock_on", DiceStub([]), gs=gs)["passed"]
    far = make_gs([me, make_ship(id="s", player=2, x=40.0, special_rules=["sirens_summon"])])
    assert do_command_check(me, "lock_on", DiceStub([2]), gs=far)["passed"]


def test_plague_ark_gives_a_fire_critical_in_boarding():
    from src.boarding import resolve_boarding
    ark = make_ship(id="a", player=1, hits_max=8, special_rules=["plague_ark"])
    foe = make_ship(id="t", player=2, hits_max=8, turrets=0)
    gs = make_gs([ark, foe])
    resolve_boarding([gs.get_ship_by_id("a")], gs.get_ship_by_id("t"),
                     DiceStub([3, 3] + [1] * 10), gs)
    assert any(c["crit_type"] == "fire" for c in gs.get_ship_by_id("t").critical_damage)


def test_boons_only_in_their_god_fleet():
    assert option_allowed("Boon of Slaanesh: Veil of Lust", ["chaos_slaanesh"])
    assert not option_allowed("Boon of Slaanesh: Veil of Lust", ["chaos_incursion"])
