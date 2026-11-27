"""Strategy candidates for every ship (owner, To do 34): flanks, the range
band, kiting, closing, screening, the edge; first moves towards them are
searched and the plan followed in the sim (src/strategies.py, lookahead_ai)."""
import math

from tests.conftest import make_ship, make_gs, make_gunship, DiceStub
from src.strategies import Strategy, plan_waypoint, strategies_for, head_for_move, PLAN_TURNS

GUN = {"name": "Batteries", "weapon_type": "battery", "range_cm": 30, "strength": 6,
       "arcs": ["left", "front", "right"]}


def _ai(ships, player=1, difficulty="normal"):
    from src.lookahead_ai import LookaheadAI
    from src.turn_controller import TurnController
    gs = make_gs(ships)
    dice = DiceStub([])
    return LookaheadAI(player, TurnController(gs, dice), gs, dice, difficulty=difficulty), gs


def test_flank_waypoint_sits_in_the_targets_rear_arc_and_tracks_it():
    t = make_ship(id="t", player=2, x=50.0, y=50.0, heading=0.0)
    me = make_ship(id="m", player=1, x=0.0, y=50.0)
    plan = Strategy("flank_left", "rel_heading", "t", 180.0 + 45.0, 20.0)
    wx, wy = plan_waypoint(plan, me, [t, me])
    assert wx < t.x                                  # behind it (it faces +x)
    assert t.get_arc_for_bearing(math.degrees(math.atan2(wy - t.y, wx - t.x)) % 360) == "rear"
    t.x, t.heading = 80.0, 90.0                      # it moves and turns: the point follows
    wx2, wy2 = plan_waypoint(plan, me, [t, me])
    assert wy2 < t.y and abs(wx2 - t.x) < 20.0


def test_every_ship_gets_flanks_and_its_band():
    me = make_ship(id="m", player=1, x=0.0, y=0.0, weapons=[dict(GUN)], points_value=150)
    foe = make_ship(id="f", player=2, x=60.0, y=0.0, heading=180.0, weapons=[dict(GUN)],
                    points_value=150)
    ai, gs = _ai([me, foe])
    names = {s.name for s in strategies_for(ai, gs.get_ship_by_id("m"), gs.get_ship_by_id("f"))}
    assert {"flank_left", "flank_right"} <= names
    cr = make_ship(id="c", player=1, x=5.0, y=5.0, hits_max=8, hits_remaining=3,
                   weapons=[dict(GUN)])
    ai2, gs2 = _ai([cr, foe])
    assert "to_edge" in {s.name for s in strategies_for(ai2, gs2.get_ship_by_id("c"),
                                                        gs2.get_ship_by_id("f"))}


def test_strategy_first_moves_are_legal_and_head_for_the_waypoint():
    me = make_ship(id="m", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(GUN)],
                   points_value=150)
    foe = make_ship(id="f", player=2, x=60.0, y=0.0, heading=180.0, weapons=[dict(GUN)],
                    points_value=150)
    ai, gs = _ai([me, foe])
    moves = ai._strategy_moves(gs.get_ship_by_id("m"), gs.get_ship_by_id("f"), "", 0)
    assert moves
    valid = ai._candidate_validator(gs.get_ship_by_id("m"), "", 0)
    for (turn, dist, at, src), strat in moves:
        assert valid(turn, dist, at) and src == "strategy:" + strat.name
    left = next(c for c, s in moves if s.name == "flank_left")
    right = next(c for c, s in moves if s.name == "flank_right")
    assert left[0] * right[0] < 0                     # they turn opposite ways


def test_the_sim_follows_a_plan_for_its_turns():
    from src.lookahead_ai import SimState, _generate_best_moves, _simulate_turn
    me = make_ship(id="m", player=1, x=0.0, y=0.0, heading=0.0, speed=25, weapons=[dict(GUN)],
                   points_value=150)
    foe = make_ship(id="f", player=2, x=60.0, y=0.0, heading=180.0, weapons=[dict(GUN)],
                    points_value=150)
    ai, gs = _ai([me, foe])
    st = SimState.from_gs(gs)
    plan = Strategy("flank_left", "rel_heading", "f", 180.0 + 45.0, 20.0)
    st.plans["m"] = [plan, PLAN_TURNS - 1]
    moves = _generate_best_moves(st, 1, ai)
    sm = next(s for s in st.ships if s.id == "m")
    wx, wy = plan_waypoint(plan, sm, st.ships)
    assert moves["m"] == head_for_move(sm, wx, wy, sm.speed, sm.turn_angle, 10.0)
    nxt = _simulate_turn(st, 1, moves, {})
    assert "m" not in nxt.plans                       # followed for its turns, then dropped


def test_the_search_tries_every_strategy_and_judges_them_over_the_same_horizon():
    me = make_ship(id="m", player=1, x=0.0, y=40.0, heading=0.0, speed=25, weapons=[dict(GUN)],
                   points_value=150)
    foe = make_ship(id="f", player=2, x=50.0, y=40.0, heading=180.0, weapons=[dict(GUN)],
                    points_value=150)
    ai, gs = _ai([me, foe, make_gunship(player=1, x=-150.0, y=-150.0),
                  make_gunship(player=2, x=150.0, y=150.0)])
    gs.table_width = gs.table_height = 200.0
    ai._plan_move_toward(gs.get_ship_by_id("m"), gs.get_ship_by_id("f"), "", 0)
    assert ai.DEPTH >= PLAN_TURNS and ai._base_depth == 1
    assert ai.beam(0) == 4 and ai.beam(1) == 1        # the strategy's extra turn: one line
