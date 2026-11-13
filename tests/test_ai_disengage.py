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


def test_certainty_equivalent_follows_the_game_state():
    """Owner (To do 2): with a turn limit the AI plays for the win. A gamble is
    worth more than its average when behind, less when ahead; without a turn
    limit it is just its average."""
    from src.ai_hazards import certainty_equivalent
    gamble = [(0.5, -200.0), (0.5, 0.0)]           # a coin flip on losing a 200pt ship
    me, gs = _scene(8)
    assert certainty_equivalent(gs, 1, gamble) == -100.0
    for behind, sign in ((True, 1), (False, -1)):
        me, gs = _scene(8)
        dead = make_ship(id="dead", player=1 if behind else 2, x=150.0, y=100.0,
                         hits_remaining=0, status="destroyed", points_value=300)
        gs.add_ship(dead)
        gs.turn_limit = gs.turn_number
        ce = certainty_equivalent(gs, 1, gamble)
        assert sign * (ce - (-100.0)) > 0


def test_disengaging_plays_for_the_win_near_the_end():
    """A healthy ship under heavy guns on the last turn: leaving is a sure 10%,
    staying a gamble on being crippled or destroyed. Ahead, leaving is worth
    more (lock the lead in); behind, less (the gamble is worth more than its
    average); no turn limit sits between. (A crippled ship concedes nothing
    extra by leaving, so for it leaving stays free either way.)"""
    def gain(behind):
        me, gs = _scene(8, n_foes=3)
        me.heading = 90.0                 # showing its 5+ side to the enemy guns
        gs.update_ship(me)
        if behind is not None:
            gs.add_ship(make_ship(id="dead", player=1 if behind else 2, x=150.0, y=100.0,
                                  hits_remaining=0, status="destroyed", points_value=200))
            gs.turn_limit = gs.turn_number
        return disengage_gain(me, gs, ld=8, contribution=5.0)
    assert gain(False) > gain(None) > gain(True)


def test_rerolls_are_not_saved_past_the_last_turn():
    """The bars that keep a last re-roll for a big swing drop to the lowest on
    the game's final turn: left-over re-rolls are worth nothing after it. A
    test worth 20 VP (between the lowest bar and the last re-roll's) keeps the
    last re-roll two turns from the end and spends it on the final turn."""
    import src.ai_rerolls as ar
    me, gs = _scene(8, n_foes=1)
    assert ar._bar(1) > 20.0 >= ar._bar(9)
    orig = ar.importance
    ar.importance = lambda *a, **k: 20.0
    try:
        gs.turn_limit = gs.turn_number + 2
        assert not ar.should_reroll(me, "special order", gs, 1)
        gs.turn_limit = gs.turn_number
        assert ar.should_reroll(me, "special order", gs, 1)
        gs.turn_limit = None
        assert not ar.should_reroll(me, "special order", gs, 1)
    finally:
        ar.importance = orig


def test_brace_follows_the_game_state_risk_preference():
    """To do 2: a brace narrows the spread of the damage taken. On the last turn
    the side ahead braces where the even game wouldn't; the side behind doesn't
    where the even game would."""
    from src.ai_player import brace_value
    gun = {"name": "Guns", "weapon_type": "battery", "range_cm": 30, "strength": 6,
           "arcs": ["left", "right", "front"]}

    def value(side, hits):
        p2 = make_ship(id="p2", player=1, x=0.0, y=10.0, hits_max=8, hits_remaining=8,
                       shields_max=2, points_value=150, weapons=[gun])
        foe = make_ship(id="e", player=2, x=20.0, y=0.0, points_value=200, hits_max=8)
        ships = [p2, foe]
        if side:
            ships.append(make_ship(id="d", player=2 if side == "ahead" else 1, x=200.0,
                                   y=200.0, points_value=150, hits_max=8, hits_remaining=0,
                                   status="destroyed"))
        gs = make_gs(ships)
        gs.active_player = 2
        if side:
            gs.turn_limit, gs.turn_number = 4, 4
        return brace_value(gs, gs.get_ship_by_id("p2"), hits)

    assert value(None, 5) < 0 < value("ahead", 5)
    assert value("behind", 6) < 0 < value(None, 6)


def test_guns_given_up_by_disengaging_are_a_gamble_too():
    """To do 2: the guns a disengaging ship gives up are a gamble (a kill or
    nothing). Behind on the last turn, a long-shot kill keeps it fighting more
    than a sure gain of the same average; ahead, less."""
    def gain(behind, outs):
        me, gs = _scene(8, n_foes=3)
        me.heading = 90.0
        gs.update_ship(me)
        gs.add_ship(make_ship(id="dead", player=1 if behind else 2, x=150.0, y=100.0,
                              hits_remaining=0, status="destroyed", points_value=200))
        gs.turn_limit = gs.turn_number
        return disengage_gain(gs.get_ship_by_id(me.id), gs, 8, 30.0, outs)
    sure, shot = [(1.0, 30.0)], [(0.2, 150.0), (0.8, 0.0)]
    assert gain(True, shot) < gain(True, sure)
    assert gain(False, shot) > gain(False, sure)
