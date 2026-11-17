"""Booklet scenarios (src/scenarios.py, To do 7): Confrontation and Domination
(XR p.117, p.125-126)."""
import math

import pytest

from src import scenarios as sc
from src.scenario import check_game_over
from tests.conftest import DiceStub, make_gs, make_ship


def _gs(ships, mode="domination", layout=1, w=180.0, h=120.0):
    gs = make_gs(ships)
    gs.table_width, gs.table_height = w, h
    gs.scenario_mode = mode
    gs.scenario_attacker = 1
    if mode == "domination":
        sc.setup_scenario(gs, layout=layout)
    return gs


@pytest.mark.parametrize("n,count", [(1, 3), (2, 3), (3, 4), (4, 4), (5, 4), (6, 3)])
def test_domination_layouts(n, count):
    gs = _gs([], layout=n)
    objs = sc.objectives(gs)
    assert len(objs) == count
    zones = sc.deployment_zones(gs)
    att = next(z for z in zones if z.player == 1)
    dfn = next(z for z in zones if z.player == 2)
    for (x, y) in objs:
        assert 0 <= x <= 180 and 0 <= y <= 120
    # The zones don't overlap each other
    for x in range(0, 181, 5):
        for y in range(0, 121, 5):
            assert not (att.contains(x, y) and dfn.contains(x, y)), (n, x, y)


def test_layout_positions_match_the_diagrams():
    gs = _gs([], layout=2)
    # 30cm from the right and top edges (top = y 120), the centre, 30cm from
    # the left and bottom edges
    assert sc.objectives(gs) == [(150.0, 90.0), (90.0, 60.0), (30.0, 30.0)]
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(100, 100) and not zones[1].contains(130, 100)
    assert zones[2].contains(70, 10) and not zones[2].contains(50, 10)
    # Domination 3: L-shaped zones
    gs = _gs([], layout=3)
    att = {z.player: z for z in sc.deployment_zones(gs)}[1]
    assert att.contains(40, 25) and att.contains(25, 40)
    assert not att.contains(40, 40) and not att.contains(25, 50)


def test_setup_rolls_the_d6():
    gs = make_gs([])
    gs.table_width, gs.table_height = 180.0, 120.0
    gs.scenario_mode = "domination"
    dice = DiceStub([4])
    sc.setup_scenario(gs, dice)
    assert dice._idx == 1 and gs.scenario_state["layout"] == 4
    assert len(sc.objectives(gs)) == 4


def test_control_needs_a_ship_within_15cm_and_no_enemy():
    a = make_ship(id="a", player=1, x=30.0, y=70.0)        # 10cm from (30, 60)
    b = make_ship(id="b", player=2, x=90.0, y=74.0)        # 14cm from the centre
    c = make_ship(id="c", player=2, x=165.0, y=60.0)       # 15cm: in range (stem)
    gs = _gs([a, b, c])
    m = sc.objectives(gs)
    assert sc.controller(gs, m[0]) == 1
    assert sc.controller(gs, m[1]) == 2
    assert sc.controller(gs, m[2]) == 2
    # An enemy ship in range contests it
    d = make_ship(id="d", player=1, x=95.0, y=60.0)
    gs.ships.append(d.to_dict())
    assert sc.controller(gs, m[1]) is None
    # A hulk holds nothing (reading)
    hulk = make_ship(id="h", player=2, x=30.0, y=55.0, status="drifting_hulk")
    gs.ships.append(hulk.to_dict())
    assert sc.controller(gs, m[0]) == 1


def test_scoring_at_the_end_of_each_players_turn_and_ending_at_10():
    a = make_ship(id="a", player=1, x=30.0, y=60.0)
    b = make_ship(id="b", player=1, x=90.0, y=60.0)
    e = make_ship(id="e", player=2, x=150.0, y=60.0)
    gs = _gs([a, b, e])
    assert sc.score_end_of_turn(gs, 1) == 2
    assert sc.score_end_of_turn(gs, 2) == 1
    assert sc.points(gs) == {1: 2, 2: 1}
    assert check_game_over(gs) is None
    for _ in range(4):
        sc.score_end_of_turn(gs, 1)
    res = check_game_over(gs)
    assert res["winner"] == 1 and res["reason"] == "objective_points"


def test_turn_controller_scores_the_active_player():
    from src.turn_controller import TurnController
    a = make_ship(id="a", player=1, x=30.0, y=60.0)
    e = make_ship(id="e", player=2, x=150.0, y=10.0)
    gs = _gs([a, e])
    tc = TurnController(gs, DiceStub([3]))
    gs.active_player = 1
    gs.current_phase = "end"
    tc.end_phase()
    assert sc.points(gs) == {1: 1, 2: 0}


def test_fleet_gone_is_decided_by_the_scenario():
    # Domination: player 2's fleet is gone but player 2 leads on points
    a = make_ship(id="a", player=1, x=30.0, y=60.0)
    e = make_ship(id="e", player=2, x=150.0, y=60.0, hits_remaining=0, status="destroyed",
                  points_value=180)
    gs = _gs([a, e])
    gs.scenario_state["points"] = {"1": 2, "2": 5}
    res = check_game_over(gs)
    assert res["reason"] == "no_ships" and res["winner"] == 2
    # Confrontation: by VP (player 1 destroyed an 8-hit cruiser)
    gs = _gs([a, e], mode="confrontation")
    res = check_game_over(gs)
    assert res["winner"] == 1


def test_confrontation_zones_and_first_turn():
    gs = _gs([], mode="confrontation")
    gs.scenario_attacker = 2
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(50, 100) and zones[1].contains(50, 20)
    assert sc.first_player(gs) == 2
    gs.scenario_mode = "standard"
    assert sc.first_player(gs) is None and sc.deployment_zones(gs) is None


def test_ai_moves_onto_an_objective_marker():
    """Domination: a Lunar 25cm short of a marker it can reach moves to hold
    it (the move score values the points it wins at the end of its turn)."""
    from src.ai_player import AIPlayer
    from src.models import Ship
    from src.ship_catalog import find_ship_class
    from src.turn_controller import TurnController

    def ship(name, player, x, y, h):
        d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"{name[:4]}{player}")
        d.update(x=x, y=y, heading=h, leadership=8)
        return Ship.from_dict(d)
    me = ship("Lunar Class Cruiser", 1, 30.0, 25.0, 90.0)
    foe = ship("Lunar Class Cruiser", 2, 150.0, 110.0, 270.0)
    gs = _gs([me, foe])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    cmds = ai._plan_move_toward(me, foe, "", 0)
    from src.movement import validate_movement
    res = validate_movement(me, cmds, "", table_width=180.0, table_height=120.0)
    ex, ey = res.path[-1]
    assert sc.controller(gs, (30.0, 60.0), [Ship.from_dict({**me.to_dict(), "x": ex, "y": ey}),
                                             foe]) == 1
    # Without the scenario the same ship doesn't go there
    gs.scenario_mode = "standard"
    cmds = ai._plan_move_toward(me, foe, "", 0)
    res = validate_movement(me, cmds, "", table_width=180.0, table_height=120.0)
    ex2, ey2 = res.path[-1]
    assert math.hypot(ex2 - 30.0, ey2 - 60.0) > 15.0


# --- Ambush, Rescue, Warp Storm ------------------------------------------------

def test_ambush_zones_unloaded_ordnance_and_no_orders_or_disengaging():
    from src.disengage import attempt_disengage
    from src.turn_controller import TurnController
    d = make_ship(id="d", player=2, x=90.0, y=60.0, leadership=10)
    a = make_ship(id="a", player=1, x=10.0, y=60.0)
    gs = _gs([a, d], mode="ambush")
    sc.setup_scenario(gs)
    d = gs.get_ship_by_id("d")
    assert not (d.ordnance_loaded_torps or d.ordnance_loaded_craft or d.ordnance_loaded_mines)
    assert gs.get_ship_by_id("a").ordnance_loaded_torps
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(90, 60) and not zones[2].contains(20, 60)
    for x, y in ((10, 60), (170, 60), (90, 10), (90, 110)):
        assert zones[1].contains(x, y)
    assert not zones[1].contains(90, 60)
    assert sc.first_player(gs) == 1
    gs.first_player = 1
    # Turns 1 (attacker) and 2 (defender): no orders, Brace or disengaging
    tc = TurnController(gs, DiceStub([1]))
    for turn in (1, 2):
        gs.turn_number = turn
        gs.active_player = 2
        assert sc.orders_forbidden(gs, d)
        assert "error" in tc.issue_special_order(d, "lock_on")
        dice = DiceStub([1])
        res = attempt_disengage(d, dice, gs)
        assert res.get("blocked") and dice._idx == 0
    gs.turn_number = 3
    assert sc.orders_forbidden(gs, d) is None and sc.disengage_forbidden(gs, d) is None
    assert sc.orders_forbidden(gs, a) is None


def test_ambush_placement_rules():
    gs = _gs([], mode="ambush")
    placed = [make_ship(id="p", player=2, x=60.0, y=60.0, heading=90.0)]
    g = [make_ship(id="q", player=2)]
    assert sc.placement_errors(gs, g, [(90.0, 60.0)], [90.0], placed) == []
    assert sc.placement_errors(gs, g, [(90.0, 60.0)], [0.0], placed)       # facing
    assert sc.placement_errors(gs, g, [(75.0, 60.0)], [90.0], placed)      # 15cm apart
    # Its own squadron may be closer; the attacker isn't bound
    sq = [make_ship(id="r", player=2, squadron_id="s")]
    placed2 = [make_ship(id="p2", player=2, x=60.0, y=60.0, heading=90.0, squadron_id="s")]
    assert sc.placement_errors(gs, sq, [(65.0, 60.0)], [90.0], placed2) == []
    assert sc.placement_errors(gs, [make_ship(id="z", player=1)], [(65.0, 60.0)], [0.0],
                               placed) == []
    zone = {z.player: z for z in sc.deployment_zones(gs)}[2]
    pos = sc.auto_positions(gs, g, zone, placed, 1)
    assert pos and all(zone.contains(*p) for p in pos)
    assert sc.placement_errors(gs, g, pos, [90.0], placed) == []


def test_rescue_flagship_placement_orders_edges_and_vp():
    from src.movement import execute_movement  # noqa: F401  (import check)
    from src.victory_points import calculate_victory_points
    flag = make_ship(id="f", player=2, is_flagship=True, points_value=200)
    other = make_ship(id="o", player=2, points_value=300)
    att = make_ship(id="a", player=1, points_value=100)
    gs = _gs([flag, other, att], mode="rescue")
    sc.setup_scenario(gs)
    assert gs.scenario_state["flagship"] == "f"
    assert sc.fixed_placements(gs) == {"f": (90.0, 60.0, 180.0)}
    assert sc.first_player(gs) == 2
    gs.first_player = 2
    gs.turn_number = 1
    f = gs.get_ship_by_id("f")
    assert sc.orders_forbidden(gs, f) and sc.orders_forbidden(gs, other) is None
    gs.turn_number = 2
    assert sc.orders_forbidden(gs, f) is None
    assert sc.disengage_forbidden(gs, f)                  # only off its own edge
    f.x, f.y = -1.0, 60.0
    assert not sc.off_table_destroyed(gs, f)              # the defender's (left) edge
    f.x, f.y = 181.0, 60.0
    assert sc.off_table_destroyed(gs, f)
    f.x, f.y = 90.0, 121.0
    assert sc.off_table_destroyed(gs, f)
    # Destroyed: the attacker scores its cost twice (destroyed + 100%)
    f.hits_remaining, f.status = 0, "destroyed"
    gs.update_ship(f)
    vp = calculate_victory_points(gs)
    assert vp[1]["total"] == 400


def test_rescue_flagship_off_the_wrong_edge_is_destroyed():
    from src.movement import MoveCommand, execute_movement, validate_movement
    flag = make_ship(id="f", player=2, is_flagship=True, x=175.0, y=60.0, heading=0.0)
    gs = _gs([flag, make_ship(id="a", player=1)], mode="rescue")
    sc.setup_scenario(gs)
    cmds = [MoveCommand("forward", 10.0)]
    res = validate_movement(flag, cmds, "", table_width=180.0, table_height=120.0)
    execute_movement(flag, res, gs)
    f = gs.get_ship_by_id("f")
    assert f.is_destroyed and not f.is_disengaged


def test_rescue_with_no_flagship_marked_uses_the_dearest_capital_ship():
    gs = _gs([make_ship(id="c", player=2, points_value=150),
              make_ship(id="b", player=2, points_value=365),
              make_ship(id="e", player=2, points_value=400, ship_type="escort", squadron_id="s")],
             mode="rescue")
    sc.setup_scenario(gs)
    assert gs.scenario_state["flagship"] == "b"


def test_warp_storm_corners_divisions_and_warp_tests():
    a1 = make_ship(id="a1", player=1, x=10.0, y=10.0, leadership=7)
    a2 = make_ship(id="a2", player=1, x=170.0, y=110.0, leadership=7)
    d1 = make_ship(id="d1", player=2, x=10.0, y=110.0, leadership=8)
    d2 = make_ship(id="d2", player=2, x=170.0, y=10.0, leadership=8)
    gs = _gs([a1, a2, d1, d2], mode="warp_storm")
    sc.setup_scenario(gs)
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(10, 10) and zones[1].contains(170, 110)
    assert zones[2].contains(10, 110) and zones[2].contains(170, 10)
    assert not zones[1].contains(90, 60)
    assert sc.division_errors(gs, 1) == [] and sc.division_errors(gs, 2) == []
    a2 = gs.get_ship_by_id("a2")
    a2.x, a2.y = 15.0, 15.0
    a3 = make_ship(id="a3", player=1, x=20.0, y=5.0)
    gs.update_ship(a2)
    gs.add_ship(a3)
    assert sc.division_errors(gs, 1)               # 3 v 0 capital ships
    # End of game: disengaged ships test Ld; a failure is destroyed
    for sid in ("a1", "d1"):
        s = gs.get_ship_by_id(sid)
        s.is_disengaged, s.status = True, "disengaged"
        gs.update_ship(s)
    dice = DiceStub([9, 8])        # a1 fails Ld 7, d1 passes Ld 8
    assert sc.end_of_game(gs, dice) and dice._idx == 2
    assert gs.get_ship_by_id("a1").is_destroyed
    assert gs.get_ship_by_id("d1").is_disengaged
    assert not sc.end_of_game(gs, DiceStub([]))    # once


def test_ai_values_for_rescue_and_warp_storm():
    from src.ai_hazards import damage_vp, disengage_gain
    flag = make_ship(id="f", player=2, is_flagship=True, points_value=200, hits_remaining=1)
    att = make_ship(id="a", player=1, points_value=100, x=20.0, y=0.0)
    gs = _gs([flag, att], mode="rescue")
    sc.setup_scenario(gs)
    rescue = damage_vp(gs.get_ship_by_id("f"), gs, 3.0)
    gs.scenario_mode = "confrontation"
    plain = damage_vp(gs.get_ship_by_id("f"), gs, 3.0)
    assert rescue > plain + 150          # +100% of 200 at P(kill) ~0.95
    # Warp Storm: leaving risks being lost in the warp, so it is worth less
    s = make_ship(id="s", player=2, points_value=200, leadership=6, hits_remaining=2,
                  x=0.0, y=0.0)
    e = make_ship(id="e", player=1, points_value=200, x=10.0, y=0.0,
                  weapons=[{"name": "B", "weapon_type": "battery", "strength": 12,
                            "range": 30, "arcs": ["front", "left", "right", "rear"]}])
    gs = _gs([s, e], mode="confrontation")
    calm = disengage_gain(gs.get_ship_by_id("s"), gs, 9, 0.0)
    gs.scenario_mode = "warp_storm"
    storm = disengage_gain(gs.get_ship_by_id("s"), gs, 9, 0.0)
    assert sc.warp_loss_chance(gs, s) == pytest.approx(21 / 36)
    assert storm < calm


# --- Immobile defences, Line Breaker, Space Assault ---------------------------

def _cat(name, player, sid, x=0.0, y=0.0, h=90.0):
    from src.models import Ship
    from src.ship_catalog import find_ship_class
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=sid)
    d.update(x=x, y=y, heading=h, leadership=d.get("leadership") or 8)
    return Ship.from_dict(d)


def test_immobile_defences_never_move_or_take_movement_orders():
    from src.ai_player import AIPlayer
    from src.disengage import attempt_disengage
    from src.turn_controller import TurnController
    st = _cat("Space Station", 1, "st", 90.0, 30.0)
    assert "immobile" in st.special_rules and "space_station_crits" in st.special_rules
    assert st.leadership == 7 and st.speed == 0
    foe = _cat("Lunar Class Cruiser", 2, "lu", 90.0, 100.0, 270.0)
    gs = _gs([st, foe], mode="standard")
    gs.active_player = 1
    tc = TurnController(gs, DiceStub([3]))
    assert tc.get_unmoved_ships() == []
    for order in ("all_ahead_full", "burn_retros", "come_to_new_heading"):
        assert "error" in tc.issue_special_order(gs.get_ship_by_id("st"), order)
    dice = DiceStub([2])
    assert attempt_disengage(gs.get_ship_by_id("st"), dice, gs).get("blocked")
    ai = AIPlayer(1, tc, gs, DiceStub([3, 3, 3, 3]))
    ai.run_movement_phase()
    s2 = gs.get_ship_by_id("st")
    assert (s2.x, s2.y, s2.heading) == (90.0, 30.0, 90.0)
    assert "st" in tc.ships_moved
    # Platforms are immobile too; a Lunar isn't
    assert "immobile" in _cat("Orbital Weapons Platform", 1, "p").special_rules
    assert "immobile" not in foe.special_rules


def test_space_station_critical_hits():
    from src.combat import _resolve_crit_cascade, weapon_disabled_by_crit
    from src.tables import crit_table_for, SPACE_STATION_CRITICAL_HITS
    st = _cat("Space Station", 1, "st")
    assert crit_table_for(st) is SPACE_STATION_CRITICAL_HITS
    assert crit_table_for(_cat("Orbital Weapons Platform", 1, "p")) is not \
        SPACE_STATION_CRITICAL_HITS                       # 2 hits: the normal table
    lances = [w for w in st.weapons if w["weapon_type"] == "lance"][0]
    guns = [w for w in st.weapons if w["weapon_type"] == "battery"][0]
    bays = [w for w in st.weapons if w["weapon_type"] == "launch_bay"][0]
    st.critical_damage = [{"crit_type": "station_lances"}]
    assert weapon_disabled_by_crit(st, lances) and not weapon_disabled_by_crit(st, guns)
    st.critical_damage = [{"crit_type": "station_batteries"}, {"crit_type": "station_bays"}]
    assert weapon_disabled_by_crit(st, guns) and weapon_disabled_by_crit(st, bays)
    st.critical_damage = [{"crit_type": "station_reactors"}]
    assert st.effective_shields == 1 and st.effective_turrets == 2
    # The Orbital Dock has no lances: the crit cascades up to Main Armament
    dock = _cat("Orbital Dock", 1, "dk")
    gs = _gs([dock], mode="standard")
    assert _resolve_crit_cascade(2, dock, gs)["crit_type"] == "station_batteries"


def test_line_breaker_zones_placement_victory_and_ai_values():
    from src.ai_hazards import damage_vp
    plats = [_cat("Orbital Weapons Platform", 2, f"p{i}") for i in range(2)]
    lunar = _cat("Lunar Class Cruiser", 2, "lu")
    att = _cat("Slaughter Class Cruiser", 1, "sl", 90.0, 110.0, 270.0)
    gs = _gs(plats + [lunar, att], mode="line_breaker")
    sc.setup_scenario(gs)
    assert not sc.force_errors(gs)                # 240pts: 2 platforms needed
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(90, 110) and not zones[1].contains(90, 100)
    assert zones[2].contains(90, 50) and zones[2].contains(90, 80)
    p = gs.get_ship_by_id("p0")
    assert sc.placement_errors(gs, [p], [(90.0, 60.0)], [90.0], []) == []
    assert sc.placement_errors(gs, [p], [(20.0, 60.0)], [90.0], [])       # near an edge
    assert sc.placement_errors(gs, [lunar], [(90.0, 80.0)], [90.0], [])   # beyond 60cm
    placed = [_cat("Orbital Weapons Platform", 2, "q", 95.0, 60.0)]
    assert sc.placement_errors(gs, [p], [(90.0, 60.0)], [90.0], placed)   # 15cm apart
    # AI: a platform carries a kill bonus for the attacker
    assert sc.kill_bonus_vp(gs, p) > 0 and sc.kill_bonus_vp(gs, lunar) == 0
    assert damage_vp(p, gs, 3.0) > damage_vp(p, _gs(plats, mode="standard"), 3.0)
    # Not won while a platform stands, even after a capital ship leaves
    a = gs.get_ship_by_id("sl")
    a.x, a.y = 90.0, -2.0
    sc.record_exit(gs, a)
    assert gs.scenario_state["exits"]["sl"] == "bottom"
    assert not sc.line_breaker_won(gs)
    for q in plats:
        q = gs.get_ship_by_id(q.id)
        q.hits_remaining, q.status = 0, "destroyed"
        gs.update_ship(q)
    assert sc.line_breaker_won(gs)
    res = check_game_over(gs)
    assert res["winner"] == 1 and res["reason"] == "breakthrough"


def test_line_breaker_platform_count():
    plats = [_cat("Orbital Weapons Platform", 2, f"p{i}") for i in range(1)]
    gs = _gs(plats + [_cat("Lunar Class Cruiser", 2, "lu")], mode="line_breaker")
    # 210pts or portion thereof: 2 platforms needed, 1 taken
    assert sc.force_errors(gs)
    gs.add_ship(_cat("Orbital Weapons Platform", 2, "p9"))
    assert not sc.force_errors(gs)


def test_space_assault_station_placement_and_vp():
    from src.victory_points import calculate_victory_points
    st = _cat("Space Station", 2, "st")
    att = _cat("Lunar Class Cruiser", 1, "lu")
    gs = _gs([st, att], mode="space_assault")
    sc.setup_scenario(gs)
    assert not sc.force_errors(gs)
    assert sc.fixed_placements(gs) == {"st": (90.0, 30.0, 90.0)}
    assert sc.first_player(gs) == 1
    vp = calculate_victory_points(gs)
    assert vp[2]["total"] == 250 and vp[1]["total"] == 0
    s = gs.get_ship_by_id("st")
    s.hits_remaining, s.status = 0, "destroyed"
    gs.update_ship(s)
    vp = calculate_victory_points(gs)
    assert vp[1]["total"] == 150 + 250 and vp[2]["total"] == 0
    assert sc.kill_bonus_vp(gs, s) == 500.0


# --- Convoy (matched play) -----------------------------------------------------

def test_transport_capacity_from_the_catalog():
    ht = _cat("Heavy Transport", 2, "ht")
    fc = _cat("Fast Clipper", 2, "fc")
    ec = _cat("Escort Carrier", 2, "ec")
    ct = _cat("Conventional Transport", 2, "ct")
    assert sc.transport(ht) == 2 and sc.transport(fc) == 0.5 and sc.transport(ct) == 1
    assert ct.points_value == 0 and not fc.weapons        # Free; unarmed but playable
    assert sc.transport(ec) == 0 and sc.transport(ec, building=True) == 1
    ht.hits_remaining = 3                                 # crippled: halved
    assert sc.transport(ht) == 1
    assert not sc.is_convoy(_cat("Lunar Class Cruiser", 2, "lu"))


def test_convoy_set_up_requirements_end_and_vp():
    from src.victory_points import calculate_victory_points
    lunar = _cat("Lunar Class Cruiser", 2, "lu")             # 180pts: 2 capacity
    c1 = _cat("Conventional Transport", 2, "c1")
    c2 = _cat("Heavy Transport", 2, "c2")
    att = _cat("Slaughter Class Cruiser", 1, "sl")
    gs = _gs([lunar, c1, c2, att], mode="convoy_matched")
    sc.setup_scenario(gs)
    assert sc.force_errors(gs)                               # 3 capacity, needs 2
    c2 = gs.get_ship_by_id("c2")
    gs.ships = [d for d in gs.ships if d["id"] != "c2"]
    gs.add_ship(_cat("Conventional Transport", 2, "c3"))
    assert not sc.force_errors(gs)
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(90, 20) and zones[1].contains(90, 90)
    assert not zones[1].contains(90, 110) and not zones[1].contains(90, 70)
    assert sc.first_player(gs) == 2
    # c1 escapes off the top: +100 to the defender; c3 leaves by a test:
    # destroyed + 50 for the attacker (its cost is 0)
    c1 = gs.get_ship_by_id("c1")
    c1.x, c1.y = 90.0, 121.0
    c1.is_disengaged, c1.status = True, "disengaged"
    gs.update_ship(c1)
    sc.record_exit(gs, c1)
    assert check_game_over(gs) is None                       # c3 still carries cargo
    c3 = gs.get_ship_by_id("c3")
    c3.is_disengaged, c3.status = True, "disengaged"
    gs.update_ship(c3)
    vp = calculate_victory_points(gs)
    assert vp[2]["total"] == 100 and vp[1]["total"] == 50
    res = check_game_over(gs)
    assert res["reason"] == "convoy_gone" and res["winner"] == 2


def test_ai_convoy_ship_runs_for_the_far_edge():
    from src.ai_player import AIPlayer
    from src.movement import validate_movement
    from src.turn_controller import TurnController
    ht = _cat("Heavy Transport", 2, "ht", 90.0, 20.0, 0.0)     # facing along the edge
    att = _cat("Slaughter Class Cruiser", 1, "sl", 30.0, 100.0, 270.0)
    gs = _gs([ht, att], mode="convoy_matched")
    sc.setup_scenario(gs)
    ai = AIPlayer(2, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    cmds = ai._plan_move_toward(ht, att, "", 0)
    res = validate_movement(ht, cmds, "", table_width=180.0, table_height=120.0)
    assert res.path[-1][1] > 23.0        # turns north as far as it can (10cm, then 45 degrees)
    assert ai._objective_stake(ht) > 100


# --- Planet Strike ---------------------------------------------------------------

def test_planet_strike_planet_zones_and_requirements():
    att = _cat("Lunar Class Cruiser", 1, "lu")
    tr = _cat("Heavy Transport", 1, "ht")
    dfn = _cat("Slaughter Class Cruiser", 2, "sl")
    plat = _cat("Orbital Weapons Platform", 2, "pl")
    gs = _gs([att, tr, dfn, plat], mode="planet_strike")
    gs.add_phenomenon(__import__("src.models", fromlist=["Phenomenon"]).Phenomenon(
        id="old", phenomenon_type="planet_small", x=50.0, y=50.0, radius=3.0))
    sc.setup_scenario(gs)
    pl = sc.strike_planet(gs)
    assert [p.id for p in gs.get_phenomena() if "planet" in p.phenomenon_type] == ["strike_planet"]
    assert pl.phenomenon_type == "planet_large" and pl.y == 60.0
    assert 180.0 - (pl.x - pl.radius) == 45.0       # the far side 45cm from the edge
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(10, 60) and not zones[1].contains(40, 60)
    assert zones[2].contains(170, 10) and zones[2].contains(pl.x - 30, 60)
    # Platforms in the gravity well, ships within 45cm of the edge
    assert sc.placement_errors(gs, [plat], [(pl.x - 30.0, 60.0)], [90.0], []) == []
    assert sc.placement_errors(gs, [plat], [(pl.x - 30.0, 20.0)], [90.0], [])
    assert sc.placement_errors(gs, [dfn], [(pl.x - 30.0, 60.0)], [90.0], [])
    # 180pts of warships: 2 capacity needed, a heavy transport carries 2
    assert sc.force_errors(gs) == []
    assert sc.first_player(gs) == 1


def test_planet_strike_bombardment_and_victory():
    pl_x = 180.0 - 45.0 + 8.0
    att = _cat("Lunar Class Cruiser", 1, "lu", pl_x - 8.0 - 1.0, 60.0)   # touching the planet
    tr = _cat("Heavy Transport", 1, "ht", pl_x, 60.0 + 9.0)
    far = _cat("Gothic Class Cruiser", 1, "go", 20.0, 60.0)
    dfn = _cat("Slaughter Class Cruiser", 2, "sl", 170.0, 10.0)
    gs = _gs([att, tr, far, dfn], mode="planet_strike")
    sc.setup_scenario(gs)
    assert sc.in_planet_contact(gs, gs.get_ship_by_id("lu"))
    assert not sc.in_planet_contact(gs, gs.get_ship_by_id("go"))
    t = gs.get_ship_by_id("ht")
    t.distance_moved_this_turn = 5.0          # moved: no points
    gs.update_ship(t)
    assert sc.score_end_of_turn(gs, 1) == 8   # the Lunar: 8 hits, no transport
    assert sc.score_end_of_turn(gs, 2) == 0   # only the attacker bombards
    t = gs.get_ship_by_id("ht")
    t.distance_moved_this_turn = 0.0
    gs.update_ship(t)
    assert sc.score_end_of_turn(gs, 1) == 8 + 6 + 2
    assert gs.scenario_state["bombardment"] == 24
    assert [sc.strike_need(p) for p in (0, 5, 6, 12, 20, 24, 30, 31)] == \
        [None, None, 6, 5, 4, 3, 2, 1]
    # The defender still holds ships: a 3+ roll decides it
    dice = DiceStub([2])
    assert sc.end_of_game(gs, dice) and dice._idx == 1
    assert sc.winner_at_end(gs, lambda g: None) == 2
    assert not sc.end_of_game(gs, DiceStub([]))
    # Holding the field wins outright
    gs.scenario_state = {"bombardment": 0}
    d = gs.get_ship_by_id("sl")
    d.hits_remaining, d.status = 0, "destroyed"
    gs.update_ship(d)
    sc.end_of_game(gs, DiceStub([]))
    assert sc.winner_at_end(gs, lambda g: None) == 1


def test_ai_holds_over_the_planet():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    pl_x = 180.0 - 45.0 + 8.0
    lu = _cat("Lunar Class Cruiser", 1, "lu", pl_x - 9.0, 60.0, 0.0)
    dfn = _cat("Slaughter Class Cruiser", 2, "sl", 170.0, 10.0)
    gs = _gs([lu, dfn], mode="planet_strike")
    sc.setup_scenario(gs)
    gs.active_player = 1
    tc = TurnController(gs, DiceStub([2]))            # passes the Burn Retros check
    ai = AIPlayer(1, tc, gs, DiceStub([2, 2, 2]))
    assert ai._bombard_hold_value(gs.get_ship_by_id("lu")) > 0
    ai.run_movement_phase()
    s = gs.get_ship_by_id("lu")
    assert s.special_order == "burn_retros" and (s.x, s.y) == (pl_x - 9.0, 60.0)
    assert sc.score_end_of_turn(gs, 1) == 8


def test_ai_prices_moves_off_the_table_and_edge_traps():
    """A healthy ship's move ending off the table is a disengage (the 10%
    conceded and its guns lost), and one ending pointed at an edge it can't
    avoid next turn costs nearly as much."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    lu = _cat("Lunar Class Cruiser", 1, "lu", 127.0, 15.0, 220.0)
    foe = _cat("Slaughter Class Cruiser", 2, "sl", 60.0, 80.0, 270.0)
    gs = _gs([lu, foe], mode="standard")
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    assert ai._off_table_score(lu, 120.0, -1.0, foe) < 0
    assert ai._edge_trap_penalty(lu, 127.0, 4.4, 220.0, foe) > 0
    assert ai._edge_trap_penalty(lu, 90.0, 60.0, 220.0, foe) == 0
    assert ai._edge_trap_penalty(lu, 127.0, 4.4, 40.0, foe) == 0     # pointing inwards
    cmds = ai._plan_move_toward(lu, foe, "", 0)
    from src.movement import validate_movement
    res = validate_movement(lu, cmds, "", table_width=180.0, table_height=120.0)
    ex, ey = res.path[-1]
    assert 0 < ey and ai._edge_trap_penalty(lu, ex, ey, res.final_heading, foe) == 0


def test_scenario_points_count_in_the_margin_and_the_expert_leaf():
    """To do 2: Domination's points (and Planet Strike's bombardment) count
    in the margin the AI plays for, and in the expert search's leaf."""
    from src.ai_hazards import game_risk
    from src.lookahead_ai import SimState, _evaluate
    a = make_ship(id="a", player=1, x=30.0, y=60.0, points_value=200)
    e = make_ship(id="e", player=2, x=150.0, y=100.0, points_value=200)
    gs = _gs([a, e])
    gs.turn_limit = 10
    base = game_risk(gs, 1)[0]
    gs.scenario_state["points"] = {"1": 4, "2": 1}
    assert game_risk(gs, 1)[0] == pytest.approx(
        base + 3 * sc.domination_point_vp(sc.table_points(gs)))
    assert sc.scenario_margin_vp(gs, 2) == -sc.scenario_margin_vp(gs, 1)
    # The leaf: holding a marker is worth more than not
    gs.turn_limit = None
    on = _evaluate(SimState.from_gs(gs), 1)
    a2 = gs.get_ship_by_id("a")
    a2.x, a2.y = 30.0, 100.0                       # 40cm from every marker
    gs.update_ship(a2)
    off = _evaluate(SimState.from_gs(gs), 1)
    assert on > off
    # Planet Strike bombardment counts for the attacker, against the defender
    gs2 = _gs([make_ship(id="b", player=1, points_value=100),
               make_ship(id="d", player=2, points_value=100)], mode="planet_strike")
    sc.setup_scenario(gs2)
    gs2.scenario_state["bombardment"] = 10
    assert sc.scenario_margin_vp(gs2, 1) > 0 > sc.scenario_margin_vp(gs2, 2)


def test_attack_ratings():
    navy = _cat("Lunar Class Cruiser", 1, "lu")
    orks = _cat("Kill Kroozer", 2, "kk") if __import__("src.ship_catalog", fromlist=["x"]
                                                         ).find_ship_class("Kill Kroozer") \
        else make_ship(id="kk", player=2, faction="orks", points_value=155)
    gs = _gs([navy, orks, _cat("Orbital Weapons Platform", 1, "pl")], mode="ambush")
    assert sc.attack_rating(gs, 1) == 2 and sc.attack_rating(gs, 2) == 3
    # Best die first, then the next; running out of dice loses
    dice = DiceStub([6, 3, 6, 5, 1])          # P1: 6,3  P2: 6,5,1
    assert sc.roll_attack_ratings(gs, dice) == 2 and dice._idx == 5
    dice = DiceStub([6, 5, 6, 5, 4])          # 6,5 v 6,5,4: player 1 runs out
    assert sc.roll_attack_ratings(gs, dice) == 2
    dice = DiceStub([2, 6, 5, 4, 3])          # P1 6,2 v P2 5,4,3
    assert sc.roll_attack_ratings(gs, dice) == 1
    # Equal ratings, equal dice: roll again
    gs2 = _gs([navy, make_ship(id="c", player=2, faction="chaos", points_value=100)])
    dice = DiceStub([4, 2, 4, 2, 6, 1, 3, 1])
    assert sc.roll_attack_ratings(gs2, dice) == 1 and dice._idx == 8
    # A Rogue Trader detachment doesn't change its fleet's rating
    gs2.add_ship(make_ship(id="rt", player=2, faction="rogue_traders", points_value=50))
    assert sc.attack_rating(gs2, 2) == 2
    # Sign-off answer 44: Rogue Traders alone 3, Dark Eldar 4, Tyranids 2
    gs3 = _gs([make_ship(id="r", player=1, faction="rogue_traders", points_value=50),
               make_ship(id="de", player=2, faction="dark_eldar", points_value=50)])
    assert sc.attack_rating(gs3, 1) == 3 and sc.attack_rating(gs3, 2) == 4


# --- Cruiser Clash, Chance Encounter ------------------------------------------------

def test_cruiser_clash_zones_facing_length_and_damage_points():
    a = make_ship(id="a", player=1, hits_max=8, hits_remaining=8)
    b = make_ship(id="b", player=2, hits_max=8, hits_remaining=8)
    gs = _gs([a, b], mode="cruiser_clash")
    dice = DiceStub([5])                        # player 1 sets up in Fleet B
    sc.setup_scenario(gs, dice)
    assert dice._idx == 1 and gs.scenario_state["fleet_a"] == 2
    assert gs.turn_limit == 16                  # eight turns each
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(90, 110) and not zones[2].contains(30, 110)
    assert zones[1].contains(90, 10) and not zones[1].contains(140, 10)
    assert sc.placement_errors(gs, [a], [(90.0, 10.0)], [90.0], []) == []
    assert sc.placement_errors(gs, [a], [(90.0, 10.0)], [45.0], [])
    assert sc.placement_errors(gs, [b], [(90.0, 110.0)], [270.0], []) == []
    assert sc.first_player(gs) is None and sc.first_turn_chooser(gs) is None
    # 5 damage and crippled: 6 points; destroyed: its 8 hits + 3
    b2 = gs.get_ship_by_id("b")
    b2.hits_remaining = 3
    gs.update_ship(b2)
    assert sc.damage_points(gs, 1) == 6 and sc.damage_points(gs, 2) == 0
    b2.hits_remaining, b2.status = 0, "destroyed"
    gs.update_ship(b2)
    assert sc.damage_points(gs, 1) == 11
    assert sc.winner_at_end(gs, lambda g: None) == 1


def test_chance_encounter_flagship_choice_and_victory():
    from src.ai_hazards import damage_vp
    flag = make_ship(id="f", player=1, is_flagship=True, points_value=500, hits_max=12,
                     hits_remaining=12)
    other = make_ship(id="o", player=1, points_value=180)
    dfn = make_ship(id="d", player=2, points_value=200)
    gs = _gs([flag, other, dfn], mode="chance_encounter")
    sc.setup_scenario(gs)
    assert gs.turn_limit == 12
    assert sc.fixed_placements(gs) == {"f": (90.0, 110.0, 270.0)}
    assert sc.first_turn_chooser(gs) == 2 and sc.first_player(gs) is None
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(90, 100) and not zones[1].contains(40, 100)
    assert zones[2].contains(40, 10)
    assert sc.chance_result(gs) is None                     # nothing yet: a draw
    # The AI values crippling the flagship far above its points
    f = gs.get_ship_by_id("f")
    gs2 = _gs([make_ship(**{**f.to_dict()}), make_ship(id="d", player=2)], mode="standard")
    assert damage_vp(f, gs, 6.0) > damage_vp(gs2.get_ship_by_id("f"), gs2, 6.0) + 100
    # Flagship and another capital ship off the bottom edge: the attacker wins
    for sid in ("f", "o"):
        s = gs.get_ship_by_id(sid)
        s.x, s.y = 90.0, -2.0
        s.is_disengaged, s.status = True, "disengaged"
        gs.update_ship(s)
        sc.record_exit(gs, s)
    assert sc.chance_result(gs) == 1
    f = gs.get_ship_by_id("f")
    f.hits_remaining = 5                                    # crippled: the defender wins
    gs.update_ship(f)
    assert sc.chance_result(gs) == 2


# --- The Raiders, Blockade Run -------------------------------------------------------

def test_raiders_set_up_alert_and_placement():
    from src.turn_controller import TurnController
    d1 = make_ship(id="d1", player=2, leadership=8)
    a1 = make_ship(id="a1", player=1, leadership=8)
    gs = _gs([a1, d1], mode="raiders")
    sc.setup_scenario(gs, DiceStub([2]))            # two turns of reduced alert
    assert gs.turn_limit == 16 and gs.get_ship_by_id("d1").leadership == 7
    assert gs.get_ship_by_id("a1").leadership == 8
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(1, 60) and zones[1].contains(90, 119) and not zones[1].contains(90, 60)
    assert zones[2].contains(90, 60) and not zones[2].contains(20, 60)
    p = [make_ship(id="p", player=2, x=60.0, y=60.0, heading=90.0)]
    assert sc.placement_errors(gs, [d1], [(100.0, 60.0)], [90.0], p) == []
    assert sc.placement_errors(gs, [d1], [(100.0, 60.0)], [45.0], p)      # not an edge
    assert sc.placement_errors(gs, [d1], [(100.0, 60.0)], [0.0], p)       # another edge
    assert sc.placement_errors(gs, [d1], [(70.0, 60.0)], [90.0], p)       # under 20cm
    tc = TurnController(gs, DiceStub([3]))
    gs.turn_number = 4
    sc.turn_start(gs)
    assert gs.get_ship_by_id("d1").leadership == 7
    gs.turn_number = 5
    tc.begin_phase("movement")
    assert gs.get_ship_by_id("d1").leadership == 8
    sc.turn_start(gs)
    assert gs.get_ship_by_id("d1").leadership == 8                         # once


def test_blockade_run_thirds_and_breakthrough_vp():
    from src.victory_points import calculate_victory_points
    b1 = make_ship(id="b1", player=2, points_value=100)
    e1 = make_ship(id="e1", player=2, ship_type="escort", squadron_id="s", points_value=40)
    e2 = make_ship(id="e2", player=2, ship_type="escort", squadron_id="s", points_value=40)
    a1 = make_ship(id="a1", player=1, points_value=200)
    a2 = make_ship(id="a2", player=1, points_value=200, hits_remaining=3)
    gs = _gs([b1, e1, e2, a1, a2], mode="blockade_run")
    dice = DiceStub([5, 2])                         # b1 third 3, the squadron third 1
    sc.setup_scenario(gs, dice)
    assert dice._idx == 2 and gs.turn_limit == 12
    assert gs.scenario_state["thirds"] == {"b1": 3, "s": 1}
    assert sc.placement_errors(gs, [b1], [(150.0, 100.0)], [0.0], []) == []
    assert sc.placement_errors(gs, [b1], [(30.0, 100.0)], [0.0], [])
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(30, 61) and not zones[2].contains(30, 59)
    assert zones[1].contains(30, 10) and not zones[1].contains(30, 20)
    for sid in ("a1", "a2"):
        s = gs.get_ship_by_id(sid)
        s.x, s.y, s.is_disengaged, s.status = 90.0, 122.0, True, "disengaged"
        gs.update_ship(s)
        sc.record_exit(gs, s)
    vp = calculate_victory_points(gs)
    # a1 uncrippled 200, a2 crippled 50; the blockader still scores them as
    # disengaged (10% and 25%)
    assert vp[1]["total"] == 250 and vp[2]["total"] == 20 + 50


# --- Reinforcements: The Bait, Rearguard Attack ---------------------------------------

def test_the_bait_reserves_arrive_and_score_nothing_until_then():
    from src.turn_controller import TurnController
    from src.victory_points import calculate_victory_points
    flee = make_ship(id="fl", player=2, points_value=180)
    big = make_ship(id="bg", player=2, points_value=365)
    e1 = make_ship(id="e1", player=2, ship_type="escort", squadron_id="s", points_value=40)
    e2 = make_ship(id="e2", player=2, ship_type="escort", squadron_id="s", points_value=40)
    att = make_ship(id="at", player=1, points_value=200, x=10.0, y=60.0)
    gs = _gs([flee, big, e1, e2, att], mode="the_bait")
    sc.setup_scenario(gs)
    assert gs.scenario_state["fleeing"] == "fl"                 # dearest unit within 250
    assert sc.is_reserve(gs.get_ship_by_id("bg")) and sc.is_reserve(gs.get_ship_by_id("e1"))
    assert not sc.is_reserve(gs.get_ship_by_id("fl"))
    assert sc.fixed_placements(gs) == {"fl": (90.0, 60.0, 0.0)}
    assert sc.first_player(gs) == 2
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(25, 60) and not zones[1].contains(35, 60)
    vp = calculate_victory_points(gs)
    assert vp[1]["total"] == 0                                  # reserves aren't "scattered"
    # The defender's turn: the hook takes the first unit offered and declines the next
    gs.active_player = 2
    asked = []
    gs.reserve_hook = lambda p, names: (asked.append(names), len(asked) == 1)[1]
    tc = TurnController(gs, DiceStub([3]))
    tc.begin_phase("movement")
    arrived = [s for s in gs.get_ships() if s.player == 2 and not sc.is_reserve(s)]
    assert len(asked) == 2 and len(arrived) == 2
    came = next(s for s in arrived if s.id != "fl")
    assert came.x > 175 and came.heading == 180.0 and came.status == "active"
    assert came.id in [s.id for s in tc.get_unmoved_ships()]   # it moves this turn
    # Escorts still in reserve keep the fleet alive
    for s in gs.get_ships():
        if s.player == 2 and not sc.is_reserve(s):
            s.hits_remaining, s.status = 0, "destroyed"
            gs.update_ship(s)
    assert check_game_over(gs) is None
    gs.reserve_hook = None
    sc.turn_start(gs)
    assert not sc.reserve_units(gs, 2)


def test_rearguard_reserves_alert_and_placement():
    ships = [make_ship(id=f"d{i}", player=2, points_value=p, leadership=8)
             for i, p in enumerate((100, 150, 200, 250))]
    gs = _gs(ships + [make_ship(id="a", player=1)], mode="rearguard")
    sc.setup_scenario(gs, DiceStub([3]))
    # 700pts: the cheapest units until a quarter (175): 100 + 150
    assert gs.scenario_state["reserve_units"] == ["d0", "d1"]
    assert sc.is_reserve(gs.get_ship_by_id("d1")) and not sc.is_reserve(gs.get_ship_by_id("d2"))
    assert gs.get_ship_by_id("d2").leadership == 7 and gs.turn_limit == 16
    assert sc.entry_edge(gs) == "left"
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(70, 60) and not zones[2].contains(50, 60) \
        and not zones[2].contains(70, 20)
    d2 = gs.get_ship_by_id("d2")
    assert sc.placement_errors(gs, [d2], [(100.0, 60.0)], [180.0], []) == []
    assert sc.placement_errors(gs, [d2], [(100.0, 60.0)], [0.0], [])
    sc.arrivals(gs, 2)
    d0 = gs.get_ship_by_id("d0")
    assert d0.x < 5 and d0.heading == 0.0 and not d0.is_disengaged


# --- Alien Intervention, Surprise Attack -----------------------------------------------

def test_alien_intervention_allies_arrive_by_turn():
    nav = make_ship(id="n", player=2, faction="imperial_navy_gothic", points_value=300)
    ally = make_ship(id="al", player=2, faction="tau_kororvesh", points_value=100)
    att = make_ship(id="a", player=1)
    gs = _gs([nav, ally, att], mode="alien_intervention")
    sc.setup_scenario(gs)
    assert sc.is_reserve(gs.get_ship_by_id("al")) and not sc.is_reserve(gs.get_ship_by_id("n"))
    assert any(p.id == "scenario_planet" for p in gs.get_phenomena()) and gs.turn_limit == 16
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(90, 60) and not zones[2].contains(50, 60)
    assert zones[1].contains(10, 60) and zones[1].contains(170, 60)
    assert not zones[1].contains(30, 60)
    # The defender's first turn: nothing; its second turn needs 4+
    gs.active_player, gs.turn_number = 2, 2
    dice = DiceStub([])
    sc.turn_start(gs, dice)
    assert dice._idx == 0 and sc.is_reserve(gs.get_ship_by_id("al"))
    gs.turn_number = 4                                   # game turn 2
    dice = DiceStub([3])
    sc.turn_start(gs, dice)
    assert dice._idx == 1 and sc.is_reserve(gs.get_ship_by_id("al"))
    gs.turn_number = 6                                   # game turn 3: 3+
    sc.turn_start(gs, DiceStub([3]))
    al = gs.get_ship_by_id("al")
    assert not sc.is_reserve(al) and al.y > 115 and al.heading == 270.0
    # First turn: the attacker's 2D6 against the defender's D6
    dice = DiceStub([5, 5, 7, 2])                        # tie re-rolled, then 7 v 2
    assert sc.roll_for_choice(gs, dice) == 1 and dice._idx == 4


def test_surprise_attack_standby_rules():
    from src.turn_controller import TurnController
    from src.ai_player import AIPlayer
    from src.hit_and_run import check_teleport_eligibility
    d = [make_ship(id=f"d{i}", player=2, points_value=p, leadership=7)
         for i, p in enumerate((300, 200, 100))]
    att = make_ship(id="a", player=1, x=5.0, y=60.0)
    gs = _gs(d + [att], mode="surprise_attack")
    sc.setup_scenario(gs, DiceStub([1]))                 # D3 = 1 unit on full alert
    assert gs.scenario_state["standby"] == ["d1", "d2"]
    pl = next(p for p in gs.get_phenomena() if p.id == "scenario_planet")
    assert pl.phenomenon_type == "planet_medium"          # 600pts
    d1 = gs.get_ship_by_id("d1")
    assert sc.on_standby(gs, d1) and not sc.on_standby(gs, gs.get_ship_by_id("d0"))
    # standby within 15cm of the planet, abeam (tangential)
    ok = sc.placement_errors(gs, [d1], [(pl.x + 10.0, pl.y)], [90.0], [])
    bad = sc.placement_errors(gs, [d1], [(pl.x + 10.0, pl.y)], [0.0], [])
    far = sc.placement_errors(gs, [d1], [(pl.x + 30.0, pl.y)], [90.0], [])
    assert ok == [] and bad and far
    gs.active_player = 2
    tc = TurnController(gs, DiceStub([]))
    assert {s.id for s in tc.get_unmoved_ships()} == {"d0"}
    assert {s.id for s in tc.get_unfired_ships()} == {"d0"}
    ok, why = check_teleport_eligibility(d1, att, gs)
    assert not ok
    # The AI leaves standby ships where they are
    for i, s in enumerate(gs.get_ships()):
        if s.player == 2:
            s.x, s.y = pl.x + 10 + 4 * i, pl.y
            gs.update_ship(s)
    AIPlayer(2, tc, gs, DiceStub([3] * 50)).run_movement_phase()
    assert gs.get_ship_by_id("d1").x == pl.x + 10 + 4
    # Defender's turn start: Ld tests (d1 passes with 7, d2 fails with 8)
    gs.turn_number = 2
    dice = DiceStub([7, 8])
    sc.turn_start(gs, dice)
    assert dice._idx == 2 and gs.scenario_state["standby"] == ["d2"]
    assert sc.orders_forbidden(gs, gs.get_ship_by_id("d1"))     # no orders this turn
    gs.turn_number = 4
    assert sc.orders_forbidden(gs, gs.get_ship_by_id("d1")) is None


def test_line_of_sight_of_zero_length_doesnt_divide_by_zero():
    from src.los import _line_intersects_circle
    assert _line_intersects_circle(5.0, 5.0, 5.0, 5.0, 0.0, 0.0, 10.0)
    assert not _line_intersects_circle(50.0, 5.0, 50.0, 5.0, 0.0, 0.0, 10.0)


# --- Fleet Engagement -------------------------------------------------------------------

def test_fleet_engagement_formations_setups_and_arrows():
    a = make_ship(id="a", player=1, speed=25)
    b = make_ship(id="b", player=2, speed=20)
    gs = _gs([a, b], mode="fleet_engagement")
    # sphere v cross: two results; player 1 (fastest ship, +1) wins the roll
    dice = DiceStub([3, 3])
    st = sc.resolve_formations(gs, "sphere", "cross", dice)
    assert dice._idx == 2 and st["chooser"] == 1
    assert st["setup"] == "A" and gs.scenario_attacker == 1     # A (Atk) for sphere
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(90, 110) and not zones[2].contains(40, 110)
    assert zones[1].contains(10, 60) and zones[1].contains(90, 10) and zones[1].contains(170, 60)
    assert sc.fe_division_at(gs, 1, 10, 60) == (0, 45.0)
    assert sc.fe_division_at(gs, 1, 170, 60) == (2, 135.0)
    assert sc.placement_errors(gs, [a], [(10.0, 60.0)], [45.0], []) == []
    assert sc.placement_errors(gs, [a], [(10.0, 60.0)], [90.0], [])
    # Every division needs a unit
    gs.update_ship(type(a).from_dict({**gs.get_ship_by_id("a").to_dict(), "x": 10.0, "y": 60.0}))
    assert sc.fe_division_errors(gs, 1)
    # A human chooser may take the other result; wedge v cross is set-up B outright
    st = sc.resolve_formations(gs, "sphere", "cross", DiceStub([1, 4]),
                               lambda p, o: o[1])
    assert st["chooser"] == 2 and st["setup"] == "D" and gs.scenario_attacker == 1
    st = sc.resolve_formations(gs, "wedge", "cross", DiceStub([]))
    assert st["setup"] == "B"
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[gs.scenario_attacker].contains(90, 10)
    assert sc.auto_heading(gs, 3 - gs.scenario_attacker, 90, 110) == 0.0


# --- Escalating Engagement ------------------------------------------------------------

def _ee_gs():
    p1 = [make_ship(id=f"a{i}", player=1, points_value=v, speed=20)
          for i, v in enumerate((300, 200, 150))]
    p2 = [make_ship(id=f"b{i}", player=2, points_value=v, speed=25)
          for i, v in enumerate((250, 180))]
    return _gs(p1 + p2, mode="escalating_engagement")


def test_escalating_divisions_and_starting_markers():
    from src import escalating as ee
    gs = _ee_gs()
    assert ee.auto_divisions(gs, 1) == [["a0"], ["a1"], ["a2"]]
    # starting division D6s (p1: 2 -> division 1; p2: a 4 is re-rolled, then 1),
    # roll-off 3 v 5 (p2 places second), p1's spot then p2's
    dice = DiceStub([2, 4, 1, 3, 5, 3, 3])
    sc.setup_scenario(gs, dice)
    assert dice._idx == 7
    st = gs.scenario_state
    assert st["start_div"] == {"1": 1, "2": 0} and st["first_marker"] == 1
    m1, m2 = ee.start_marker(gs, 1), ee.start_marker(gs, 2)
    for (x, y) in (m1, m2):
        assert 30 <= x <= 150 and 30 <= y <= 90
    assert math.hypot(m1[0] - m2[0], m1[1] - m2[1]) >= 60
    # only the starting divisions are on the table
    assert [s.id for s in gs.get_ships() if not sc.is_reserve(s)] == ["a1", "b0"]
    assert st["waiting"] == {"1": [0, 2], "2": [1]}
    # deployment within 10cm of the marker
    a1 = gs.get_ship_by_id("a1")
    zone = {z.player: z for z in sc.deployment_zones(gs)}[1]
    assert zone.contains(m1[0] + 9, m1[1])
    assert sc.placement_errors(gs, [a1], [(m1[0] + 9, m1[1])], [0.0], []) == []
    assert sc.placement_errors(gs, [a1], [(m1[0] + 8, m1[1] + 8)], [0.0], [])
    pts = sc.auto_positions(gs, [a1], zone, [], 0)
    assert math.hypot(pts[0][0] - m1[0], pts[0][1] - m1[1]) <= 10


def test_escalating_edge_markers_and_arrivals():
    from src import escalating as ee
    gs = _ee_gs()
    sc.setup_scenario(gs, DiceStub([2, 1, 3, 5, 3, 3]))
    a1, b0 = gs.get_ship_by_id("a1"), gs.get_ship_by_id("b0")
    a1.x, a1.y = 40.0, 20.0
    b0.x, b0.y = 150.0, 100.0
    gs.update_ship(a1)
    gs.update_ship(b0)
    # player 1's end phase: division D6 (2 of [0, 2] -> 2), edge 4 = bottom;
    # a1 is within 30cm of the bottom edge, so the marker goes within 30cm of it
    ee.end_of_turn(gs, 1, DiceStub([2, 4]))
    m = gs.scenario_state["edge_markers"][0]
    assert (m["player"], m["div"], m["edge"]) == (1, 2, "bottom") and m["y"] == 0.0
    assert math.hypot(m["x"] - 40.0, m["y"] - 20.0) <= 30
    assert gs.scenario_state["waiting"]["1"] == [0]
    # start of player 1's turn: speed 20 needs 5+, friends within 30cm +2: a 3 arrives
    gs.active_player = 1
    sc.turn_start(gs, DiceStub([3]))
    a2 = gs.get_ship_by_id("a2")
    assert not sc.is_reserve(a2) and a2.y < 5 and a2.heading == 90.0
    assert abs(a2.x - m["x"]) <= 10
    assert gs.scenario_state["edge_markers"] == []


def test_escalating_marker_waits_or_slides():
    from src import escalating as ee
    gs = _ee_gs()
    sc.setup_scenario(gs, DiceStub([2, 1, 3, 5, 3, 3]))
    a1, b0 = gs.get_ship_by_id("a1"), gs.get_ship_by_id("b0")
    a1.x, a1.y = 90.0, 60.0
    b0.x, b0.y = 0.0, 60.0         # an enemy within 60cm of the whole left edge
    gs.update_ship(a1)
    gs.update_ship(b0)
    ee.end_of_turn(gs, 1, DiceStub([1, 1]))          # left edge: nowhere legal
    assert gs.scenario_state["edge_markers"] == [] and gs.scenario_state["waiting"]["1"] == [0, 2]
    ee.end_of_turn(gs, 1, DiceStub([1, 6]))          # right edge, division 0
    m = gs.scenario_state["edge_markers"][0]
    assert m["edge"] == "right" and m["div"] == 0
    # a failed roll (speed 20: 5+, no friends near): the marker slides towards a1
    m0 = dict(m)
    a1.y = 110.0
    gs.update_ship(a1)
    gs.active_player = 1
    sc.turn_start(gs, DiceStub([4]))
    m = gs.scenario_state["edge_markers"][0]
    assert sc.is_reserve(gs.get_ship_by_id("a0"))
    assert m["y"] == min(110.0, m0["y"] + 20.0)


# --- Navigate the Storm ---------------------------------------------------------------

def _storm_gs():
    from src.models import Phenomenon
    att = [make_ship(id="a1", player=1, points_value=200, leadership=8, x=120.0, y=80.0),
           make_ship(id="a2", player=1, points_value=200, leadership=8, x=130.0, y=80.0)]
    dfn = [make_ship(id="d1", player=2, points_value=300, x=50.0, y=30.0)]
    convoy = [make_ship(id=f"c{i}", player=2, ship_type="escort", squadron_id="cv",
                        points_value=20, x=40.0 + 5 * i, y=20.0, special_rules=["transport:2"])
              for i in range(5)]
    gs = _gs(att + dfn + convoy, mode="navigate_storm")
    gs.add_phenomenon(Phenomenon(id="old", phenomenon_type="asteroid_field", x=10, y=10,
                                 width=10, height=10, radius=0))
    return gs


def test_navigate_storm_setup_rifts_and_zones():
    from src import navigate_storm as ns
    gs = _storm_gs()
    sc.setup_scenario(gs, DiceStub([1, 6] + [3, 4] * 15))
    rifts = gs.get_phenomena()
    assert len(rifts) == 16 and all(p.phenomenon_type == "warp_rift" for p in rifts)
    # D3x5cm wide, D3x10cm long (sign-off answer 17): 1 -> 5cm, 6 -> 30cm
    assert (rifts[0].width, rifts[0].height) == (30.0, 5.0)
    assert all((r.width, r.height) == (20.0, 10.0) for r in rifts[1:])
    for i, a in enumerate(rifts):
        for b in rifts[i + 1:]:
            gap = max(abs(a.x - b.x) - (a.width + b.width) / 2,
                      abs(a.y - b.y) - (a.height + b.height) / 2)
            assert gap >= 10.0 - 1e-9
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[2].contains(30, 10) and not zones[2].contains(15, 10)
    assert zones[1].contains(150, 100) and not zones[1].contains(165, 100) \
        and not zones[1].contains(150, 115)
    assert sc.first_turn_chooser(gs) == 1 and sc.first_player(gs) is None
    assert sc.force_errors(gs) == []                 # 5 x 2 capacity
    s = gs.get_ship_by_id("c0")
    s.x, s.y = 181.0, 85.0
    assert ns.via_exit_point(gs, s)
    s.y = 50.0
    assert not ns.via_exit_point(gs, s)


def test_navigate_storm_lost_ships_return_and_materialise():
    from src import navigate_storm as ns
    from src.terrain_effects import resolve_warp_rift_navigation
    from src.turn_controller import TurnController
    gs = _storm_gs()
    sc.setup_scenario(gs)
    a1 = gs.get_ship_by_id("a1")
    res = resolve_warp_rift_navigation(a1, DiceStub([6, 5, 4]), gs)     # 15 vs Ld 8
    assert not res["passed"]
    a1 = gs.get_ship_by_id("a1")
    assert a1.status == ns.LOST and a1.is_disengaged and gs.scenario_state["lost"] == ["a1"]
    # a defending ship lost in the warp counts as destroyed
    c0 = gs.get_ship_by_id("c0")
    resolve_warp_rift_navigation(c0, DiceStub([6, 6, 6]), gs)
    assert gs.get_ship_by_id("c0").is_destroyed and ns.capacity_destroyed(gs) == 2
    # the attacker's end phase: a 1 stays lost, then a 4 brings it back near
    # the capital ship nearest the convoy (the defender's d1)
    ns.end_phase(gs, 1, DiceStub([1]))
    assert gs.scenario_state["lost"] == ["a1"]
    ns.end_phase(gs, 1, DiceStub([4]))
    a1 = gs.get_ship_by_id("a1")
    d1 = gs.get_ship_by_id("d1")
    assert a1.status == "active" and a1.is_disengaged and ns.is_materialising(a1)
    assert math.hypot(a1.x - d1.x, a1.y - d1.y) <= 20
    # the attacker's next turn: it comes into play to move, then recovers at
    # the end of the movement phase: a failed Ld test halves its armament
    gs.active_player = 1
    ns.turn_start(gs, 1)
    assert not gs.get_ship_by_id("a1").is_disengaged
    a1 = gs.get_ship_by_id("a1")
    a1.x, a1.y = 120.0, 100.0
    gs.update_ship(a1)
    tc = TurnController(gs, DiceStub([9]))
    gs.current_phase = "movement"
    tc.end_phase()
    a1 = gs.get_ship_by_id("a1")
    assert not ns.is_materialising(a1) and ns.halved(a1)
    from src.combat import effective_battery_firepower
    assert effective_battery_firepower(a1, {"strength": 6, "name": "b"}) == 3
    # sign-off answer 14: ordnance is halved too
    from src.ordnance import mine_launch_strength
    assert mine_launch_strength(a1, {"strength": 4}) == 2
    ns.clear_half_armament(gs, 1)
    assert not ns.halved(gs.get_ship_by_id("a1"))


def test_navigate_storm_victory():
    from src import navigate_storm as ns
    gs = _storm_gs()
    sc.setup_scenario(gs)
    # three convoy ships (6 capacity) and d1 (300 of 400: >= 25%) off the exit point
    for sid in ("c0", "c1", "c2", "d1"):
        s = gs.get_ship_by_id(sid)
        s.x, s.y = 182.0, 80.0
        s.is_disengaged = True
        s.status = "disengaged"
        gs.update_ship(s)
        sc.record_exit(gs, s)
    assert ns.capacity_evacuated(gs) == 6 and ns.points_evacuated(gs) == 360
    met = ns.objectives_met(gs)
    assert met == {"attacker": False, "defender": True} and ns.winner(gs) == 2
    # evacuated ships give the attacker nothing
    from src.victory_points import calculate_victory_points
    assert calculate_victory_points(gs)[1]["total"] == 0
    # the last two convoy ships destroyed: no capacity left, the game ends
    for sid in ("c3", "c4"):
        s = gs.get_ship_by_id(sid)
        s.status = "destroyed"
        s.hits_remaining = 0
        gs.update_ship(s)
    end = sc.check_end(gs)
    assert end and end["winner"] == 2 and end["reason"] == "convoy_gone"


# --- Destroy the Docks ----------------------------------------------------------------

def _docks_gs():
    att = [make_ship(id=f"a{i}", player=1, points_value=v) for i, v in
           enumerate((300, 250, 200, 150))]
    dfn = [make_ship(id="d1", player=2, points_value=200, speed=20, is_flagship=True),
           make_ship(id="d2", player=2, points_value=150, speed=30)]
    gs = _gs(att + dfn, mode="destroy_docks")
    return gs


def test_destroy_docks_setup():
    from src import destroy_docks as dd
    gs = _docks_gs()
    sc.setup_scenario(gs)
    pl = dd.planet(gs)
    assert pl.phenomenon_type == "planet_large" and (pl.x, pl.y) == (90.0, 60.0)
    roles = gs.scenario_state["roles"]
    assert len(roles["station"]) == 2 and len(roles["dock"]) == 1 \
        and len(roles["inner"]) == 4 and len(roles["outer"]) == 4 \
        and len(roles["escort"]) == 2 and len(roles["monitor"]) == 1
    assert roles["fleet"] == ["d1", "d2"] and sc.is_reserve(gs.get_ship_by_id("d1"))
    assert gs.get_ship_by_id("d1").rerolls_remaining >= 1
    assert gs.scenario_state["forces"] == {"left": ["a0", "a3"], "right": ["a1", "a2"]}
    assert gs.turn_limit == 16 and sc.entry_edge(gs) == "top"
    # asteroid fields outside the well
    for p in gs.get_phenomena():
        if p.phenomenon_type == "asteroid_field":
            assert math.hypot(p.x - pl.x, p.y - pl.y) - 7.5 > pl.gravity_well_radius
    st = gs.get_ship_by_id(roles["station"][0])
    outer = gs.get_ship_by_id(roles["outer"][0])
    a0 = gs.get_ship_by_id("a0")
    assert sc.placement_errors(gs, [st], [(90.0, 80.0)], [90.0], []) == []
    assert sc.placement_errors(gs, [st], [(20.0, 20.0)], [90.0], [])
    assert sc.placement_errors(gs, [outer], [(20.0, 20.0)], [90.0], []) == []
    assert sc.placement_errors(gs, [a0], [(5.0, 60.0)], [0.0], []) == []
    assert sc.placement_errors(gs, [a0], [(175.0, 60.0)], [0.0], [])
    zone = {z.player: z for z in sc.deployment_zones(gs)}[2]
    pos = sc.auto_positions(gs, [st], zone, [], 0)
    assert dd.in_well(gs, *pos[0])


def test_destroy_docks_arrivals_mines_and_victory():
    from src import destroy_docks as dd
    from src.victory_points import calculate_victory_points
    gs = _docks_gs()
    sc.setup_scenario(gs)
    gs.active_player = 2
    # d1 (speed 20: 5+) rolls 4, d2 (speed 30: 3+) rolls 3
    sc.turn_start(gs, DiceStub([4, 3]))
    assert sc.is_reserve(gs.get_ship_by_id("d1"))
    d2 = gs.get_ship_by_id("d2")
    assert not sc.is_reserve(d2) and d2.y > 115
    assert len([m for m in gs.get_ordnance() if m.id.startswith("orbital_mine_")]) == 8
    # two failed turns: d1 needs 4+ now
    sc.turn_start(gs, DiceStub([2]))
    assert gs.scenario_state["fails"]["d1"] == 2
    sc.turn_start(gs, DiceStub([4]))
    assert not sc.is_reserve(gs.get_ship_by_id("d1"))
    # mines removed give the attacker 5 VP each
    gs.ordnance = [m for m in gs.ordnance if m["id"] not in ("orbital_mine_0", "orbital_mine_1")]
    vp = calculate_victory_points(gs)
    assert vp[1]["scenario"] == 10
    # the targets all destroyed, but not 25% of the reinforcements (350 -> 87.5)
    assert dd.winner(gs) == 2
    for sid in dd.targets(gs):
        s = gs.get_ship_by_id(sid)
        s.status = "destroyed"
        s.hits_remaining = 0
        gs.update_ship(s)
    assert dd.winner(gs) == 2
    d2 = gs.get_ship_by_id("d2")
    d2.status = "destroyed"
    d2.hits_remaining = 0
    gs.update_ship(d2)
    assert dd.winner(gs) == 1


# --- Convoy (narrative) ---------------------------------------------------------------

def _cn_gs():
    att = [make_ship(id="x", player=1, faction="chaos", points_value=100)]
    escort = [make_ship(id="d1", player=2, points_value=180, speed=20)]
    convoy = [make_ship(id=f"c{i}", player=2, ship_type="escort", squadron_id="cv",
                        points_value=0, speed=15, special_rules=["transport:1"])
              for i in range(4)]
    return _gs(att + escort + convoy, mode="convoy_narrative")


def test_convoy_narrative_force_and_markers():
    from src import convoy_narrative as cn
    gs = _cn_gs()
    # 4 capacity: 2 + 2 rolls: 2 (two clusters), 6 (a capital ship), 4 (escorts),
    # 1 (one cluster); the entry D6 5 -> right
    dice = DiceStub([2, 6, 4, 1, 5])
    sc.setup_scenario(gs, dice)
    assert dice._idx == 5
    st = gs.scenario_state
    kinds = [m["kind"] for m in st["markers"]]
    assert kinds == ["torpedoes", "craft", "unit", "unit", "torpedoes"]
    assert gs.get_ship_by_id("x") is None and st["replaced"] == ["x"]
    cap = next(m for m in st["markers"] if m["kind"] == "unit")
    s0 = gs.get_ship_by_id(cap["ships"][0])
    assert s0.faction == "chaos" and s0.points_value <= 200 and sc.is_reserve(s0)
    esc = [m for m in st["markers"] if m["kind"] == "unit"][1]
    assert sum(gs.get_ship_by_id(i).points_value for i in esc["ships"]) <= 100
    for i, a in enumerate(st["markers"]):
        assert 30 <= a["x"] <= 150 and 30 <= a["y"] <= 90
        for b in st["markers"][i + 1:]:
            assert math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= 30
    assert st["entry_edge"] == "right" and cn.exit_edge_for(gs) == "left"
    assert sc.first_player(gs) == 2
    assert cn.force_errors(gs) == []          # 180 <= 2 x 100; squadron of 4


def test_convoy_narrative_arrival_activation_and_end():
    from src import convoy_narrative as cn
    from src.turn_controller import TurnController
    gs = _cn_gs()
    sc.setup_scenario(gs, DiceStub([1, 1, 1, 1, 2]))           # 4 clusters, left entry
    gs.active_player = 2
    gs.turn_number = 1
    sc.turn_start(gs, DiceStub([]))
    c0 = gs.get_ship_by_id("c0")
    assert not sc.is_reserve(c0) and c0.x < 5 and abs(c0.y - 60) < 20
    assert gs.scenario_state["start_pos"]["c0"]
    # moving to within 30cm of the nearest marker activates it at the end of
    # the movement phase: torpedoes (D6+2 = 6) facing the nearest defender
    m = min((x for x in gs.scenario_state["markers"] if x["kind"] == "torpedoes"),
            key=lambda m: m["x"])
    c0.x, c0.y = m["x"] - 25.0, m["y"]
    gs.update_ship(c0)
    gs.current_phase = "movement"
    tc = TurnController(gs, DiceStub([4]))
    tc.end_phase()
    m = next(x for x in gs.scenario_state["markers"] if x["id"] == m["id"])
    assert m["deployed"]
    torp = next(o for o in gs.get_ordnance() if o.id == f"deadfall_{m['id']}")
    assert torp.strength == 6 and torp.speed == 30 and abs(torp.heading - 180.0) < 1
    # three convoy ships off the far (right) edge: a Convoy Win
    for sid in ("c0", "c1", "c2"):
        s = gs.get_ship_by_id(sid)
        s.x, s.status, s.is_disengaged = 182.0, "disengaged", True
        gs.update_ship(s)
        sc.record_exit(gs, s)
    assert cn.capacity_escaped(gs) == 3
    c3 = gs.get_ship_by_id("c3")
    c3.status, c3.hits_remaining = "destroyed", 0
    gs.update_ship(c3)
    gs.turn_number = 3
    end = sc.check_end(gs)
    assert end["winner"] == 2 and "Convoy Win" in end["detail"]


def test_convoy_narrative_activation_follows_the_path():
    """Sign-off answer 6: the actual path, turns included, not a straight line
    from the start to the end."""
    from src import convoy_narrative as cn
    gs = _cn_gs()
    sc.setup_scenario(gs, DiceStub([1, 1, 1, 1, 2]))
    st = dict(gs.scenario_state)
    st["markers"] = [{"id": "m", "kind": "torpedoes", "x": 100.0, "y": 100.0,
                      "active": False}]
    gs.scenario_state = st
    c0 = gs.get_ship_by_id("c0")
    c0.x, c0.y, c0.status, c0.is_disengaged = 60.0, 40.0, "active", False
    gs.update_ship(c0)
    cn.record_start_positions(gs, 2)
    # out to (80, 80), within 28cm of the marker, then back to (100, 40):
    # the straight line from start to end passes 60cm away
    c0.x, c0.y = 100.0, 40.0
    gs.update_ship(c0)
    cn.record_path(gs, c0, [(60.0, 40.0), (80.0, 80.0), (100.0, 40.0)])
    assert cn.check_activation(gs) == ["m"]
