"""Space Marine fleet lists (bfgxr/rules/03_space-marines.md; CHANGES update 18)."""
from tests.test_fleet_lists import rows
from src.fleet_lists import fleet_list_errors


def has(errs, text):
    return any(text in e for e in errs)


def test_navy_nova_cannons_one_per_500_or_part():
    r = rows("Dominator Cruiser", "Dominator Cruiser", "Gothic Cruiser", list_key="navy_gothic")
    assert not has(fleet_list_errors("navy_gothic", r, 600), "Nova cannons")
    assert has(fleet_list_errors("navy_gothic", r, 500), "Nova cannons")
    r[2]["upgrades"] = []
    lunar = rows("Lunar Cruiser", list_key="navy_gothic",
                 upgrades=["Refit: prow nova cannon for the torpedoes"])
    assert has(fleet_list_errors("navy_gothic", r + lunar, 1000), "Nova cannons")   # refit counts


def test_crusade_strike_cruisers_0_to_10():
    r = rows(*["Strike Cruiser"] * 11, list_key="sm_crusade")
    assert has(fleet_list_errors("sm_crusade", r, 1600), "Strike Cruisers")


def test_dominion_reserves():
    sc = rows(*["Strike Cruiser"] * 4, list_key="sm_dominion")
    sword = rows("Sword Rapid Strike Vessel", "Sword Rapid Strike Vessel", list_key="sm_dominion")
    assert not has(fleet_list_errors("sm_dominion", sc + sword, 700), "isn't in")
    navy_esc = rows("Sword Frigate", list_key="reserve:navy_gothic")
    assert has(fleet_list_errors("sm_dominion", sc + navy_esc, 700), "no Imperial Navy escorts")
    two = rows("Dominator Cruiser", "Dominator Cruiser", list_key="reserve:navy_gothic")
    errs = fleet_list_errors("sm_dominion", sc + two, 1000)
    assert not has(errs, "per two strike") and has(errs, "Nova cannons")    # 1 per 1000
    assert not has(fleet_list_errors("sm_dominion", sc + two, 1001), "Nova cannons")
    mech = rows("Mechanicus Lunar Cruiser", list_key="reserve:admech_explorator")
    assert not has(fleet_list_errors("sm_dominion", sc + mech, 900), "Mechanicus")
    full = rows(*["Strike Cruiser"] * 9, list_key="sm_dominion")
    errs = fleet_list_errors("sm_dominion", full + mech + rows(
        "Gothic Cruiser", list_key="reserve:navy_gothic"), 1700)
    assert has(errs, "Strike Cruisers: 11 with the reserves")


def test_sm_options_and_gating():
    from src.ship_catalog import find_ship_class
    from src.fleet_lists import option_allowed
    sc = find_ship_class("Strike Cruiser")
    names = {u.name: u for u in sc.upgrades_available}
    sb = "Torpedoes: short burn torpedoes (instead of boarding torpedoes)"
    assert names[sb].points_cost == 0 and "requires:Variant: prow torpedoes" in names[sb].restrictions
    assert "Master of the Fleet (Ld 10)" in names and "Veteran honour guard" in names
    assert option_allowed("Veteran honour guard", ["sm_crusade"])
    assert not option_allowed("Veteran honour guard", ["navy_armageddon"])
    assert option_allowed("Space Marine Captain", ["sm_dominion"])
    assert not option_allowed("Space Marine Captain", ["sm_crusade"])
    assert not option_allowed("Chapter tactic: Wings of Fury", ["navy_gothic"])
    assert option_allowed("Chapter tactic: Wings of Fury", ["sm_dominion"])
    d = find_ship_class("Lunar Cruiser").to_ship_dict(name="l", player=1,
                                                      upgrades=["Space Marine Captain"])
    assert d["leadership_table"] == "Astartes" and d["points_value"] == 205


def test_master_of_the_fleet_rides_a_battle_barge_if_there_is_one():
    from src.ship_catalog import find_ship_class
    from src.booklet_options import fleet_option_errors
    mof = "Master of the Fleet (Ld 10)"
    sc, bb, ult = (find_ship_class(n) for n in
                   ("Strike Cruiser", "Space Marine Battle Barge", "Ultima Battle Barge"))
    assert not fleet_option_errors([(sc, [mof]), (sc, [])], 800)
    assert fleet_option_errors([(sc, [mof]), (bb, [])], 1200)
    assert not fleet_option_errors([(sc, []), (bb, [mof])], 1200)
    assert fleet_option_errors([(bb, [mof]), (ult, [])], 1500)       # the Chapter flagship


def test_mixed_rsv_squadron_rolls_on_the_space_marine_table():
    from tests.conftest import make_gs, make_ship, DiceStub
    from src.fleet_loader import roll_starting_leadership
    from src.booklet_ships import LEADERSHIP_TABLES
    a = make_ship(id="a", ship_type="escort", squadron_id="q")
    b = make_ship(id="b", ship_type="escort", squadron_id="q")
    gs = make_gs([a, b])
    gs.ships[0]["leadership_table"], gs.ships[1]["leadership_table"] = "Default", "Astartes"
    dice = DiceStub([1])
    roll_starting_leadership(gs, dice)
    assert dice._idx == 1
    assert gs.ships[0]["leadership"] == gs.ships[1]["leadership"] == LEADERSHIP_TABLES["Astartes"][0]
