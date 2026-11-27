"""Fleets relying on optional rules are flagged before the game (owner)."""
from tests.conftest import make_ship
from src.fleet_rule_check import fleet_rule_warnings, warning_text

IMPALER_BAY = {"name": "Prow Impaler Bay", "weapon_type": "launch_bay", "strength": 1,
               "craft_types": ["impaler"], "impaler_bay": True}
MIXED_BAY = {"name": "Launch Bays", "weapon_type": "launch_bay", "strength": 2,
             "craft_types": ["fighter", "bomber", "assault_boat"]}


def test_impaler_fleet_needs_hit_and_run():
    s = make_ship(name="Corsair", weapons=[dict(IMPALER_BAY)])
    w = fleet_rule_warnings([s], {"hit_and_run": False, "teleport": False, "boarding": False})
    assert list(w) == ["hit_and_run"] and "Impalers" in w["hit_and_run"][0]
    assert fleet_rule_warnings([s], {"hit_and_run": True}) == {}
    assert "Hit and Run Raids" in warning_text({1: w})


def test_ordinary_mixed_bays_and_faction_bonuses_not_flagged():
    s = make_ship(weapons=[dict(MIXED_BAY)], special_rules=["teleport_assault",
                                                            "space_marine_crew"])
    assert fleet_rule_warnings([s], {"hit_and_run": False, "teleport": False}) == {}


def test_bought_upgrades_flagged():
    s = make_ship(name="Kroozer", special_rules=["soopa_tellyporta", "mega_armoured_boarders"])
    w = fleet_rule_warnings([s], {"hit_and_run": False, "teleport": False, "boarding": False})
    assert set(w) == {"hit_and_run", "teleport", "boarding"}
