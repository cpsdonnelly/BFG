"""Ships with three Armour values use front / abeam / rear (Ork faction rules),
by the quadrant the attack comes from (s.9 bearing compass)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import resolve_batteries
from src.models import OrdnanceMarker, OrdnanceType
from src.ordnance import resolve_torpedo_attack
from src.ship_catalog import find_ship_class


def _kroozer(**kw):
    base = dict(id="k", player=2, x=50.0, y=50.0, heading=0.0, hits_max=10,
                shields_max=0, turrets=0, armor_prow="6+", armor_side="5+",
                armor_rear="4+")
    base.update(kw)
    return make_ship(**base)


def test_armour_by_quadrant():
    k = _kroozer()
    assert k.armor_vs(60.0, 50.0) == 6     # front
    assert k.armor_vs(50.0, 60.0) == 5     # left
    assert k.armor_vs(50.0, 40.0) == 5     # right
    assert k.armor_vs(40.0, 50.0) == 4     # rear
    assert k.lowest_armor_value == 4


def test_two_value_ships_use_side_armour_from_the_rear():
    g = make_ship(x=50.0, y=50.0, heading=0.0, armor_prow="6+", armor_side="5+")
    assert g.armor_vs(40.0, 50.0) == 5 and g.lowest_armor_value == 5


def test_catalog_three_value_armour():
    kk = find_ship_class("Kill Kroozer")
    assert (kk.armor_prow, kk.armor_side, kk.armor_rear) == ("6+", "5+", "4+")
    assert kk.playable
    d = kk.to_ship_dict("Kill", 1)
    assert d["armor_rear"] == "4+"
    assert find_ship_class("Gothic Cruiser").armor_rear == ""


def test_batteries_from_behind_hit_on_rear_armour():
    gun = {"name": "Gunz", "weapon_type": "battery", "strength": 2, "range_cm": 30,
           "arcs": ["front"]}
    attacker = make_ship(id="a", player=1, x=30.0, y=50.0, heading=0.0, weapons=[gun])
    k = _kroozer()
    from src.tables import lookup_gunnery_dice, get_gunnery_column
    n = lookup_gunnery_dice(2, get_gunnery_column("capital",
                            attacker.get_target_orientation(k)), 0)
    rolls = [4] * n
    dice = DiceStub(rolls)
    r = resolve_batteries(attacker, k, gun, dice, [])
    assert dice._idx == n and r.hits == n          # 4s hit the 4+ rear armour


def test_torpedoes_from_behind_use_rear_armour():
    k = _kroozer()
    gs = make_gs([k])
    torp = OrdnanceMarker(id="t", ordnance_type=OrdnanceType.TORPEDO_STANDARD.value,
                          owner_player=1, launched_by="a", x=46.0, y=50.0, heading=0.0,
                          strength=2)
    rolls = [4, 3,          # vs rear 4+: one hit
             1]             # crit check for that hit
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(torp, k, dice, gs)
    assert dice._idx == len(rolls) and r["hits"] == 1
