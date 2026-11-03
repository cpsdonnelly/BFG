"""Owner ruling: a hulk that takes at least one point of damage rolls on the
Catastrophic Damage table again. Standard torpedoes attack hulks (s.16)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import apply_damage
from src.models import OrdnanceMarker, OrdnanceType
from src.ordnance import resolve_torpedo_attack, torpedo_valid_target


def _hulk(status="drifting_hulk", **kw):
    base = dict(id="h", player=2, x=50.0, y=50.0, heading=90.0, hits_max=8,
                shields_max=0, armor_prow="6+", armor_side="5+", turrets=2)
    base.update(kw)
    s = make_ship(**base)
    s.status, s.hits_remaining = status, 0
    return s


def test_damaged_hulk_rerolls_catastrophic():
    h = _hulk()
    gs = make_gs([h])
    rolls = [8]                        # 2D6 = 8: burning hulk
    dice = DiceStub(rolls)
    r = apply_damage(h, 2, dice, gs, ignores_shields=True)
    assert dice._idx == len(rolls)
    assert r["catastrophic"] == "burning_hulk"
    s = gs.get_ship_by_id("h")
    assert s.status == "burning_hulk" and s.hits_remaining == 0
    assert s.critical_damage == []     # no crit checks on a hulk


def test_hulk_has_no_shields():
    # s.34: hulks have no shields, turrets or other defences
    h = _hulk(shields_max=2, turrets=3)
    gs = make_gs([h])
    rolls = [4]                        # catastrophic 2D6 = 4: drifting hulk again
    dice = DiceStub(rolls)
    r = apply_damage(h, 1, dice, gs)
    assert dice._idx == len(rolls) and r["shield_hits"] == 0 and r["catastrophic"]
    assert h.effective_turrets == 0


def test_hulk_rerolls_into_an_explosion():
    h = _hulk(x=10.0, y=10.0)
    gs = make_gs([h])
    rolls = [10,          # plasma drive overload
             1, 1, 1]     # blast radius 3cm: nothing else near
    dice = DiceStub(rolls)
    r = apply_damage(h, 1, dice, gs, ignores_shields=True)
    assert dice._idx == len(rolls)
    assert r["catastrophic"] == "plasma_drive_overload" and r["destroyed"]
    assert gs.get_ship_by_id("h").status == "destroyed"


def _torp(otype=OrdnanceType.TORPEDO_STANDARD.value, player=1):
    return OrdnanceMarker(id="t", ordnance_type=otype, owner_player=player,
                          launched_by="a", x=55.0, y=50.0, heading=180.0, strength=3)


def test_standard_torpedoes_attack_hulks_boarding_torps_pass_over():
    h = _hulk()
    assert torpedo_valid_target(_torp(), h)
    assert torpedo_valid_target(_torp(player=2), h)     # own hulk too: friend or foe
    assert not torpedo_valid_target(_torp(OrdnanceType.TORPEDO_BOARDING.value), h)


def test_torpedo_hit_on_hulk_no_turrets_and_catastrophic_reroll():
    h = _hulk()
    gs = make_gs([h])
    rolls = [5, 1, 1,     # vs side armour 5+ (no turret fire from a hulk): 1 hit
             4]           # catastrophic 2D6 = 4: drifting hulk again
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_torp(), h, dice, gs)
    assert dice._idx == len(rolls)
    assert r["turret_kills"] == 0 and r["hits"] == 1 and r["remaining_strength"] == 2
    assert gs.get_ship_by_id("h").status == "drifting_hulk"


# ── Hulk drift and hulks in combat (s.34) ────────────────────────────────────
from src.end_phase import resolve_hulk_drift
from src.models import BlastMarker, Phenomenon
from src.combat import check_los_clear


def test_hulk_drift_slowed_and_damaged_by_blast_markers():
    h = _hulk(x=10.0, y=50.0, heading=0.0)
    gs = make_gs([h])
    gs.add_blast_marker(BlastMarker(id="bm", x=18.0, y=50.0))
    rolls = [3, 3, 3, 3,     # drift 12cm; touches the marker after a few cm -> 7cm
             6,              # 6: 1 damage moving through blast markers
             4]              # catastrophic re-roll: drifting hulk
    dice = DiceStub(rolls)
    resolve_hulk_drift(gs, dice)
    s = gs.get_ship_by_id("h")
    assert dice._idx == len(rolls)
    assert abs(s.x - 17.0) < 0.01 and s.status == "drifting_hulk"


def test_hulk_ignores_its_own_blast_marker():
    h = _hulk(x=10.0, y=50.0, heading=0.0)
    gs = make_gs([h])
    gs.add_blast_marker(BlastMarker(id="hulk_drift_h_1", x=10.0, y=50.0))
    dice = DiceStub([2, 2, 2, 2])
    resolve_hulk_drift(gs, dice)
    assert dice._idx == 4 and abs(gs.get_ship_by_id("h").x - 18.0) < 0.01


def test_hulk_turns_towards_planet_and_is_destroyed_by_it():
    # Starts 13cm from a small planet's centre (gravity well 18cm): turns 45
    # degrees towards it, drifts 24cm, ends inside the planet -> destroyed
    h = _hulk(x=50.0, y=27.0, heading=45.0)
    gs = make_gs([h])
    gs.phenomena = [Phenomenon(id="p", phenomenon_type="planet_small", x=50.0, y=40.0,
                               radius=8.0).to_dict()]
    dice = DiceStub([2, 2, 2, 2])       # drift 8cm
    logs = resolve_hulk_drift(gs, dice)
    s = gs.get_ship_by_id("h")
    assert dice._idx == 4
    assert any("gravity well" in l for l in logs)
    assert s.status == "destroyed"      # 8cm north lands at y=35, inside the planet


def test_hulk_outside_gravity_well_drifts_straight():
    h = _hulk(x=10.0, y=10.0, heading=0.0)
    gs = make_gs([h])
    gs.phenomena = [Phenomenon(id="p", phenomenon_type="planet_small", x=80.0, y=80.0,
                               radius=8.0).to_dict()]
    resolve_hulk_drift(gs, DiceStub([1, 1, 1, 1]))
    s = gs.get_ship_by_id("h")
    assert s.heading == 0.0 and abs(s.x - 14.0) < 0.01


def test_hulks_block_line_of_fire():
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    t = make_ship(id="t", player=2, x=30.0, y=0.0)
    h = _hulk(x=15.0, y=0.0)
    r = check_los_clear(a, t, [], [], [a, t, h])
    assert not r["clear"] and "hulk" in r["blocked_by"]
    assert check_los_clear(a, t, [], [], [a, t])["clear"]
