"""Disengaging (core s.37) and Demiurg Mercenaries (Xenos p.91-94)."""
from tests.conftest import make_gs, make_ship, DiceStub
from src.disengage import attempt_disengage, forced_disengage_tests, mercenary_must_disengage


def test_voluntary_escort_disengage_is_one_squadron_test():
    a = make_ship(id="a", ship_type="escort", squadron_id="q", leadership=8, x=10.0, y=10.0)
    b = make_ship(id="b", ship_type="escort", squadron_id="q", leadership=8, x=12.0, y=10.0)
    gs = make_gs([a, b])
    dice = DiceStub([6])
    r = attempt_disengage(gs.get_ship_by_id("a"), dice, gs)
    assert dice._idx == 1 and r["success"]
    assert all(gs.get_ship_by_id(i).is_disengaged for i in ("a", "b"))


def test_capital_ship_that_fails_falls_out_of_its_squadron():
    c = make_ship(id="c", squadron_id="q", leadership=6, x=10.0, y=10.0)
    gs = make_gs([c])
    dice = DiceStub([11])
    r = attempt_disengage(gs.get_ship_by_id("c"), dice, gs)
    assert dice._idx == 1 and not r["success"] and gs.get_ship_by_id("c").squadron_id == ""


def test_forced_disengagement_at_leadership_one_and_flee_after_failing():
    s = make_ship(id="s", player=1, leadership=1, x=60.0, y=60.0)
    gs = make_gs([s])
    dice = DiceStub([5])
    forced_disengage_tests(gs, dice, 1)
    assert dice._idx == 1 and gs.get_ship_by_id("s").must_flee


def test_demiurg_mercenaries():
    d = make_ship(id="d", player=1, hits_max=8, hits_remaining=4,
                  special_rules=["demiurg_commerce"])
    tau = make_ship(id="t", player=1)
    imp = make_ship(id="i", player=2)
    gs = make_gs([d, tau, imp])
    assert mercenary_must_disengage(gs.get_ship_by_id("d"), gs)
    ork = make_ship(id="o", player=2, faction="orks")
    gs2 = make_gs([d, tau, ork])
    assert not mercenary_must_disengage(gs2.get_ship_by_id("d"), gs2)   # 4 hits > 2
    gs3 = make_gs([d, imp])
    assert not mercenary_must_disengage(gs3.get_ship_by_id("d"), gs3)  # all Demiurg


def test_ai_fleeing_ship_heads_for_the_nearest_edge():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    s = make_ship(id="s", player=1, x=20.0, y=60.0, heading=0.0, speed=20, must_flee=True)
    e = make_ship(id="e", player=2, x=100.0, y=60.0)
    gs = make_gs([s, e])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    cmds = ai._plan_flee(gs.get_ship_by_id("s"), "", 0)
    from src.movement import validate_movement, MoveCommand

    def edge(c):
        r = validate_movement(gs.get_ship_by_id("s"), c, "", table_width=gs.table_width,
                              table_height=gs.table_height)
        assert r.valid
        return min(r.final_x, r.final_y, gs.table_width - r.final_x, gs.table_height - r.final_y)
    straight = edge([MoveCommand("forward", 20)])
    assert edge(cmds) < straight               # a turn brings it closer to an edge


def test_celestial_phenomena_measured_to_their_edge():
    from src.models import Phenomenon
    from src.disengage import get_disengage_ld_modifiers
    s = make_ship(id="s", x=50.0, y=50.0, leadership=7)
    gs = make_gs([s])
    gs.add_phenomenon(Phenomenon(id="a", phenomenon_type="asteroid_field", x=50.0, y=78.0,
                                 width=30.0, height=30.0))    # centre 28cm, edge 13cm away
    assert get_disengage_ld_modifiers(gs.get_ship_by_id("s"), gs)["effective_ld"] == 10
