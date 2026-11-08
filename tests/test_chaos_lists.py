"""Chaos fleet lists (bfgxr/rules/07_chaos.md; CHANGES update 25)."""
from tests.conftest import make_gs, make_ship, DiceStub
from tests.test_fleet_lists import rows
from src.fleet_lists import fleet_list_errors, reserve_allowed, list_stat_changes


def has(errs, text):
    return any(text in e for e in errs)


def test_planet_killer_counts_as_a_battleship():
    r = rows("The Planet Killer", "Despoiler Battleship", "Carnage Cruiser", "Carnage Cruiser",
             "Carnage Cruiser", list_key="chaos_black_crusade")
    assert has(fleet_list_errors("chaos_black_crusade", r, 1500), "Battleships")


def test_reserves_between_incursion_crusade_and_renegades():
    assert reserve_allowed("chaos_incursion", "chaos_black_crusade", "Carnage Cruiser")
    assert not reserve_allowed("chaos_incursion", "chaos_black_crusade", "The Planet Killer")
    assert not reserve_allowed("chaos_black_crusade", "chaos_renegades", "Chaos Space Hulk")
    own = rows(*["Carnage Cruiser"] * 3, list_key="chaos_incursion")
    res = rows("Murder Cruiser", list_key="reserve:chaos_black_crusade")
    assert not has(fleet_list_errors("chaos_incursion", own + res, 800), "Reserves")


def test_renegade_cruisers_minus_one_rolled_leadership():
    assert list_stat_changes("chaos_renegades", "Lunar Cruiser") == {"special_rules": ["ld_rolled:-1"]}
    assert list_stat_changes("chaos_renegades", "Carnage Cruiser") == {}
    from src.fleet_loader import roll_starting_leadership
    from src.booklet_ships import LEADERSHIP_TABLES
    s = make_ship(id="r", special_rules=["ld_rolled:-1"])
    gs = make_gs([s])
    gs.ships[0]["leadership_table"] = "Default"
    dice = DiceStub([4])
    roll_starting_leadership(gs, dice)
    assert dice._idx == 1 and gs.ships[0]["leadership"] == LEADERSHIP_TABLES["Default"][3] - 1
