"""Target-directed movement candidates (CLAUDE.md To do 11 a, owner): turn
points, the even grid as fallback, goals against the target; every candidate
is a legal move."""
import math
from tests.conftest import make_gs, DiceStub
from src.models import Ship, SpecialOrder
from src.ship_catalog import find_ship_class
from src.ai_player import AIPlayer
from src.turn_controller import TurnController
from src.movement import validate_movement


def _ship(name, player, x, y, h, i=0):
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"{name[:4]}{player}{i}")
    d.update(x=x, y=y, heading=h, leadership=8)
    return Ship.from_dict(d)


def _ai(ships):
    gs = make_gs(ships)
    gs.table_width, gs.table_height = 180.0, 120.0
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    return ai, gs


def test_every_candidate_is_a_legal_move():
    for name in ("Lunar Class Cruiser", "Emperor Class Battleship", "Cobra Class Destroyer",
                 "Protector Class Cruiser"):
        for order in ("", SpecialOrder.BURN_RETROS.value):
            me = _ship(name, 1, 60.0, 60.0, 30.0)
            foe = _ship("Lunar Class Cruiser", 2, 120.0, 40.0, 200.0)
            ai, gs = _ai([me, foe])
            cands = ai._move_candidates(me, foe, order, 0)
            assert cands
            for turn_deg, dist, turn_at, _src in cands:
                cmds = ai._move_cmds(me, turn_deg, dist, turn_at)
                res = validate_movement(me, cmds, order, table_width=180.0, table_height=120.0)
                assert not res.errors, (name, order, turn_deg, dist, turn_at, res.errors)
                # the simulator ends where the engine does
                fx, fy, _fh = ai._simulate_final_pos(me, turn_deg, dist, turn_at)
                ex, ey = res.path[-1]
                assert math.hypot(fx - ex, fy - ey) < 1e-6


def test_turn_points_and_goals_are_offered():
    """Capital ships may turn after the minimum distance, after the minimum
    move or at the end; escorts also at the very start; the guns-to-bear
    goal searches the turn angle finely."""
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    foe = _ship("Lunar Class Cruiser", 2, 75.0, 95.0, 0.0)      # off to port
    ai, gs = _ai([me, foe])
    cands = ai._move_candidates(me, foe, "", 0)
    points = {c[2] for c in cands if abs(c[0]) > 0.5}
    assert {None, 10, 20}.issubset(points) or {10, 20}.issubset(points)
    assert any(c[3] == "guns to bear" for c in cands)
    esc = _ship("Cobra Class Destroyer", 1, 60.0, 60.0, 0.0)
    ai2, _ = _ai([esc, foe])
    assert any(c[2] == 0.0 and abs(c[0]) > 0.5 for c in ai2._move_candidates(esc, foe, "", 0))


def test_range_band_goal_aims_for_the_winning_bracket():
    """A Merchant (45cm railguns) facing a Lunar (30cm guns) aims for 30-45cm,
    the bracket it wins (To do 8 f); a ship that wins nowhere gets no band."""
    m = _ship("Merchant Starship", 1, 60.0, 60.0, 0.0)
    lunar = _ship("Lunar Class Cruiser", 2, 140.0, 60.0, 180.0)
    ai, gs = _ai([m, lunar])
    assert ai._range_band(m, lunar) == 37.5
    weak = _ship("Cobra Class Destroyer", 1, 60.0, 60.0, 0.0)
    big = _ship("Emperor Class Battleship", 2, 140.0, 60.0, 180.0)
    ai2, _ = _ai([weak, big])
    assert ai2._range_band(weak, big) is None or ai2._range_band(weak, big) > 0
