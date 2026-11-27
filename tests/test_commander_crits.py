"""Booklet update 62: result 9 on the Dark Eldar, Eldar, Necron and Tyranid
tables counts as Bridge Smashed (s.5): the commander aboard dies (re-rolls
lost for the battle, even after a repair; the opponent scores the commander's
points; Kill the Admiral ends). Eldar use XR's critical hits table."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import roll_critical_hit, weapon_disabled_by_crit
from src.geometry import current_shields
from src.turn_controller import TurnController
from src.victory_points import calculate_victory_points
from src.models import commander_dead


def _flag(rules, **kw):
    base = dict(id="f", player=1, is_flagship=True, rerolls_remaining=2, hits_max=8,
                points_value=300, special_rules=list(rules))
    base.update(kw)
    return make_ship(**base)


def test_result_nine_kills_the_commander_on_each_alien_table():
    for rules in (["dark_eldar", "shadowfield"], ["eldar_mms", "fragile", "holofield"],
                  ["necron", "reactive_hull:4"], ["tyranid"]):
        gs = make_gs([_flag(rules), make_ship(id="e", player=2)])
        s = gs.get_ship_by_id("f")
        roll_critical_hit(s, DiceStub([9, 1, 1, 1]), gs)
        gs.update_ship(s)
        assert commander_dead(gs.get_ship_by_id("f")), rules
        assert TurnController(gs, DiceStub([])).get_fleet_rerolls(1) == 0, rules


def test_a_repaired_synapse_link_still_lost_the_rerolls():
    gs = make_gs([_flag(["tyranid"]), make_ship(id="e", player=2)])
    s = gs.get_ship_by_id("f")
    roll_critical_hit(s, DiceStub([9]), gs)
    s.critical_damage = []                       # repaired
    gs.update_ship(s)
    assert commander_dead(gs.get_ship_by_id("f"))
    assert TurnController(gs, DiceStub([])).get_fleet_rerolls(1) == 0


def test_eldar_xr_table_field_generators_and_second_prow_hit():
    port = {"name": "Port Pulsar Lance", "weapon_type": "lance", "strength": 1,
            "range_cm": 30, "arcs": ["left"]}
    e = make_ship(id="el", player=1, shields_max=1, special_rules=["eldar_mms", "holofield"],
                  weapons=[port])
    gs = make_gs([e])
    s = gs.get_ship_by_id("el")
    roll_critical_hit(s, DiceStub([10]), gs)
    assert current_shields(s, []) == 0 and "holofield" not in s.special_rules
    s.critical_damage = [{"crit_type": "prow_armament"}]
    assert not weapon_disabled_by_crit(s, port)
    s.critical_damage *= 2
    assert weapon_disabled_by_crit(s, port)


def test_opponent_scores_the_commanders_points_when_he_dies():
    from src.ship_catalog import get_ship_class
    lunar = get_ship_class("imperial_navy_gothic", "Lunar Cruiser")
    d = lunar.to_ship_dict("L", 1, ship_id="L",
                           upgrades=["Vice Admiral (Ld 8)", "Commander: 1 extra re-roll"])
    from src.models import Ship
    s = Ship.from_dict(d)
    gs = make_gs([s, make_ship(id="e", player=2, points_value=100)])
    base = calculate_victory_points(gs)[2]["total"]
    s = gs.get_ship_by_id("L")
    s.critical_damage = [{"crit_type": "bridge_smashed"}]
    gs.update_ship(s)
    assert calculate_victory_points(gs)[2]["total"] == base + 75   # Vice Admiral 50 + re-roll 25
