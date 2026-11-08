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
