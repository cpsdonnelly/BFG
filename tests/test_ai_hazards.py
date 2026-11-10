"""AI hazard assessment (src/ai_hazards.py)."""
from tests.conftest import make_gs, make_ship, make_marker, DiceStub
from src.ai_hazards import move_hazard_vp, p_sum_at_most
from src.models import Phenomenon


def test_probability_helper():
    assert abs(p_sum_at_most(2, 7) - 21 / 36) < 1e-9
    assert p_sum_at_most(2, 1) == 0.0 and p_sum_at_most(3, 18) == 1.0


def test_a_mine_is_more_dangerous_than_a_torpedo_salvo():
    s = make_ship(id="s", player=1, x=50.0, y=50.0, points_value=180, hits_max=8, turrets=2)
    mine = make_marker(id="m", ordnance_type="mine", owner_player=2, x=62.0, y=50.0,
                       heading=180.0, speed=10.0, strength=1)
    torp = make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2, x=80.0,
                       y=50.0, heading=180.0, speed=30.0, strength=4)
    gs_m, gs_t = make_gs([s]), make_gs([s])
    gs_m.add_ordnance(mine)
    gs_t.add_ordnance(torp)
    end, path = (50.0, 50.0), [(50.0, 50.0), (50.0, 50.0)]
    vm = move_hazard_vp(s, end, path, gs_m)["vp"]
    vt = move_hazard_vp(s, end, path, gs_t)["vp"]
    assert vm > vt > 0


def test_asteroid_field_risk_depends_on_leadership():
    lo = make_ship(id="a", leadership=6, points_value=180, hits_max=8, shields_max=1)
    hi = make_ship(id="b", leadership=10, points_value=180, hits_max=8, shields_max=1)
    gs = make_gs([lo, hi])
    gs.add_phenomenon(Phenomenon(id="f", phenomenon_type="asteroid_field", x=20.0, y=0.0,
                                 width=10.0, height=10.0))
    path = [(0.0, 0.0), (30.0, 0.0)]
    assert move_hazard_vp(lo, (30.0, 0.0), path, gs)["vp"] > move_hazard_vp(
        hi, (30.0, 0.0), path, gs)["vp"] > 0


def test_planner_steers_out_of_a_torpedo_line():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    s = make_ship(id="s", player=1, x=40.0, y=60.0, heading=0.0, speed=20, points_value=180,
                  hits_max=8, leadership=8,
                  weapons=[{"name": "Prow", "weapon_type": "battery", "range_cm": 30,
                            "strength": 4, "arcs": ["front"]}])
    e = make_ship(id="e", player=2, x=110.0, y=60.0)
    gs = make_gs([s, e])
    # a salvo crossing the ship's straight-ahead end point (60, 60) next phase
    gs.add_ordnance(make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2,
                                x=60.0, y=90.0, heading=270.0, speed=40.0, strength=6))
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    cmds = ai._plan_move_toward(gs.get_ship_by_id("s"), gs.get_ship_by_id("e"), "", 0)
    from src.movement import validate_movement
    r = validate_movement(gs.get_ship_by_id("s"), cmds, "", table_width=gs.table_width,
                          table_height=gs.table_height)
    assert r.valid and abs(r.final_x - 60.0) > 3.0       # doesn't end in the salvo's path


def test_targeting_prefers_a_kill_and_avoids_overkill():
    from src.ai_hazards import shot_vp
    gun = {"name": "Port", "weapon_type": "battery", "range_cm": 30, "strength": 8, "arcs": ["left"]}
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    weak = make_ship(id="w", player=2, x=20.0, y=0.0, points_value=180, hits_max=8,
                     hits_remaining=2, shields_max=1)
    fresh = make_ship(id="f", player=2, x=20.0, y=0.0, points_value=180, hits_max=8,
                      hits_remaining=8, shields_max=2)
    gs = make_gs([a, weak, fresh])
    assert shot_vp(a, gun, weak, gs) > shot_vp(a, gun, fresh, gs)
    assert shot_vp(a, gun, weak, gs, committed=10.0) < shot_vp(a, gun, fresh, gs)   # already dead


def test_commanders_ship_counts_its_exposure_and_braces_earlier():
    from src.ai_player import AIPlayer, ai_should_brace
    from src.turn_controller import TurnController
    gun = {"name": "Port", "weapon_type": "battery", "range_cm": 30, "strength": 8, "arcs": ["left"]}
    flag = make_ship(id="c", player=1, x=0.0, y=0.0, is_flagship=True, rerolls_remaining=1,
                     points_value=250, hits_max=8)
    plain = make_ship(id="p", player=1, x=0.0, y=0.0, points_value=250, hits_max=8)
    foe = make_ship(id="e", player=2, x=40.0, y=0.0, weapons=[gun])
    gs = make_gs([flag, plain, foe])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    near = ai._position_penalty(20.0, 0.0, gs.get_ship_by_id("c"), [(0.0, 0.0), (20.0, 0.0)])
    far = ai._position_penalty(-60.0, 0.0, gs.get_ship_by_id("c"), [(0.0, 0.0), (-60.0, 0.0)])
    other = ai._position_penalty(20.0, 0.0, gs.get_ship_by_id("p"), [(0.0, 0.0), (20.0, 0.0)])
    assert near > far and near > other
    # 12 hits, 2 shields, 4 hits incoming (2 hull): the flagship braces (12/6), a
    # plain ship doesn't (12/4); the foe is out of range, so no follow-on fire
    f2 = make_ship(id="c2", player=1, x=0.0, y=0.0, is_flagship=True, rerolls_remaining=1,
                   hits_max=12, hits_remaining=12, shields_max=2)
    p2 = make_ship(id="p2", player=1, x=0.0, y=0.0, hits_max=12, hits_remaining=12, shields_max=2)
    gs2 = make_gs([f2, p2])
    assert ai_should_brace(gs2, gs2.get_ship_by_id("c2"), 4)
    assert not ai_should_brace(gs2, gs2.get_ship_by_id("p2"), 4)


def test_fighters_go_for_the_most_dangerous_ordnance():
    from src.ordnance import ai_craft_target
    s = make_ship(id="s", player=1, x=0.0, y=0.0, points_value=180, hits_max=8)
    gs = make_gs([s])
    f = make_marker(id="f", ordnance_type="fighter", owner_player=1, x=20.0, y=0.0, speed=30.0)
    torp = make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2, x=25.0,
                       y=5.0, heading=180.0, speed=30.0, strength=2)
    mine = make_marker(id="m", ordnance_type="mine_launcher", owner_player=2, x=12.0, y=0.0,
                       heading=180.0, speed=10.0, strength=1)
    for m in (f, torp, mine):
        gs.add_ordnance(m)
    assert ai_craft_target(f, gs) == "m"


def test_ship_shoots_an_incoming_mine_when_nothing_better_is_in_reach():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    lance = {"name": "Prow Lances", "weapon_type": "lance", "range_cm": 30, "strength": 3,
             "arcs": ["front"]}
    s = make_ship(id="s", player=1, x=0.0, y=0.0, heading=0.0, points_value=180, hits_max=8,
                  weapons=[lance])
    far = make_ship(id="e", player=2, x=0.0, y=90.0)
    gs = make_gs([s, far])
    gs.add_ordnance(make_marker(id="m", ordnance_type="mine_launcher", owner_player=2, x=15.0,
                                y=0.0, heading=180.0, speed=10.0, strength=1))
    dice = DiceStub([6, 2, 3])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.run_shooting_phase()
    assert dice._idx == 3 and not gs.ordnance          # the mine is gone
