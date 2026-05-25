"""Tests for src/movement.py — pure speed and turn helpers."""
from tests.conftest import make_ship
from src.movement import get_effective_speed, get_max_turns
from src.models import SpecialOrder


# ── get_effective_speed ───────────────────────────────────────────────────────

def _speed(order, ship=None, aaf_bonus=0, blast=False):
    s = ship or make_ship(speed=20)
    return get_effective_speed(s, order, aaf_bonus=aaf_bonus, blast_slowdown=blast)


def test_normal_order_speed_range():
    lo, hi = _speed(SpecialOrder.NONE.value)
    assert lo == 10   # max(1, 20//2)
    assert hi == 20


def test_lock_on_speed_range():
    lo, hi = _speed(SpecialOrder.LOCK_ON.value)
    assert lo == 10
    assert hi == 20


def test_burn_retros_speed_range():
    lo, hi = _speed(SpecialOrder.BURN_RETROS.value)
    assert lo == 0
    assert hi == 10   # 20 // 2


def test_aaf_speed_equals_base_plus_bonus():
    lo, hi = _speed(SpecialOrder.ALL_AHEAD_FULL.value, aaf_bonus=8)
    assert lo == hi == 28


def test_aaf_bonus_zero():
    lo, hi = _speed(SpecialOrder.ALL_AHEAD_FULL.value, aaf_bonus=0)
    assert lo == hi == 20


def test_brace_speed_like_normal():
    lo, hi = _speed(SpecialOrder.BRACE_FOR_IMPACT.value)
    assert lo == 10
    assert hi == 20


def test_brace_after_aaf_preserves_aaf_speed():
    s = make_ship(speed=20, previous_order=SpecialOrder.ALL_AHEAD_FULL.value)
    # Ship is braced but was on AAF last turn → AAF speed persists
    # We need to simulate aaf_bonus; use 6 as a typical roll
    lo, hi = get_effective_speed(s, SpecialOrder.BRACE_FOR_IMPACT.value, aaf_bonus=6)
    assert lo == hi == 26


def test_blast_slowdown_reduces_max():
    lo, hi = _speed(SpecialOrder.NONE.value, blast=True)
    assert hi == 15   # 20 - 5
    assert lo <= hi


def test_blast_slowdown_does_not_affect_aaf():
    # AAF uses (base + bonus, base + bonus); blast_slowdown path isn't taken
    lo, hi = _speed(SpecialOrder.ALL_AHEAD_FULL.value, aaf_bonus=4, blast=True)
    assert lo == hi == 24


def test_crippled_ship_lower_effective_speed():
    s = make_ship(speed=20, hits_max=8, hits_remaining=4)   # crippled → speed 15
    lo, hi = get_effective_speed(s, SpecialOrder.NONE.value)
    assert hi == 15
    assert lo == max(1, 15 // 2)   # 7


# ── get_max_turns ─────────────────────────────────────────────────────────────

def test_normal_order_one_turn():
    s = make_ship()
    assert get_max_turns(SpecialOrder.NONE.value, s) == 1


def test_reload_one_turn():
    s = make_ship()
    assert get_max_turns(SpecialOrder.RELOAD_ORDNANCE.value, s) == 1


def test_aaf_no_turns():
    s = make_ship()
    assert get_max_turns(SpecialOrder.ALL_AHEAD_FULL.value, s) == 0


def test_lock_on_no_turns():
    s = make_ship()
    assert get_max_turns(SpecialOrder.LOCK_ON.value, s) == 0


def test_come_to_new_heading_two_turns():
    s = make_ship()
    assert get_max_turns(SpecialOrder.COME_TO_NEW_HEADING.value, s) == 2


def test_ponderous_ctnh_no_turns():
    s = make_ship(special_rules=["ponderous"])
    assert get_max_turns(SpecialOrder.COME_TO_NEW_HEADING.value, s) == 0


def test_engine_room_crit_no_turns():
    s = make_ship(critical_damage=[{"crit_type": "engine_room"}])
    assert get_max_turns(SpecialOrder.NONE.value, s) == 0


def test_engine_room_crit_overrides_ctnh():
    s = make_ship(critical_damage=[{"crit_type": "engine_room"}])
    assert get_max_turns(SpecialOrder.COME_TO_NEW_HEADING.value, s) == 0
