"""Low orbit (s.39, src/low_orbit.py) and the two planet scenarios built on it,
Exterminatus! and Planetary Assault (src/planet_scenarios.py)."""
import math

from src import low_orbit as lo
from src import scenarios as sc
from src import planet_scenarios as ps
from tests.conftest import DiceStub, make_gs, make_ship


def _gs(ships, mode="exterminatus"):
    gs = make_gs(ships)
    gs.table_width, gs.table_height = 180.0, 120.0
    gs.scenario_mode = mode
    gs.scenario_attacker = 1
    return gs


def _setup(gs, rolls):
    dice = DiceStub(rolls)
    sc.setup_scenario(gs, dice)
    assert dice._idx == len(rolls)


def test_planet_placement_and_zones():
    gs = _gs([make_ship(id="a", player=1, points_value=900, hits_max=8),
              make_ship(id="d", player=2, points_value=300)])
    _setup(gs, [6])                                   # a large planet
    pl = lo.planet(gs)
    assert pl.phenomenon_type == "planet_large" and pl.radius == 8.0
    # its near edge 150cm from the attacker's (right) short edge, centred
    assert abs((180.0 - (pl.x + pl.radius)) - 150.0) < 1e-9 and pl.y == 60.0
    zones = {z.player: z for z in sc.deployment_zones(gs)}
    assert zones[1].contains(170, 60) and not zones[1].contains(160, 60)
    assert zones[2].contains(40, 40) and not zones[2].contains(20, 40)


def test_entering_falling_landing_and_leaving():
    esc = make_ship(id="e", player=1, ship_type="escort", x=0, y=0)
    cap = make_ship(id="c", player=1, x=0, y=0)
    gs = _gs([esc, cap, make_ship(id="d", player=2, points_value=300)])
    _setup(gs, [2])                                    # medium planet: falls 8cm
    pl = lo.planet(gs)
    for s in (esc, cap):
        s = gs.get_ship_by_id(s.id)
        s.x, s.y = pl.x + pl.radius + 5.0, pl.y
        gs.update_ship(s)
        assert lo.can_enter(gs, s)
        lo.enter(gs, s)
    c = gs.get_ship_by_id("c")
    assert lo.in_low_orbit(c) and c.y < lo.Y0 + 3 and c.heading in (0.0, 180.0)
    assert lo.entered_this_turn(gs, c)
    # far from the planet edge (60cm): no fall
    lo.falling(gs)
    assert gs.get_ship_by_id("c").y < lo.Y0 + 3
    # within 45cm: falls 8cm; off the planet edge that way, destroyed
    c.y = lo.planet_edge_y() - 20.0
    gs.update_ship(c)
    lo.falling(gs)
    assert abs(gs.get_ship_by_id("c").y - (lo.planet_edge_y() - 12.0)) < 1e-9
    c = gs.get_ship_by_id("c")
    c.y = lo.planet_edge_y() - 3.0
    gs.update_ship(c)
    lo.falling(gs)
    assert gs.get_ship_by_id("c").is_destroyed
    # an escort moving off the planet edge lands (disengages)
    e = gs.get_ship_by_id("e")
    e.y = lo.planet_edge_y() + 1.0
    gs.update_ship(e)
    assert lo.handle_move_end(gs, e)
    e = gs.get_ship_by_id("e")
    assert e.is_disengaged and "landed" in e.special_rules


def test_return_to_high_orbit_and_no_leaving_the_turn_it_entered():
    s = make_ship(id="s", player=1)
    gs = _gs([s, make_ship(id="d", player=2)])
    _setup(gs, [2])
    pl = lo.planet(gs)
    s = gs.get_ship_by_id("s")
    s.x, s.y = pl.x - pl.radius - 4.0, pl.y
    gs.update_ship(s)
    lo.enter(gs, s)
    s = gs.get_ship_by_id("s")
    x_in = s.x
    s.y = lo.Y0 - 2.0                     # off the edge furthest from the planet
    gs.update_ship(s)
    assert lo.handle_move_end(gs, s)
    s = gs.get_ship_by_id("s")
    assert lo.in_low_orbit(s) and s.y >= lo.Y0          # entered this turn: stays
    gs.turn_number += 1
    s.y = lo.Y0 - 2.0
    gs.update_ship(s)
    lo.handle_move_end(gs, s)
    s = gs.get_ship_by_id("s")
    assert not lo.in_low_orbit(s)
    assert abs(math.hypot(s.x - pl.x, s.y - pl.y) - (pl.radius + s.base_radius + 0.1)) < 1e-6
    assert x_in > 0


def test_low_orbit_movement_shooting_and_launch_limits():
    from src.movement import validate_movement, MoveCommand, get_effective_speed
    from src.combat import get_column_shifts, resolve_lances
    from src.ordnance import launch_torpedoes
    a = make_ship(id="a", player=1, x=50.0, y=lo.Y0 + 20.0, heading=0.0,
                  special_rules=["in_low_orbit"])
    t = make_ship(id="t", player=2, x=70.0, y=lo.Y0 + 20.0, special_rules=["in_low_orbit"])
    gs = _gs([a, t])
    a = gs.get_ship_by_id("a")
    assert get_effective_speed(a, "")[0] == 0                   # no minimum move
    r = validate_movement(a, [MoveCommand("turn_left", 45), MoveCommand("forward", 10)], "",
                          table_width=180, table_height=120)
    assert r.valid, r.errors                                    # turning at once
    assert r.final_y > lo.Y0                                    # not clamped to the main table
    plain = make_ship(id="p", player=1, x=50.0, y=lo.Y0 + 20.0)
    assert get_column_shifts(a, t, [], []) == get_column_shifts(plain, t, [], []) + 1
    w = {"name": "Lance", "weapon_type": "lance", "strength": 2, "range_cm": 30,
         "arcs": ["front"]}
    res = resolve_lances(a, t, w, DiceStub([3]))                # fails to fire on a 3
    assert "fails to fire" in res.description
    torp = {"name": "Torps", "weapon_type": "torpedo", "strength": 6, "arcs": ["front"]}
    assert launch_torpedoes(a, torp, gs) is None


def test_exterminators_rolls_and_victory():
    big = make_ship(id="big", player=1, hits_max=10, points_value=400,
                    weapons=[{"name": "Prow Torpedoes", "weapon_type": "torpedo",
                              "strength": 6, "location": "Prow", "arcs": ["front"]},
                             {"name": "Port Macrobatteries", "weapon_type": "battery",
                              "strength": 6, "arcs": ["left"]}])
    small = make_ship(id="sm", player=1, hits_max=6, points_value=300)
    d = [make_ship(id=f"d{i}", player=2, points_value=v) for i, v in enumerate((300, 200))]
    gs = _gs([big, small] + d)
    _setup(gs, [2])
    st = gs.scenario_state
    # one Exterminator per 1000pts or portion (700pts: one), the most hits
    assert st["exterminators"] == ["big"]
    b = gs.get_ship_by_id("big")
    assert [w["name"] for w in b.weapons] == ["Port Macrobatteries"]   # prow replaced
    # one patrol per 500pts or portion (500: one), the cheapest
    assert st["patrol"] == ["d1"] and sc.is_reserve(gs.get_ship_by_id("d1"))
    # the defender treats an Exterminator as the closest enemy
    assert ps.priority_free(gs, gs.get_ship_by_id("d0"), b)
    # in low orbit within 45cm of the planet edge: 4+ destroys the planet
    pl = lo.planet(gs)
    b.x, b.y = pl.x + pl.radius + 3.0, pl.y
    gs.update_ship(b)
    lo.enter(gs, b)
    b = gs.get_ship_by_id("big")
    b.y = lo.planet_edge_y() - 40.0
    gs.update_ship(b)
    gs.active_player = 1
    ps.turn_start(gs, 1, DiceStub([3]))
    assert not gs.scenario_state.get("planet_destroyed")
    ps.turn_start(gs, 1, DiceStub([4]))
    end = sc.check_end(gs)
    assert end["winner"] == 1 and end["reason"] == "exterminatus"


def test_patrols_arrive_from_a_random_edge():
    gs = _gs([make_ship(id="a", player=1, points_value=500),
              make_ship(id="d0", player=2, points_value=300, speed=20),
              make_ship(id="d1", player=2, points_value=100, speed=30)])
    _setup(gs, [2])
    assert gs.scenario_state["patrol"] == ["d1"]
    # speed 30: 3+; the edge D6 2 -> top
    ps.turn_start(gs, 2, DiceStub([3, 2]))
    d1 = gs.get_ship_by_id("d1")
    assert not sc.is_reserve(d1) and d1.y > 115 and d1.heading == 270.0


def test_planetary_assault_points_and_result():
    cap = make_ship(id="c", player=1, points_value=300)
    tr = make_ship(id="t", player=1, ship_type="escort", points_value=40,
                   special_rules=["transport:1"])
    gs = _gs([cap, tr, make_ship(id="d", player=2, points_value=300)],
             mode="planetary_assault")
    _setup(gs, [2])
    assert gs.scenario_state["alert"] == ["d"]
    assert sc.force_errors(gs)                      # 640pts: 4 capacity needed, has 1
    pl = lo.planet(gs)
    for sid in ("c", "t"):
        s = gs.get_ship_by_id(sid)
        s.x, s.y = pl.x + pl.radius + 3.0, pl.y
        gs.update_ship(s)
        lo.enter(gs, s)
        s = gs.get_ship_by_id(sid)
        s.y = lo.planet_edge_y() - 25.0
        gs.update_ship(s)
    gs.ai_spectator = True
    ps.shooting_start(gs, 1)
    # capital ship: at least ½ capacity -> 1 point; the transport 2
    assert gs.scenario_state["assault_points"] == 3.0
    assert ps.assaulting(gs, gs.get_ship_by_id("c")) and gs.get_ship_by_id("c").has_fired
    assert ps.assault_result(3) == "Defender's Marginal Win"
    assert ps.assault_result(6) == "Attacker's Marginal Win"
    st = dict(gs.scenario_state)
    st["assault_points"] = 10.0
    gs.scenario_state = st
    end = sc.check_end(gs)
    assert end["winner"] == 1 and "Attacker's Victory" in end["detail"]
