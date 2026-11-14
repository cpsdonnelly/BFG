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
