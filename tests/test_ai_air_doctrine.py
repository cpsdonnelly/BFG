"""Owner: carrier doctrine. With more launch capacity than the enemy, the AI
should prioritise taking down the enemy's carriers (air supremacy); with less,
it should protect its carriers and fly more interception."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.models import Ship
from src.ai_hazards import bay_threat_vp, added_vp, air_balance

GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["right"]}]


def _carrier(sid, player, x, y=0.0, heading=0.0):
    d = find_ship_class("Dictator Class Cruiser").to_ship_dict(sid, player, ship_id=sid)
    d.update(x=x, y=y, heading=heading, leadership=8)
    return Ship.from_dict(d)


def _gun_cruiser(sid, player, x, y=0.0, pts=None):
    return make_ship(id=sid, player=player, x=x, y=y, heading=180.0, weapons=[dict(w) for w in GUNS],
                     points_value=pts or 220, hits_max=8, armor_prow="5+", armor_side="5+")


def test_enemy_carrier_worth_more_to_kill_the_more_we_launch():
    """Its fighters deny our strikes (one squadron each, up to our capacity), so
    killing it is worth more to a carrier-heavy fleet."""
    enemy_cv = _carrier("ecv", 2, 40.0, heading=180.0)
    gun_only = [_gun_cruiser("g1", 1, 0.0)]
    carriers = [_carrier(f"c{i}", 1, 0.0, 10.0 * i) for i in range(2)]   # 8 squadrons
    gs_guns = make_gs(gun_only + [enemy_cv])
    gs_cv = make_gs(carriers + [enemy_cv])
    assert air_balance(gs_cv, 1) == (8, 4)
    assert bay_threat_vp(enemy_cv, gs_cv) > bay_threat_vp(enemy_cv, gs_guns) > 0
    assert bay_threat_vp(_gun_cruiser("x", 2, 40.0), gs_cv) == 0.0


def test_air_supremacy_puts_guns_on_the_enemy_carrier():
    """Two enemies of equal points and toughness, one a carrier: our carrier-heavy
    fleet values hits on the carrier more (damage_vp counts the threat removed)."""
    enemy_cv = _carrier("ecv", 2, 40.0, heading=180.0)
    twin = _gun_cruiser("eg", 2, 40.0, 20.0, pts=enemy_cv.points_value)
    twin = Ship.from_dict({**twin.to_dict(), "hits_max": enemy_cv.hits_max,
                           "hits_remaining": enemy_cv.hits_remaining,
                           "shields_max": enemy_cv.shields_max,
                           "armor_prow": enemy_cv.armor_prow, "armor_side": enemy_cv.armor_side,
                           "armor_rear": enemy_cv.armor_rear, "weapons": []})
    gs = make_gs([_carrier("c0", 1, 0.0), _carrier("c1", 1, 0.0, 10.0), enemy_cv, twin])
    hits = enemy_cv.hits_max          # enough to kill either
    assert added_vp(enemy_cv, gs, 0.0, hits) > added_vp(twin, gs, 0.0, hits)


def test_out_carriered_the_ai_protects_its_carrier_and_flies_more_cap():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    mine = _carrier("c0", 1, 0.0)
    rivals = [_carrier(f"e{i}", 2, 45.0, 15.0 * i, heading=180.0) for i in range(3)]
    gs_weak = make_gs([mine] + rivals)             # 4 vs 12 squadrons
    gs_even = make_gs([mine, rivals[0]])           # 4 vs 4
    tgt = rivals[0]

    def ai_for(gs):
        dice = DiceStub([])
        a = AIPlayer(1, TurnController(gs, dice), gs, dice)
        a.difficulty = "normal"
        return a
    weak, even = ai_for(gs_weak), ai_for(gs_even)
    assert weak._anticipated_weight() > even._anticipated_weight()
    inside = weak._carrier_exposure(mine, 10.0, 0.0, tgt)
    outside = weak._carrier_exposure(mine, -80.0, 0.0, tgt)
    assert inside > even._carrier_exposure(mine, 10.0, 0.0, tgt) > 0 and outside == 0.0
    # gun ships carry no carrier-protection term
    assert weak._carrier_exposure(_gun_cruiser("g", 1, 0.0), 10.0, 0.0, tgt) == 0.0


def _umbrella_case(airborne=False):
    from tests.conftest import make_marker
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    d = find_ship_class("Emperor Class Battleship").to_ship_dict("Emp", 1, ship_id="emp")
    d.update(x=0.0, y=0.0, heading=0.0, leadership=8)
    emp = Ship.from_dict(d)
    covered = make_ship(id="covered", player=2, x=50.0, y=20.0, heading=90.0, speed=0,
                        turrets=2, armor_prow="5+", armor_side="5+", points_value=180)
    open_ = make_ship(id="open", player=2, x=50.0, y=-20.0, heading=90.0, speed=0,
                      turrets=2, armor_prow="5+", armor_side="5+", points_value=180)
    ships = [emp, covered, open_]
    if not airborne:
        fbay = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30,
                "strength": 6, "arcs": [], "craft_types": ["fury_fighter"],
                "craft_speeds": {"fury_fighter": 30}}
        ships.append(make_ship(id="cv", player=2, x=40.0, y=25.0, heading=90.0, speed=0,
                               weapons=[fbay], points_value=150))
    gs = make_gs(ships)
    if airborne:
        for i in range(6):
            gs.add_ordnance(make_marker(id=f"f{i}", ordnance_type="fighter", owner_player=2,
                                        x=40.0, y=55.0, speed=30))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    s = gs.get_ship_by_id("emp")
    cts = [c for w in s.weapons if w.get("weapon_type") == "launch_bay"
           for c in w.get("craft_types", [])]
    foes = [gs.get_ship_by_id("covered"), gs.get_ship_by_id("open")]
    vals = {t.id: ai._strike_option(s, cts, 8, [t])[0] for t in foes}
    return ai._strike_option(s, cts, 8, foes), vals


def test_strike_outside_the_enemy_carriers_umbrella():
    """Owner: a fleet with less launch capacity can still neuter one with more
    (6 interceptors cut a wave of 8 to 2, and turrets take more): enemy carriers
    threaten our strikes, so strike targets outside their fighters' reach."""
    for airborne in (False, True):
        best, vals = _umbrella_case(airborne)
        assert best[3].id == "open"
        assert vals["covered"] < 0.75 * vals["open"]


def _turret_target(sid="t", y=0.0, ork=False):
    rules = ["ork_turrets"] if ork else []
    return make_ship(id=sid, player=2, x=25.0, y=y, heading=90.0, speed=0, turrets=4,
                     armor_prow="5+", armor_side="5+", points_value=180, special_rules=rules)


def test_turret_split_gain():
    """s.28 (owner): turrets fire at craft or at torpedoes in a phase, not both,
    so a salvo and a bomber wave arriving together gain the smaller of the two
    turret savings; Ork turrets fire at everything, so no gain."""
    from src.ai_hazards import turret_split_gain
    t = _turret_target()
    gs = make_gs([t])
    gain = turret_split_gain(t, gs, 5, 2, 2)
    assert gain > 0
    assert turret_split_gain(_turret_target(ork=True), make_gs([_turret_target(ork=True)]),
                             5, 2, 2) == 0.0
    assert turret_split_gain(t, gs, 5, 2, 0) == 0.0          # no bombers, nothing to split


def test_missiles_join_the_bomber_wave():
    """Owner: co-ordinate bombers and missiles (e.g. a Tau Protector fleet). With a
    bomber wave due at one of two equal targets this phase, the missiles go for
    the same one; against Ork turrets the wave gives them no reason to."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    tau_w = {"name": "Gravitic Launcher", "weapon_type": "torpedo", "range_cm": 30,
             "strength": 5, "arcs": ["front"], "torpedo_type": "guided", "torpedo_speed": 30}
    for ork in (False, True):
        me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(tau_w)])
        a, b = _turret_target("a", 4.0, ork), _turret_target("b", -4.0, ork)
        gs = make_gs([me, b, a])          # on a tie the first listed ("b") would win
        dice = DiceStub([])
        ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
        ai.difficulty = "normal"
        ai._ord_committed = {}
        ai._ord_arrivals = {"a": {"craft": [(0, 2, 2, 0, 0)]}}
        plan_a = ai._approach_for_launch(gs.get_ship_by_id("me"), tau_w, gs.get_ship_by_id("a"))
        plan_b = ai._approach_for_launch(gs.get_ship_by_id("me"), tau_w, gs.get_ship_by_id("b"))
        assert plan_a["phase"] == plan_b["phase"] == 0
        assert abs(plan_a["value"] - plan_b["value"]) < 1e-6            # equal on their own
        pick = ai._best_torp_target(gs.get_ship_by_id("me"), tau_w, ai._live_enemies())
        if not ork:
            assert pick.id == "a"
            ai._ord_committed = {}
            ai._craft_due = lambda t: []            # without the split bonus: the tie
            assert ai._best_torp_target(gs.get_ship_by_id("me"), tau_w,
                                        ai._live_enemies()).id == "b"
        ai._ord_arrivals = {}
        ai._ord_committed = {}
        if ork:
            # Orks: the wave makes no difference to the missiles' value
            from src.ai_hazards import turret_split_gain
            assert turret_split_gain(gs.get_ship_by_id("a"), gs, 5, 2, 2) == 0.0


def test_bombers_join_the_missiles():
    """The other way round: with missiles launched this phase at one of two
    equal targets, the carrier's wave is worth more against the same one."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    bay = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 4,
           "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"],
           "craft_speeds": {"fury_fighter": 30, "starhawk_bomber": 20}}
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[bay])
    a = make_ship(id="a", player=2, x=15.0, y=4.0, heading=90.0, speed=0, turrets=4,
                  armor_prow="5+", armor_side="5+", points_value=180)
    b = make_ship(id="b", player=2, x=15.0, y=-4.0, heading=90.0, speed=0, turrets=4,
                  armor_prow="5+", armor_side="5+", points_value=180)
    gs = make_gs([me, a, b])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    cts = bay["craft_types"]
    s = gs.get_ship_by_id("me")
    alone = {t: ai._strike_option(s, cts, 4, [gs.get_ship_by_id(t)])[0] for t in ("a", "b")}
    ai._ord_arrivals = {"a": {"torps": [(0, 5, (0.0, 0.0))]}}
    joined = {t: ai._strike_option(s, cts, 4, [gs.get_ship_by_id(t)])[0] for t in ("a", "b")}
    assert abs(alone["a"] - alone["b"]) < 1e-6
    assert joined["a"] > joined["b"] == alone["b"]


def test_wave_in_flight_avoids_the_enemy_umbrella():
    """Craft already flying are re-targeted with the same interception cases
    as planned strikes (ai_hazards.interception_cases): reactive CAP from the
    target, other carriers' launches and fighters already flying. A bomber wave
    in flight between two equal targets goes for the one outside a loaded
    enemy carrier's fighter reach."""
    from tests.conftest import make_marker
    from src.ai_hazards import plan_strike_targets
    covered = make_ship(id="covered", player=2, x=50.0, y=20.0, heading=90.0, speed=0,
                        turrets=2, armor_prow="5+", armor_side="5+", points_value=180)
    open_ = make_ship(id="open", player=2, x=50.0, y=-20.0, heading=90.0, speed=0,
                      turrets=2, armor_prow="5+", armor_side="5+", points_value=180)
    me = make_ship(id="me", player=1, x=-60.0, y=0.0, heading=0.0, speed=0)
    fbay = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30,
            "strength": 6, "arcs": [], "craft_types": ["fury_fighter"],
            "craft_speeds": {"fury_fighter": 30}}
    cv = make_ship(id="cv", player=2, x=40.0, y=25.0, heading=90.0, speed=0,
                   weapons=[fbay], points_value=150)
    for with_carrier, expect in ((False, None), (True, "open")):
        gs = make_gs([me, covered, open_] + ([cv] if with_carrier else []))
        for i in range(4):
            gs.add_ordnance(make_marker(id=f"b{i}", ordnance_type="bomber", owner_player=1,
                                        x=0.0, y=0.0, speed=20, wave_id="w1"))
        plan = plan_strike_targets(gs, 1)
        assert set(plan) == {"b0", "b1", "b2", "b3"}
        if expect:
            assert set(plan.values()) == {expect}
