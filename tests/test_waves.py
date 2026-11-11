"""Waves of attack craft (core rules s.25; s.23, s.24, s.27 in waves)."""
from tests.conftest import make_gs, make_marker, DiceStub
from src.models import OrdnanceMarker, OrdnanceType
from src.waves import (form_wave, members, is_lead, wave_speed, split_from_wave,
                       whole_wave_ids, ship_attack_plan, tidy_waves)
from src.ordnance import resolve_ordnance_interactions


def craft(mid, otype, player=1, x=10.0, y=10.0, speed=30.0, **kw):
    return make_marker(id=mid, ordnance_type=otype, owner_player=player, x=x, y=y,
                       heading=0.0, speed=speed, strength=1, **kw)


def gs_with(*markers):
    gs = make_gs([])
    for m in markers:
        gs.add_ordnance(m)
    return gs


def ms(gs):
    return [OrdnanceMarker.from_dict(o) for o in gs.ordnance]


def test_form_wave_puts_fighters_ahead_and_stacks_on_the_lead():
    gs = gs_with(craft("b", "bomber", x=5.0, speed=20.0), craft("th", "thunderhawk", x=6.0),
                 craft("f", "fighter", x=7.0))
    wid = form_wave(gs, ["b", "th", "f"], "loose")
    w = members(ms(gs), wid)
    assert [m.id for m in w] == ["f", "th", "b"]          # pure fighters, MR fighters, rest
    assert {(m.x, m.wave_formation) for m in w} == {(7.0, "loose")}
    assert wave_speed(w) == 20.0                           # slowest squadron
    assert is_lead(w[0], w) and not is_lead(w[1], w)
    assert sorted(whole_wave_ids(gs, "b")) == ["b", "f", "th"]


def test_split_off_alone_or_as_a_new_wave():
    gs = gs_with(*(craft(f"f{i}", "fighter") for i in range(4)))
    wid = form_wave(gs, ["f0", "f1", "f2", "f3"], "close")
    new = split_from_wave(gs, ["f2", "f3"])
    assert new and new != wid
    assert [m.id for m in members(ms(gs), new)] == ["f2", "f3"]
    assert members(ms(gs), new)[0].wave_formation == "close"   # same formation
    assert split_from_wave(gs, ["f1"]) == ""
    left = {m.id: m.wave_id for m in ms(gs)}
    assert left["f0"] == "" and left["f1"] == ""              # a wave of one is no wave


def test_fighter_wave_meets_enemy_wave_one_squadron_at_a_time():
    # Two fighters against three enemy bombers: each fighter intercepts one
    # bomber (both removed); the third bomber survives
    gs = gs_with(craft("f1", "fighter"), craft("f2", "fighter"),
                 craft("b1", "bomber", player=2), craft("b2", "bomber", player=2),
                 craft("b3", "bomber", player=2))
    form_wave(gs, ["f1", "f2"])
    form_wave(gs, ["b1", "b2", "b3"])
    dice = DiceStub([])
    resolve_ordnance_interactions(gs, dice)
    assert dice._idx == 0
    assert [m.id for m in ms(gs)] == ["b3"]


def test_resilient_lead_stays_and_meets_the_next_squadron():
    # The s.23 example: two resilient Thunderhawks vs two Swiftdeath fighters
    gs = gs_with(craft("t1", "thunderhawk", resilient_save=4),
                 craft("t2", "thunderhawk", resilient_save=4),
                 craft("s1", "fighter", player=2), craft("s2", "fighter", player=2))
    form_wave(gs, ["t1", "t2"])
    form_wave(gs, ["s1", "s2"])
    rolls = [5]              # t1's save vs s1 passes; vs s2 it can't save again
    dice = DiceStub(rolls)
    resolve_ordnance_interactions(gs, dice)
    assert dice._idx == len(rolls)
    assert [m.id for m in ms(gs)] == ["t2"]


def test_wave_lead_bomber_doesnt_meet_enemy_bombers():
    gs = gs_with(craft("b1", "bomber"), craft("f1", "fighter", player=2))
    gs2 = gs_with(craft("b1", "bomber"), craft("b2", "bomber"),
                  craft("e1", "bomber", player=2))
    form_wave(gs2, ["b1", "b2"])
    resolve_ordnance_interactions(gs2, DiceStub([]))
    assert len(gs2.ordnance) == 3                       # bombers don't interact
    resolve_ordnance_interactions(gs, DiceStub([]))
    assert gs.ordnance == []                            # fighter intercepts bomber


def test_ship_attack_plan_turrets_take_the_front_then_fighters_suppress():
    # s.27 example: 3 fighters + 3 bombers, two squadrons lost to turrets: one
    # fighter left, so one bomber makes exactly 3 attacks
    w = [craft(f"f{i}", "fighter") for i in range(3)] + \
        [craft(f"b{i}", "bomber") for i in range(3)]
    plan = ship_attack_plan(w, 2)
    assert plan["killed"] == ["f0", "f1"]
    assert plan["suppressors"] == 1 and plan["suppressed"] == {"b0"}
    assert [m.id for m in plan["attackers"]] == ["b0", "b1", "b2"]
    assert sorted(plan["removed_after"]) == sorted(m.id for m in w)


def test_fighta_bommerz_dont_suppress():
    w = [craft("fb", OrdnanceType.FIGHTA_BOMMER.value), craft("b", "bomber")]
    plan = ship_attack_plan(w, 0)
    assert plan["suppressors"] == 0 and plan["suppressed"] == set()


def test_tidy_waves_renumbers_and_dissolves():
    gs = gs_with(craft("a", "fighter"), craft("b", "fighter"), craft("c", "bomber"))
    form_wave(gs, ["a", "b", "c"])
    gs.ordnance = [o for o in gs.ordnance if o["id"] != "a"]
    tidy_waves(gs)
    assert [(o["id"], o["wave_order"]) for o in gs.ordnance] == [("b", 0), ("c", 1)]
    gs.ordnance = [o for o in gs.ordnance if o["id"] != "b"]
    tidy_waves(gs)
    assert gs.ordnance[0]["wave_id"] == ""


def test_multi_role_suppress_choice_s27():
    from src.waves import apply_mr_suppress, best_mr_suppress, mr_suppress_candidates
    th = [craft(f"t{i}", "thunderhawk", wave_order=i) for i in range(3)]
    g, sup = apply_mr_suppress(th, 5)
    assert len(sup) == 2                                   # at least one must attack
    assert [m.id for m in g][:2] == list(sup)               # suppressors at the front
    # 4 Thunderhawks vs 4 turrets (2 kills from the front): three suppress, two
    # die, the third gives the last attacker exactly 3 attacks (vs D6-4 = 0.5)
    four = [craft(f"u{i}", "thunderhawk", wave_order=i) for i in range(4)]
    assert best_mr_suppress(four, 4, 0.5, 5) == 3
    # no turrets: suppression gains nothing over D6 attacks each
    assert best_mr_suppress(th, 0, 0.5, 5) == 0
    fb = [craft("f", "fighta_bommer"), craft("b", "bomber")]
    assert mr_suppress_candidates(fb) == []                # Fighta-Bommerz never suppress


def test_suppression_depends_on_turrets_and_wave_size():
    from src.waves import best_mr_suppress
    wave = lambda n: [craft(f"w{i}", "thunderhawk", wave_order=i) for i in range(n)]
    # no turrets: suppressing gains nothing (D6 attacks each beat a fixed 3 on average)
    assert best_mr_suppress(wave(4), 0, 0.5, 5) == 0
    # more turrets -> more worth suppressing, never fewer
    picks = [best_mr_suppress(wave(4), t, 0.5, 5) for t in range(0, 7)]
    assert picks == sorted(picks) and picks[-1] > 0
    # a bigger wave can afford more suppressors against the same turrets
    assert best_mr_suppress(wave(6), 4, 0.5, 5) >= best_mr_suppress(wave(3), 4, 0.5, 5)
    # massed turrets add shots (more kills at the front) but don't reduce attacks
    assert best_mr_suppress(wave(4), 2, 0.5, 5, shots=5) >= 0


def test_best_wave_split():
    from src.waves import best_wave_split
    # no turrets, no CAP: all bombers (D6 each beats a fixed 3 only through suppression)
    assert best_wave_split(4, 0, 0, 0, 5)[0] == 0
    # heavy turrets: fighters in front soak kills and suppress
    f, b, _ = best_wave_split(6, 4, 4, 0, 5)
    assert f >= 1 and b >= 1 and f + b == 6
    # enemy CAP takes squadrons from the front: more fighters ahead pay off
    f_cap, _, _ = best_wave_split(6, 4, 4, 2, 5)
    assert f_cap >= f
    assert best_wave_split(1, 4, 4, 0, 5)[:2] == (0, 1)   # one slot: it must be a bomber


def test_cap_survivors_resilient_rules_s23():
    from src.waves import cap_survivors
    # Plain: each CAP squadron removes the lead squadron (fighters lead)
    assert cap_survivors(1, 2, 2) == {(0, 1): 1.0}
    # Resilient 4+ fighter vs 2 CAP: fail (1/2) -> it and CAP 1 gone, CAP 2 takes a bomber;
    # pass -> CAP 1 gone, CAP 2 meets it again without a save: both gone
    d = cap_survivors(1, 2, 2, f_save=4)
    assert abs(d[(0, 1)] - 0.5) < 1e-9 and abs(d[(0, 2)] - 0.5) < 1e-9
    # Resilient bomber that saves stays in play and still attacks
    d = cap_survivors(0, 1, 1, b_save=4)
    assert abs(d[(0, 1)] - 0.5) < 1e-9 and abs(d[(0, 0)] - 0.5) < 1e-9
    # Both resilient and both pass: both removed
    d = cap_survivors(0, 1, 1, b_save=4, cap_save=4)
    assert abs(d[(0, 1)] - 0.25) < 1e-9


def test_resilience_changes_the_best_split():
    from src.waves import best_wave_split
    # Resilient bombers need no escort against CAP (3 turrets, 2 CAP)
    assert best_wave_split(6, 3, 3, 2, 5)[:2] == (4, 2)
    assert best_wave_split(6, 3, 3, 2, 5, b_save=4)[:2] == (0, 6)
    # Resilient fighters break CAP: fewer needed (4 turrets, 2 CAP) ...
    assert best_wave_split(6, 4, 4, 2, 5)[:2] == (5, 1)
    assert best_wave_split(6, 4, 4, 2, 5, f_save=4)[:2] == (4, 2)
    # ... and worth taking even against 2 turrets
    assert best_wave_split(6, 2, 2, 1, 5)[:2] == (0, 6)
    assert best_wave_split(6, 2, 2, 1, 5, f_save=4)[:2] == (1, 5)
    # A smaller wave than the bays (others launched outside it)
    assert sum(best_wave_split(6, 3, 3, 0, 5)[:2]) == 6


def _ai_launch(turrets, enemy_ord=False):
    from tests.conftest import make_ship, make_gs, DiceStub, make_marker
    from src.ship_catalog import find_ship_class
    from src.models import Ship
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    d = find_ship_class("Emperor Class Battleship").to_ship_dict("Emp", 1, ship_id="emp")
    d.update(x=0.0, y=0.0, heading=0.0, leadership=8)
    emp = Ship.from_dict(d)
    tgt = make_ship(id="t", player=2, x=60.0, y=0.0, turrets=turrets, armor_side="5+",
                    armor_prow="5+")
    gs = make_gs([emp, tgt])
    gs.current_phase = "ordnance"
    if enemy_ord:
        gs.add_ordnance(make_marker(id="torp", ordnance_type="torpedo", owner_player=2,
                                    x=25.0, y=0.0, heading=180.0, speed=30, strength=6))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._launch_ship_ordnance(gs.get_ship_by_id("emp"))
    craft = [o for o in gs.ordnance if o["owner_player"] == 1]
    if enemy_ord:
        return craft
    return [o["ordnance_type"] for o in craft], {o.get("wave_id") for o in craft}


def test_ai_launch_uses_wave_planner():
    from src.waves import best_wave_split
    types, waves = _ai_launch(turrets=4)
    f, b, _ = best_wave_split(8, 4, 4, 0, 5)
    assert types.count("fighter") == f and types.count("bomber") == b and f > 0
    assert len(waves) == 1 and None not in waves
    types, _ = _ai_launch(turrets=1)
    assert types.count("fighter") == 0 and types.count("bomber") == 8
    # A salvo closing on the carrier: one fighter on CAP covers all of it (s.19),
    # the other seven bays strike as one wave (CAP vs strikes, To do 1)
    craft = _ai_launch(turrets=4, enemy_ord=True)
    cap = [o for o in craft if o.get("cap_ship_id") == "emp"]
    wave = [o for o in craft if o.get("wave_id")]
    assert len(cap) == 1 and cap[0]["ordnance_type"] == "fighter" and not cap[0].get("wave_id")
    assert len(wave) == 7 and len({o["wave_id"] for o in wave}) == 1


def _craft(i, kind, save=0, order=0, owner=1):
    from tests.conftest import make_marker
    return make_marker(id=i, ordnance_type=kind, owner_player=owner, resilient_save=save,
                       wave_order=order)


def test_cap_meets_wave_lead_first_plain():
    from tests.conftest import make_gs, DiceStub
    from src.waves import resolve_cap_vs_group
    gs = make_gs([])
    group = [_craft("f1", "fighter", order=0), _craft("b1", "bomber", order=1),
             _craft("b2", "bomber", order=2)]
    caps = [_craft("c1", "fighter", owner=2), _craft("c2", "fighter", owner=2)]
    dice = DiceStub([])
    r = resolve_cap_vs_group(group, caps, dice, gs)
    assert r["removed"] == ["f1", "b1"] and r["cap_removed"] == ["c1", "c2"]
    assert [m.id for m in r["survivors"]] == ["b2"] and dice._idx == 0


def test_cap_vs_resilient_lead_s23():
    from tests.conftest import make_gs, DiceStub
    from src.waves import resolve_cap_vs_group
    gs = make_gs([])
    # Resilient fighter passes vs CAP 1 (CAP 1 gone), stays lead; CAP 2 removes it
    # (no second save) and is removed too; the bomber gets through
    group = [_craft("f1", "fighter", save=4, order=0), _craft("b1", "bomber", order=1)]
    caps = [_craft("c1", "fighter", owner=2), _craft("c2", "fighter", owner=2)]
    rolls = [5]
    dice = DiceStub(rolls)
    r = resolve_cap_vs_group(group, caps, dice, gs)
    assert dice._idx == len(rolls)
    assert r["removed"] == ["f1"] and r["cap_removed"] == ["c1", "c2"]
    assert [m.id for m in r["survivors"]] == ["b1"]


def test_cap_both_resilient_pass_both_removed():
    from tests.conftest import make_gs, DiceStub
    from src.waves import resolve_cap_vs_group
    gs = make_gs([])
    group = [_craft("b1", "bomber", save=4, order=0), _craft("b2", "bomber", order=1)]
    caps = [_craft("c1", "fighter", save=4, owner=2)]
    rolls = [6, 4]          # CAP passes, bomber passes: both removed anyway
    dice = DiceStub(rolls)
    r = resolve_cap_vs_group(group, caps, dice, gs)
    assert dice._idx == len(rolls)
    assert r["removed"] == ["b1"] and r["cap_removed"] == ["c1"]
    assert [m.id for m in r["survivors"]] == ["b2"]


def test_resilient_cap_saves_and_meets_next_lead():
    from tests.conftest import make_gs, DiceStub
    from src.waves import resolve_cap_vs_group
    gs = make_gs([])
    group = [_craft("b1", "bomber", order=0), _craft("b2", "bomber", order=1)]
    caps = [_craft("c1", "fighter", save=4, owner=2)]
    rolls = [5]             # CAP saves vs b1 (b1 gone), then meets b2 without a save
    dice = DiceStub(rolls)
    r = resolve_cap_vs_group(group, caps, dice, gs)
    assert dice._idx == len(rolls)
    assert r["removed"] == ["b1", "b2"] and r["cap_removed"] == ["c1"]
    assert r["survivors"] == []


def test_bombers_vs_assault_boats_owner_example():
    from tests.conftest import make_ship, make_gs
    from src.waves import bomber_squadron_value, raid_squadron_value, best_attack_mode
    from src.ai_hazards import value_per_hit
    W = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 4,
          "arcs": ["left"]},
         {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 4,
          "arcs": ["right"]},
         {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
          "arcs": ["front"]},
         {"name": "Dorsal Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
          "arcs": ["left", "front", "right"]}]
    # 4 turrets, Armour 6+ all round, nothing of ours in reach (armament crits worth 0)
    t = make_ship(id="t", player=2, turrets=4, armor_prow="6+", armor_side="6+",
                  points_value=200, weapons=W)
    gs = make_gs([t])
    gs.rule_hit_and_run = True
    vph = value_per_hit(t, gs)
    assert abs(bomber_squadron_value(t, gs) - 0.5 * (1 / 6) * vph) < 1e-9     # 0.083 hits
    assert abs(raid_squadron_value(t, gs, 1) - vph / 6) < 1e-9               # Engine Room
    assert best_attack_mode(t, gs, 1) == "assault_boat"


def test_bombers_beat_assault_boats_against_escorts():
    from tests.conftest import make_ship, make_gs
    from src.waves import bomber_squadron_value, raid_squadron_value, best_attack_mode
    esc = make_ship(id="e", player=2, ship_type="escort", hits_max=1, turrets=1,
                    armor_prow="5+", armor_side="5+", points_value=40)
    gs = make_gs([esc])
    gs.rule_hit_and_run = True
    assert abs(raid_squadron_value(esc, gs, 1) - 0.5 * 40) < 1e-9       # 4+: destroyed
    assert bomber_squadron_value(esc, gs) > raid_squadron_value(esc, gs, 1)
    assert best_attack_mode(esc, gs, 1) == "bomber"


def _carrier_launch(turrets, armour, x=60.0):
    from tests.conftest import make_ship, make_gs, DiceStub
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    bay = {"name": "Port Launch Bays", "weapon_type": "launch_bay", "range_cm": 30,
           "strength": 4, "arcs": [],
           "craft_types": ["fury_fighter", "starhawk_bomber", "shark_assault_boat"],
           "craft_speeds": {"fury_fighter": 30, "starhawk_bomber": 20, "shark_assault_boat": 30}}
    c = make_ship(id="c", player=1, weapons=[bay], points_value=250)
    W = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 4,
          "arcs": ["left"]},
         {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
          "arcs": ["front"]}]
    t = make_ship(id="t", player=2, x=x, heading=180.0, turrets=turrets, armor_prow=armour,
                  armor_side=armour, points_value=200, weapons=W)
    gs = make_gs([c, t])
    gs.rule_hit_and_run = True
    gs.current_phase = "ordnance"
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._launch_ship_ordnance(gs.get_ship_by_id("c"))
    return sorted(o["ordnance_type"] for o in gs.ordnance if o["owner_player"] == 1)


def test_ai_carrier_picks_assault_boats_vs_armoured_target():
    # Its prow lance bears on our carrier: raid crits are worth something
    assert set(_carrier_launch(4, "6+", x=25.0)) == {"assault_boat"}
    assert "bomber" in _carrier_launch(1, "4+", x=25.0)
    # Owner's example with turret suppression counted, crits threatening nothing:
    # 3 fighters + 1 suppressed bomber (~0.36 hits) edge out 4 boats (~0.33)
    assert "bomber" in _carrier_launch(4, "6+")



def test_ai_many_threats_go_to_cap():
    """Several mines / salvos closing in: fighters before bombers."""
    from tests.conftest import make_ship, make_gs, DiceStub, make_marker
    from src.ship_catalog import find_ship_class
    from src.models import Ship
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    d = find_ship_class("Dictator Class Cruiser").to_ship_dict("D", 1, ship_id="d")
    d.update(x=0.0, y=0.0, heading=0.0, leadership=8)
    gs = make_gs([Ship.from_dict(d),
                  make_ship(id="t", player=2, x=80.0, turrets=4, points_value=150)])
    gs.current_phase = "ordnance"
    for i in range(4):
        gs.add_ordnance(make_marker(id=f"m{i}", ordnance_type="torpedo", owner_player=2,
                                    x=20.0 + 3 * i, y=0.0, heading=180.0, speed=30,
                                    strength=6))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._launch_ship_ordnance(gs.get_ship_by_id("d"))
    craft = [o for o in gs.ordnance if o["owner_player"] == 1
             and "torpedo" not in o["ordnance_type"]]     # its own prow torpedoes too
    assert len(craft) == 4 and all(o["ordnance_type"] == "fighter" for o in craft)
    assert all(o.get("cap_ship_id") == "d" for o in craft)
