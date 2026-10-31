"""Boarding torpedoes: one hit-and-run raid per hit (core rules s.28)."""
import pytest
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType, SpecialOrder
from src.ordnance import (resolve_torpedo_attack, launch_torpedoes,
                          torpedo_ordnance_type)


def _marker(strength=4, rules=None):
    # Abeam of the target (side armour 5+)
    return OrdnanceMarker(id="bt", ordnance_type=OrdnanceType.TORPEDO_BOARDING.value,
                          owner_player=1, launched_by="a", x=50.0, y=55.0,
                          heading=270.0, strength=strength,
                          special_rules=list(rules or []))


def _target(**kw):
    base = dict(id="t", player=2, x=50.0, y=50.0, heading=0.0, hits_max=8,
                turrets=2, armor_prow="6+", armor_side="5+")
    base.update(kw)
    return make_ship(**base)


def _no_brace_called(*a):
    raise AssertionError("brace callback should not be called")


def test_hits_become_raids_not_damage():
    target = _target()
    gs = make_gs([target])
    rolls = [4, 1,          # turrets: one torpedo shot down (Str 4 -> 3)
             5, 2, 6,       # attack vs side armour 5+: two hits
             6, 1]          # raids: Engine Room (+1 damage), failure
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(), target, dice, gs)
    assert dice._idx == len(rolls)
    assert r["turret_kills"] == 1 and r["hits"] == 2
    assert r["remaining_strength"] == 1
    raids = r["raids"]
    assert raids["raid_rolls"] == [6, 1]
    assert raids["failures"] == 1
    assert [c["crit_type"] for c in raids["crits_applied"]] == ["engine_room"]
    # Only the crit's extra damage; the torpedo hits themselves do no damage
    assert gs.get_ship_by_id("t").hits_remaining == 7


def test_target_may_brace_before_raids_are_rolled():
    target = _target(turrets=0)
    gs = make_gs([target])
    asked = []

    def brace(ship, msg, n_raids):
        asked.append(n_raids)
        return True, True

    rolls = [5, 6, 1, 1,    # two hits
             6, 4,          # raid 1 succeeds, repelled on 4+
             6, 2]          # raid 2 succeeds, repel fails
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(), target, dice, gs, brace_decision_fn=brace)
    assert dice._idx == len(rolls)
    assert asked == [2]
    assert r["raids"]["repelled"] == 1
    assert len(r["raids"]["crits_applied"]) == 1


def test_already_braced_target_saves_without_being_asked():
    target = _target(turrets=0, special_order=SpecialOrder.BRACE_FOR_IMPACT.value)
    gs = make_gs([target])
    rolls = [5, 1, 1, 1,    # one hit
             6, 5]          # raid succeeds, repelled
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(), target, dice, gs,
                               brace_decision_fn=_no_brace_called)
    assert dice._idx == len(rolls)
    assert r["raids"]["repelled"] == 1
    assert gs.get_ship_by_id("t").hits_remaining == 8


def test_no_hits_no_raids_no_brace_question():
    target = _target(turrets=0)
    gs = make_gs([target])
    rolls = [1, 2, 3, 4]
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(), target, dice, gs,
                               brace_decision_fn=_no_brace_called)
    assert dice._idx == len(rolls)
    assert r["hits"] == 0 and r["raids"] is None


def test_raids_on_small_escort_do_one_damage_on_4_plus():
    # Escorts with fewer than 3 starting hits don't use the Critical Hits table
    target = _target(turrets=0, ship_type="escort", hits_max=2,
                     armor_prow="5+", armor_side="5+")
    gs = make_gs([target])
    rolls = [5, 6, 1, 1,    # two hits
             4, 3]          # raids: 4 -> 1 damage, 3 -> no effect
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(), target, dice, gs)
    assert dice._idx == len(rolls)
    assert r["raids"]["damage"] == 1 and r["raids"]["crits_applied"] == []
    assert gs.get_ship_by_id("t").hits_remaining == 1


def test_launcher_raid_bonus_carries_to_its_boarding_torps():
    target = _target(turrets=0)
    gs = make_gs([target])
    rolls = [5, 1, 1, 1,    # one hit
             5]             # raid 5 +1 (Space Marines) = 6: Engine Room
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(rules=["space_marine_crew"]), target, dice, gs)
    assert dice._idx == len(rolls)
    assert r["raids"]["crits_applied"][0]["crit_type"] == "engine_room"


TORPS = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6,
         "torpedo_type": "standard", "torpedo_speed": 30}


@pytest.mark.parametrize("weapon,boarding,expected", [
    ({**TORPS, "boarding_torpedoes": True}, True, OrdnanceType.TORPEDO_BOARDING.value),
    ({**TORPS, "boarding_torpedoes": True}, False, OrdnanceType.TORPEDO_STANDARD.value),
    (TORPS, True, OrdnanceType.TORPEDO_STANDARD.value),   # launcher has no boarding torps
    ({**TORPS, "torpedo_type": "guided", "boarding_torpedoes": True}, True,
     OrdnanceType.TORPEDO_GUIDED.value),
])
def test_torpedo_ordnance_type(weapon, boarding, expected):
    assert torpedo_ordnance_type(weapon, boarding) == expected


def test_launch_boarding_torpedoes_carries_launcher_rules():
    ship = make_ship(id="a", player=1, x=50.0, y=50.0,
                     special_rules=["space_marine_crew"],
                     weapons=[{**TORPS, "boarding_torpedoes": True}])
    gs = make_gs([ship])
    m = launch_torpedoes(ship, ship.weapons[0], gs, boarding=True)
    assert m.ordnance_type == OrdnanceType.TORPEDO_BOARDING.value
    assert m.special_rules == ["space_marine_crew"]
    assert m.strength == 6


def test_standard_torpedoes_still_do_damage():
    target = _target(turrets=0)
    gs = make_gs([target])
    m = _marker()
    m.ordnance_type = OrdnanceType.TORPEDO_STANDARD.value
    rolls = [5, 6, 1, 1]    # two hits = two damage, crit checks only on 6s
    dice = DiceStub(rolls + [1] * 10)
    r = resolve_torpedo_attack(m, target, dice, gs)
    assert r["hits"] == 2 and r["raids"] is None
    assert gs.get_ship_by_id("t").hits_remaining <= 6


def test_friendly_ships_are_not_valid_targets_for_boarding_torps():
    from src.ordnance import torpedo_valid_target
    friend = make_ship(id="f", player=1)
    enemy = make_ship(id="e", player=2)
    boarding = _marker()                     # owner_player=1
    standard = _marker()
    standard.ordnance_type = OrdnanceType.TORPEDO_STANDARD.value
    assert not torpedo_valid_target(boarding, friend)
    assert torpedo_valid_target(boarding, enemy)
    assert torpedo_valid_target(standard, friend)   # standard torps: friend or foe
    assert torpedo_valid_target(standard, enemy)
