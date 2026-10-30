"""Blast markers and staged movement (core rules s.7, s.9 Minimum Movement)."""
from src.models import BlastMarker
from src.movement import (MoveCommand, validate_movement, execute_movement,
                          movement_budget)
from tests.conftest import make_ship, make_gs, DiceStub

COLLAPSED = [{"crit_type": "shields_collapse", "description": "Shields Collapse",
              "repairable": False, "turn_inflicted": 1}]


def fwd(cm):
    return MoveCommand("forward", cm)


def shield_hit_marker(ship):
    # Where apply_damage puts the marker for a shield hit: base radius + 1.2cm out
    return BlastMarker(id="bm", x=ship.x, y=ship.y - (ship.base_radius + 1.2))


# ── -5cm speed when moving through blast markers ─────────────────────────────

def test_touching_a_marker_at_the_start_slows_the_ship():
    ship = make_ship(speed=20)
    markers = [shield_hit_marker(ship)]
    assert validate_movement(ship, [fwd(15)], "none", blast_markers=markers).valid
    r = validate_movement(ship, [fwd(20)], "none", blast_markers=markers)
    assert not r.valid
    assert any("Max speed is 15cm" in e for e in r.errors)


def test_crossing_a_marker_mid_move_slows_the_ship():
    ship = make_ship(speed=20)
    markers = [BlastMarker(id="bm", x=8.0, y=1.0)]
    r = validate_movement(ship, [fwd(20)], "none", blast_markers=markers)
    assert r.crossed_blast_markers
    assert not r.valid


def test_markers_well_clear_of_the_path_have_no_effect():
    ship = make_ship(speed=20)
    markers = [BlastMarker(id="bm", x=8.0, y=10.0)]
    r = validate_movement(ship, [fwd(20)], "none", blast_markers=markers)
    assert r.valid and not r.crossed_blast_markers


def test_movement_budget_includes_blast_penalty():
    ship = make_ship(speed=20)
    assert movement_budget(ship, "none", blast_markers=[shield_hit_marker(ship)]) == (10, 15)
    assert movement_budget(ship, "none") == (10, 20)


# ── Staged moves: limits apply to the whole phase ────────────────────────────

def test_second_stage_counts_distance_already_moved():
    # Cruiser already moved 10cm: may now turn straight away and needs no
    # further half-speed minimum
    ship = make_ship(speed=20, ship_type="cruiser")
    r = validate_movement(ship, [fwd(2), MoveCommand("turn_left", 45), fwd(2)], "none",
                          distance_already_moved=10.0)
    assert r.valid, r.errors


def test_second_stage_cannot_exceed_phase_maximum():
    ship = make_ship(speed=20)
    r = validate_movement(ship, [fwd(10)], "none", distance_already_moved=15.0)
    assert not r.valid
    assert any("moved 25.0cm" in e for e in r.errors)


def test_blast_penalty_from_an_earlier_stage_carries_over():
    ship = make_ship(speed=20)
    r = validate_movement(ship, [fwd(10)], "none", distance_already_moved=10.0,
                          blast_already_crossed=True)
    assert not r.valid
    assert movement_budget(make_ship(speed=20, distance_moved_this_turn=10.0,
                                     crossed_blast_this_turn=True), "none") == (0, 5)


def test_first_stage_still_needs_minimum_before_turning():
    ship = make_ship(speed=20, ship_type="cruiser")
    r = validate_movement(ship, [fwd(5), MoveCommand("turn_left", 45), fwd(10)], "none")
    assert any("before turning" in e for e in r.errors)


# ── Shieldless ships take damage on a 6 (once per phase) ─────────────────────

def _cross(ship, gs, dice):
    r = validate_movement(ship, [fwd(10)], "none",
                          blast_markers=[BlastMarker(id="bm", x=ship.x + 5.0, y=ship.y + 0.5)],
                          distance_already_moved=ship.distance_moved_this_turn,
                          blast_already_crossed=ship.crossed_blast_this_turn)
    execute_movement(ship, r, gs, dice)
    return gs.get_ship_by_id(ship.id)


def test_ship_with_collapsed_shields_damaged_on_a_six():
    ship = make_ship(id="s", y=50.0, hits_max=8, critical_damage=list(COLLAPSED))
    gs = make_gs([ship])
    rolls = [6, 1]          # blast test 6 -> 1 damage; crit check 1
    dice = DiceStub(rolls)
    s = _cross(ship, gs, dice)
    assert dice._idx == len(rolls)
    assert s.hits_remaining == 7 and s.crossed_blast_this_turn


def test_shieldless_test_made_only_once_per_phase():
    ship = make_ship(id="s", y=50.0, hits_max=8, shields_max=0)
    gs = make_gs([ship])
    dice = DiceStub([5])    # first crossing: 5, no damage
    s = _cross(ship, gs, dice)
    s.distance_moved_this_turn = 10.0
    gs.update_ship(s)
    _cross(gs.get_ship_by_id("s"), gs, dice)     # second stage crosses again
    assert dice._idx == 1


def test_ship_with_shields_up_makes_no_test():
    ship = make_ship(id="s", y=50.0, shields_max=2)
    gs = make_gs([ship])
    dice = DiceStub([6])
    s = _cross(ship, gs, dice)
    assert dice._idx == 0 and s.hits_remaining == s.hits_max
