"""Fixes from the code review (CLAUDE.md To do 15)."""
from src.hit_and_run import _apply_raid_crit, raid_crit_preview, describe_raid_result
from tests.conftest import DiceStub, make_gs, make_ship


def test_raid_crit_path_applies_bridge_smashed():
    # The raid / boarding crit path applies every crit effect, as roll_critical_hit does
    s = make_ship(leadership=8)
    gs = make_gs([s])
    crit = _apply_raid_crit(9, s, gs, DiceStub([]))
    assert crit["crit_type"] == "bridge_smashed"
    assert gs.get_ship_by_id("t1").leadership == 5


def test_necron_raid_crit_loses_leadership():
    # Necron Main Drive Damaged (6): -1 Ld each time (Xenos p.41)
    s = make_ship(leadership=9, special_rules=["necron"])
    gs = make_gs([s])
    crit = _apply_raid_crit(6, s, gs, DiceStub([]))
    assert crit["crit_type"] == "main_drive"
    assert gs.get_ship_by_id("t1").leadership == 8


def test_raid_preview_uses_the_targets_own_table():
    eldar = make_ship(special_rules=["eldar_mms"])
    assert raid_crit_preview(2, eldar) == "infinity_circuit"
    assert describe_raid_result(2, eldar) == "critical hit: Infinity Circuit Damaged"
    necron = make_ship(special_rules=["necron"])
    assert raid_crit_preview(6, necron) == "main_drive"


def test_sunward_change_reaches_eldar_speeds():
    from src import eldar
    from src.optional_rules import set_sunward
    set_sunward(False, "south")
    assert eldar.sunward_edge() == "south"
    set_sunward(True, "north")
    assert eldar.sunward_edge() == "north"


def test_marker_ids_are_unique_serials():
    gs = make_gs([])
    a, b = gs.next_serial(), gs.next_serial()
    assert a != b and b == a + 1
