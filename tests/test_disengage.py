"""Tests for src/disengage.py."""
from tests.conftest import make_ship, make_gs, make_blast, DiceStub
from src.disengage import (check_off_table, process_involuntary_disengage,
                            get_disengage_ld_modifiers, attempt_disengage)
from src.models import OrdnanceMarker


# ── check_off_table ───────────────────────────────────────────────────────────

def test_ship_on_table_not_off():
    ship = make_ship(id="s", x=60, y=60, base_size="small")
    assert check_off_table(ship, 120, 120) is False


def test_ship_off_left_edge():
    # base_radius for small = 1.6cm; x - 1.6 < 0 → off
    ship = make_ship(id="s", x=1, y=60, base_size="small")
    assert check_off_table(ship, 120, 120) is True


def test_ship_off_right_edge():
    ship = make_ship(id="s", x=119, y=60, base_size="small")
    assert check_off_table(ship, 120, 120) is True


def test_ship_off_top_edge():
    ship = make_ship(id="s", x=60, y=119, base_size="small")
    assert check_off_table(ship, 120, 120) is True


def test_ship_off_bottom_edge():
    ship = make_ship(id="s", x=60, y=1, base_size="small")
    assert check_off_table(ship, 120, 120) is True


# ── process_involuntary_disengage ─────────────────────────────────────────────

def test_involuntary_disengage_sets_status():
    ship = make_ship(id="s")
    gs = make_gs([ship])
    process_involuntary_disengage(ship, gs)
    assert ship.is_disengaged is True
    assert ship.status == "disengaged"


# ── get_disengage_ld_modifiers ────────────────────────────────────────────────

def test_base_ld_no_modifiers():
    ship = make_ship(id="s", leadership=7)
    gs = make_gs([ship])
    info = get_disengage_ld_modifiers(ship, gs)
    assert info["base_ld"] == 7
    assert info["effective_ld"] == 7
    assert info["total_modifier"] == 0


def test_blast_marker_within_5cm_adds_modifier():
    ship = make_ship(id="s", x=50, y=50, leadership=7)
    gs = make_gs([ship])
    # Place blast marker 3cm away
    gs.add_blast_marker(make_blast(x=53, y=50, bid="bm1"))
    info = get_disengage_ld_modifiers(ship, gs)
    assert info["total_modifier"] >= 1
    assert info["effective_ld"] >= 8


def test_enemy_ship_within_15cm_penalizes():
    ship = make_ship(id="s", x=50, y=50, leadership=7, player=1)
    enemy = make_ship(id="e", x=60, y=50, player=2)  # 10cm away
    gs = make_gs([ship, enemy])
    info = get_disengage_ld_modifiers(ship, gs)
    # Enemy within 15cm → -1 Ld
    assert info["total_modifier"] <= -1


def test_enemy_outside_15cm_no_penalty():
    ship = make_ship(id="s", x=0, y=0, leadership=7, player=1)
    enemy = make_ship(id="e", x=20, y=0, player=2)  # 20cm away
    gs = make_gs([ship, enemy])
    info = get_disengage_ld_modifiers(ship, gs)
    assert info["total_modifier"] == 0


# ── attempt_disengage ─────────────────────────────────────────────────────────

def test_attempt_disengage_pass():
    ship = make_ship(id="s", leadership=7)
    gs = make_gs([ship])
    dice = DiceStub([7])  # roll 7 ≤ Ld 7 → pass
    r = attempt_disengage(ship, dice, gs)
    assert r["success"] is True
    assert ship.is_disengaged is True
    assert ship.status == "disengaged"


def test_attempt_disengage_fail():
    ship = make_ship(id="s", leadership=7)
    gs = make_gs([ship])
    dice = DiceStub([8])  # roll 8 > Ld 7 → fail
    r = attempt_disengage(ship, dice, gs)
    assert r["success"] is False
    assert ship.disengage_failed_this_turn is True
    assert ship.has_fired is True  # prevent firing
    assert ship.is_disengaged is False


def test_attempt_disengage_effective_ld_capped_at_10():
    ship = make_ship(id="s", leadership=7, x=50, y=50)
    gs = make_gs([ship])
    # Add 10 blast markers within 5cm → +10 modifier, but effective Ld capped at 10
    for i in range(10):
        gs.add_blast_marker(make_blast(x=50.0 + i * 0.1, y=50, bid=f"bm{i}"))
    info = get_disengage_ld_modifiers(ship, gs)
    assert info["effective_ld"] <= 10
