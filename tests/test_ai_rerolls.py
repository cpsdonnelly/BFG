"""AI re-roll spending by importance (src/ai_rerolls.py)."""
from tests.conftest import make_gs, make_ship
from src.ai_rerolls import should_reroll, importance, commander_in_danger

GUNS = [{"name": "Port", "weapon_type": "battery", "range_cm": 30, "strength": 8, "arcs": ["left"]}]


def test_warp_rift_is_worth_the_last_reroll_minor_order_is_not():
    s = make_ship(id="s", player=1, points_value=200, hits_max=8)
    gs = make_gs([s])
    assert should_reroll(s, "warp rift navigation", gs, 1)
    assert not should_reroll(s, "come_to_new_heading", gs, 1)
    assert not should_reroll(s, "come_to_new_heading", gs, 3)


def test_target_priority_worth_more_when_a_kill_is_in_reach():
    s = make_ship(id="s", player=1, x=0.0, y=0.0, weapons=GUNS, points_value=180, hits_max=8)
    weak = make_ship(id="w", player=2, x=20.0, y=0.0, points_value=180, hits_max=8,
                     hits_remaining=2, shields_max=0)
    fresh = make_ship(id="f", player=2, x=20.0, y=0.0, points_value=180, hits_max=8,
                      hits_remaining=8, shields_max=2)
    a = importance(s, "target priority", make_gs([s, weak]))
    b = importance(s, "target priority", make_gs([s, fresh]))
    assert a > b and should_reroll(s, "target priority", make_gs([s, weak]), 2)


def test_spend_everything_when_the_commanders_ship_is_about_to_go():
    flag = make_ship(id="c", player=1, is_flagship=True, rerolls_remaining=2,
                     hits_max=8, hits_remaining=2)
    gs = make_gs([flag])
    assert commander_in_danger(gs, 1)
    assert should_reroll(flag, "come_to_new_heading", gs, 1)


def test_ai_obeys_target_priority():
    from tests.conftest import DiceStub
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    gun = {"name": "Port", "weapon_type": "battery", "range_cm": 45, "strength": 8,
           "arcs": ["left", "front", "right", "rear"]}
    a = make_ship(id="a", player=1, x=0.0, y=0.0, leadership=7, weapons=[gun])
    near = make_ship(id="n", player=2, x=15.0, y=0.0, points_value=100, hits_max=8, shields_max=2)
    weak = make_ship(id="w", player=2, x=35.0, y=0.0, points_value=200, hits_max=8,
                     hits_remaining=2, shields_max=0)
    gs = make_gs([a, near, weak])
    dice = DiceStub([11])                     # target priority test fails (no re-rolls)
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    t = ai._pick_target(gs.get_ship_by_id("a"), gun, [gs.get_ship_by_id("n"), gs.get_ship_by_id("w")])
    assert dice._idx == 1 and t.id == "n"
    dice2 = DiceStub([5])
    gs2 = make_gs([a, near, weak])
    ai2 = AIPlayer(1, TurnController(gs2, dice2), gs2, dice2)
    t2 = ai2._pick_target(gs2.get_ship_by_id("a"), gun, [gs2.get_ship_by_id("n"), gs2.get_ship_by_id("w")])
    assert dice2._idx == 1 and t2.id == "w"
