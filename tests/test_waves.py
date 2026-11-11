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
