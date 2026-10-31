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


# ── s.5 Maneuvering Squadrons: escort squadron that loses a ship off the table ──

def _escort_squadron(n=3, **kw):
    return [make_ship(id=f"e{i}", name=f"E{i}", player=1, ship_type="escort", hits_max=1,
                      leadership=7, x=4.0 + 5.0 * i, y=60.0, heading=180.0,
                      squadron_id="sq", **kw) for i in range(n)]


def _drive_off_table(gs, ship_id, dice):
    from src.movement import MoveCommand, validate_movement, execute_movement
    ship = gs.get_ship_by_id(ship_id)
    r = validate_movement(ship, [MoveCommand("forward", 10.0)], "none")
    execute_movement(ship, r, gs, dice)


def test_rest_of_escort_squadron_tests_right_away_and_leaves_on_a_pass():
    gs = make_gs(_escort_squadron())
    dice = DiceStub([5])                 # squadron disengage 2D6 = 5 <= Ld 7
    _drive_off_table(gs, "e0", dice)
    assert dice._idx == 1
    assert [gs.get_ship_by_id(f"e{i}").is_disengaged for i in range(3)] == [True, True, True]


def test_failed_test_blocks_firing_this_turn_and_squadron_keeps_trying():
    from src.turn_controller import TurnController
    import tempfile
    gs = make_gs(_escort_squadron())
    gs.turn_number = 3
    dice = DiceStub([11])                # fails
    _drive_off_table(gs, "e0", dice)
    for sid in ("e1", "e2"):
        s = gs.get_ship_by_id(sid)
        assert not s.is_disengaged and s.must_disengage
        assert s.disengage_failed_this_turn and s.has_fired
        assert s.must_disengage_tested_turn == 3

    tc = TurnController(gs, dice, save_dir=tempfile.mkdtemp())
    gs.current_phase, gs.active_player = "movement", 1
    tc.end_phase()                        # same turn: already tested, no second roll
    assert dice._idx == 1

    gs.turn_number = 5                    # its next turn
    dice._results, dice._idx = [6], 0     # passes
    tc.end_phase()
    assert dice._idx == 1
    assert gs.get_ship_by_id("e1").is_disengaged and gs.get_ship_by_id("e2").is_disengaged


def test_squadron_test_uses_best_placed_members_leadership():
    from src.disengage import squadron_disengage_test
    from src.models import BlastMarker
    ships = _escort_squadron()
    enemy = make_ship(id="foe", player=2, x=ships[2].x + 6.0, y=60.0)     # -1 Ld near e1, e2 (16cm from e0)
    gs = make_gs(ships + [enemy])
    for i in range(2):                                                    # +2 Ld near e0
        gs.add_blast_marker(BlastMarker(id=f"bm{i}", x=ships[0].x, y=63.0))
    dice = DiceStub([9])                  # passes only on e0's Ld 9
    r = squadron_disengage_test(ships, dice, gs)
    assert r["needed"] == 9 and r["success"]
    assert dice._idx == 1


def test_capital_ship_leaving_table_does_not_force_its_squadron_out():
    cruisers = [make_ship(id=f"c{i}", player=1, ship_type="cruiser", x=4.0 + 8.0 * i,
                          y=60.0, heading=180.0, squadron_id="csq") for i in range(2)]
    gs = make_gs(cruisers)
    dice = DiceStub([2])
    _drive_off_table(gs, "c0", dice)
    assert dice._idx == 0
    c1 = gs.get_ship_by_id("c1")
    assert not c1.is_disengaged and not c1.must_disengage
