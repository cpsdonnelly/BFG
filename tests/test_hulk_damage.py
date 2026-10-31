"""Owner ruling: a hulk that takes at least one point of damage rolls on the
Catastrophic Damage table again. Standard torpedoes attack hulks (s.13)."""
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


def test_hulk_saved_by_shields_does_not_reroll():
    h = _hulk(shields_max=2)           # hits 0 -> crippled -> 1 shield
    gs = make_gs([h])
    dice = DiceStub([8])
    r = apply_damage(h, 1, dice, gs)
    assert dice._idx == 0
    assert "catastrophic" not in r and gs.get_ship_by_id("h").status == "drifting_hulk"


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
