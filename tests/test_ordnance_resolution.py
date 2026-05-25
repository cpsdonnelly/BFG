"""Tests for src/ordnance.py — torpedo, bomber, fighter, missile resolution."""
from tests.conftest import make_ship, make_gs, make_marker, DiceStub
from src.ordnance import (
    resolve_torpedo_attack, degrade_tau_missiles,
    resolve_bomber_interception, resolve_bomber_attack,
    resolve_fighter_intercept, check_ordnance_vs_blast,
)
from src.models import BlastMarker, OrdnanceType


# ── resolve_torpedo_attack ────────────────────────────────────────────────────

# Ship heading=180 (facing west), marker approaching from east (x=5).
# target.bearing_to(5,0) = 0° → relative to heading 180° = 180° → REAR arc → side armour.

def _torp_target(**kw):
    defaults = dict(id="t", turrets=0, shields_max=2,
                    armor_prow="6+", armor_side="5+",
                    hits_max=8, heading=180)
    defaults.update(kw)
    return make_ship(**defaults)


def test_torpedo_turrets_kill_all():
    target = _torp_target(turrets=2)
    gs = make_gs([target])
    marker = make_marker(strength=2, x=5, y=0, heading=180)
    # 2 turret dice both hit (4+) → 2 kills → remaining_strength=0 → no attacks
    r = resolve_torpedo_attack(marker, target, DiceStub([4, 4]), gs)
    assert r["turret_kills"] == 2
    assert r["remaining_strength"] == 0
    assert r["hits"] == 0


def test_torpedo_attacks_after_partial_turret_kill():
    target = _torp_target(turrets=1)
    gs = make_gs([target])
    # Strength 3, 1 turret misses (roll=1), 3 attacks vs side armour 5+; all roll 5 → 3 hits
    # Dice sequence: turret=1 (miss), attack_rolls=[5,5,5] (hits), crit_checks=[1,1,1]
    dice = DiceStub([1, 5, 5, 5, 1, 1, 1])
    marker = make_marker(strength=3, x=5, y=0, heading=180)
    r = resolve_torpedo_attack(marker, target, dice, gs)
    assert r["turret_kills"] == 0
    assert r["hits"] == 3


def test_torpedo_hits_bypass_shields():
    # 2 shields; torpedoes ignore them; all 2 hull hits land
    target = _torp_target(turrets=0, shields_max=2, armor_side="3+", hits_max=8)
    gs = make_gs([target])
    # strength 2; rolls 3+ → 2 hits; crit checks = 1, 1
    dice = DiceStub([3, 3, 1, 1])
    marker = make_marker(strength=2, x=5, y=0, heading=180)
    r = resolve_torpedo_attack(marker, target, dice, gs)
    assert r["hits"] == 2
    # Both hits went directly to hull (no shield absorption)
    assert target.hits_remaining == 6


def test_torpedo_partial_hit_remaining_strength():
    # Strength 6, 2 turrets score 1 kill → 5 attack dice.
    # Armour 5+; rolls [5,6,3,2,2] → 2 hits.
    # Torps that hit are spent; 5 - 2 = 3 pass through.
    target = _torp_target(turrets=2, armor_side="5+", hits_max=8)
    gs = make_gs([target])
    marker = make_marker(strength=6, x=5, y=0, heading=180)
    # Dice: turret[2]=[4,1] → 1 kill; attack[5]=[5,6,3,2,2] → 2 hits; crit_checks[2]=[1,1]
    dice = DiceStub([4, 1, 5, 6, 3, 2, 2, 1, 1])
    r = resolve_torpedo_attack(marker, target, dice, gs)
    assert r["turret_kills"] == 1
    assert r["hits"] == 2
    assert r["remaining_strength"] == 3


def test_torpedo_miss_does_not_remove_marker():
    # Torpedoes that miss their target keep moving — they are NOT consumed.
    target = _torp_target(turrets=0, armor_side="6+")
    gs = make_gs([target])
    marker = make_marker(id="persist_torp", strength=3, x=5, y=0, heading=180)
    gs.add_ordnance(marker)
    # All attack rolls fail vs 6+ armour → 0 hits, full strength passes through
    r = resolve_torpedo_attack(marker, target, DiceStub([1]), gs)
    assert r["hits"] == 0
    assert r["remaining_strength"] == 3
    assert any(o["id"] == "persist_torp" for o in gs.ordnance)


def test_torpedo_turret_blocked_by_craft_use():
    target = _torp_target(turrets=2, turrets_used_vs="craft", armor_side="6+")
    gs = make_gs([target])
    marker = make_marker(strength=3, x=5, y=0, heading=180)
    # Turrets blocked; all attack rolls = 1 (fail vs 6+)
    r = resolve_torpedo_attack(marker, target, DiceStub([1]), gs)
    assert r["turret_kills"] == 0
    assert r["hits"] == 0


# ── degrade_tau_missiles ──────────────────────────────────────────────────────

def test_tau_missile_loses_strength():
    gs = make_gs()
    marker = make_marker(id="m1", ordnance_type="torpedo_guided",
                         strength=3, launched_turn=1)
    gs.add_ordnance(marker)
    # 2 ones → 2 losses; strength 3 → 1
    degrade_tau_missiles(gs, DiceStub([1, 1, 6]), current_turn=2)
    surviving = [o for o in gs.ordnance if o["id"] == "m1"]
    assert len(surviving) == 1
    assert surviving[0]["strength"] == 1


def test_tau_missile_removed_at_zero_strength():
    gs = make_gs()
    marker = make_marker(id="m1", ordnance_type="torpedo_guided",
                         strength=1, launched_turn=1)
    gs.add_ordnance(marker)
    # 1 one → strength 0 → removed
    degrade_tau_missiles(gs, DiceStub([1]), current_turn=2)
    assert all(o["id"] != "m1" for o in gs.ordnance)


def test_tau_missile_same_turn_not_degraded():
    gs = make_gs()
    marker = make_marker(id="m1", ordnance_type="torpedo_guided",
                         strength=3, launched_turn=2)
    gs.add_ordnance(marker)
    # launched_turn == current_turn → skipped
    degrade_tau_missiles(gs, DiceStub([1]), current_turn=2)
    surviving = [o for o in gs.ordnance if o["id"] == "m1"]
    assert surviving[0]["strength"] == 3


def test_standard_torpedo_not_degraded():
    gs = make_gs()
    marker = make_marker(id="m1", ordnance_type="torpedo_standard",
                         strength=6, launched_turn=1)
    gs.add_ordnance(marker)
    degrade_tau_missiles(gs, DiceStub([1]), current_turn=2)
    surviving = [o for o in gs.ordnance if o["id"] == "m1"]
    assert surviving[0]["strength"] == 6


# ── resolve_bomber_interception ───────────────────────────────────────────────

def test_bomber_interception_kills_two():
    target = make_ship(id="t", turrets=2, hits_max=8)
    gs = make_gs([target])
    # 2 turret dice both 4+ → 2 kills out of 3 bombers
    r = resolve_bomber_interception(3, target, [target], DiceStub([4, 4]), gs)
    assert r["killed"] == 2


def test_bomber_interception_capped_at_bomber_count():
    target = make_ship(id="t", turrets=3, hits_max=8)
    gs = make_gs([target])
    # 3 hits but only 2 bombers → capped at 2
    r = resolve_bomber_interception(2, target, [target], DiceStub([4, 4, 4]), gs)
    assert r["killed"] == 2


def test_bomber_interception_no_turrets_kills_nothing():
    target = make_ship(id="t", turrets=0, hits_max=8)
    gs = make_gs([target])
    r = resolve_bomber_interception(3, target, [target], DiceStub([1]), gs)
    assert r["killed"] == 0


def test_bomber_interception_marks_turrets_used():
    target = make_ship(id="t", turrets=2, hits_max=8)
    gs = make_gs([target])
    resolve_bomber_interception(3, target, [target], DiceStub([1, 1]), gs)
    assert target.turrets_used_vs == "craft"


# ── resolve_bomber_attack ─────────────────────────────────────────────────────

def test_bomber_attack_basic():
    target = make_ship(id="t", turrets=2, armor_prow="5+", armor_side="5+", hits_max=8)
    gs = make_gs([target])
    # attack_roll=6, turrets=2 → 4 attacks; hit_rolls all 5 (≥5+) → 4 hits; crits=1×4
    dice = DiceStub([6, 5, 5, 5, 5, 1, 1, 1, 1])
    r = resolve_bomber_attack(make_marker(), target, dice, gs)
    assert r["attacks"] == 4
    assert r["hits"] == 4


def test_bomber_attack_suppressed_gives_three_attacks():
    target = make_ship(id="t", turrets=2, armor_prow="5+", armor_side="5+", hits_max=8)
    gs = make_gs([target])
    # suppressed → 3 attacks (no attack_roll die consumed); hit_rolls=[5,5,5]; crits=1×3
    dice = DiceStub([5, 5, 5, 1, 1, 1])
    r = resolve_bomber_attack(make_marker(), target, dice, gs, suppressed_by_fighter=True)
    assert r["suppressed"] is True
    assert r["attacks"] == 3
    assert r["hits"] == 3


def test_bomber_attack_zero_when_turrets_exceed_roll():
    target = make_ship(id="t", turrets=6, armor_prow="5+", armor_side="5+", hits_max=8)
    gs = make_gs([target])
    # attack_roll=3, turrets=6 → max(0, 3-6) = 0 attacks
    r = resolve_bomber_attack(make_marker(), target, DiceStub([3]), gs)
    assert r["attacks"] == 0
    assert r["hits"] == 0


def test_bomber_attack_marks_turrets_used():
    target = make_ship(id="t", turrets=2, armor_prow="5+", armor_side="5+", hits_max=8)
    gs = make_gs([target])
    # attack_roll=1 → 0 attacks (1 - 2 = -1 → 0); turrets_used_vs set regardless
    resolve_bomber_attack(make_marker(), target, DiceStub([1]), gs)
    assert target.turrets_used_vs == "craft"


# ── resolve_fighter_intercept ─────────────────────────────────────────────────

def test_fighter_destroys_torpedo_salvo():
    fighter = make_marker(id="f", ordnance_type="fighter", owner_player=1)
    torp = make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2)
    gs = make_gs()
    r = resolve_fighter_intercept(fighter, torp, DiceStub([1]), gs)
    assert r["fighter_removed"] is True
    assert r["target_removed"] is True


def test_fighter_resilient_save_vs_torpedo():
    # Fighter with resilient_save=4 passes save (roll=4) and survives
    fighter = make_marker(id="f", ordnance_type="fighter", owner_player=1,
                          resilient_save=4)
    torp = make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2)
    gs = make_gs()
    r = resolve_fighter_intercept(fighter, torp, DiceStub([4]), gs)
    assert r["fighter_removed"] is False
    assert r["target_removed"] is True


def test_fighter_resilient_fail_vs_torpedo():
    fighter = make_marker(id="f", ordnance_type="fighter", owner_player=1,
                          resilient_save=4)
    torp = make_marker(id="t", ordnance_type="torpedo_standard", owner_player=2)
    gs = make_gs()
    r = resolve_fighter_intercept(fighter, torp, DiceStub([3]), gs)
    assert r["fighter_removed"] is True


def test_fighter_vs_bomber_mutual_destruction():
    fighter = make_marker(id="f", ordnance_type="fighter", owner_player=1)
    bomber = make_marker(id="b", ordnance_type="bomber", owner_player=2)
    gs = make_gs()
    # No resilient saves on either side; DiceStub([1]) unused
    r = resolve_fighter_intercept(fighter, bomber, DiceStub([1]), gs)
    assert r["fighter_removed"] is True
    assert r["target_removed"] is True


def test_target_resilient_save_vs_fighter():
    # Bomber has resilient_save=4; fighter has none; bomber passes save (roll=4)
    fighter = make_marker(id="f", ordnance_type="fighter", owner_player=1)
    bomber = make_marker(id="b", ordnance_type="bomber", owner_player=2,
                         resilient_save=4)
    gs = make_gs()
    r = resolve_fighter_intercept(fighter, bomber, DiceStub([4]), gs)
    assert r["fighter_removed"] is True
    assert r["target_removed"] is False


# ── check_ordnance_vs_blast ───────────────────────────────────────────────────

def test_ordnance_destroyed_in_blast_marker():
    marker = make_marker(x=0, y=0)
    bm = BlastMarker(id="bm1", x=1.0, y=0, source="test", heading=0)
    assert check_ordnance_vs_blast(marker, [bm], DiceStub([6])) is True


def test_ordnance_survives_blast_marker():
    marker = make_marker(x=0, y=0)
    bm = BlastMarker(id="bm1", x=1.0, y=0, source="test", heading=0)
    assert check_ordnance_vs_blast(marker, [bm], DiceStub([5])) is False


def test_ordnance_far_from_blast_no_roll():
    marker = make_marker(x=0, y=0)
    bm = BlastMarker(id="bm1", x=10.0, y=0, source="test", heading=0)
    # DiceStub([6]) would destroy if called — but it shouldn't be
    assert check_ordnance_vs_blast(marker, [bm], DiceStub([6])) is False


def test_ordnance_no_blast_markers_always_safe():
    marker = make_marker(x=0, y=0)
    assert check_ordnance_vs_blast(marker, [], DiceStub([6])) is False
