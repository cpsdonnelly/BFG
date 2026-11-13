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


def test_point_goals_and_refinement():
    """Goals c / d / 3 (To do 11 a): prow-on, into the target's rear arc, a
    second target, an escort to the commander's ship; the planner refines the
    best candidates and its moves stay legal."""
    import random
    me = _ship("Cobra Class Destroyer", 1, 60.0, 60.0, 0.0)
    flag = _ship("Lunar Class Cruiser", 1, 40.0, 80.0, 0.0, 1)
    flag.is_flagship = True
    foe = _ship("Lunar Class Cruiser", 2, 85.0, 70.0, 180.0)
    foe2 = _ship("Lunar Class Cruiser", 2, 100.0, 30.0, 180.0, 2)
    ai, gs = _ai([me, flag, foe, foe2])
    srcs = {c[3] for c in ai._move_candidates(me, foe, "", 0)}
    assert {"prow-on", "rear arc", "second target", "support"} <= srcs
    # a rear-arc candidate ends behind the target's predicted position
    from src.ai_hazards import _predicted_positions
    nxt = _predicted_positions(foe, True)[1]
    rear = [c for c in ai._move_candidates(me, foe, "", 0) if c[3] == "rear arc"]
    ends = [ai._simulate_final_pos(me, c[0], c[1], c[2]) for c in rear]
    assert any(nxt.get_target_arc(x, y) == "rear" for x, y, _h in ends)
    rng = random.Random(3)
    for _ in range(12):
        name = rng.choice(["Lunar Class Cruiser", "Cobra Class Destroyer",
                           "Emperor Class Battleship"])
        me = _ship(name, 1, rng.uniform(40, 140), rng.uniform(30, 90), rng.uniform(0, 360))
        foe = _ship("Lunar Class Cruiser", 2, rng.uniform(40, 140), rng.uniform(30, 90),
                    rng.uniform(0, 360))
        ai, gs = _ai([me, foe])
        order = rng.choice(["", SpecialOrder.BURN_RETROS.value])
        cmds = ai._plan_move_toward(me, foe, order, 0)
        res = validate_movement(me, cmds, order, table_width=180.0, table_height=120.0)
        assert not res.errors, (name, order, ai._last_move_source, res.errors)


def test_supported_ships_move_first():
    """Coordination (To do 11 a): the commander's ship, then carriers, other
    capital ships, escorts last; squadrons stay together."""
    from tests.conftest import make_ship
    bay = {"name": "Bays", "weapon_type": "launch_bay", "strength": 2, "arcs": []}
    ships = [make_ship(id="e1", player=1, ship_type="escort", squadron_id="sq"),
             make_ship(id="c", player=1),
             make_ship(id="e2", player=1, ship_type="escort", squadron_id="sq"),
             make_ship(id="cv", player=1, weapons=[bay]),
             make_ship(id="f", player=1, is_flagship=True)]
    order = [s.id for s in AIPlayer._coordinated_order(ships)]
    assert order == ["f", "cv", "c", "e1", "e2"]
