"""Hazards in the AI's target choices (owner): ordnance through blast markers,
dust clouds and asteroid fields; batteries shifted by blast markers and dust,
lances not; asteroid fields and planets block direct fire."""
from tests.conftest import make_ship, make_gs, make_blast, make_phenomenon, DiceStub
from src.ai_hazards import ordnance_path_survival
from src.combat import expected_hits


def _gs(*phen, blasts=()):
    gs = make_gs([])
    for p in phen:
        gs.add_phenomenon(p)
    for b in blasts:
        gs.add_blast_marker(b)
    return gs


def test_path_survival_by_hazard_and_ordnance_kind():
    ast = make_phenomenon("asteroid_field", x=20.0, y=0.0, width=6.0, height=6.0)
    gs = _gs(ast)
    assert ordnance_path_survival(0, 0, 40, 0, gs, "torpedo") == 0.0        # detonates
    assert abs(ordnance_path_survival(0, 0, 40, 0, gs, "craft") - 5 / 6) < 1e-9
    dust = make_phenomenon("gas_dust_cloud", x=20.0, y=0.0, width=6.0, height=6.0)
    gs = _gs(dust)
    assert abs(ordnance_path_survival(0, 0, 40, 0, gs, "torpedo") - 5 / 6) < 1e-9
    assert abs(ordnance_path_survival(0, 0, 40, 0, gs, "craft") - 5 / 6) < 1e-9   # owner
    gs = _gs(blasts=[make_blast(x=20.0, y=0.0)])
    assert abs(ordnance_path_survival(0, 0, 40, 0, gs, "torpedo") - 5 / 6) < 1e-9
    assert abs(ordnance_path_survival(0, 0, 40, 0, gs, "seeking") - 4 / 6) < 1e-9
    assert ordnance_path_survival(0, 20, 40, 20, gs, "torpedo") == 1.0      # clear lane


def test_battery_estimate_shifted_by_blast_markers_lances_not():
    bat = {"name": "Prow Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
           "arcs": ["front"]}
    lance = {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
             "arcs": ["front"]}
    a = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, weapons=[bat, lance])
    t = make_ship(id="t", player=2, x=25.0, y=0.0, heading=90.0, armor_side="5+")
    clear = make_gs([a, t])
    blocked = make_gs([a, t])
    blocked.add_blast_marker(make_blast(x=12.0, y=0.0))
    assert expected_hits(a, bat, t, blocked) < expected_hits(a, bat, t, clear)
    assert expected_hits(a, lance, t, blocked) == expected_hits(a, lance, t, clear)


def test_ai_torpedoes_avoid_a_target_behind_an_asteroid_field():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    torp = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30,
            "strength": 6, "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[torp])
    # The easier target sits behind an asteroid field; the harder one is in the clear
    easy = make_ship(id="easy", player=2, x=30.0, y=-4.0, armor_prow="4+", armor_side="4+",
                     turrets=1, points_value=200)
    hard = make_ship(id="hard", player=2, x=30.0, y=6.0, armor_prow="5+", armor_side="5+",
                     turrets=2, points_value=200)
    gs = make_gs([me, easy, hard])
    gs.add_phenomenon(make_phenomenon("asteroid_field", x=15.0, y=-4.0, width=4.0, height=4.0))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    assert ai._best_torp_target(gs.get_ship_by_id("me"), torp, ai._live_enemies()).id == "hard"


def test_craft_route_round_an_asteroid_field():
    """Owner: attack craft can fly round obstacles. The detour is worth more than
    flying through (1 in 6 lost), and AI craft really fly it; a human's don't."""
    from src.ai_hazards import best_route
    from src.ordnance import craft_target_point
    from tests.conftest import make_marker
    ast = make_phenomenon("asteroid_field", x=20.0, y=0.0, width=6.0, height=6.0)
    target = make_ship(id="t", player=2, x=40.0, y=0.0)
    gs = make_gs([target])
    gs.add_phenomenon(ast)
    value, surv, length, wp = best_route(0, 0, 40, 0, gs, "craft", 20)
    from src.ai_hazards import ordnance_path_survival, travel_discount
    straight = ordnance_path_survival(0, 0, 40, 0, gs, "craft") * travel_discount(40, 20)
    assert surv == 1.0 and wp is not None and value > straight   # safe, a little longer
    # Standard torpedoes can't turn: straight through (and detonate)
    assert best_route(0, 0, 40, 0, gs, "torpedo", 30, max_turn=0)[1] == 0.0
    # Guided torpedoes may go round if the turn is within 45 degrees
    assert best_route(0, 0, 40, 0, gs, "torpedo", 30, max_turn=45)[1] == 1.0
    m = make_marker(id="b", ordnance_type="bomber", owner_player=1, x=0.0, y=0.0,
                    speed=20, craft_target_id="t")
    gs.ai_player = 1
    assert craft_target_point(m, gs) == wp
    gs.ai_player = 2                                   # player 1 is human: straight
    assert craft_target_point(m, gs) == (40.0, 0.0)



def test_blast_markers_and_dust_give_one_shift_between_them():
    """Owner ruling: a dust cloud in the line of fire shifts macrobatteries even
    if neither ship touches it, but it doesn't stack with blast markers."""
    from src.los import check_los
    from src.combat import get_column_shifts
    dust = make_phenomenon("gas_dust_cloud", x=10.0, y=0.0, width=4.0, height=4.0)
    dust2 = make_phenomenon("gas_dust_cloud", x=18.0, y=0.0, width=4.0, height=4.0, id="p2")
    blast = make_blast(x=14.0, y=0.0)
    assert check_los(0, 0, 25, 0, [dust], [])["column_shifts"] == 1
    assert check_los(0, 0, 25, 0, [dust, dust2], [blast])["column_shifts"] == 1
    assert check_los(0, 0, 25, 0, [], [])["column_shifts"] == 0
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    t = make_ship(id="t", player=2, x=25.0, y=0.0)
    assert get_column_shifts(a, t, [blast], [dust, dust2]) == get_column_shifts(a, t, [], [dust])


def test_attack_craft_in_dust_destroyed_on_a_six():
    """Owner ruling: attack craft in a gas / dust cloud are destroyed on a 6."""
    from src.ordnance import check_ordnance_vs_phenomena
    from tests.conftest import make_marker
    dust = make_phenomenon("gas_dust_cloud", x=0.0, y=0.0, width=10.0, height=10.0)
    m = make_marker(id="b", ordnance_type="bomber", owner_player=1, x=0.0, y=0.0)
    rolls = [6]
    dice = DiceStub(rolls)
    assert check_ordnance_vs_phenomena(m, [dust], dice) == (True, "gas_dust_cloud")
    assert dice._idx == len(rolls)
    rolls = [5]
    dice = DiceStub(rolls)
    assert check_ordnance_vs_phenomena(m, [dust], dice) == (False, "")
    assert dice._idx == len(rolls)


def test_craft_route_with_two_waypoints():
    """A field behind a field: every one-waypoint detour round the first still
    crosses one of the second pair, so the route goes round both (two
    waypoints); craft re-plan each move and follow it."""
    from src.ai_hazards import best_route, ordnance_path_survival
    gs = make_gs([])
    for i, (fx, fy) in enumerate(((20.0, 0.0), (40.0, 3.0), (40.0, -3.0))):
        gs.add_phenomenon(make_phenomenon("asteroid_field", x=fx, y=fy, width=4.0,
                                          height=4.0, id=f"a{i}"))
    assert len(gs.get_phenomena()) == 3
    for w in ((25.0, 5.0), (25.0, -5.0), (15.0, 5.0), (15.0, -5.0)):
        one = (ordnance_path_survival(0.0, 0.0, w[0], w[1], gs, "craft")
               * ordnance_path_survival(w[0], w[1], 60.0, 0.0, gs, "craft"))
        assert one < 1.0
    v, surv, length, wp = best_route(0.0, 0.0, 60.0, 0.0, gs, "craft", 20.0)
    assert surv == 1.0 and wp is not None
    assert v > best_route(0.0, 0.0, 60.0, 0.0, gs, "craft", 20.0, max_turn=0)[0]
