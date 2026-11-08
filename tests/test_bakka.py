"""Battlefleet Bakka (bfgxr/rules/01_imperial-navy.md, Bakka Sector, Imperium p.93)."""
from tests.conftest import make_ship
from tests.test_fleet_lists import rows
from src.fleet_lists import fleet_list_errors, option_allowed, list_stat_changes
from src.ordnance import get_massed_turret_bonus


def test_starred_classes_gain_a_turret_only_from_the_bakka_list():
    assert list_stat_changes("navy_bakka", "Lunar Cruiser") == {"turrets": 1}
    assert list_stat_changes("navy_bakka", "Siluria Light Cruiser") == {}
    assert list_stat_changes("navy_gothic", "Lunar Cruiser") == {}


def test_veteran_captains_replace_strategic_commanders():
    assert option_allowed("Veteran Captain (+1 Ld, max 10)", ["navy_bakka"])
    assert not option_allowed("Veteran Captain (+1 Ld, max 10)", ["navy_gothic"])
    assert not option_allowed("Strategic Commander (+1 Ld, max 9)", ["navy_bakka"])
    assert option_allowed("Strategic Commander (+1 Ld, max 9)", ["navy_gothic"])
    assert option_allowed("Refit: Fleet Defence Turrets", ["navy_bakka"])
    assert not option_allowed("Refit: Fleet Defence Turrets", ["navy_armageddon"])


def test_mechanicus_cruisers_take_battlecruiser_places():
    r = rows("Lunar Cruiser", "Lunar Cruiser", "Mechanicus Lunar Cruiser", list_key="navy_bakka")
    r += rows("Endeavour Light Cruiser", "Endeavour Light Cruiser", "Endeavour Light Cruiser",
              "Endeavour Light Cruiser", list_key="navy_bakka")
    assert not any("Battlecruisers" in e for e in fleet_list_errors("navy_bakka", r, 1400))
    r += rows("Mechanicus Gothic Cruiser", "Mercury Battlecruiser",
              list_key="navy_bakka")             # three, with two allowed for six cruisers
    assert any("Battlecruisers" in e for e in fleet_list_errors("navy_bakka", r, 1600))


def test_fleet_defence_turrets_give_plus_one_within_15cm_capped_at_3():
    fdt = make_ship(id="f", player=1, x=0.0, y=0.0, special_rules=["fleet_defence_turrets"])
    near = make_ship(id="n", player=1, x=16.0, y=0.0)    # under 15cm base to base
    far = make_ship(id="x", player=1, x=60.0, y=0.0)
    ships = [fdt, near, far]
    assert get_massed_turret_bonus(fdt, ships) == 1          # itself included
    assert get_massed_turret_bonus(near, ships) == 1
    assert get_massed_turret_bonus(far, ships) == 0
    many = [make_ship(id=f"f{i}", player=1, x=0.0, y=float(i), special_rules=["fleet_defence_turrets"])
            for i in range(5)]
    assert get_massed_turret_bonus(near, many) == 3


def test_fleet_defence_turrets_option_costs_two_turrets():
    from src.ship_catalog import find_ship_class
    d = find_ship_class("Lunar Cruiser").to_ship_dict(name="l", player=1,
                                                      upgrades=["Refit: Fleet Defence Turrets"])
    assert d["turrets"] == 0 and d["points_value"] == 185
