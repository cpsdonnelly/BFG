"""Tests for game-end detection in scenario.py."""
from src.scenario import check_game_over, vp_winner
from tests.conftest import make_ship, make_gs


def _turn_limit_gs(p2_destroyed: bool):
    p1 = make_ship(id="a", player=1, points_value=200)
    p2 = make_ship(id="b", player=2, points_value=200)
    p2b = make_ship(id="c", player=2, points_value=150,
                    hits_remaining=0 if p2_destroyed else 8,
                    status="destroyed" if p2_destroyed else "active")
    gs = make_gs([p1, p2, p2b])
    gs.turn_limit = 3
    gs.turn_number = 4
    return gs


def test_turn_limit_ends_game_with_vp_winner():
    result = check_game_over(_turn_limit_gs(p2_destroyed=True))
    assert result == {"winner": 1, "reason": "turn_limit", "detail": ""}


def test_turn_limit_tie_has_no_winner():
    result = check_game_over(_turn_limit_gs(p2_destroyed=False))
    assert result["reason"] == "turn_limit"
    assert result["winner"] is None


def test_vp_winner_player2():
    p1 = make_ship(id="a", player=1, points_value=300,
                   hits_remaining=0, status="destroyed")
    p2 = make_ship(id="b", player=2, points_value=100)
    assert vp_winner(make_gs([p1, p2])) == 2


def test_game_continues_before_turn_limit():
    gs = _turn_limit_gs(p2_destroyed=False)
    gs.turn_number = 3
    assert check_game_over(gs) is None
