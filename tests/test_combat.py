"""Tests for src/combat.py — pure helper functions."""
from tests.conftest import make_ship
from src.combat import check_weapon_in_arc, check_weapon_in_range


# ── check_weapon_in_arc ───────────────────────────────────────────────────────

def _ship(heading=0):
    return make_ship(x=0, y=0, heading=heading)


def test_front_arc_weapon_on_target_ahead():
    s = _ship(heading=0)  # heading east
    weapon = {"arcs": ["front"], "range_cm": 60}
    # Target due east of ship → front arc
    assert check_weapon_in_arc(s, weapon, 30, 0)


def test_front_arc_weapon_misses_target_abeam():
    s = _ship(heading=0)
    weapon = {"arcs": ["front"], "range_cm": 60}
    # Target due north → left arc, not front
    assert not check_weapon_in_arc(s, weapon, 0, 30)


def test_port_weapon_on_target_to_port():
    s = _ship(heading=0)  # heading east; north = port
    weapon = {"arcs": ["left"], "range_cm": 45}
    assert check_weapon_in_arc(s, weapon, 0, 30)


def test_port_weapon_misses_starboard_target():
    s = _ship(heading=0)
    weapon = {"arcs": ["left"], "range_cm": 45}
    # Target south of ship → right (starboard) arc
    assert not check_weapon_in_arc(s, weapon, 0, -30)


def test_multi_arc_weapon_hits_either_arc():
    s = _ship(heading=0)
    weapon = {"arcs": ["left", "front", "right"], "range_cm": 60}
    assert check_weapon_in_arc(s, weapon, 30, 0)    # front
    assert check_weapon_in_arc(s, weapon, 0, 30)    # left
    assert check_weapon_in_arc(s, weapon, 0, -30)   # right


def test_multi_arc_weapon_misses_rear():
    s = _ship(heading=0)
    weapon = {"arcs": ["left", "front", "right"], "range_cm": 60}
    assert not check_weapon_in_arc(s, weapon, -30, 0)  # rear


def test_empty_arcs_means_no_restriction():
    # Launch bays and torpedoes often have no arc restriction
    s = _ship()
    weapon = {"arcs": [], "range_cm": 30}
    assert check_weapon_in_arc(s, weapon, 0, 30)
    assert check_weapon_in_arc(s, weapon, -30, 0)


def test_arc_check_respects_ship_heading():
    # Ship heading north (90°), target is east → right (starboard) arc
    s = _ship(heading=90)
    weapon = {"arcs": ["right"], "range_cm": 60}
    assert check_weapon_in_arc(s, weapon, 30, 0)


# ── check_weapon_in_range ─────────────────────────────────────────────────────

def test_target_within_range():
    s = make_ship(x=0, y=0)
    weapon = {"range_cm": 45}
    assert check_weapon_in_range(s, weapon, 30, 0)


def test_target_at_exact_range():
    s = make_ship(x=0, y=0)
    weapon = {"range_cm": 30}
    assert check_weapon_in_range(s, weapon, 30, 0)


def test_target_beyond_range():
    s = make_ship(x=0, y=0)
    weapon = {"range_cm": 30}
    assert not check_weapon_in_range(s, weapon, 40, 0)


def test_zero_range_means_no_restriction():
    # Torpedoes/launch bays stored with range_cm=0 have no direct-fire range check
    s = make_ship(x=0, y=0)
    weapon = {"range_cm": 0}
    assert check_weapon_in_range(s, weapon, 200, 0)


def test_range_measured_from_ship_position():
    # Ship at (50, 50); target at (80, 50); distance = 30
    s = make_ship(x=50, y=50)
    weapon = {"range_cm": 30}
    assert check_weapon_in_range(s, weapon, 80, 50)
    assert not check_weapon_in_range(s, weapon, 81, 50)
