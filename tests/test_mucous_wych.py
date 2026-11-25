"""Tyranid Mucous Membrane (assault boats -1 to raids, bombers -1 attack,
torpedoes Armour +1) and the Dark Eldar Wych Cult's boarding modifier
(enemy capital ships count as crippled)."""
from tests.conftest import make_ship, make_gs, make_marker, DiceStub
from src.hit_and_run import _raid_roll_modifier, ASSAULT_BOAT_RAID
from src.boarding import _get_ship_modifier
from src.ordnance import resolve_bomber_attack, resolve_torpedo_attack


def test_mucous_raids_assault_boats_only():
    t = make_ship(id="t", special_rules=["tyranid", "mucous_membrane"])
    assert _raid_roll_modifier([ASSAULT_BOAT_RAID], t) == -2      # Tyranid -1 and mucous -1
    assert _raid_roll_modifier([], t) == -1                       # a teleport: Tyranid only


def test_mucous_bombers_one_attack_fewer():
    t = make_ship(id="t", player=2, turrets=0, special_rules=["tyranid", "mucous_membrane"])
    gs = make_gs([t])
    b = make_marker(id="b", ordnance_type="bomber", owner_player=1, strength=1)
    dice = DiceStub([4, 6, 6, 6])                  # D6 4 attacks -> 3, three hits rolled
    res = resolve_bomber_attack(b, gs.get_ship_by_id("t"), dice, gs)
    assert res["attacks"] == 3                     # D6 4 - 0 turrets - 1 mucous


def test_mucous_torpedoes_armour_plus_one():
    t = make_ship(id="t", player=2, x=50.0, y=50.0, turrets=0,
                  special_rules=["tyranid", "mucous_membrane"])
    gs = make_gs([t])
    m = make_marker(id="m", owner_player=1, x=50.0, y=40.0, heading=90.0, strength=2)
    dice = DiceStub([5, 6])                         # 5+ armour becomes 6+: one hit
    res = resolve_torpedo_attack(m, gs.get_ship_by_id("t"), dice, gs)
    assert res["hits"] == 1


def test_wych_cult_counts_capital_ships_as_crippled_for_boarding():
    cruiser = make_ship(id="c", ship_type="cruiser")
    escort = make_ship(id="e", ship_type="escort")
    gs = make_gs([cruiser, escort])
    wych = ["dark_eldar", "wych_cult"]
    assert _get_ship_modifier(cruiser, gs, wych) - _get_ship_modifier(cruiser, gs) == 2
    assert _get_ship_modifier(escort, gs, wych) == _get_ship_modifier(escort, gs)
