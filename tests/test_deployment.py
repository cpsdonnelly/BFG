"""Tests for src/deployment.py — deployment logic (no tkinter)."""
import math
import pytest
from tests.conftest import make_ship
from src.deployment import (
    DeploymentZone, get_default_zones, validate_placement,
    validate_squadron_placement, group_ships_for_deployment,
    DeploymentState, COHERENCY_CM, ZONE_DEPTH_CM,
)


# ── DeploymentZone ────────────────────────────────────────────────────────────

def test_zone_contains_point_inside():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    assert zone.contains(60, 15) is True


def test_zone_excludes_point_outside():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    assert zone.contains(60, 35) is False


def test_zone_boundary_is_inclusive():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    assert zone.contains(0, 0) is True
    assert zone.contains(120, 30) is True


# ── get_default_zones ─────────────────────────────────────────────────────────

def test_default_zones_returns_two():
    zones = get_default_zones(120, 120)
    assert len(zones) == 2


def test_default_zones_player_assignment():
    zones = get_default_zones(120, 120)
    players = {z.player for z in zones}
    assert players == {1, 2}


def test_default_zones_depth():
    zones = get_default_zones(120, 120)
    for z in zones:
        depth = z.y_max - z.y_min
        assert abs(depth - ZONE_DEPTH_CM) < 0.01


def test_default_zones_p1_at_bottom():
    zones = get_default_zones(120, 120)
    z1 = next(z for z in zones if z.player == 1)
    assert z1.y_min == pytest.approx(0.0)


def test_default_zones_p2_at_top():
    zones = get_default_zones(120, 120)
    z2 = next(z for z in zones if z.player == 2)
    assert z2.y_max == pytest.approx(120.0)


# ── validate_placement ────────────────────────────────────────────────────────

def test_valid_placement_inside_zone():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    ship = make_ship(id="s1")
    ok, reason = validate_placement(ship, 60, 15, zone, [])
    assert ok
    assert reason == ""


def test_placement_outside_zone_invalid():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    ship = make_ship(id="s1")
    ok, reason = validate_placement(ship, 60, 50, zone, [])
    assert not ok
    assert "outside" in reason.lower()


def test_placement_too_close_to_existing_ship():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    ship = make_ship(id="s1")
    placed = make_ship(id="s0")
    placed.x, placed.y = 60.0, 15.0
    ok, reason = validate_placement(ship, 60.5, 15.0, zone, [placed])
    assert not ok
    assert "close" in reason.lower()


def test_placement_far_enough_from_existing_ship():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    ship = make_ship(id="s1")
    placed = make_ship(id="s0")
    placed.x, placed.y = 50.0, 15.0
    ok, _ = validate_placement(ship, 60.0, 15.0, zone, [placed])
    assert ok


# ── validate_squadron_placement ───────────────────────────────────────────────

def test_squadron_within_coherency_valid():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    s1 = make_ship(id="e1", ship_type="escort")
    s2 = make_ship(id="e2", ship_type="escort")
    positions = [(55.0, 15.0), (65.0, 15.0)]  # 10cm apart
    ok, errors = validate_squadron_placement([s1, s2], positions, zone, [])
    assert ok
    assert errors == []


def test_squadron_exceeds_coherency_invalid():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    s1 = make_ship(id="e1", ship_type="escort")
    s2 = make_ship(id="e2", ship_type="escort")
    # 20cm apart — exceeds COHERENCY_CM=15
    positions = [(50.0, 15.0), (70.0, 15.0)]
    ok, errors = validate_squadron_placement([s1, s2], positions, zone, [])
    assert not ok
    assert any("coherency" in e.lower() or "apart" in e.lower() for e in errors)


def test_squadron_member_outside_zone():
    zone = DeploymentZone(player=1, x_min=0, y_min=0, x_max=120, y_max=30)
    s1 = make_ship(id="e1", ship_type="escort")
    s2 = make_ship(id="e2", ship_type="escort")
    positions = [(60.0, 15.0), (60.0, 45.0)]  # second is outside zone
    ok, errors = validate_squadron_placement([s1, s2], positions, zone, [])
    assert not ok
    assert any("outside" in e.lower() for e in errors)


# ── group_ships_for_deployment ────────────────────────────────────────────────

def test_solo_ships_each_get_own_group():
    ships = [make_ship(id="s1"), make_ship(id="s2")]
    groups = group_ships_for_deployment(ships)
    assert len(groups) == 2
    assert all(len(g) == 1 for g in groups)


def test_squadron_ships_grouped_together():
    e1 = make_ship(id="e1", ship_type="escort")
    e1.squadron_id = "sq1"
    e2 = make_ship(id="e2", ship_type="escort")
    e2.squadron_id = "sq1"
    captain = make_ship(id="cap", ship_type="cruiser")
    groups = group_ships_for_deployment([e1, e2, captain])
    assert len(groups) == 2  # 1 solo + 1 squadron
    squadron_group = next(g for g in groups if len(g) == 2)
    assert {s.id for s in squadron_group} == {"e1", "e2"}


def test_different_squadrons_separate_groups():
    e1 = make_ship(id="e1", ship_type="escort")
    e1.squadron_id = "sq1"
    e2 = make_ship(id="e2", ship_type="escort")
    e2.squadron_id = "sq2"
    groups = group_ships_for_deployment([e1, e2])
    assert len(groups) == 2


# ── DeploymentState (sequential) ─────────────────────────────────────────────

def _make_state(n_p1=2, n_p2=2, mode="sequential"):
    p1 = [make_ship(id=f"p1s{i}", player=1) for i in range(n_p1)]
    p2 = [make_ship(id=f"p2s{i}", player=2) for i in range(n_p2)]
    zones = get_default_zones(120, 120)
    return DeploymentState(p1, p2, zones, mode=mode), p1, p2


def test_sequential_starts_with_player1():
    state, _, _ = _make_state(mode="sequential")
    assert state.active_player == 1


def test_alternating_starts_with_player2():
    state, _, _ = _make_state(mode="alternating")
    assert state.active_player == 2


def test_not_complete_at_start():
    state, _, _ = _make_state()
    assert not state.is_complete()


def test_place_group_advances_index():
    state, _, _ = _make_state(n_p1=1, n_p2=1, mode="sequential")
    group = state.current_group()
    zone = state.zones[1]
    cx = (zone.x_min + zone.x_max) / 2
    cy = (zone.y_min + zone.y_max) / 2
    ok, errors = state.place_group([(cx, cy)], [0.0])
    assert ok, errors
    assert state.next_idx[1] == 1


def test_sequential_switches_to_p2_after_p1_done():
    state, _, _ = _make_state(n_p1=1, n_p2=1, mode="sequential")
    zone = state.zones[1]
    cx = (zone.x_min + zone.x_max) / 2
    cy = (zone.y_min + zone.y_max) / 2
    state.place_group([(cx, cy)], [0.0])
    assert state.active_player == 2


def test_complete_after_all_groups_placed():
    state, _, _ = _make_state(n_p1=1, n_p2=1, mode="sequential")
    z1 = state.zones[1]
    z2 = state.zones[2]
    state.place_group(
        [((z1.x_min + z1.x_max) / 2, (z1.y_min + z1.y_max) / 2)], [0.0])
    state.active_player = 2  # normally handled by _advance_player
    state.place_group(
        [((z2.x_min + z2.x_max) / 2, (z2.y_min + z2.y_max) / 2)], [180.0])
    assert state.is_complete()


def test_place_outside_zone_fails():
    state, _, _ = _make_state(n_p1=1, n_p2=0, mode="sequential")
    # P1 zone is y=0..30; place at y=80 → outside
    ok, errors = state.place_group([(60.0, 80.0)], [0.0])
    assert not ok
    assert any("outside" in e.lower() for e in errors)


def test_place_group_updates_ship_position():
    state, p1, _ = _make_state(n_p1=1, n_p2=0, mode="sequential")
    z = state.zones[1]
    cx, cy = (z.x_min + z.x_max) / 2, (z.y_min + z.y_max) / 2
    ok, _ = state.place_group([(cx, cy)], [90.0])
    assert ok
    ship = state.placed_ships[0]
    assert abs(ship.x - cx) < 0.01
    assert abs(ship.y - cy) < 0.01
    assert abs(ship.heading - 90.0) < 0.01


def test_alternating_switches_between_players():
    state, _, _ = _make_state(n_p1=2, n_p2=2, mode="alternating")
    assert state.active_player == 2
    z2 = state.zones[2]
    cx, cy = (z2.x_min + z2.x_max) / 2, (z2.y_min + z2.y_max) / 2
    state.place_group([(cx, cy)], [180.0])
    assert state.active_player == 1


def test_groups_remaining_decreases():
    state, _, _ = _make_state(n_p1=2, n_p2=0, mode="sequential")
    assert state.groups_remaining(1) == 2
    z = state.zones[1]
    cx, cy = (z.x_min + z.x_max) / 2, (z.y_min + z.y_max) / 2
    state.place_group([(cx, cy)], [0.0])
    assert state.groups_remaining(1) == 1
