"""Booklet scenarios (src/scenarios.py, To do 7): Confrontation and Domination
(XR p.117, p.125-126)."""
import math

import pytest

from src import scenarios as sc
from src.scenario import check_game_over
from tests.conftest import DiceStub, make_gs, make_ship


def _gs(ships, mode="domination", layout=1, w=180.0, h=120.0):
    gs = make_gs(ships)
    gs.table_width, gs.table_height = w, h
    gs.scenario_mode = mode
    gs.scenario_attacker = 1
    if mode == "domination":
        sc.setup_scenario(gs, layout=layout)
    return gs


@pytest.mark.parametrize("n,count", [(1, 3), (2, 3), (3, 4), (4, 4), (5, 4), (6, 3)])
def test_domination_layouts(n, count):
    gs = _gs([], layout=n)
    objs = sc.objectives(gs)
    assert len(objs) == count
    zones = sc.deployment_zones(gs)
    att = next(z for z in zones if z.player == 1)
    dfn = next(z for z in zones if z.player == 2)
    for (x, y) in objs:
        assert 0 <= x <= 180 and 0 <= y <= 120
    # The zones don't overlap each other
    for x in range(0, 181, 5):
        for y in range(0, 121, 5):
            assert not (att.contains(x, y) and dfn.contains(x, y)), (n, x, y)


def test_layout_positions_match_the_diagrams():
    gs = _gs([], layout=2)
    # 30cm from the right and top edges (top = y 120), the centre, 30cm from
    # the left and bottom edges
    assert sc.objectives(gs) == [(150.0, 90.0), (90.0, 60.0), (30.0, 30.0)]
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(100, 100) and not zones[1].contains(130, 100)
    assert zones[2].contains(70, 10) and not zones[2].contains(50, 10)
    # Domination 3: L-shaped zones
    gs = _gs([], layout=3)
    att = {z.player: z for z in sc.deployment_zones(gs)}[1]
    assert att.contains(40, 25) and att.contains(25, 40)
    assert not att.contains(40, 40) and not att.contains(25, 50)


def test_setup_rolls_the_d6():
    gs = make_gs([])
    gs.table_width, gs.table_height = 180.0, 120.0
    gs.scenario_mode = "domination"
    dice = DiceStub([4])
    sc.setup_scenario(gs, dice)
    assert dice._idx == 1 and gs.scenario_state["layout"] == 4
    assert len(sc.objectives(gs)) == 4


def test_control_needs_a_ship_within_15cm_and_no_enemy():
    a = make_ship(id="a", player=1, x=30.0, y=70.0)        # 10cm from (30, 60)
    b = make_ship(id="b", player=2, x=90.0, y=74.0)        # 14cm from the centre
    c = make_ship(id="c", player=2, x=165.0, y=60.0)       # 15cm: in range (stem)
    gs = _gs([a, b, c])
    m = sc.objectives(gs)
    assert sc.controller(gs, m[0]) == 1
    assert sc.controller(gs, m[1]) == 2
    assert sc.controller(gs, m[2]) == 2
    # An enemy ship in range contests it
    d = make_ship(id="d", player=1, x=95.0, y=60.0)
    gs.ships.append(d.to_dict())
    assert sc.controller(gs, m[1]) is None
    # A hulk holds nothing (reading)
    hulk = make_ship(id="h", player=2, x=30.0, y=55.0, status="drifting_hulk")
    gs.ships.append(hulk.to_dict())
    assert sc.controller(gs, m[0]) == 1


def test_scoring_at_the_end_of_each_players_turn_and_ending_at_10():
    a = make_ship(id="a", player=1, x=30.0, y=60.0)
    b = make_ship(id="b", player=1, x=90.0, y=60.0)
    e = make_ship(id="e", player=2, x=150.0, y=60.0)
    gs = _gs([a, b, e])
    assert sc.score_end_of_turn(gs, 1) == 2
    assert sc.score_end_of_turn(gs, 2) == 1
    assert sc.points(gs) == {1: 2, 2: 1}
    assert check_game_over(gs) is None
    for _ in range(4):
        sc.score_end_of_turn(gs, 1)
    res = check_game_over(gs)
    assert res["winner"] == 1 and res["reason"] == "objective_points"


def test_turn_controller_scores_the_active_player():
    from src.turn_controller import TurnController
    a = make_ship(id="a", player=1, x=30.0, y=60.0)
    e = make_ship(id="e", player=2, x=150.0, y=10.0)
    gs = _gs([a, e])
    tc = TurnController(gs, DiceStub([3]))
    gs.active_player = 1
    gs.current_phase = "end"
    tc.end_phase()
    assert sc.points(gs) == {1: 1, 2: 0}


def test_fleet_gone_is_decided_by_the_scenario():
    # Domination: player 2's fleet is gone but player 2 leads on points
    a = make_ship(id="a", player=1, x=30.0, y=60.0)
    e = make_ship(id="e", player=2, x=150.0, y=60.0, hits_remaining=0, status="destroyed",
                  points_value=180)
    gs = _gs([a, e])
    gs.scenario_state["points"] = {"1": 2, "2": 5}
    res = check_game_over(gs)
    assert res["reason"] == "no_ships" and res["winner"] == 2
    # Confrontation: by VP (player 1 destroyed an 8-hit cruiser)
    gs = _gs([a, e], mode="confrontation")
    res = check_game_over(gs)
    assert res["winner"] == 1


def test_confrontation_zones_and_first_turn():
    gs = _gs([], mode="confrontation")
    gs.scenario_attacker = 2
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(50, 100) and zones[1].contains(50, 20)
    assert sc.first_player(gs) == 2
    gs.scenario_mode = "standard"
    assert sc.first_player(gs) is None and sc.deployment_zones(gs) is None


def test_ai_moves_onto_an_objective_marker():
    """Domination: a Lunar 25cm short of a marker it can reach moves to hold
    it (the move score values the points it wins at the end of its turn)."""
    from src.ai_player import AIPlayer
    from src.models import Ship
    from src.ship_catalog import find_ship_class
    from src.turn_controller import TurnController

    def ship(name, player, x, y, h):
        d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"{name[:4]}{player}")
        d.update(x=x, y=y, heading=h, leadership=8)
        return Ship.from_dict(d)
    me = ship("Lunar Class Cruiser", 1, 30.0, 25.0, 90.0)
    foe = ship("Lunar Class Cruiser", 2, 150.0, 110.0, 270.0)
    gs = _gs([me, foe])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    cmds = ai._plan_move_toward(me, foe, "", 0)
    from src.movement import validate_movement
    res = validate_movement(me, cmds, "", table_width=180.0, table_height=120.0)
    ex, ey = res.path[-1]
    assert sc.controller(gs, (30.0, 60.0), [Ship.from_dict({**me.to_dict(), "x": ex, "y": ey}),
                                             foe]) == 1
    # Without the scenario the same ship doesn't go there
    gs.scenario_mode = "standard"
    cmds = ai._plan_move_toward(me, foe, "", 0)
    res = validate_movement(me, cmds, "", table_width=180.0, table_height=120.0)
    ex2, ey2 = res.path[-1]
    assert math.hypot(ex2 - 30.0, ey2 - 60.0) > 15.0
