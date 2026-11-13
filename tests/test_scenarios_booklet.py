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
