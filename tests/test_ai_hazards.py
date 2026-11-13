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
    # doesn't end in the salvo's path (its base plus the marker's half width)
    from src.ai_hazards import TORP_CONTACT_HALF_W
    contact = gs.get_ship_by_id("s").base_radius + TORP_CONTACT_HALF_W
    assert r.valid and abs(r.final_x - 60.0) > contact


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
    # Priced brace (To do 11 c): 5 hits at 2 shields; bracing halves each ship's
    # fire next turn (a foe 20cm off), but the commander's ship is worth double
    # while it has re-rolls to lose, so it braces and the plain ship doesn't
    g6 = {"name": "Guns", "weapon_type": "battery", "range_cm": 30, "strength": 6,
          "arcs": ["left", "right", "front"]}
    f2 = make_ship(id="c2", player=1, x=0.0, y=0.0, is_flagship=True, rerolls_remaining=1,
                   hits_max=8, hits_remaining=8, shields_max=2, points_value=150, weapons=[g6])
    p2 = make_ship(id="p2", player=1, x=0.0, y=10.0, hits_max=8, hits_remaining=8,
                   shields_max=2, points_value=150, weapons=[g6])
    foe2 = make_ship(id="e2", player=2, x=20.0, y=0.0, points_value=200, hits_max=8)
    gs2 = make_gs([f2, p2, foe2])
    gs2.active_player = 2
    assert ai_should_brace(gs2, gs2.get_ship_by_id("c2"), 5)
    assert not ai_should_brace(gs2, gs2.get_ship_by_id("p2"), 5)


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


def _fleet():
    s = make_ship(id="s", player=1, x=0.0, y=0.0, points_value=180, hits_max=8, turrets=1)
    return make_gs([s])


def test_two_fighters_split_between_a_mine_and_a_salvo():
    from src.ordnance import plan_fighter_intercepts
    gs = _fleet()
    for m in (make_marker(id="f1", ordnance_type="fighter", owner_player=1, x=5.0, y=0.0, speed=30.0),
              make_marker(id="f2", ordnance_type="fighter", owner_player=1, x=5.0, y=2.0, speed=30.0),
              make_marker(id="m", ordnance_type="mine_launcher", owner_player=2, x=15.0, y=0.0,
                          heading=180.0, speed=10.0, strength=1),
              make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2, x=25.0,
                          y=0.0, heading=180.0, speed=30.0, strength=6)):
        gs.add_ordnance(m)
    plan = plan_fighter_intercepts(gs, 1)
    assert sorted(plan.values()) == ["m", "t"]          # not both on the mine


def test_a_salvo_is_worth_one_fighter_a_bomber_wave_one_per_squadron():
    from src.ai_hazards import intercept_gain
    from src.waves import form_wave
    from src.models import OrdnanceMarker
    gs = _fleet()
    salvo = make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2, x=25.0, y=0.0,
                        heading=180.0, speed=30.0, strength=6)
    gs.add_ordnance(salvo)
    for i in range(3):
        gs.add_ordnance(make_marker(id=f"b{i}", ordnance_type="bomber", owner_player=2,
                                    x=15.0, y=0.0, heading=180.0, speed=20.0, strength=1))
    form_wave(gs, ["b0", "b1", "b2"])
    lead = OrdnanceMarker.from_dict(next(o for o in gs.ordnance if o["id"] == "b0"))
    assert intercept_gain(gs, 1, salvo) > 0 and intercept_gain(gs, 1, salvo, already=1) == 0
    one = intercept_gain(gs, 1, lead)
    assert one > 0 and intercept_gain(gs, 1, lead, already=1) == one   # the next squadron
    assert intercept_gain(gs, 1, lead, already=3) == 0
    assert intercept_gain(gs, 1, salvo) > one          # S6 salvo gone vs one bomber squadron


def test_a_spare_fighter_does_not_chase_a_covered_mine():
    from src.ordnance import assign_ai_craft_targets
    gs = _fleet()
    e = make_ship(id="e", player=2, x=80.0, y=0.0)
    gs.add_ship(e)
    for m in (make_marker(id="f1", ordnance_type="fighter", owner_player=1, x=5.0, y=0.0, speed=30.0),
              make_marker(id="f2", ordnance_type="fighter", owner_player=1, x=5.0, y=2.0, speed=30.0),
              make_marker(id="m", ordnance_type="mine_launcher", owner_player=2, x=15.0, y=0.0,
                          heading=180.0, speed=10.0, strength=1)):
        gs.add_ordnance(m)
    assign_ai_craft_targets(gs, 1)
    t = {o["id"]: o["craft_target_id"] for o in gs.ordnance}
    assert sorted([t["f1"], t["f2"]]) == ["e", "m"]


def test_seeking_and_guided_torpedo_turn_cones():
    """s.16: seeking salvos turn up to 45 degrees at the nearest enemy, guided ones may
    turn 45 on a Leadership test; standard ones run straight."""
    import math
    from src.ai_hazards import marker_hits, GUIDED_TURN_CHANCE
    me = make_ship(id="me", player=1, x=20.0 * math.cos(math.radians(30)),
                   y=20.0 * math.sin(math.radians(30)), armor_prow="5+", armor_side="5+",
                   turrets=0)
    end, pts = (me.x, me.y), [(me.x, me.y)]

    def salvo(kind, can_turn=False):
        return make_marker(id="t", ordnance_type=kind, owner_player=2, x=0.0, y=0.0,
                           heading=0.0, speed=30.0, strength=6, can_turn=can_turn)
    straight, _ = marker_hits(me, salvo("torpedo_standard"), end, pts, [me])
    seeking, _ = marker_hits(me, salvo("torpedo_seeking"), end, pts, [me])
    guided, _ = marker_hits(me, salvo("torpedo_guided_ld"), end, pts, [me])
    tau, _ = marker_hits(me, salvo("torpedo_guided", can_turn=True), end, pts, [me])
    assert straight == 0.0
    assert abs(seeking - 6 * 2 / 6) < 1e-9                     # turns 30 degrees onto us
    assert abs(guided - seeking * GUIDED_TURN_CHANCE) < 1e-9
    assert abs(tau - seeking * 5 / 6) < 1e-9                   # loses strength on 1s
    boarding, _ = marker_hits(me, salvo("torpedo_boarding"), end, pts, [me])
    assert abs(boarding - seeking * 0.5) < 1e-9                 # manned: turns freely; raids
    # 60 degrees off the bow is outside every cone
    far = make_ship(id="f", player=1, x=20.0 * math.cos(math.radians(60)),
                    y=20.0 * math.sin(math.radians(60)), armor_side="5+", turrets=0)
    assert marker_hits(far, salvo("torpedo_seeking"), (far.x, far.y), [(far.x, far.y)],
                       [far])[0] == 0.0


def test_guided_turn_chance_uses_the_launchers_leadership():
    from src.ai_hazards import guided_turn_chance, p_sum_at_most
    launcher = make_ship(id="L", player=2, leadership=10)
    gs = make_gs([launcher])
    m = make_marker(id="g", ordnance_type="torpedo_guided_ld", owner_player=2,
                    launched_by="L")
    assert abs(guided_turn_chance(m, gs) - p_sum_at_most(2, 10)) < 1e-9
    gone = make_marker(id="g2", ordnance_type="torpedo_guided_ld", owner_player=2,
                       launched_by="nobody")
    assert guided_turn_chance(gone, gs) == 0.0          # launcher out of play: no turn


def test_burn_retros_when_it_avoids_more_hazard_than_it_costs():
    """Burn Retros by expected VP: a cruiser that can't avoid an asteroid field at
    normal speed (minimum 10cm) stops short of it on Burn Retros (0-10cm)."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, speed=20,
                   leadership=8, points_value=180)
    far = make_ship(id="e", player=2, x=200.0, y=0.0)
    gs = make_gs([me, far])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    assert ai._burn_retros_worth_it(gs.get_ship_by_id("me")) is False      # open space
    gs.add_phenomenon(Phenomenon(id="ast", phenomenon_type="asteroid_field", x=14.0,
                                 y=0.0, width=14.0, height=80.0, radius=0.0, rotation=0.0))
    assert ai._burn_retros_worth_it(gs.get_ship_by_id("me")) is True



def test_tau_missiles_reach_40cm():
    """s.09: Tau missiles move 20-40cm at their owner's choice; a 30cm salvo can't reach."""
    from src.ai_hazards import marker_hits
    me = make_ship(id="me", player=1, x=36.0, y=0.0, armor_side="5+", turrets=0)
    tau = make_marker(id="m", ordnance_type="torpedo_guided", owner_player=2, x=0.0, y=0.0,
                      heading=0.0, speed=30.0, strength=6, can_turn=True)
    std = make_marker(id="s", ordnance_type="torpedo_standard", owner_player=2, x=0.0, y=0.0,
                      heading=0.0, speed=30.0, strength=6)
    end, pts = (me.x, me.y), [(me.x, me.y)]
    assert marker_hits(me, std, end, pts, [me])[0] == 0.0
    assert marker_hits(me, tau, end, pts, [me])[0] > 0.0
