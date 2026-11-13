"""Ordnance focus by expected VP (owner: focusing on easier targets should be
optimal; CLAUDE.md To do 1)."""
from tests.conftest import make_ship, make_gs, DiceStub, make_marker
from src.ai_hazards import plan_strike_targets, torpedo_salvo_hits

TORP = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30, "strength": 6,
        "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}


def _hard(i, x, y):
    return make_ship(id=i, player=2, x=x, y=y, turrets=4, armor_prow="6+", armor_side="6+",
                     points_value=200)


def _easy(i, x, y, hits=3):
    return make_ship(id=i, player=2, x=x, y=y, turrets=1, armor_prow="4+", armor_side="4+",
                     points_value=200, hits_remaining=hits)


def test_torpedo_salvo_hits_ignore_shields_count_turrets():
    hard = _hard("h", 30.0, 0.0)
    gs = make_gs([hard])
    # 6 torps, 4 turret dice on 4+ (2 down), 4 left hitting 6+
    assert abs(torpedo_salvo_hits(6, hard, gs, (0.0, 0.0)) - 4 / 6) < 1e-9


def test_ai_torpedoes_go_for_the_easier_target():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    me = make_ship(id="me", player=1, x=0.0, y=0.0, weapons=[dict(TORP)])
    gs = make_gs([me, _hard("h", 30.0, 3.0), _easy("e", 32.0, -3.0)])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    t = ai._best_torp_target(gs.get_ship_by_id("me"), TORP, ai._live_enemies())
    assert t.id == "e" and ai._ord_committed["e"] > 0


def test_strike_waves_focus_then_move_on():
    from src.waves import form_wave
    mid = make_ship(id="h", player=2, x=40.0, y=0.0, turrets=2, armor_prow="5+",
                    armor_side="5+", points_value=200)
    gs = make_gs([mid, _easy("e", 40.0, 20.0, hits=1)])
    for i in range(3):
        gs.add_ordnance(make_marker(id=f"a{i}", ordnance_type="bomber", owner_player=1,
                                    x=10.0, y=10.0, speed=20))
    form_wave(gs, ["a0", "a1", "a2"], "close")
    for i in range(3):
        gs.add_ordnance(make_marker(id=f"b{i}", ordnance_type="bomber", owner_player=1,
                                    x=10.0, y=12.0, speed=20))
    form_wave(gs, ["b0", "b1", "b2"], "close")
    plan = plan_strike_targets(gs, 1)
    # The wave (biggest group first) takes the 1-hit easy ship; the second wave,
    # with that ship likely dead, goes for the other. (Against a really hard
    # target, 4 turrets / 6+, it would add so little that topping up the easy
    # kill stays better: focus on easier targets, owner.)
    first, second = ("a", "b") if plan["a0"] == "e" else ("b", "a")
    assert all(plan[f"{first}{i}"] == "e" for i in range(3))
    assert all(plan[f"{second}{i}"] == "h" for i in range(3))


GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["right"]},
        {"name": "Prow Lances", "weapon_type": "lance", "range_cm": 30, "strength": 2,
         "arcs": ["front"]}]


def _fleet():
    ours = [make_ship(id=f"o{i}", player=1, x=0.0, y=10.0 * i, weapons=[dict(w) for w in GUNS],
                      points_value=180) for i in range(2)]
    hard = make_ship(id="hard", player=2, x=35.0, y=0.0, heading=180.0, turrets=3,
                     armor_prow="6+", armor_side="6+", shields_max=2, points_value=200,
                     weapons=[dict(w) for w in GUNS])
    soft = make_ship(id="soft", player=2, x=45.0, y=25.0, heading=180.0, armor_prow="4+",
                     armor_side="4+", shields_max=1, hits_remaining=3, points_value=200,
                     weapons=[dict(w) for w in GUNS])
    return make_gs(ours + [hard, soft])


def test_fleet_focus_prefers_the_easier_damaged_ship():
    from src.ai_hazards import fleet_focus_targets
    ranked = fleet_focus_targets(_fleet(), 1)
    assert ranked[0][1].id == "soft"


def test_movement_closes_on_the_focus_target():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    gs = _fleet()
    gs.current_phase = "movement"
    dice = DiceStub([1] * 40)
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._focus = "soft"
    o0 = gs.get_ship_by_id("o0")
    assert ai._focus_for(o0).id == "soft"          # nearer "hard" is not the plan target
    ai._focus = "missing"
    assert ai._focus_for(o0) is None
    ai.run_movement_phase()
    assert any("fleet focus: Test Ship" in line for line in gs.log)


def test_exposure_is_higher_in_the_enemy_arcs_than_behind():
    from src.ai_hazards import position_exposure_hits
    gs = _fleet()
    me = gs.get_ship_by_id("o0")
    me.armor_prow = me.armor_side         # same Armour all round: arcs only here
    gs.update_ship(me)
    beside = position_exposure_hits(me, 35.0, 15.0, 0.0, gs)    # off "hard"'s port side
    behind = position_exposure_hits(me, 60.0, 0.0, 0.0, gs)     # astern of both, far
    assert beside > behind


def test_exposure_respects_our_armour_facing():
    """To do 8 a: the enemy's guns hit the Armour facing they see at our end
    heading. Ending prow-on to an enemy broadside (6+ prow) is safer than
    showing it a 5+ side; lances hit on 4+ whatever the Armour."""
    from src.ai_hazards import position_exposure_hits, mount_hits
    me = make_ship(id="me", player=1, x=0.0, y=0.0, armor_prow="6+", armor_side="5+",
                   shields_max=0)
    foe = make_ship(id="foe", player=2, x=20.0, y=0.0, heading=90.0, shields_max=0,
                    weapons=[dict(w) for w in GUNS[:2]])          # broadsides only
    gs = make_gs([me, foe])
    prow_on = position_exposure_hits(me, 0.0, 0.0, 0.0, gs)       # pointing at it
    side_on = position_exposure_hits(me, 0.0, 0.0, 90.0, gs)      # showing a side
    assert 0 < prow_on < side_on
    assert abs(prow_on / side_on - 0.5) < 1e-9                   # 1/6 vs 2/6 to hit
    lance = {"name": "Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
             "arcs": ["left", "right", "front"]}
    assert mount_hits(foe, lance, me) == 1.0


def test_escort_screens_the_flagship_against_incoming_ordnance():
    """An escort ending in base contact with the commander's ship adds a massed
    turret (s.29) while enemy ordnance can reach it."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    from tests.conftest import make_marker
    flag = make_ship(id="f", player=1, x=0.0, y=0.0, is_flagship=True, points_value=250,
                     rerolls_remaining=1)
    esc = make_ship(id="e", player=1, x=0.0, y=-20.0, ship_type="escort", hits_max=1,
                    turrets=1, points_value=40)
    foe = make_ship(id="x", player=2, x=60.0, y=0.0)
    gs = make_gs([flag, esc, foe])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    touching = (0.0, -(flag.base_radius + esc.base_radius))
    assert ai._screen_bonus(esc, *touching, 90.0, foe) == 0.0       # nothing incoming
    # Owner: only torpedoes, bombers, assault boats (and mines) are worth massing against
    gs.add_ordnance(make_marker(id="ftr", ordnance_type="fighter", owner_player=2, x=20.0,
                                y=0.0, speed=30))
    assert ai._screen_bonus(esc, *touching, 90.0, foe) == 0.0       # fighters only
    gs.add_ordnance(make_marker(id="bmb", ordnance_type="bomber", owner_player=2, x=25.0,
                                y=5.0, speed=20))
    assert ai._screen_bonus(esc, *touching, 90.0, foe) > 0.0        # a bomber wave coming
    gs.ordnance = [o for o in gs.ordnance if o["id"] != "bmb"]
    gs.add_ordnance(make_marker(id="tb", ordnance_type="torpedo_bomber", owner_player=2,
                                x=25.0, y=5.0, speed=20))
    assert ai._screen_bonus(esc, *touching, 90.0, foe) > 0.0        # torpedo bombers too
    gs.ordnance = [o for o in gs.ordnance if o["id"] != "tb"]
    gs.add_ordnance(make_marker(id="t", ordnance_type="torpedo", owner_player=2, x=30.0,
                                y=0.0, heading=180.0, speed=30, strength=6))
    assert ai._screen_bonus(esc, *touching, 90.0, foe) > 0.0
    assert ai._screen_bonus(esc, 0.0, -20.0, 90.0, foe) == 0.0       # not in contact


def test_several_focus_targets_split_once_a_kill_is_covered():
    """Owner: focus fire, but no overkill. Two ships are plenty to finish the
    1-hit enemy; the rest go to the second target, all within reach."""
    from src.ai_hazards import fleet_focus_assignment
    ours = [make_ship(id=f"o{i}", player=1, x=0.0, y=10.0 * i, heading=0.0, speed=20,
                      weapons=[dict(w) for w in GUNS]) for i in range(4)]
    dying = make_ship(id="dying", player=2, x=40.0, y=10.0, armor_prow="5+", armor_side="5+",
                      shields_max=1, hits_remaining=1, points_value=200)
    fresh = make_ship(id="fresh", player=2, x=40.0, y=25.0, armor_prow="5+", armor_side="5+",
                      shields_max=1, points_value=200)
    gs = make_gs(ours + [dying, fresh])
    plan = fleet_focus_assignment(gs, 1)
    assert set(plan) == {s.id for s in ours}
    on = {t: sum(1 for v in plan.values() if v == t) for t in ("dying", "fresh")}
    assert on["dying"] >= 1 and on["fresh"] >= 1
    # A ship out of every enemy's reach gets no focus (plans against its nearest)
    far = make_ship(id="far", player=1, x=-300.0, y=0.0, weapons=[dict(w) for w in GUNS])
    gs2 = make_gs(ours + [far, dying, fresh])
    assert "far" not in fleet_focus_assignment(gs2, 1)


def test_batteries_fire_before_lances(tmp_path):
    """To do 11 d: shield hits leave blast markers that shift later batteries,
    never lances, so a ship fires its batteries first."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    from src.dice import DiceRoller
    L = {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
         "arcs": ["front"]}
    B = {"name": "Prow Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["front"]}
    s = make_ship(id="s", player=1, x=0.0, y=0.0, heading=0.0, weapons=[L, B], points_value=100)
    t = make_ship(id="t", player=2, x=20.0, y=0.0, points_value=200, shields_max=2, hits_max=8)
    gs = make_gs([s, t])
    d = DiceRoller(mode="auto")
    ai = AIPlayer(1, TurnController(gs, d, save_dir=str(tmp_path)), gs, d)
    ai.difficulty = "normal"
    order = []
    real = ai._offer_brace

    def spy(ship, target, weapons=None, expected=None):
        order.extend(w["name"] for w in (weapons or []))
        return real(ship, target, weapons, expected)
    ai._offer_brace = spy
    ai.run_shooting_phase()
    assert order[:2] == ["Prow Battery", "Prow Lance"], order
