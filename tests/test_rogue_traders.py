"""Rogue Traders (bfgxr/rules/05_rogue-traders.md; CHANGES updates 20-21)."""
from tests.conftest import make_ship
from tests.test_fleet_lists import rows
from src.fleet_lists import (fleet_list_errors, notable_xenos_cost, notable_xenos_first,
                             xenos_cutter_errors)

RAIDER = "Fra'al Raider (Notable Xenos)"


def squad(rs, sid):
    for r in rs:
        r["squadron_id"] = sid
    return rs


def test_notable_xenos_cost_30_per_squadron():
    a = squad(rows(RAIDER, RAIDER, list_key="rt_wolf_pack"), "a")
    b = squad(rows(RAIDER, RAIDER, RAIDER, list_key="rt_wolf_pack"), "b")
    cut = squad(rows("Xenos Cutter", "Xenos Cutter", list_key="rt_wolf_pack"), "c")
    fleet = a + b + cut
    assert notable_xenos_cost(fleet) == 60
    assert notable_xenos_first(fleet) == {0, 2}


def test_cutters_squadron_only_with_their_own_type():
    mixed = squad(rows(RAIDER, "Xenos Cutter", list_key="rt_wolf_pack"), "m")
    assert xenos_cutter_errors(mixed)
    assert not xenos_cutter_errors(squad(rows(RAIDER, RAIDER), "s"))
    navy = rows("Lunar Cruiser") + rows(RAIDER)
    assert any("Imperial Navy" in e for e in xenos_cutter_errors(navy))


def test_pirate_limits_or_portion_thereof():
    r = rows("Murder Cruiser", "Murder Cruiser", list_key="rt_wolf_pack")
    assert not any("Pirate Cruisers" in e for e in fleet_list_errors("rt_wolf_pack", r, 600))


def test_fraal_targeting_matrix():
    from src.combat import get_column_shifts
    a = make_ship(id="a", player=1, x=0.0, y=0.0, special_rules=["fraal_targeting"])
    plain = make_ship(id="p", player=1, x=0.0, y=0.0)
    t = make_ship(id="t", player=2, x=40.0, y=0.0, heading=0.0)
    assert get_column_shifts(a, t, []) == get_column_shifts(plain, t, []) - 1
    assert a.get_target_orientation(t) == "closing"
    from src.ship_catalog import find_ship_class
    assert "fraal_targeting" in find_ship_class(RAIDER).special_rules
