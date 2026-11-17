"""Imperial Navy profile refits (bfgxr/rules/01_imperial-navy.md roster notes)."""
from tests.conftest import make_gs, make_ship, DiceStub
from src.ship_catalog import find_ship_class
from src.booklet_options import ship_option_errors
from src.models import Ship


def build(cls, upgrades):
    d = find_ship_class(cls).to_ship_dict(name="x", player=1, upgrades=upgrades)
    return d


def weapons(d):
    return [(w["name"], w["range_cm"], w["strength"]) for w in d["weapons"]]


def test_lunar_swaps_torpedoes_for_a_nova_cannon_and_loses_torpedo_types():
    d = build("Lunar Cruiser", ["Refit: prow nova cannon for the torpedoes"])
    assert d["points_value"] == 200
    assert [w["weapon_type"] for w in d["weapons"]].count("nova_cannon") == 1
    assert not any(w["weapon_type"] == "torpedo" for w in d["weapons"])
    lunar = find_ship_class("Lunar Cruiser")
    assert ship_option_errors(lunar, ["Refit: prow nova cannon for the torpedoes",
                                      "Torpedoes: guided (turn 45° on a Leadership test)"])


def test_mercury_changes_only_its_45cm_macrobatteries():
    d = build("Mercury Battlecruiser", ["Refit: 45cm macrobatteries to 60cm"])
    assert ("Port Macrobatteries", 60, 4) in weapons(d) and ("Port Macrobatteries", 60, 6) in weapons(d)
    assert not any(r == 45 for _, r, _ in weapons(d))
    assert "catastrophic_3d6" in d["special_rules"]


def test_victory_torpedo_types_need_the_torpedo_refit():
    v = find_ship_class("Victory Battleship")
    guided = "Torpedoes: guided (turn 45° on a Leadership test)"
    assert ship_option_errors(v, [guided])
    assert not ship_option_errors(v, [guided, "Refit: prow torpedoes (S9) for the nova cannon"])
    assert next(u for u in v.upgrades_available if u.name == guided).points_cost == 45


def test_grand_cruiser_buys_one_refit_and_prow_torps_lose_ablative_armour():
    ex = find_ship_class("Exorcist Grand Cruiser")
    assert ship_option_errors(ex, ["Refit: Prow Torps (S6)", "Refit: Improved Thrusters"])
    d = build("Exorcist Grand Cruiser", ["Refit: Prow Torps (S6)", "Refit: macrobatteries 30cm FP10",
                                         "Attack craft: assault boats"])
    assert "ablative_prow_armor" not in d["special_rules"]
    assert ("Port Macrobatteries", 30, 10) in weapons(d)
    bays = [w for w in d["weapons"] if w["weapon_type"] == "launch_bay"]
    assert all(len(b["craft_types"]) == 3 for b in bays)
    assert d["points_value"] == 260 + 25 + 5


def test_mars_refits():
    d = build("Mars Battlecruiser", ["Refit: Targeting Matrix", "Refit: Extra Turrets (2 to 3)"])
    assert d["turrets"] == 3 and "targeting_matrix" in d["special_rules"]


def test_sensors_and_comms_uplink_add_one_ld_after_the_roll_max_10():
    from src.fleet_loader import roll_starting_leadership
    from src.booklet_ships import LEADERSHIP_TABLES
    a = make_ship(id="a", player=1, special_rules=["ld_always:1"])
    b = make_ship(id="b", player=1, special_rules=["ld_always:1"])
    gs = make_gs([a, b])
    gs.ships[0]["leadership_table"] = "Default"
    gs.ships[1]["leadership_table"], gs.ships[1]["leadership"] = "", 10   # a Solar Admiral
    dice = DiceStub([2])
    roll_starting_leadership(gs, dice)
    assert dice._idx == 1
    assert gs.ships[0]["leadership"] == min(10, LEADERSHIP_TABLES["Default"][1] + 1)
    assert gs.ships[1]["leadership"] == 10
    assert "ld_always:1" in find_ship_class("Emperor Battleship").special_rules


def test_cobra_sensor_array_gives_plus_two_for_enemy_contacts():
    from src.movement import do_command_check
    s = make_ship(leadership=7, special_rules=["improved_sensor_array"])
    dice = DiceStub([9])
    r = do_command_check(s, "lock_on", dice, enemy_on_special=True)
    assert dice._idx == 1 and r["needed"] == 9 and r["passed"]


def test_mercury_rolls_3d6_catastrophic():
    from src.combat import resolve_catastrophic
    from src.ship_catalog import find_ship_class
    d = find_ship_class("Mercury Battlecruiser").to_ship_dict(name="m", player=1)
    d.update(id="m", x=0.0, y=0.0, heading=0.0, hits_remaining=0)
    ship = Ship.from_dict(d)
    gs = make_gs([ship])
    dice = DiceStub([2, 2, 3])
    out = resolve_catastrophic(ship, dice, gs)
    assert dice._idx == 3
    assert any("(rolled 7)" in str(e) for e in gs.log)
    assert out
