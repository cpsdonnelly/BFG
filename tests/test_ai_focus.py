"""Ordnance focus by expected VP (owner: focusing on easier targets should be
optimal; CLAUDE.md To do 1)."""
from tests.conftest import make_ship, make_gs, DiceStub, make_marker
from src.ai_hazards import plan_strike_targets, torpedo_salvo_hits

TORP = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30, "strength": 6,
        "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}


def _hard(i, x, y):
    return make_ship(id=i, player=2, x=x, y=y, turrets=4, armor_prow="6+", armor_side="6+",
                     points_value=200)


def _easy(i, x, y, hits=3):
    return make_ship(id=i, player=2, x=x, y=y, turrets=1, armor_prow="4+", armor_side="4+",
                     points_value=200, hits_remaining=hits)


def test_torpedo_salvo_hits_ignore_shields_count_turrets():
    hard = _hard("h", 30.0, 0.0)
    gs = make_gs([hard])
    # 6 torps, 4 turret dice on 4+ (2 down), 4 left hitting 6+
    assert abs(torpedo_salvo_hits(6, hard, gs, (0.0, 0.0)) - 4 / 6) < 1e-9


def test_ai_torpedoes_go_for_the_easier_target():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    me = make_ship(id="me", player=1, x=0.0, y=0.0, weapons=[dict(TORP)])
    gs = make_gs([me, _hard("h", 30.0, 3.0), _easy("e", 32.0, -3.0)])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    t = ai._best_torp_target(gs.get_ship_by_id("me"), TORP, ai._live_enemies())
    assert t.id == "e" and ai._ord_committed["e"] > 0


def test_strike_waves_focus_then_move_on():
    from src.waves import form_wave
    mid = make_ship(id="h", player=2, x=40.0, y=0.0, turrets=2, armor_prow="5+",
                    armor_side="5+", points_value=200)
    gs = make_gs([mid, _easy("e", 40.0, 20.0, hits=1)])
    for i in range(3):
        gs.add_ordnance(make_marker(id=f"a{i}", ordnance_type="bomber", owner_player=1,
                                    x=10.0, y=10.0, speed=20))
    form_wave(gs, ["a0", "a1", "a2"], "close")
    for i in range(3):
        gs.add_ordnance(make_marker(id=f"b{i}", ordnance_type="bomber", owner_player=1,
                                    x=10.0, y=12.0, speed=20))
    form_wave(gs, ["b0", "b1", "b2"], "close")
    plan = plan_strike_targets(gs, 1)
    # The wave (biggest group first) takes the 1-hit easy ship; the second wave,
    # with that ship likely dead, goes for the other. (Against a really hard
    # target, 4 turrets / 6+, it would add so little that topping up the easy
    # kill stays better: focus on easier targets, owner.)
    first, second = ("a", "b") if plan["a0"] == "e" else ("b", "a")
    assert all(plan[f"{first}{i}"] == "e" for i in range(3))
    assert all(plan[f"{second}{i}"] == "h" for i in range(3))
