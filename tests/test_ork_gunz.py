"""Ork Gunz are macrobatteries; Heavy Gunz use their bracketed firepower
within 15cm (Ork faction rules)."""
from tests.conftest import make_ship, DiceStub
from src.combat import effective_battery_firepower, resolve_batteries
from src.ship_catalog import find_ship_class
from src.tables import lookup_gunnery_dice, get_gunnery_column

HEAVY = {"name": "Heavy Gunz", "weapon_type": "battery", "strength": 6,
         "strength_close": 10, "range_cm": 30, "arcs": ["front", "left", "right"]}


def test_catalog_gunz_are_batteries():
    grunt = find_ship_class("Grunt Assault Ship")
    assert grunt.playable
    assert [(w["name"], w["weapon_type"], w["strength"]) for w in grunt.weapons] == [
        ("Gunz", "battery", 2)]


def test_catalog_heavy_gunz_keep_both_values():
    savage = find_ship_class("Savage Gunship")
    assert savage.playable
    w = savage.weapons[0]
    assert (w["weapon_type"], w["strength"], w["strength_close"]) == ("battery", 2, 6)


def _pair(dist):
    attacker = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, weapons=[HEAVY])
    target = make_ship(id="t", player=2, x=dist, y=0.0, heading=90.0)
    return attacker, target


def test_heavy_gunz_firepower_by_range():
    a, near = _pair(14.0)
    assert effective_battery_firepower(a, HEAVY, near) == 10
    a, far = _pair(15.0)
    assert effective_battery_firepower(a, HEAVY, far) == 6
    assert effective_battery_firepower(a, HEAVY) == 6      # no target: printed value


def test_heavy_gunz_close_value_is_halved_like_any_firepower():
    a, near = _pair(10.0)
    a.special_order = "brace_for_impact"
    assert effective_battery_firepower(a, HEAVY, near) == 5


def test_heavy_gunz_roll_close_firepower_within_15cm():
    a, near = _pair(10.0)
    col = get_gunnery_column("capital", a.get_target_orientation(near))
    n = lookup_gunnery_dice(10, col, -1)          # FP10, <15cm left shift
    rolls = [1] * n
    dice = DiceStub(rolls)
    r = resolve_batteries(a, near, HEAVY, dice, [])
    assert dice._idx == n and len(r.dice_rolled) == n
