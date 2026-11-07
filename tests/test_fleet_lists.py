"""Fleet lists (core rules s.4 and the faction Fleet Composition sections)."""
from src.fleet_lists import (ALL_LISTS, LISTS, list_ships, list_cost, fleet_list_errors,
                             lists_for_faction, detachments_for, option_allowed)
from src.ship_catalog import find_ship_class


def rows(*names, list_key="", upgrades=None):
    out = []
    for n in names:
        e = find_ship_class(n)
        assert e is not None, n
        out.append({"entry": e, "upgrades": list(upgrades or []), "list": list_key})
    return out


def test_every_listed_ship_is_in_the_catalog():
    missing = [(fl["key"], c) for fl in ALL_LISTS for c in list_ships(fl)
               if find_ship_class(c) is None]
    assert missing == []


def test_list_costs_override_profile_costs():
    assert list_cost(LISTS["navy_bakka"], "Gothic Cruiser", 180) == 185
    assert list_cost(LISTS["navy_gothic"], "Gothic Cruiser", 180) == 180
    assert list_cost(None, "Gothic Cruiser", 180) == 180


def test_gothic_battleship_ratio_and_cruiser_cap():
    ok = rows("Emperor Battleship", "Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser",
              list_key="navy_gothic")
    assert fleet_list_errors("navy_gothic", ok, 1500) == []
    bad = rows("Emperor Battleship", "Gothic Cruiser", "Lunar Cruiser", list_key="navy_gothic")
    errs = fleet_list_errors("navy_gothic", bad, 1500)
    assert len(errs) == 1 and "Battleships" in errs[0]
    many = rows(*["Lunar Cruiser"] * 13, list_key="navy_gothic")
    assert any("at most 12" in e for e in fleet_list_errors("navy_gothic", many, 3000))


def test_ship_not_in_the_list():
    r = rows("Siluria Light Cruiser", list_key="navy_gothic")
    assert any("isn't in" in e for e in fleet_list_errors("navy_gothic", r, 1000))


def test_battlecruisers_count_towards_battleships_but_need_cruisers():
    r = rows("Retribution Battleship", "Mars Battlecruiser", "Gothic Cruiser",
             "Lunar Cruiser", list_key="navy_gothic")
    assert fleet_list_errors("navy_gothic", r, 1500) == []      # 1 BC per 2 cruisers; BS per 3


def test_bakka_battleships_per_750_points_and_dauntless_cap():
    r = rows("Retribution Battleship", "Victory Battleship", list_key="navy_bakka")
    errs = fleet_list_errors("navy_bakka", r, 1000)
    assert any("per 750pts" in e for e in errs)
    assert not any("per 750pts" in e for e in fleet_list_errors("navy_bakka", r, 1500))
    d = rows(*["Dauntless Light Cruiser"] * 3, list_key="navy_bakka")
    assert any("Dauntless" in e and "at most 2" in e
               for e in fleet_list_errors("navy_bakka", d, 1500))


def test_armageddon_endurance_defiant_combined_per_500():
    r = rows("Endurance Light Cruiser", "Defiant Light Cruiser", "Endurance Light Cruiser",
             list_key="navy_armageddon")
    assert any("combined" in e for e in fleet_list_errors("navy_armageddon", r, 500))   # max 2
    assert not any("combined" in e for e in fleet_list_errors("navy_armageddon", r, 1000))


def test_bastion_grand_cruisers_dont_count_for_battleships():
    r = rows("Emperor Battleship", "Exorcist Grand Cruiser", "Gothic Cruiser",
             "Lunar Cruiser", list_key="navy_bastion")
    errs = fleet_list_errors("navy_bastion", r, 1500)
    assert any(e.startswith("Battleships") for e in errs)        # 2 cruisers + GC isn't 3


def test_reserves_one_per_three_of_the_same_type():
    own = rows("Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser", list_key="navy_gothic")
    res = rows("Mechanicus Lunar Cruiser", list_key="reserve:admech_explorator")
    assert fleet_list_errors("navy_gothic", own + res, 1500) == []
    res2 = res + rows("Mechanicus Gothic Cruiser", list_key="reserve:admech_explorator")
    assert any("Reserves" in e for e in fleet_list_errors("navy_gothic", own + res2, 1500))


def test_crusade_needs_master_of_the_fleet_at_750():
    r = rows("Space Marine Battle Barge", list_key="sm_crusade")
    assert any("fleet commander" in e for e in fleet_list_errors("sm_crusade", r, 1000))
    r = rows("Space Marine Battle Barge", list_key="sm_crusade",
             upgrades=["Master of the Fleet (Ld 10)"])
    assert fleet_list_errors("sm_crusade", r, 1000) == []
    assert fleet_list_errors("sm_crusade", rows("Strike Cruiser", list_key="sm_crusade"),
                             500) == []


def test_lightning_thrusters_lets_dominion_take_vanguards():
    lt = ["Master of the Fleet (Ld 10)", "Chapter tactic: Lightning Thrusters"]
    barge = rows("Space Marine Battle Barge", list_key="sm_dominion", upgrades=lt)
    van = rows("Vanguard Cruiser", "Vanguard Cruiser", list_key="sm_dominion")
    assert fleet_list_errors("sm_dominion", barge + van, 1000) == []
    plain = rows("Space Marine Battle Barge", list_key="sm_dominion",
                 upgrades=["Master of the Fleet (Ld 10)"])
    assert any("Vanguard" in e for e in fleet_list_errors("sm_dominion", plain + van, 1000))
    five = rows(*["Vanguard Cruiser"] * 5, list_key="sm_dominion")
    assert any("Vanguard" in e for e in fleet_list_errors("sm_dominion", barge + five, 1500))


def test_dominion_reserves_per_strike_cruisers():
    own = rows("Strike Cruiser", "Strike Cruiser", list_key="sm_dominion")
    res = rows("Lunar Cruiser", list_key="reserve:navy_gothic")
    assert fleet_list_errors("sm_dominion", own + res, 500) == []
    res2 = res + rows("Gothic Cruiser", list_key="reserve:navy_gothic")
    assert any("Reserves" in e for e in fleet_list_errors("sm_dominion", own + res2, 500))


def test_inquisition_detachment_joins_navy_and_limits_cruisers():
    assert "inq_detachment" in [d["key"] for d in detachments_for("navy_gothic")]
    own = rows("Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser", list_key="navy_gothic")
    inq = rows("Inquisitorial Cruiser", list_key="inq_detachment")
    assert fleet_list_errors("navy_gothic", own + inq, 1500, ["inq_detachment"]) == []
    inq2 = inq + rows("Inquisitorial Cruiser", list_key="inq_detachment")
    assert any("Inquisitorial Cruisers" in e
               for e in fleet_list_errors("navy_gothic", own + inq2, 1500, ["inq_detachment"]))


def test_inferno_torpedoes_only_with_the_detachment():
    assert not option_allowed("Inferno Torpedoes", ["inq_banisher"])
    assert option_allowed("Inferno Torpedoes", ["navy_gothic", "inq_detachment"])
    assert option_allowed("Inferno Torpedoes", [])                 # no fleet list
    assert option_allowed("Torpedoes: short burn (40cm; out of fuel on a 6)", ["navy_gothic"])


def test_every_faction_with_ships_has_a_list():
    for f in ("imperial_navy_gothic", "adeptus_mechanicus", "space_marines",
              "inquisition_grey_knights", "chaos", "orks", "tau_kororvesh"):
        assert lists_for_faction(f), f


def test_every_ratio_reserve_and_join_names_something_real():
    for fl in ALL_LISTS:
        names = {sec["name"] for sec in fl["sections"]}
        for sec in fl["sections"]:
            if sec.get("ratio") and sec["ratio"][1] != ["*cruisers"]:
                assert set(sec["ratio"][1]) <= names, (fl["key"], sec["name"])
        for k in fl.get("reserves", []) + fl.get("joins", []):
            assert k in LISTS, (fl["key"], k)


def test_ork_battleships_need_two_kroozers_each():
    r = rows("Gorbag's Revenge (0-1)", "Kill Kroozer", list_key="orks_green_tide")
    assert any("Battleships" in e for e in fleet_list_errors("orks_green_tide", r, 1500))
    r += rows("Terror Ship", list_key="orks_green_tide")
    assert not any("Battleships" in e for e in fleet_list_errors("orks_green_tide", r, 1500))
