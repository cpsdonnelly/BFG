"""Strikes valued when they land (To do 2, HANDOFF "Ordnance strike planning"):
arrival phase, which turn the wave lands in (the raid's repair window), enemy
guns on the way (one 6 removes the whole wave, s.25 / s.30) and reactive CAP."""
from tests.conftest import make_ship, make_gs
from src.ai_hazards import strike_timeline

GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
         "arcs": ["right"]}]


def test_arrival_phase_and_landing_turn():
    t = make_ship(id="t", player=2, x=25.0, y=0.0, heading=90.0, speed=0)
    gs = make_gs([t])
    now = strike_timeline(0.0, 0.0, 30.0, t, gs, 1)
    assert now["phase"] == 0 and now["end_phases"] == 1      # lands in our own phase
    far = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0)
    later = strike_timeline(0.0, 0.0, 30.0, far, make_gs([far]), 1)
    assert later["phase"] == 1 and later["end_phases"] == 2  # in the enemy's phase,
    #                                                          after it has fired
    assert strike_timeline(0.0, 0.0, 30.0, far, make_gs([far]), 1, max_phases=1) is None


def test_enemy_guns_on_the_way_cost_survival():
    """A wave waiting where an enemy broadside reaches it in the enemy's
    shooting phase may lose everything to one 6."""
    t = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0)
    gunship = make_ship(id="g", player=2, x=30.0, y=20.0, heading=0.0, speed=0,
                        weapons=[dict(w) for w in GUNS])
    safe = strike_timeline(0.0, 0.0, 30.0, t, make_gs([t]), 1)
    risky = strike_timeline(0.0, 0.0, 30.0, t, make_gs([t, gunship]), 1)
    assert safe["survival"] == 1.0 and 0.0 < risky["survival"] < 1.0


def test_reactive_cap_from_a_loaded_target_carrier():
    bay = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 2,
           "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"],
           "craft_speeds": {"fury_fighter": 30, "starhawk_bomber": 20}}
    t = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0, weapons=[bay])
    assert strike_timeline(0.0, 0.0, 30.0, t, make_gs([t]), 1)["reactive_cap"] == 2
    t.ordnance_loaded_craft = False
    assert strike_timeline(0.0, 0.0, 30.0, t, make_gs([t]), 1)["reactive_cap"] == 0
    # landing in our own phase, before the enemy has an ordnance phase: no reaction
    near = make_ship(id="t", player=2, x=25.0, y=0.0, heading=90.0, speed=0, weapons=[bay])
    assert strike_timeline(0.0, 0.0, 30.0, near, make_gs([near]), 1)["reactive_cap"] == 0


def test_reactive_intercept_from_another_carrier():
    """Owner: reactive intercept is a strategy too. A loaded enemy carrier
    whose fighters can reach our waiting wave in its ordnance phase launches
    them at it; out of reach, or unloaded, it can't."""
    bay = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 3,
           "arcs": [], "craft_types": ["fury_fighter"], "craft_speeds": {"fury_fighter": 30}}
    t = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0)
    carrier = make_ship(id="cv", player=2, x=35.0, y=25.0, heading=90.0, speed=0,
                        weapons=[bay])
    tl = strike_timeline(0.0, 0.0, 30.0, t, make_gs([t, carrier]), 1)
    assert tl["phase"] == 1 and tl["reactive_intercept"] == 3 and tl["reactive_cap"] == 0
    far = make_ship(id="cv", player=2, x=40.0, y=120.0, heading=90.0, speed=0, weapons=[bay])
    assert strike_timeline(0.0, 0.0, 30.0, t, make_gs([t, far]), 1)["reactive_intercept"] == 0
    carrier.ordnance_loaded_craft = False
    assert strike_timeline(0.0, 0.0, 30.0, t, make_gs([t, carrier]), 1)["reactive_intercept"] == 0
    # landing in our own phase, before any enemy ordnance phase: no interception
    near = make_ship(id="t", player=2, x=25.0, y=0.0, heading=90.0, speed=0)
    cv2 = make_ship(id="cv", player=2, x=20.0, y=20.0, heading=90.0, speed=0, weapons=[bay])
    assert strike_timeline(0.0, 0.0, 30.0, near, make_gs([near, cv2]), 1)["reactive_intercept"] == 0


def test_split_wave_survival_spreads_the_guns():
    """One hit removes a whole wave (s.25) but each weapon fires at one marker:
    two waves share the shots out, so each survives better than one wave."""
    from src.ai_hazards import split_wave_survival, ENEMY_FIRE_AT_WAVE
    one, = split_wave_survival([4.0, 4.0], 1)
    a, b = split_wave_survival([4.0, 4.0], 2)
    assert abs(one - (5 / 6) ** (8 * ENEMY_FIRE_AT_WAVE)) < 1e-9
    assert a == b and a > one
    assert split_wave_survival([], 2) == [1.0, 1.0]


def _split_scene(guns, turrets, side=None):
    from tests.conftest import DiceStub
    from src.models import Ship
    from src.ship_catalog import find_ship_class
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    d = find_ship_class("Emperor Class Battleship").to_ship_dict("Emp", 1, ship_id="emp")
    d.update(x=0.0, y=0.0, heading=0.0, leadership=8)
    t = make_ship(id="t", player=2, x=55.0, y=0.0, heading=90.0, speed=0, turrets=turrets,
                  armor_prow="5+", armor_side="5+", points_value=180)
    ships = [Ship.from_dict(d), t]
    for i, (x, y, h) in enumerate([(30.0, 15.0, 0.0), (30.0, -15.0, 180.0)][:guns]):
        ships.append(make_ship(id=f"g{i}", player=2, x=x, y=y, heading=h, speed=0,
                               weapons=[dict(w) for w in GUNS]))
    if side:          # a destroyed ship puts player 1 ahead or behind
        ships.append(make_ship(id="dead", player=2 if side == "ahead" else 1, x=300.0,
                               y=300.0, points_value=200, hits_remaining=0, status="destroyed"))
    gs = make_gs(ships)
    if side:
        gs.turn_limit, gs.turn_number = 3, 3
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    s = gs.get_ship_by_id("emp")
    cts = [c for w in s.weapons if w.get("weapon_type") == "launch_bay"
           for c in w.get("craft_types", [])]
    return ai, ai._strike_option(s, cts, 8, [gs.get_ship_by_id("t")])


def test_strike_splits_into_two_waves_under_enemy_guns():
    """To do 2: a strike that must wait under enemy guns splits into two waves
    when the target's turrets are weak (the guns can only remove one wave per
    weapon); with no guns on the way, or against strong turrets (each wave
    faces them alone and suppresses alone), it stays one wave."""
    _ai, opt = _split_scene(guns=0, turrets=1)
    assert "two waves" not in opt[2]
    ai, opt = _split_scene(guns=2, turrets=1)
    assert opt[2].endswith("in two waves")
    _ai, opt4 = _split_scene(guns=2, turrets=4)
    assert "two waves" not in opt4[2]
    # The launch forms the two waves: each craft type shared out
    from tests.conftest import make_marker
    ai._strike_target = ("t", 0.0)
    plan = opt[1]
    ms = [make_marker(id=f"m{i}", ordnance_type="bomber") for i in range(8)]
    groups = ai._wave_groups(ms, plan)
    assert [len(g) for g in groups] == [4, 4]


def test_strike_value_follows_the_risk_preference():
    """To do 2: a strike under enemy guns is a gamble (it gets through or it
    doesn't); on the last turn it is worth more to the side behind and less to
    the side ahead than its expected value."""
    even = _split_scene(guns=2, turrets=4)[1][0]
    ahead = _split_scene(guns=2, turrets=4, side="ahead")[1][0]
    behind = _split_scene(guns=2, turrets=4, side="behind")[1][0]
    assert ahead < even < behind
