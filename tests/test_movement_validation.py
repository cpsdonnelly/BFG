"""Tests for src/movement.py — validation and execution."""
import math
from tests.conftest import make_ship, make_gs, make_blast, DiceStub
from src.movement import (validate_movement, execute_movement,
                          do_command_check, resolve_aaf_speed, MoveCommand)
from src.models import SpecialOrder


def _fwd(dist: float) -> MoveCommand:
    return MoveCommand("forward", dist)


def _left(deg: float) -> MoveCommand:
    return MoveCommand("turn_left", deg)


def _right(deg: float) -> MoveCommand:
    return MoveCommand("turn_right", deg)


# ── forward movement ──────────────────────────────────────────────────────────

def test_forward_within_speed_valid():
    ship = make_ship(id="s", speed=20, ship_type="escort")
    r = validate_movement(ship, [_fwd(15)], SpecialOrder.NONE.value)
    assert r.valid
    assert abs(r.total_distance - 15) < 0.1
    assert abs(r.final_x - 15) < 0.1
    assert r.final_y == 0


def test_forward_exceeds_max_speed_invalid():
    ship = make_ship(id="s", speed=20, ship_type="escort")
    r = validate_movement(ship, [_fwd(25)], SpecialOrder.NONE.value)
    assert not r.valid
    assert any("speed" in e.lower() for e in r.errors)


def test_counts_as_defense_under_5cm():
    ship = make_ship(id="s", speed=20, ship_type="escort")
    # Escorts have no min_turn_distance so moving 3cm is just flagged, not invalid
    r = validate_movement(ship, [_fwd(3)], SpecialOrder.NONE.value)
    assert r.counts_as_defense is True


# ── turning ───────────────────────────────────────────────────────────────────

def test_turn_left_changes_heading():
    ship = make_ship(id="s", speed=20, ship_type="escort", turn_angle=45)
    r = validate_movement(ship, [_left(45), _fwd(10)], SpecialOrder.NONE.value)
    assert r.valid
    assert abs(r.final_heading - 45) < 1


def test_turn_right_changes_heading():
    ship = make_ship(id="s", speed=20, ship_type="escort", turn_angle=45)
    r = validate_movement(ship, [_right(45), _fwd(10)], SpecialOrder.NONE.value)
    assert r.valid
    assert abs(r.final_heading - 315) < 1


def test_turn_exceeds_max_angle_invalid():
    ship = make_ship(id="s", speed=20, ship_type="escort", turn_angle=45)
    r = validate_movement(ship, [_left(90), _fwd(10)], SpecialOrder.NONE.value)
    assert not r.valid
    assert any("turn" in e.lower() or "90" in e for e in r.errors)


def test_escort_turns_at_any_point():
    # Escorts have min_turn_distance = 0, so they may turn before moving.
    ship = make_ship(id="s", speed=20, ship_type="escort", turn_angle=45)
    r = validate_movement(ship, [_left(45), _fwd(10)], SpecialOrder.NONE.value)
    assert r.valid
    assert r.turns_used == 1


def test_cruiser_requires_min_distance_before_turn():
    # Cruiser min_turn_distance = 10cm; turning after only 5cm → error
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(5), _left(45), _fwd(10)], SpecialOrder.NONE.value)
    assert not r.valid
    assert any("must move" in e.lower() or "10cm" in e for e in r.errors)


def test_cruiser_ok_after_min_distance():
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(45)], SpecialOrder.NONE.value)
    assert r.valid


def test_battleship_requires_15cm_before_turn():
    ship = make_ship(id="s", speed=20, ship_type="battleship", turn_angle=45,
                     base_size="large")
    r = validate_movement(ship, [_fwd(10), _left(45), _fwd(5)], SpecialOrder.NONE.value)
    assert not r.valid
    assert any("15cm" in e or "must move" in e.lower() for e in r.errors)


def test_battleship_ok_after_15cm():
    ship = make_ship(id="s", speed=20, ship_type="battleship", turn_angle=45,
                     base_size="large")
    r = validate_movement(ship, [_fwd(15), _left(45), _fwd(5)], SpecialOrder.NONE.value)
    assert r.valid
    assert r.turns_used == 1


def test_aaf_no_turns_allowed():
    ship = make_ship(id="s", speed=20, ship_type="escort", turn_angle=45)
    r = validate_movement(ship, [_left(45)], SpecialOrder.ALL_AHEAD_FULL.value,
                          aaf_bonus=5)
    assert not r.valid
    assert any("turn" in e.lower() or "aaf" in e.lower() or
               SpecialOrder.ALL_AHEAD_FULL.value in e.lower() for e in r.errors)


# ── one-turn limit and the "unused degrees" rule ──────────────────────────────

def test_normal_order_only_one_turn():
    # Cruiser moves 10cm, turns 30° CCW (using less than its 45° max), moves 10cm.
    # It may NOT spend the leftover 15° as a second turn under a normal order.
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(30), _fwd(10), _left(15)],
                          SpecialOrder.NONE.value)
    assert not r.valid
    assert any("used 1/1" in e or "turn" in e.lower() for e in r.errors)


def test_consecutive_turns_no_forward_are_one_turn():
    # turn 30 then turn 15 with no forward between = single 45° turn action.
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(30), _left(15), _fwd(10)],
                          SpecialOrder.NONE.value)
    assert r.valid
    assert r.turns_used == 1
    assert abs(r.final_heading - 45) < 0.1


def test_single_turn_action_cannot_exceed_turn_angle():
    # 30 + 30 = 60° in one continuous turn exceeds the 45° max.
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(30), _left(30), _fwd(10)],
                          SpecialOrder.NONE.value)
    assert not r.valid
    assert any("exceeds maximum" in e for e in r.errors)


def test_opposing_turns_cancel_no_turn_consumed():
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(30), _right(30), _fwd(10)],
                          SpecialOrder.NONE.value)
    assert r.valid
    assert r.turns_used == 0
    assert abs(r.final_heading - 0) < 0.1


# ── Come To New Heading: allows a second turn ─────────────────────────────────

def test_ctnh_allows_second_turn_ccw():
    # Cruiser: 10cm, turn 30° CCW, 10cm, then a second full 45° CCW turn.
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(30), _fwd(10), _left(45)],
                          SpecialOrder.COME_TO_NEW_HEADING.value)
    assert r.valid
    assert r.turns_used == 2
    assert abs(r.final_heading - 75) < 0.1  # 30 + 45


def test_ctnh_allows_second_turn_cw():
    # Second turn may be the other direction.
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(ship, [_fwd(10), _left(30), _fwd(10), _right(45)],
                          SpecialOrder.COME_TO_NEW_HEADING.value)
    assert r.valid
    assert r.turns_used == 2
    assert abs(r.final_heading - 345) < 0.1  # 30 - 45 = -15 → 345


def test_ctnh_rejects_third_turn():
    ship = make_ship(id="s", speed=20, ship_type="cruiser", turn_angle=45)
    r = validate_movement(
        ship,
        [_fwd(10), _left(45), _fwd(5), _right(45), _fwd(5), _left(10)],
        SpecialOrder.COME_TO_NEW_HEADING.value
    )
    assert not r.valid
    assert any("used 2/2" in e or "turn" in e.lower() for e in r.errors)


# ── crossed blast markers ──────────────────────────────────────────────────────

def test_blast_markers_flagged_when_crossed():
    ship = make_ship(id="s", speed=40, ship_type="escort")
    bm = make_blast(x=20, y=0)
    r = validate_movement(ship, [_fwd(40)], SpecialOrder.NONE.value, blast_markers=[bm])
    assert r.crossed_blast_markers is True


def test_no_blast_marker_crossed_when_beside():
    ship = make_ship(id="s", speed=40, ship_type="escort")
    bm = make_blast(x=20, y=50)  # far away
    r = validate_movement(ship, [_fwd(40)], SpecialOrder.NONE.value, blast_markers=[bm])
    assert r.crossed_blast_markers is False


# ── execute_movement ──────────────────────────────────────────────────────────

def test_execute_applies_final_position():
    ship = make_ship(id="s", speed=20, ship_type="escort")
    gs = make_gs([ship])
    r = validate_movement(ship, [_fwd(15)], SpecialOrder.NONE.value)
    execute_movement(ship, r, gs)
    assert abs(ship.x - 15) < 0.1
    assert ship.moved_this_turn is True


def test_execute_sets_counts_as_defense():
    ship = make_ship(id="s", speed=20, ship_type="escort")
    gs = make_gs([ship])
    r = validate_movement(ship, [_fwd(3)], SpecialOrder.NONE.value)
    assert r.counts_as_defense is True


# ── do_command_check ──────────────────────────────────────────────────────────

def test_command_check_pass():
    ship = make_ship(id="s", leadership=7)
    dice = DiceStub([7])  # roll 7 vs Ld 7 → pass (roll <= ld)
    r = do_command_check(ship, SpecialOrder.LOCK_ON.value, dice)
    assert r["passed"] is True
    assert r["roll"] == 7


def test_command_check_fail():
    ship = make_ship(id="s", leadership=7)
    dice = DiceStub([8])  # roll 8 vs Ld 7 → fail
    r = do_command_check(ship, SpecialOrder.LOCK_ON.value, dice)
    assert r["passed"] is False


def test_command_check_in_blast_reduces_ld():
    ship = make_ship(id="s", leadership=7)
    dice = DiceStub([7])  # would normally pass Ld 7, but in_blast gives Ld 6
    r = do_command_check(ship, SpecialOrder.LOCK_ON.value, dice, in_blast=True)
    # effective Ld = 7 - 1 = 6; roll 7 > 6 → fail
    assert r["passed"] is False
    assert r["needed"] == 6


def test_command_check_enemy_on_special_increases_ld():
    ship = make_ship(id="s", leadership=7)
    dice = DiceStub([8])  # normally fail Ld 7, but enemy_on_special gives Ld 8
    r = do_command_check(ship, SpecialOrder.LOCK_ON.value, dice, enemy_on_special=True)
    assert r["passed"] is True
    assert r["needed"] == 8


# ── resolve_aaf_speed ─────────────────────────────────────────────────────────

def test_aaf_speed_sum_of_4d6():
    ship = make_ship(id="s")
    dice = DiceStub([3, 4, 5, 6])
    bonus = resolve_aaf_speed(ship, dice)
    assert bonus == 3 + 4 + 5 + 6
