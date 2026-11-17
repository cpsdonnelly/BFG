"""Tests for AIPlayer torpedo intercept aiming (_torpedo_aim_heading)."""
import math
from tests.conftest import make_ship, make_gs
from src.ai_player import AIPlayer


def _ai(gs):
    # tc/dice are unused by _torpedo_aim_heading, so stubs are fine.
    return AIPlayer(player=1, tc=None, gs=gs, dice=None, difficulty="normal")


def test_short_range_stationary_aims_directly_at_target():
    # Target dead ahead, not moving: aim should be straight at it (heading 0).
    ship = make_ship(id="s", x=0, y=0, heading=0, player=1)
    target = make_ship(id="e", x=20, y=0, heading=0, speed=0, player=2)
    gs = make_gs([ship, target])
    weapon = {"torpedo_speed": 30, "strength": 6}
    aim = _ai(gs)._torpedo_aim_heading(ship, weapon, target)
    assert abs(aim - 0.0) < 0.5


def test_short_range_offset_aims_at_current_position():
    # Target offset +30deg within the front arc, not moving: aim at it directly.
    ship = make_ship(id="s", x=0, y=0, heading=0, player=1)
    tx = 20 * math.cos(math.radians(30))
    ty = 20 * math.sin(math.radians(30))
    target = make_ship(id="e", x=tx, y=ty, heading=0, speed=0, player=2)
    gs = make_gs([ship, target])
    weapon = {"torpedo_speed": 30, "strength": 6}
    aim = _ai(gs)._torpedo_aim_heading(ship, weapon, target)
    assert abs(aim - 30.0) < 1.0


def test_long_range_crossing_target_leads_ahead():
    # Target far ahead, crossing to port (moving +y). Aim should lead above 0deg
    # toward where the target is going, but stay within the +45deg arc.
    ship = make_ship(id="s", x=0, y=0, heading=0, player=1)
    target = make_ship(id="e", x=120, y=0, heading=90, speed=20, player=2)
    gs = make_gs([ship, target])
    weapon = {"torpedo_speed": 30, "strength": 6}
    aim = _ai(gs)._torpedo_aim_heading(ship, weapon, target)
    assert 0.0 < aim <= 45.0


def test_aim_clamped_to_forward_arc():
    # Target far off to the side (90deg) so the intercept would exceed the arc;
    # result must be clamped to <= 45deg.
    ship = make_ship(id="s", x=0, y=0, heading=0, player=1)
    target = make_ship(id="e", x=0, y=60, heading=0, speed=0, player=2)
    gs = make_gs([ship, target])
    weapon = {"torpedo_speed": 30, "strength": 6}
    aim = _ai(gs)._torpedo_aim_heading(ship, weapon, target)
    assert abs(aim - 45.0) < 0.5
