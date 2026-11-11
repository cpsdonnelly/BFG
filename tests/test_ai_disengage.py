"""AI voluntary disengagement by expected VP (s.37 / s.38; CLAUDE.md To do 1)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ai_hazards import disengage_gain, incoming_hits

GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
         "arcs": ["right"]},
        {"name": "Prow Lances", "weapon_type": "lance", "range_cm": 30, "strength": 3,
         "arcs": ["front"]}]


def _scene(hits_left, enemy_x=40.0, n_foes=3):
    me = make_ship(id="me", player=1, hits_max=8, hits_remaining=hits_left, points_value=180,
                   weapons=[dict(GUNS[0])])
    foes = [make_ship(id=f"e{i}", player=2, x=enemy_x, y=10.0 * i, heading=180.0,
                      points_value=180,
                      weapons=[dict(w) for w in GUNS]) for i in range(n_foes)]
    return me, make_gs([me] + foes)


def test_crippled_ship_under_the_guns_disengages():
    me, gs = _scene(2)
    assert me.is_crippled and incoming_hits(me, gs) > 4
    assert disengage_gain(me, gs, ld=8, contribution=5.0) > 0


def test_healthy_or_safe_ships_fight_on():
    me, gs = _scene(8, n_foes=1)
    assert disengage_gain(me, gs, ld=8, contribution=5.0) < 0     # not worth 10% + its guns
    me2, gs2 = _scene(2, enemy_x=200.0)                            # crippled but out of reach
    assert incoming_hits(me2, gs2) == 0
    assert disengage_gain(me2, gs2, ld=8, contribution=5.0) < 0


def test_ai_attempts_disengage_after_moving():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    me, gs = _scene(2)
    gs.current_phase = "movement"
    rolls = [5]                         # 2D6 total 5 vs Ld 8: passes
    dice = DiceStub(rolls)
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    gs.update_ship(me.__class__.from_dict({**me.to_dict(), "leadership": 8}))
    ai._consider_disengage(gs.get_ship_by_id("me"))
    assert dice._idx == len(rolls)
    assert gs.get_ship_by_id("me").is_disengaged


def test_both_broadsides_at_different_targets():
    """An enemy between two of our ships fires port at one, starboard at the other."""
    sides = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
              "arcs": ["left"]},
             {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30,
              "strength": 8, "arcs": ["right"]}]
    e = make_ship(id="e", player=2, x=0.0, y=0.0, heading=0.0, shields_max=0,
                  weapons=[dict(w) for w in sides])
    a = make_ship(id="a", player=1, x=0.0, y=20.0, shields_max=0)      # its left
    b = make_ship(id="b", player=1, x=0.0, y=-20.0, shields_max=0)     # its right
    gs = make_gs([e, a, b])
    assert abs(incoming_hits(a, gs) - 8 * 0.35) < 1e-9
    assert abs(incoming_hits(b, gs) - 8 * 0.35) < 1e-9
    # A lone target only ever faces one broadside
    gs1 = make_gs([e, a])
    assert abs(incoming_hits(a, gs1) - 8 * 0.35) < 1e-9
    # Two of ours on the same side: the broadside goes wholly to one of them
    # (focus fire, owner), the more damaged one when it can finish it
    c = make_ship(id="c", player=1, x=10.0, y=20.0, shields_max=0, hits_remaining=2)
    gs2 = make_gs([e, a, c])
    assert abs(incoming_hits(c, gs2) - 8 * 0.35) < 1e-9 and incoming_hits(a, gs2) == 0.0


def test_focus_fire_moves_on_once_a_target_is_likely_dead():
    from src.ai_hazards import enemy_fire_plan
    big = [{"name": f"Prow Lances {i}", "weapon_type": "lance", "range_cm": 30,
            "strength": 4, "arcs": ["front"]} for i in range(3)]
    e = make_ship(id="e", player=2, x=0.0, y=0.0, heading=0.0, weapons=big)
    weak = make_ship(id="w", player=1, x=20.0, y=2.0, shields_max=0, hits_remaining=1,
                     points_value=180)
    other = make_ship(id="o", player=1, x=20.0, y=-2.0, shields_max=0, points_value=180)
    plan = enemy_fire_plan(make_gs([e, weak, other]), 1)
    assert plan["w"] == 2.0 and plan["o"] == 4.0     # one mount finishes it, the rest move on
