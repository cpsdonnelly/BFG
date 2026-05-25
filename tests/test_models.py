"""Tests for src/models.py — Ship dataclass and related types."""
from tests.conftest import make_ship
from src.models import Ship, BaseSize, SpecialOrder


# ── post_init ────────────────────────────────────────────────────────────────

def test_post_init_sets_hits_to_hits_max():
    s = make_ship(hits_max=10)
    assert s.hits_remaining == 10


def test_post_init_respects_explicit_hits_remaining():
    s = make_ship(hits_max=10, hits_remaining=3)
    assert s.hits_remaining == 3


def test_post_init_preserves_zero_hits():
    # Destroyed ships stored with hits_remaining=0 must not be reset
    s = make_ship(hits_max=8, hits_remaining=0)
    assert s.hits_remaining == 0


# ── base_radius ───────────────────────────────────────────────────────────────

def test_base_radius_small():
    s = make_ship(base_size="small")
    assert s.base_radius == 1.6


def test_base_radius_large():
    s = make_ship(base_size="large")
    assert s.base_radius == 3.0


# ── is_crippled ───────────────────────────────────────────────────────────────

def test_is_crippled_at_exactly_half():
    s = make_ship(hits_max=8, hits_remaining=4)
    assert s.is_crippled


def test_is_crippled_below_half():
    s = make_ship(hits_max=8, hits_remaining=2)
    assert s.is_crippled


def test_not_crippled_above_half():
    s = make_ship(hits_max=8, hits_remaining=5)
    assert not s.is_crippled


def test_not_crippled_at_full():
    s = make_ship(hits_max=8)
    assert not s.is_crippled


def test_not_crippled_at_zero_hits():
    # A destroyed ship is NOT crippled (is_crippled requires hits_remaining > 0)
    s = make_ship(hits_max=8, hits_remaining=0)
    assert not s.is_crippled


# ── is_destroyed ──────────────────────────────────────────────────────────────

def test_is_destroyed_at_zero_hits():
    s = make_ship(hits_remaining=0)
    assert s.is_destroyed


def test_not_destroyed_at_one_hit():
    s = make_ship(hits_remaining=1)
    assert not s.is_destroyed


# ── armor values ─────────────────────────────────────────────────────────────

def test_armor_prow_value_6():
    assert make_ship(armor_prow="6+").armor_prow_value == 6


def test_armor_prow_value_5():
    assert make_ship(armor_prow="5+").armor_prow_value == 5


def test_armor_side_value():
    assert make_ship(armor_side="4+").armor_side_value == 4


# ── effective_speed ───────────────────────────────────────────────────────────

def test_effective_speed_healthy():
    s = make_ship(speed=20)
    assert s.effective_speed == 20


def test_effective_speed_crippled():
    s = make_ship(speed=20, hits_max=8, hits_remaining=4)
    assert s.effective_speed == 15   # -5


def test_effective_speed_thrusters_crit():
    s = make_ship(speed=20, critical_damage=[{"crit_type": "thrusters_damaged"}])
    assert s.effective_speed == 10   # -10


def test_effective_speed_crippled_and_crit():
    s = make_ship(speed=20, hits_max=8, hits_remaining=4,
                  critical_damage=[{"crit_type": "thrusters_damaged"}])
    assert s.effective_speed == 5   # -5 crippled, -10 crit = 5


def test_effective_speed_floor_zero():
    s = make_ship(speed=5, hits_max=8, hits_remaining=4,
                  critical_damage=[{"crit_type": "thrusters_damaged"}])
    assert s.effective_speed == 0


# ── effective_shields ─────────────────────────────────────────────────────────

def test_effective_shields_healthy():
    s = make_ship(shields_max=4)
    assert s.effective_shields == 4


def test_effective_shields_crippled_even():
    s = make_ship(shields_max=4, hits_max=8, hits_remaining=4)
    assert s.effective_shields == 2


def test_effective_shields_crippled_odd():
    # Rounds up: 3 → 2 (halved, rounded up = ceil(1.5) = 2)
    s = make_ship(shields_max=3, hits_max=8, hits_remaining=4)
    assert s.effective_shields == 2


def test_effective_shields_collapse_crit():
    s = make_ship(shields_max=4, critical_damage=[{"crit_type": "shields_collapse"}])
    assert s.effective_shields == 0


# ── effective_turrets ─────────────────────────────────────────────────────────

def test_effective_turrets_healthy():
    s = make_ship(turrets=4)
    assert s.effective_turrets == 4


def test_effective_turrets_crippled():
    s = make_ship(turrets=4, hits_max=8, hits_remaining=4)
    assert s.effective_turrets == 2


# ── bearing_to / get_target_arc ───────────────────────────────────────────────

def test_bearing_to_east():
    s = make_ship(x=0, y=0)
    assert abs(s.bearing_to(10, 0) - 0) < 0.01


def test_bearing_to_north():
    s = make_ship(x=0, y=0)
    assert abs(s.bearing_to(0, 10) - 90) < 0.01


def test_get_target_arc_front():
    # Ship heading east (0°), target dead ahead east → front
    s = make_ship(x=0, y=0, heading=0)
    assert s.get_target_arc(10, 0).value == "front"


def test_get_target_arc_left():
    # Ship heading east (0°), target due north → left (port) arc
    s = make_ship(x=0, y=0, heading=0)
    assert s.get_target_arc(0, 10).value == "left"


def test_get_target_arc_right():
    # Ship heading east (0°), target due south → right (starboard) arc
    s = make_ship(x=0, y=0, heading=0)
    assert s.get_target_arc(0, -10).value == "right"


def test_get_target_arc_rear():
    # Ship heading east (0°), target due west → rear arc
    s = make_ship(x=0, y=0, heading=0)
    assert s.get_target_arc(-10, 0).value == "rear"
