"""Tests for src/victory_points.py."""
from tests.conftest import make_ship, make_gs
from src.victory_points import calculate_victory_points, format_vp_summary


def _make_game(ships):
    gs = make_gs(ships)
    gs.player1_name = "Player 1"
    gs.player2_name = "Player 2"
    return gs


# ── destroyed ships ───────────────────────────────────────────────────────────

def test_destroyed_ship_gives_100_pct_vp():
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=0, status="destroyed")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["destroyed"] == 200
    assert vp[1]["destroyed"] == 0


def test_hulk_counts_as_destroyed():
    p1_ship = make_ship(id="s1", player=1, points_value=150, hits_max=8,
                        status="drifting_hulk")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["destroyed"] == 150


# ── crippled ships ────────────────────────────────────────────────────────────

def test_crippled_ship_gives_25_pct_vp():
    # hits_remaining=4, hits_max=8 → is_crippled property = True (50%)
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=4)
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["crippled"] == 50  # 25% of 200 = 50


# ── disengaged ships ──────────────────────────────────────────────────────────

def test_disengaged_not_crippled_gives_10_pct_vp():
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=8, is_disengaged=True, status="disengaged")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["disengaged"] == 20  # 10% of 200 = 20


def test_crippled_and_disengaged_gives_25_pct_vp():
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=4, is_disengaged=True,
                        status="disengaged")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["crippled"] == 50  # 25% not 10%


# ── totals ────────────────────────────────────────────────────────────────────

def test_totals_sum_all_categories():
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=0, status="destroyed")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["total"] == 200


def test_no_points_value_ship_earns_nothing():
    p1_ship = make_ship(id="s1", player=1, points_value=0, hits_max=8,
                        hits_remaining=0, status="destroyed")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    assert vp[2]["total"] == 0


# ── holding the field ─────────────────────────────────────────────────────────

def test_holding_field_earns_50_pct_of_hulk_points():
    # P2 hulk has hits_remaining=0 so is_destroyed=True and won't block field control.
    # It still has status="drifting_hulk" so _hulk_points counts it.
    p1 = make_ship(id="p1s", player=1, points_value=200, hits_max=8,
                   hits_remaining=8, status="active")
    p2_hulk = make_ship(id="p2h", player=2, points_value=100, hits_max=8,
                        hits_remaining=0, status="drifting_hulk")
    gs = _make_game([p1, p2_hulk])
    vp = calculate_victory_points(gs)
    # P1 holds field: P2 hulk is_destroyed (hits=0) so not enemy_on_table; P1 is active
    # Hulk 100pts → 50% = 50 VP
    assert vp[1]["holding_field"] == 50


# ── escort squadrons ──────────────────────────────────────────────────────────

def test_full_squadron_destroyed_gives_100_pct():
    e1 = make_ship(id="e1", player=1, ship_type="escort", points_value=40,
                   squadron_id="sq1", hits_max=2, hits_remaining=0, status="destroyed")
    e2 = make_ship(id="e2", player=1, ship_type="escort", points_value=40,
                   squadron_id="sq1", hits_max=2, hits_remaining=0, status="destroyed")
    gs = _make_game([e1, e2])
    vp = calculate_victory_points(gs)
    assert vp[2]["destroyed"] == 80  # 100% of 40+40


def test_half_squadron_destroyed_gives_crippled_vp():
    # 2 escort squadron, 1 destroyed → half = cripple threshold
    e1 = make_ship(id="e1", player=1, ship_type="escort", points_value=40,
                   squadron_id="sq1", hits_max=2, hits_remaining=0, status="destroyed")
    e2 = make_ship(id="e2", player=1, ship_type="escort", points_value=40,
                   squadron_id="sq1", hits_max=2, hits_remaining=2)
    gs = _make_game([e1, e2])
    vp = calculate_victory_points(gs)
    # 1 of 2 destroyed reaches the cripple threshold: 25% of the squadron, nothing else
    assert vp[2]["crippled"] == 20
    assert vp[2]["destroyed"] == 0
    assert vp[2]["total"] == 20


def _escort(id, **kw):
    return make_ship(id=id, player=1, ship_type="escort", points_value=40,
                     squadron_id="sq1", hits_max=2, **kw)


def test_crippled_squadron_destroyed_escorts_not_counted_twice():
    dead = dict(hits_remaining=0, status="destroyed")
    gs = _make_game([_escort("e1", **dead), _escort("e2", **dead),
                     _escort("e3"), _escort("e4")])
    vp = calculate_victory_points(gs)
    # 2 of 4 destroyed: crippled, 25% of 160 = 40, and no 80 for the dead escorts
    assert (vp[2]["destroyed"], vp[2]["crippled"], vp[2]["total"]) == (0, 40, 40)


def test_mostly_destroyed_squadron_that_ran_counts_as_crippled_not_scattered():
    dead = dict(hits_remaining=0, status="destroyed")
    gs = _make_game([_escort("e1", **dead), _escort("e2", **dead),
                     _escort("e3", is_disengaged=True)])
    vp = calculate_victory_points(gs)
    # 2 of 3 destroyed (threshold 2): crippled 25% of 120 = 30, not 80 + 4
    assert (vp[2]["destroyed"], vp[2]["crippled"], vp[2]["disengaged"]) == (0, 30, 0)


def test_squadron_that_disengaged_with_light_losses_is_scattered():
    gs = _make_game([_escort("e1", hits_remaining=0, status="destroyed"),
                     _escort("e2", is_disengaged=True),
                     _escort("e3", is_disengaged=True)])
    vp = calculate_victory_points(gs)
    # 1 of 3 destroyed (below threshold 2), the rest disengaged: 10% of 120 = 12
    assert (vp[2]["destroyed"], vp[2]["crippled"], vp[2]["disengaged"]) == (0, 0, 12)


def test_lightly_damaged_squadron_still_fighting_scores_nothing():
    gs = _make_game([_escort("e1", hits_remaining=0, status="destroyed"),
                     _escort("e2"), _escort("e3")])
    assert calculate_victory_points(gs)[2]["total"] == 0


# ── format_vp_summary ─────────────────────────────────────────────────────────

def test_format_vp_summary_produces_output():
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=0, status="destroyed")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    summary = format_vp_summary(vp, gs)
    assert "Player 1" in summary or "Player 2" in summary
    assert "VP" in summary


def test_format_vp_winner_shown():
    p1_ship = make_ship(id="s1", player=1, points_value=200, hits_max=8,
                        hits_remaining=0, status="destroyed")
    gs = _make_game([p1_ship])
    vp = calculate_victory_points(gs)
    summary = format_vp_summary(vp, gs)
    assert "WINNER" in summary or "DRAW" in summary
