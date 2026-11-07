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
