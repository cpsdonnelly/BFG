"""Ork kustom force fields, the Onslaught's zzapp gun and looted vessels
(11_orks.md)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import get_ship_class
from src.models import Ship
from src.orks import loot, roll_force_fields, own_goal, looted_errors
from src.movement import do_command_check


def test_kustom_force_field_trades_a_shield_for_d3():
    e = get_ship_class("orks", "Basha Lite Kroozer")
    s = Ship.from_dict(e.to_ship_dict("B", 1, ship_id="B", upgrades=["Kustom force field"]))
    assert s.shields_max == e.shields_max - 1 and s.points_value == 125
    gs = make_gs([s])
    roll_force_fields(gs, DiceStub([3]))
    assert gs.get_ship_by_id("B").effective_shields == e.shields_max - 1 + 3


def test_onslaught_zzapp_gun_swap():
    e = get_ship_class("orks", "Onslaught Attack Ship")
    d = e.to_ship_dict("O", 1, upgrades=["Zzapp gun (gunz to FP2)"])
    gunz = next(w for w in d["weapons"] if w["name"] == "Gunz")
    zz = next(w for w in d["weapons"] if w["weapon_type"] == "lance")
    assert gunz["strength"] == 2 and not gunz.get("strength_dice")
    assert zz["hits_on"] == 5 and zz["strength"] == 1


def test_looted_dominator():
    dom = get_ship_class("imperial_navy_gothic", "Dominator Cruiser")
    d = loot(dom.to_ship_dict("D", 1))
    kinds = [w["weapon_type"] for w in d["weapons"]]
    assert "nova_cannon" not in kinds and any(w["name"] == "Prow Killkannon" for w in d["weapons"])
    assert d["leadership_table"] == "Orks" and "looted" in d["special_rules"]
    assert "ork_turrets" in d["special_rules"]
    lunar = get_ship_class("imperial_navy_gothic", "Lunar Cruiser")
    ld = loot(lunar.to_ship_dict("L", 1))
    assert all(w.get("hits_on") == 5 for w in ld["weapons"] if w["weapon_type"] == "lance")
    rows = [{"entry": get_ship_class("imperial_navy_gothic", "Firestorm Frigate"),
             "upgrades": [], "list": "reserve:navy_gothic"}]
    assert looted_errors(rows)


def test_looted_ship_damages_itself_on_a_failed_test():
    s = make_ship(id="L", hits_max=8, special_rules=["looted"], leadership=6)
    gs = make_gs([s])
    dice = DiceStub([11, 2, 3])              # fails the check, then 2: 1 damage; its crit check
    do_command_check(gs.get_ship_by_id("L"), "lock_on", dice, gs=gs)
    assert dice._idx == 3 and gs.get_ship_by_id("L").hits_remaining == 7
    assert not own_goal(gs.get_ship_by_id("L"), DiceStub([5]), gs)
