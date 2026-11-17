"""Rules checked against booklet export 7 (s.3, s.6, s.7, Support Assets)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.movement import (do_command_check, attempt_brace, squadron_aaf_bonuses,
                          aaf_bonus_dice, get_effective_speed)
from src.ship_catalog import find_ship_class


def test_leadership_one_or_less_always_fails():
    s = make_ship(leadership=2)
    r = do_command_check(s, "lock_on", DiceStub([2]), in_blast=True)    # Ld 1 after Under Fire
    assert r["needed"] == 1 and not r["passed"]


def test_brace_uses_command_check_modifiers():
    s = make_ship(id="s", player=1, leadership=7)
    enemy = make_ship(id="e", player=2, x=100.0, special_order="lock_on")
    gs = make_gs([s, enemy])
    r = attempt_brace(s, gs, DiceStub([8]))          # Enemy Contacts: Ld 8
    assert r["needed"] == 8 and r["passed"]


def test_squadron_all_ahead_full_one_roll_highest_dice():
    a = make_ship(id="a", ship_type="escort")
    b = make_ship(id="b", ship_type="escort", special_rules=["improved_thrusters"])  # 5 dice
    rolls = [1, 6, 2, 5, 3]
    dice = DiceStub(rolls)
    got = squadron_aaf_bonuses([a, b], dice)
    assert dice._idx == 5
    assert got == {"b": 17, "a": 16}                 # a uses its 4 highest: 6+5+3+2


def test_support_assets_fixed_ld_and_three_dice():
    sys_esc = find_ship_class("System Escort")
    assert sys_esc.leadership == 7 and sys_esc.leadership_table == ""
    assert "fleet_support" in sys_esc.special_rules
    s = make_ship(special_rules=["fleet_support"])
    assert aaf_bonus_dice(s) == 3
    assert aaf_bonus_dice(make_ship(special_rules=["fleet_support", "aaf_5d6"])) == 5


def test_brace_after_aaf_expires_next_turn():
    # The order before bracing affects only the move already made (s.7): the
    # turn controller clears previous_order at the start of the movement phase
    s = make_ship(speed=20, special_order="brace_for_impact", previous_order="all_ahead_full")
    assert get_effective_speed(s, "brace_for_impact", 0) == (20, 20)    # still this turn
    s.previous_order = "none"
    assert get_effective_speed(s, "brace_for_impact", 0) == (10, 20)


def test_turn_controller_clears_previous_order_at_movement_start():
    from src.turn_controller import TurnController
    s = make_ship(id="s", player=1, special_order="brace_for_impact",
                  previous_order="all_ahead_full")
    gs = make_gs([s])
    gs.active_player = 1
    tc = TurnController(gs, DiceStub([1]))
    tc._clear_previous_orders()
    fresh = gs.get_ship_by_id("s")
    assert fresh.special_order == "brace_for_impact" and fresh.previous_order == "none"
