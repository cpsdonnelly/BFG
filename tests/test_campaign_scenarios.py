"""Campaign set pieces (src/campaign_scenarios.py): The Defence of Pelucidar
and Macharia's End (XR p.111-112)."""
from src import scenarios as sc
from src import campaign_scenarios as cs
from src.scenario import check_game_over
from tests.conftest import DiceStub, make_gs, make_ship


def _gs(ships, mode, w=180.0, h=120.0):
    gs = make_gs(ships)
    gs.table_width, gs.table_height = w, h
    gs.scenario_mode = mode
    gs.scenario_attacker = 1
    return gs


def _imperial(id_, x=90.0, y=60.0, pts=180, **kw):
    return make_ship(id=id_, name=id_, player=2, faction="imperial_navy_gothic",
                     points_value=pts, x=x, y=y, **kw)


# --- The Defence of Pelucidar ----------------------------------------------------

def test_pelucidar_table():
    assert cs.pelucidar_result(2) == "fighta_bommerz"
    assert cs.pelucidar_result(4) == "fighta_bommerz"
    assert cs.pelucidar_result(5) == "one_squadron"
    assert cs.pelucidar_result(9) == "two_squadrons"
    assert cs.pelucidar_result(10) == "three_squadrons"
    assert cs.pelucidar_result(11) == "kroozer"
    assert cs.pelucidar_result(12) == "two_kroozers"
    assert cs.pelucidar_result(13) == "hammer"
    # the Space Hulk / Rok aren't playable: the next lowest result
    assert cs.pelucidar_result(15) == "hammer"


def test_pelucidar_setup_removes_the_ork_fleet_and_places_the_planet():
    orks = make_ship(id="o1", player=1, faction="orks", points_value=150)
    gs = _gs([orks, _imperial("i1")], "pelucidar")
    sc.setup_scenario(gs, DiceStub([]))
    assert [s.id for s in gs.get_ships()] == ["i1"]
    planet = next(p for p in gs.get_phenomena() if p.id == "scenario_planet")
    assert planet.phenomenon_type == "planet_medium"
    assert sc.first_player(gs) == 1                 # the Orks always go first


def test_pelucidar_arrivals_roll_d6_plus_turn():
    gs = _gs([_imperial("i1")], "pelucidar")
    gs.turn_number = 1                              # game turn 1
    # D6 4 + 1 = 5: one squadron of D6 (3) escorts; edge D6 5 (bottom);
    # three Ld rolls on the Orks table
    dice = DiceStub([4, 5, 3, 2, 6, 1])
    cs.pelucidar_arrivals(gs, dice)
    assert dice._idx == 6
    orks = [s for s in gs.get_ships() if s.player == 1]
    assert len(orks) == 3 and all(s.ship_class == cs.ORK_ESCORT for s in orks)
    assert len({s.squadron_id for s in orks}) == 1
    assert sorted(s.leadership for s in orks) == [5, 6, 8]
    assert all(s.y < 10 and s.heading == 90.0 for s in orks)   # on the bottom edge, facing in


def test_pelucidar_arrivals_fighta_bommerz_wave():
    gs = _gs([_imperial("i1")], "pelucidar")
    gs.turn_number = 1
    dice = DiceStub([1, 1])                         # 1 + 1 = 2; the left edge
    cs.pelucidar_arrivals(gs, dice)
    wave = gs.get_ordnance()
    assert len(wave) == 4 and len({m.wave_id for m in wave}) == 1
    assert all(m.x < 2 and m.owner_player == 1 for m in wave)


def test_pelucidar_game_goes_on_without_ork_ships_and_no_one_holds_the_field():
    gs = _gs([_imperial("i1")], "pelucidar")
    assert check_game_over(gs) is None               # no Ork ship on the table
    from src.victory_points import calculate_victory_points
    vp = calculate_victory_points(gs)
    assert vp[2]["holding_field"] == 0


def test_pelucidar_needs_2000_more_vp():
    dead = [make_ship(id=f"o{i}", player=1, faction="orks", points_value=400,
                      status="destroyed", hits_remaining=0) for i in range(5)]
    gs = _gs(dead + [_imperial("i1")], "pelucidar")
    assert cs.pelucidar_winner(gs) == 2              # 2000 VP ahead
    gs.ships[0]["status"] = "active"
    gs.ships[0]["hits_remaining"] = 8
    assert cs.pelucidar_winner(gs) == 1              # only 1600: the Orks win


def test_pelucidar_force_errors_flag_escorts():
    gs = _gs([_imperial("i1"), _imperial("e1", ship_type="escort")], "pelucidar")
    assert cs.pelucidar_force_errors(gs)


# --- Macharia's End ---------------------------------------------------------------

def _macharia(extra=()):
    chaos = make_ship(id="c1", player=1, faction="chaos", points_value=200, x=170, y=60)
    gs = _gs([chaos, _imperial("i1", x=10), _imperial("v1", pts=150, x=90)] + list(extra),
             "macharia")
    sc.setup_scenario(gs, DiceStub([4]))            # the Planet Killer's Ld roll
    return gs


def test_macharia_setup():
    gs = _macharia()
    pk = cs.planet_killer(gs)
    assert pk is not None and pk.points_value == 0 and pk.leadership == 8
    assert sc.is_reserve(pk)
    pl = cs.macharia(gs)
    assert pl.phenomenon_type == "planet_medium" and pl.x == pl.radius
    # the vanguard: the cheapest units up to 500pts
    assert set(gs.scenario_state["vanguard"]) == {"i1", "v1"}
    assert sc.first_player(gs) == 2


def test_planet_killer_arrives_then_charges():
    gs = _macharia()
    gs.active_player = 1
    cs.macharia_turn_start(gs, 1, DiceStub([]), ask=lambda s: True)
    pk = cs.planet_killer(gs)
    assert not sc.is_reserve(pk) and pk.x > 170        # on the Chaos (right) edge
    cs.macharia_turn_start(gs, 1, DiceStub([]), ask=lambda s: True)
    pk = cs.planet_killer(gs)
    assert gs.scenario_state["charge"] == 1
    assert "overcharging" in pk.special_rules
    from src.movement import get_max_turns
    assert get_max_turns("none", pk) == 0
    from src.combat import weapon_disabled_by_crit
    lances = [w for w in pk.weapons if w.get("weapon_type") == "lance"]
    assert lances and all(weapon_disabled_by_crit(pk, w) for w in lances)
    assert cs.order_forbidden(gs, pk, "reload_ordnance")
    shields = pk.shields_max
    cs.macharia_turn_start(gs, 1, DiceStub([]))
    cs.macharia_turn_start(gs, 1, DiceStub([]))
    assert cs.charged(gs) and cs.planet_killer(gs).shields_max == shields


def test_overcharged_shot_destroys_macharia_and_ships_on_the_way():
    gs = _macharia()
    pk = cs.planet_killer(gs)
    pl = cs.macharia(gs)
    for sd in gs.ships:
        if sd["id"] == pk.id:
            sd.update(status="active", is_disengaged=False, x=pl.x + 50.0, y=pl.y,
                      heading=180.0)
        if sd["id"] == "v1":
            sd.update(x=pl.x + 30.0, y=pl.y + 1.0)
    gs.scenario_state["charge"] = 3
    cs.shooting_start(gs, 1)
    assert gs.get_ship_by_id("v1").is_destroyed
    assert gs.scenario_state["planet_destroyed"]
    assert sc.check_end(gs)["winner"] == 1


def test_a_miss_needs_two_reloads_on_consecutive_turns():
    gs = _macharia()
    pk = cs.planet_killer(gs)
    pl = cs.macharia(gs)
    for sd in gs.ships:
        if sd["id"] == pk.id:
            sd.update(status="active", is_disengaged=False, x=pl.x + 50.0, y=pl.y + 40.0,
                      heading=180.0)
    gs.scenario_state["charge"] = 3
    cs.shooting_start(gs, 1)
    assert not gs.scenario_state.get("planet_destroyed") and cs.recharging(gs)
    pk = cs.planet_killer(gs)
    assert "pk_recharging" in pk.special_rules
    assert cs.order_forbidden(gs, pk, "lock_on")
    assert cs.order_forbidden(gs, pk, "reload_ordnance") is None
    gs.turn_number = 3
    cs.record_reload(gs, pk)
    gs.turn_number = 7                               # not the next Chaos turn: starts again
    cs.record_reload(gs, pk)
    assert cs.recharging(gs)
    gs.turn_number = 9
    cs.record_reload(gs, pk)
    assert not cs.recharging(gs)
    assert "pk_recharging" not in cs.planet_killer(gs).special_rules


def test_crippling_the_planet_killer_wins_and_no_retreat():
    gs = _macharia()
    pk = cs.planet_killer(gs)
    for sd in gs.ships:
        if sd["id"] == pk.id:
            sd.update(status="active", is_disengaged=False)
    assert sc.check_end(gs) is None
    assert sc.disengage_forbidden(gs, cs.planet_killer(gs))
    assert sc.off_table_destroyed(gs, cs.planet_killer(gs))
    for sd in gs.ships:
        if sd["id"] == pk.id:
            sd["hits_remaining"] = sd["hits_remaining"] // 2
    assert sc.check_end(gs)["winner"] == 2
    assert sc.cripple_bonus_vp(gs, pk) > 0


def test_ai_overcharge_needs_the_planet_ahead():
    gs = _macharia()
    pk = cs.planet_killer(gs)
    pl = cs.macharia(gs)
    pk.x, pk.y, pk.heading = pl.x + 60.0, pl.y, 180.0
    assert cs.wants_overcharge(gs, pk)
    pk.heading = 150.0
    assert not cs.wants_overcharge(gs, pk)
    pk.heading, pk.x = 180.0, pl.x + 120.0
    assert not cs.wants_overcharge(gs, pk)


# --- Craftworld Assault -------------------------------------------------------------

from src import craftworld as cw  # noqa: E402
from src import low_orbit as lo  # noqa: E402


def _cw_gs(extra=()):
    att = [make_ship(id="a1", player=1, faction="chaos", points_value=200, x=170, y=60)]
    eld = [make_ship(id=f"e{i}", player=2, faction="eldar", points_value=150 + 10 * i,
                     special_rules=["eldar_mms"]) for i in range(3)]
    gs = _gs(att + eld + list(extra), "craftworld_assault")
    return gs


def test_craftworld_setup_is_iyanden_with_alert_and_patrols():
    gs = _cw_gs()
    gs.scenario_attacker = 2                      # set from the factions: Eldar defend
    dice = DiceStub([2])                          # the one patrol: placed by the attacker
    sc.setup_scenario(gs, dice)
    assert dice._idx == 1 and gs.scenario_attacker == 1
    pl = cw.craftworld(gs)
    assert pl.radius == 12.5 and pl.gravity_well_radius == 32.5
    assert pl.x + pl.radius == gs.table_width - 150.0
    st = gs.scenario_state
    assert st["alert"] == ["e2", "e1"]             # the dearest, until half the points
    assert st["patrol_by_attacker"] == ["e0"]
    assert lo.planet(gs).id == pl.id


def test_craftworld_first_turn_by_d6_plus_attack_rating():
    gs = _cw_gs()
    sc.setup_scenario(gs, DiceStub([6, 6]))
    # attacker (Chaos 2) rolls 3 = 5, defender (Eldar 3) rolls 3 = 6: Eldar choose
    assert sc.roll_for_choice(gs, DiceStub([3, 3])) == 2
    # a tie (4 + 2 = 3 + 3) is re-rolled
    assert sc.roll_for_choice(gs, DiceStub([4, 3, 6, 1])) == 1


def test_fortresses_negate_assault_points():
    gs = _cw_gs()
    sc.setup_scenario(gs, DiceStub([6, 6]))
    # 2 points: rolls 4 (negated) and 3 (kept)
    assert cw.filter_assault_points(gs, 2.0, DiceStub([4, 3])) == 1.0
    gs.scenario_state["fortress_damage"] = 2          # 5+ now
    assert cw.filter_assault_points(gs, 2.0, DiceStub([4, 5])) == 1.0
    gs.scenario_state["fortress_damage"] = 4          # 6+
    assert cw.filter_assault_points(gs, 1.0, DiceStub([5])) == 1.0
    gs.scenario_state["fortress_damage"] = 6          # no cover at all
    assert cw.negate_need(gs) is None and cw.fortresses(gs) == 0
    assert cw.filter_assault_points(gs, 3.0, DiceStub([])) == 3.0


def test_fortress_fire_hits_low_orbit_ships_near_the_planet_edge():
    gs = _cw_gs()
    sc.setup_scenario(gs, DiceStub([6, 6]))
    a = gs.get_ship_by_id("a1")
    a.x, a.y = 60.0, lo.planet_edge_y() - 20.0
    a.special_rules = [lo.FLAG]
    gs.update_ship(a)
    shields, hp = a.shields_max, a.hits_remaining
    # fortress 1: hit, follow-up hit, follow-up miss (2 hits); fortress 2: miss
    dice = DiceStub([4, 5, 2, 1])
    hits = cw.fortress_fire(gs, dice)
    assert hits == 2 and dice._idx == 4
    assert gs.get_ship_by_id("a1").hits_remaining == hp - max(0, 2 - shields)
    # out of reach (more than 45cm from the planet edge): no attack
    a = gs.get_ship_by_id("a1")
    a.y = lo.planet_edge_y() - 50.0
    gs.update_ship(a)
    assert cw.fortress_targets(gs) == []


def test_defence_damage_rolls_in_the_end_phase():
    gs = _cw_gs()
    sc.setup_scenario(gs, DiceStub([6, 6]))
    gs.scenario_state["assault_points"] = 2.0
    cw.end_phase(gs, 1, DiceStub([6, 6, 1, 6]))     # fortresses: two 6s = one damage
    assert gs.scenario_state["fortress_damage"] == 1
    assert gs.scenario_state["spear_damage"] == 1
    cw.end_phase(gs, 2, DiceStub([1, 2, 6, 2]))
    assert gs.scenario_state["fortress_damage"] == 1
    assert gs.scenario_state["spear_damage"] == 2 and not cw.spear_ready(gs)


def test_docking_at_the_forges():
    gs = _cw_gs()
    sc.setup_scenario(gs, DiceStub([6, 6]))
    e = gs.get_ship_by_id("e2")
    e.x, e.y, e.heading = 60.0, lo.planet_edge_y() + 1.0, 90.0
    e.special_rules = list(e.special_rules) + [lo.FLAG, "lo_entered:0"]
    e.hits_remaining = e.hits_max - 2
    gs.update_ship(e)
    gs.turn_number = 4
    assert lo.handle_move_end(gs, gs.get_ship_by_id("e2"))
    e = gs.get_ship_by_id("e2")
    assert cw.docked(e) and not e.is_disengaged
    assert sc.on_standby(gs, e)                     # no moving / shooting / launching
    y = e.y
    lo.falling(gs)
    assert gs.get_ship_by_id("e2").y == y          # docked ships don't fall
    # the forges: +4D6 and a hit back for every 6 with nothing to repair
    from src.end_phase import resolve_damage_control
    n = e.hits_remaining + 4
    resolve_damage_control(e, DiceStub([6, 6, 6] + [1] * (n - 3)), gs)
    assert gs.get_ship_by_id("e2").hits_remaining == e.hits_max
    # undocked at the end of the next Eldar turn, safe until its next move
    gs.turn_number = 6
    cw.end_phase(gs, 2, DiceStub([]))
    e = gs.get_ship_by_id("e2")
    assert not cw.docked(e) and cw.held_in_orbit(e)
    cw.turn_start(gs, 2, DiceStub([]))
    assert not cw.held_in_orbit(gs.get_ship_by_id("e2"))


def test_gates_bring_reserves_from_the_second_eldar_turn():
    gs = _cw_gs()
    gs.scenario_state = {"gate_reserves": ["e0"]}
    sc.setup_scenario(gs, DiceStub([6]))            # one patrol roll (e1)
    assert sc.is_reserve(gs.get_ship_by_id("e0"))
    gs.turn_number = 2
    cw.turn_start(gs, 2, DiceStub([]))              # the first Eldar turn: nothing
    assert sc.is_reserve(gs.get_ship_by_id("e0"))
    gs.turn_number = 4
    cw.turn_start(gs, 2, DiceStub([5, 2]))         # 5+: D3 (1) units
    e = gs.get_ship_by_id("e0")
    pl = cw.craftworld(gs)
    assert not sc.is_reserve(e)
    import math
    assert abs(math.hypot(e.x - pl.x, e.y - pl.y) - (pl.radius + e.base_radius + 0.1)) < 0.5 \
        or e.x <= e.base_radius + 0.01
    assert sc.on_standby(gs, e)                     # can't move or shoot this turn
    gs.turn_number = 6
    assert not sc.on_standby(gs, gs.get_ship_by_id("e0"))


class _Hit:
    """Dice for a direct nova hit: scatter "hit", then 6s (D6 hits = 6, no
    crit rolls needed below 6 matter)."""
    def roll_scatter(self, *a, **k):
        return True

    def roll_scatter_direction(self, *a, **k):
        return 0

    def roll_d6(self, n=1, *a, **k):
        return [6] * n

    def roll_2d6(self, *a, **k):
        return 12


def test_spear_of_light_fires_as_a_nova_cannon():
    gs = _cw_gs()
    sc.setup_scenario(gs, DiceStub([6, 6]))
    pl = cw.craftworld(gs)
    a = gs.get_ship_by_id("a1")
    a.x, a.y = pl.x + pl.radius + 60.0, pl.y
    a.shields_max = 0                    # 2 shields would stop the expected hits
    gs.update_ship(a)
    assert cw.spear_target(gs).id == "a1"
    hp = a.hits_remaining
    res = cw.fire_spear(gs, a, _Hit())
    assert "error" not in res and res["ship_hits"]
    assert gs.get_ship_by_id("a1").hits_remaining < hp


# --- The Gauntlet ---------------------------------------------------------------------

def _gauntlet():
    orks = [make_ship(id=f"o{i}", player=1, faction="orks", ship_type="escort",
                      squadron_id="sq_a" if i < 2 else "sq_b", points_value=40, hits_max=1)
            for i in range(4)]
    convoy = [make_ship(id=f"t{i}", player=2, ship_type="escort", points_value=0,
                        special_rules=["transport:1"], x=20, y=40 + 10 * i) for i in range(3)]
    gs = _gs(orks + convoy, "gauntlet")
    sc.setup_scenario(gs, DiceStub([]))
    return gs


def test_gauntlet_orks_wait_then_move_on_from_the_long_edges():
    gs = _gauntlet()
    assert all(sc.is_reserve(gs.get_ship_by_id(f"o{i}")) for i in range(4))
    assert sc.first_player(gs) == 1
    zone = {z.player: z for z in sc.deployment_zones(gs)}[2]
    assert zone.contains(40, 60) and not zone.contains(50, 60)
    assert sc.auto_heading(gs, 2, 20, 60) == 0.0
    gs.active_player = 1
    sc.turn_start(gs, DiceStub([]))
    orks = [gs.get_ship_by_id(f"o{i}") for i in range(4)]
    assert not any(sc.is_reserve(s) for s in orks)
    tops = [s for s in orks if s.y > 100]
    bottoms = [s for s in orks if s.y < 20]
    assert len(tops) == 2 and len(bottoms) == 2
    assert all(s.heading == 270.0 for s in tops) and all(s.heading == 90.0 for s in bottoms)


def test_gauntlet_needs_three_capacity_out():
    from src import convoy_narrative as cn
    gs = _gauntlet()
    gs.scenario_state["escaped"] = ["t0", "t1"]
    assert cn.winner(gs) == 1 and "Attackers Marginal" in cn.result_text(gs)
    gs.scenario_state["escaped"] = ["t0", "t1", "t2"]
    assert cn.winner(gs) == 2 and "Convoy Marginal" in cn.result_text(gs)
    assert not cn.gauntlet_force_errors(gs)
