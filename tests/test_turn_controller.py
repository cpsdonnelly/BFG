"""Tests for special orders and fleet re-rolls in turn_controller.py."""
from src.turn_controller import TurnController
from tests.conftest import make_ship, make_gs, DiceStub

TORPS = [{"name": "Prow Torpedoes", "weapon_type": "torpedo", "strength": 6,
          "range": 30, "arcs": ["front"]}]


def _tc(gs, rolls, tmp_path):
    return TurnController(gs, DiceStub(rolls), save_dir=str(tmp_path))


def test_flagship_rerolling_its_own_check_spends_the_reroll(tmp_path):
    flag = make_ship(id="flag", is_flagship=True, rerolls_remaining=1, leadership=7)
    gs = make_gs([flag])
    tc = _tc(gs, [12, 2, 2], tmp_path)        # fail, re-roll pass, (unused)

    assert not tc.issue_special_order(flag, "lock_on")["success"]
    assert tc.attempt_reroll_command_check(flag, "lock_on")["success"]

    assert gs.get_ship_by_id("flag").rerolls_remaining == 0
    assert gs.get_ship_by_id("flag").special_order == "lock_on"
    assert tc.attempt_reroll_command_check(flag, "lock_on") == {
        "success": False, "error": "No re-rolls available"}


def test_reload_ordnance_passed_on_reroll_reloads(tmp_path):
    flag = make_ship(id="flag", is_flagship=True, rerolls_remaining=1)
    ship = make_ship(id="s", weapons=TORPS, ordnance_loaded_torps=False,
                     leadership=7, x=50.0)
    gs = make_gs([flag, ship])
    tc = _tc(gs, [12, 2], tmp_path)

    assert not tc.issue_special_order(ship, "reload_ordnance")["success"]
    assert tc.attempt_reroll_command_check(ship, "reload_ordnance")["success"]

    reloaded = gs.get_ship_by_id("s")
    assert reloaded.special_order == "reload_ordnance"
    assert reloaded.ordnance_loaded_torps is True


def test_reload_ordnance_passed_first_time_still_reloads(tmp_path):
    ship = make_ship(id="s", weapons=TORPS, ordnance_loaded_torps=False, leadership=7)
    gs = make_gs([ship])
    tc = _tc(gs, [2], tmp_path)

    assert tc.issue_special_order(ship, "reload_ordnance")["success"]
    assert gs.get_ship_by_id("s").ordnance_loaded_torps is True
