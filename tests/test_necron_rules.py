"""Necron first slice (To do 14; bfgxr/rules/09_necrons.md)."""
from types import SimpleNamespace

from tests.conftest import DiceStub
from src import necrons


def test_reactive_hulls_and_brace():
    assert necrons.parse_reactive_hull("RH 4+") == 4 and necrons.parse_reactive_hull("2") is None
    assert necrons.hull_save(5, braced=False) == 5 and necrons.hull_save(5, braced=True) == 2
    assert necrons.armour_when_braced(6, True) == 4 and necrons.armour_when_braced(6, False) == 6
    assert not necrons.order_allowed("reload_ordnance")
    assert necrons.order_allowed("reload_ordnance", tomb_complex=True)


def test_alert_levels_and_awakening():
    assert necrons.starting_alert(1500, 1000) == 3
    assert necrons.starting_alert(1000, 1000, hostile_specials=1) == 2
    a = necrons.AlertTracker(1)
    assert a.ld_required() == 10 and not a.may_awaken(9)
    a.unsaved_hit(2)
    assert a.ld_required() == 8 and a.may_awaken(8)
    a.unsaved_hit(5)
    assert a.level == 5 and a.may_awaken(1)
    cap = SimpleNamespace(special_rules=["necron"], ship_type="cruiser")
    esc = SimpleNamespace(special_rules=["necron"], ship_type="escort")
    assert necrons.conserving_power(cap) and not necrons.conserving_power(esc)
    cap.special_rules.append("necron_awake")
    assert not necrons.conserving_power(cap) and necrons.vp_multiplier(cap) == 2.0


def test_inertialess_drive_and_weapons():
    assert necrons.inertialess_extra(4) == 40 and necrons.inertialess_turns(45) == 2
    assert necrons.field_usable(False, "lock_on") and not necrons.field_usable(True, "")
    assert not necrons.field_usable(False, "all_ahead_full")
    dice = DiceStub([5, 4])
    assert necrons.nightmare_field(dice, 8) and dice._idx == 2       # 9 > Ld 8: failed
    dice = DiceStub([4, 3, 6])
    assert necrons.field_ordnance_kills(dice, ["a", "b", "c"], "x") == ["a", "c"]
    dice = DiceStub([6, 4])
    assert necrons.star_pulse_hits(dice, [6, 5]) == [True, False]
    dice = DiceStub([6, 4, 2])
    assert necrons.particle_whip(dice, 3) == (2, 1)
    assert necrons.portal_strength(3, 1) == 1 and necrons.portal_strength(4, 2) == 1
