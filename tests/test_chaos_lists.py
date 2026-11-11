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
    assert list_stat_changes("chaos_renegades", "Lunar Cruiser") == {"special_rules": ["ld_rolled:-1", "chaos_crew"]}
    assert list_stat_changes("chaos_renegades", "Carnage Cruiser") == {}
    from src.fleet_loader import roll_starting_leadership
    from src.booklet_ships import LEADERSHIP_TABLES
    s = make_ship(id="r", special_rules=["ld_rolled:-1"])
    gs = make_gs([s])
    gs.ships[0]["leadership_table"] = "Default"
    dice = DiceStub([4])
    roll_starting_leadership(gs, dice)
    assert dice._idx == 1 and gs.ships[0]["leadership"] == LEADERSHIP_TABLES["Default"][3] - 1


# ── Marks of Chaos, Chaos Space Marine crews, boarding (07_chaos.md, s.32) ────

def test_mark_options_gated_by_list():
    from src.fleet_lists import option_allowed
    assert option_allowed("Mark of Khorne", ["chaos_incursion"])
    assert option_allowed("Mark of Nurgle", ["chaos_nurgle"])
    assert not option_allowed("Mark of Khorne", ["chaos_nurgle"])
    assert not option_allowed("Chaos Space Marine crew", ["chaos_incursion"])
    assert option_allowed("Chaos Terminators", ["chaos_renegades"])
    assert not option_allowed("Chaos Terminators", ["chaos_black_crusade"])
    assert not option_allowed("Mark of Khorne", ["navy_gothic"])


def test_mark_needs_a_leader_or_csm_and_crusade_marks_are_unique():
    r = rows("Carnage Cruiser", "Carnage Cruiser", "Carnage Cruiser", list_key="chaos_incursion")
    r[0]["upgrades"] = ["Mark of Khorne"]
    assert has(fleet_list_errors("chaos_incursion", r, 600), "needs a Chaos Lord")
    r[0]["upgrades"] = ["Mark of Khorne", "Aspiring Champion (+1 Ld, max 9)"]
    assert not has(fleet_list_errors("chaos_incursion", r, 600), "needs a Chaos Lord")
    c = rows("Carnage Cruiser", "Carnage Cruiser", list_key="chaos_black_crusade")
    for x in c:
        x["upgrades"] = ["Mark of Nurgle"]
    assert has(fleet_list_errors("chaos_black_crusade", c, 400), "one of each Mark")
    g = rows("Carnage Cruiser", list_key="chaos_renegades", upgrades=["Mark of Tzeentch"])
    assert has(fleet_list_errors("chaos_renegades", g, 300), "Chaos Space Marine crew or")
    g[0]["upgrades"] = ["Mark of Tzeentch", "Chaos Space Marine crew", "Chaos Terminators"]
    errs = fleet_list_errors("chaos_renegades", g, 800)
    assert not has(errs, "Chaos Space Marine crew or") and has(errs, "Terminators only")


def test_mark_effects_khorne_nurgle_and_chaos_boarding_bonus():
    from src.boarding import troop_rating, _crew_damage_bonus
    from src.ship_catalog import find_ship_class
    k = make_ship(hits_remaining=6, turrets=2, special_rules=["mark:khorne", "chaos_crew"])
    assert troop_rating(k) == 14 and _crew_damage_bonus(k) == 1
    csm = make_ship(special_rules=["chaos_crew", "space_marine_crew"])
    assert _crew_damage_bonus(csm) == 2                      # largest bonus only
    nicassar = make_ship(hits_remaining=5, turrets=0, special_rules=["frail_crew"])
    assert troop_rating(nicassar) == 5 and troop_rating(nicassar, defending=True) == 3
    base = find_ship_class("Carnage Cruiser")
    d = base.to_ship_dict(name="n", player=1, upgrades=["Mark of Nurgle"])
    assert d["hits_max"] == base.hits_max + 1


def test_slaanesh_minus_one_ld_within_15cm():
    from src.movement import do_command_check
    s = make_ship(id="s", player=2, x=0.0, y=0.0, special_rules=["mark:slaanesh"])
    t = make_ship(id="t", player=1, x=12.0, y=0.0, leadership=8)
    gs = make_gs([s, t])
    dice = DiceStub([8])
    r = do_command_check(t, "lock_on", dice, gs=gs)
    assert dice._idx == 1 and r["needed"] == 7 and not r["passed"]


def test_tzeentch_rerolls_a_bad_critical_it_suffers():
    from src.combat import roll_critical_hit
    t = make_ship(id="t", hits_max=8, hits_remaining=8, special_rules=["mark:tzeentch"])
    gs = make_gs([t])
    gs.ai_player = 1
    dice = DiceStub([12, 2])          # 2D6 totals: 12 (re-rolled), then 2
    roll_critical_hit(t, dice, gs, {})
    assert dice._idx == 2 and "Mark of Tzeentch" in " ".join(gs.log)


def test_csm_crew_uses_the_astartes_table_or_adds_one_to_a_commander():
    from src.fleet_loader import roll_starting_leadership
    from src.booklet_ships import LEADERSHIP_TABLES
    a = make_ship(id="a", special_rules=["csm_crew"])
    b = make_ship(id="b", special_rules=["csm_crew"], leadership=9)
    gs = make_gs([a, b])
    gs.ships[0]["leadership_table"] = "Default"
    gs.ships[1]["leadership_table"] = ""
    dice = DiceStub([1])
    roll_starting_leadership(gs, dice)
    assert dice._idx == 1 and gs.ships[0]["leadership"] == LEADERSHIP_TABLES["Astartes"][0]
    assert gs.ships[1]["leadership"] == 10


def test_troop_rating_turrets_after_doubling_no_massed():
    from src.boarding import troop_rating
    k = make_ship(hits_max=8, hits_remaining=6, turrets=4, special_rules=["mark:khorne"])
    assert troop_rating(k) == 6 * 2 + 4       # turrets added after the doubling
