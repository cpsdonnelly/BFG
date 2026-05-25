"""Tests for src/combat.py — column shifts, batteries, lances, apply_damage, catastrophic."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import (get_column_shifts, resolve_batteries, resolve_lances,
                        apply_damage, resolve_catastrophic)
from src.models import SpecialOrder


# ── get_column_shifts ─────────────────────────────────────────────────────────

def test_short_range_gives_minus_one():
    # 10cm < 15cm threshold → left shift
    a = make_ship(id="a", x=0, y=0)
    t = make_ship(id="t", x=10, y=0)
    assert get_column_shifts(a, t, blast_markers=[], phenomena=[]) == -1


def test_long_range_gives_plus_one():
    # 40cm > 30cm threshold → right shift
    a = make_ship(id="a", x=0, y=0)
    t = make_ship(id="t", x=40, y=0)
    assert get_column_shifts(a, t, blast_markers=[], phenomena=[]) == 1


def test_mid_range_no_range_shift():
    # 20cm is in the 15-30cm band → no range modifier
    a = make_ship(id="a", x=0, y=0)
    t = make_ship(id="t", x=20, y=0)
    assert get_column_shifts(a, t, blast_markers=[], phenomena=[]) == 0


def test_targeting_matrix_extra_minus_one():
    a = make_ship(id="a", x=0, y=0, special_rules=["targeting_matrix"])
    t = make_ship(id="t", x=20, y=0)
    # mid-range (0) + targeting_matrix (-1) = -1
    assert get_column_shifts(a, t, blast_markers=[], phenomena=[]) == -1


# ── resolve_batteries ─────────────────────────────────────────────────────────

# Attacker at x=0 heading east, target at x=20 heading east (facing away → rear arc).
# Aspect = moving_away → col 3.  FP 6 col 3: GUNNERY_TABLE[6][2] = 3 dice.
# Side armour = 5+.  Use no_column_shifts=True to bypass LoS checks.

_BATTERY = {"name": "Broadside", "strength": 6,
            "arcs": ["front", "left", "right", "rear"]}


def _pair():
    a = make_ship(id="a", x=0, y=0, heading=0)
    t = make_ship(id="t", x=20, y=0, heading=0, armor_prow="6+", armor_side="5+")
    return a, t


def test_batteries_all_hit():
    a, t = _pair()
    dice = DiceStub([5, 5, 5])
    r = resolve_batteries(a, t, _BATTERY, dice, blast_markers=[], no_column_shifts=True)
    assert r.hits == 3


def test_batteries_all_miss():
    a, t = _pair()
    dice = DiceStub([1, 1, 1])
    r = resolve_batteries(a, t, _BATTERY, dice, blast_markers=[], no_column_shifts=True)
    assert r.hits == 0


def test_batteries_crippled_halves_firepower():
    # Crippled: FP 6 → 3; col 3 FP3: GUNNERY_TABLE[3][2] = 2 dice
    a = make_ship(id="a", x=0, y=0, heading=0, hits_max=8, hits_remaining=4)
    t = make_ship(id="t", x=20, y=0, heading=0, armor_prow="6+", armor_side="5+")
    dice = DiceStub([5, 5])
    r = resolve_batteries(a, t, _BATTERY, dice, blast_markers=[], no_column_shifts=True)
    assert r.hits == 2


def test_batteries_aaf_halves_firepower():
    a = make_ship(id="a", x=0, y=0, heading=0,
                  special_order=SpecialOrder.ALL_AHEAD_FULL.value)
    t = make_ship(id="t", x=20, y=0, heading=0, armor_prow="6+", armor_side="5+")
    # Same halving as crippled: FP 3 → 2 dice
    dice = DiceStub([5, 5])
    r = resolve_batteries(a, t, _BATTERY, dice, blast_markers=[], no_column_shifts=True)
    assert r.hits == 2


def test_batteries_lock_on_rerolls_misses():
    a, t = _pair()
    # 3 dice all miss then reroll 3 → all hit
    dice = DiceStub([1, 1, 1, 5, 5, 5])
    r = resolve_batteries(a, t, _BATTERY, dice, blast_markers=[],
                          lock_on=True, no_column_shifts=True)
    assert r.hits == 3
    assert len(r.reroll_dice) == 3


# ── resolve_lances ────────────────────────────────────────────────────────────

def test_lances_all_hit():
    a = make_ship(id="a", x=0)
    t = make_ship(id="t", x=20)
    w = {"name": "Lance", "strength": 3}
    r = resolve_lances(a, t, w, DiceStub([4, 4, 4]))
    assert r.hits == 3


def test_lances_all_miss():
    a = make_ship(id="a", x=0)
    t = make_ship(id="t", x=20)
    w = {"name": "Lance", "strength": 3}
    r = resolve_lances(a, t, w, DiceStub([3, 3, 3]))
    assert r.hits == 0


def test_lances_crippled_halves_strength():
    # Crippled: strength 3 → 2
    a = make_ship(id="a", x=0, hits_max=8, hits_remaining=4)
    t = make_ship(id="t", x=20)
    w = {"name": "Lance", "strength": 3}
    r = resolve_lances(a, t, w, DiceStub([4, 4]))
    assert r.hits == 2


def test_lances_lock_on_rerolls_misses():
    a = make_ship(id="a", x=0)
    t = make_ship(id="t", x=20)
    w = {"name": "Lance", "strength": 3}
    # 3 initial misses; reroll 3 → all hit
    dice = DiceStub([3, 3, 3, 4, 4, 4])
    r = resolve_lances(a, t, w, dice, lock_on=True)
    assert r.hits == 3


# ── apply_damage ──────────────────────────────────────────────────────────────

def test_shields_absorb_hits():
    target = make_ship(id="t", shields_max=2, hits_max=8)
    gs = make_gs([target])
    # 2 hits vs 2 shields → absorbed; no hull hits, no crit rolls
    r = apply_damage(target, 2, DiceStub([1]), gs)
    assert r["shield_hits"] == 2
    assert r["hull_hits"] == 0
    assert r["destroyed"] is False


def test_shields_overflow_to_hull():
    target = make_ship(id="t", shields_max=2, hits_max=8)
    gs = make_gs([target])
    # 3 hits: 2 shields, 1 hull hit; crit check = 1 (no crit)
    r = apply_damage(target, 3, DiceStub([1]), gs)
    assert r["shield_hits"] == 2
    assert r["hull_hits"] == 1
    assert target.hits_remaining == 7


def test_ignores_shields_sends_all_to_hull():
    target = make_ship(id="t", shields_max=2, hits_max=8)
    gs = make_gs([target])
    # 2 hits, ignores shields → 2 hull hits; crit checks = 1, 1
    r = apply_damage(target, 2, DiceStub([1]), gs, ignores_shields=True)
    assert r["shield_hits"] == 0
    assert r["hull_hits"] == 2
    assert target.hits_remaining == 6


def test_brace_saves_all():
    target = make_ship(id="t", shields_max=0, hits_max=8)
    gs = make_gs([target])
    # 2 hull hits, both brace-saved on 4+
    r = apply_damage(target, 2, DiceStub([4, 4]), gs,
                     ignores_shields=True, target_braced=True)
    assert r["brace_saves"] == 2
    assert r["hull_hits"] == 0
    assert target.hits_remaining == 8


def test_brace_saves_partial():
    target = make_ship(id="t", shields_max=0, hits_max=8)
    gs = make_gs([target])
    # 2 hull hits; brace save 1=fail(3), brace save 2=pass(4); 1 hull hit lands; crit=1
    r = apply_damage(target, 2, DiceStub([3, 4, 1]), gs,
                     ignores_shields=True, target_braced=True)
    assert r["brace_saves"] == 1
    assert r["hull_hits"] == 1


def test_crit_triggered_on_six():
    target = make_ship(id="t", shields_max=0, hits_max=8)
    gs = make_gs([target])
    # 1 hull hit; crit check=6 → fires crit; 2d6=7 → "Fire!"
    r = apply_damage(target, 1, DiceStub([6, 7]), gs, ignores_shields=True)
    assert len(r["crits"]) == 1
    assert "Fire!" in r["crits"]


def test_crit_not_triggered_on_non_six():
    target = make_ship(id="t", shields_max=0, hits_max=8)
    gs = make_gs([target])
    r = apply_damage(target, 1, DiceStub([5]), gs, ignores_shields=True)
    assert r["crits"] == []


def test_bridge_smashed_reduces_leadership():
    target = make_ship(id="t", shields_max=0, hits_max=8, leadership=7)
    gs = make_gs([target])
    # 1 hull hit; crit=6 → 2d6=9 → Bridge Smashed; leadership 7→4
    apply_damage(target, 1, DiceStub([6, 9]), gs, ignores_shields=True)
    assert target.leadership == 4


def test_ship_destroyed_when_hp_zero():
    target = make_ship(id="t", shields_max=0, hits_max=8, hits_remaining=2)
    gs = make_gs([target])
    # 2 hull hits; crit checks cycling through 1 (no crits)
    r = apply_damage(target, 2, DiceStub([1]), gs, ignores_shields=True)
    assert r["destroyed"] is True
    assert target.hits_remaining <= 0


def test_cripple_flag_set_at_threshold():
    # hits_max=8, threshold=4; start at 5; apply 1 hit → 4 (= threshold, crippled)
    target = make_ship(id="t", shields_max=0, hits_max=8, hits_remaining=5)
    gs = make_gs([target])
    r = apply_damage(target, 1, DiceStub([1]), gs, ignores_shields=True)
    assert r["crippled"] is True


def test_blast_markers_placed_for_shield_hits():
    target = make_ship(id="t", shields_max=2, hits_max=8)
    gs = make_gs([target])
    r = apply_damage(target, 2, DiceStub([1]), gs)
    assert r["blast_markers_placed"] == 2


# ── resolve_catastrophic ──────────────────────────────────────────────────────

def test_escort_destroyed_no_dice():
    target = make_ship(id="t", ship_type="escort", hits_max=2)
    gs = make_gs([target])
    r = resolve_catastrophic(target, DiceStub([1]), gs)
    assert r == "escort_destroyed"
    assert target.status == "destroyed"


def test_capital_drifting_hulk():
    target = make_ship(id="t", ship_type="cruiser", hits_max=8)
    gs = make_gs([target])
    # roll_2d6 → 5 → drifting_hulk
    r = resolve_catastrophic(target, DiceStub([5]), gs)
    assert r == "drifting_hulk"
    assert target.status == "drifting_hulk"


def test_capital_burning_hulk():
    target = make_ship(id="t", ship_type="cruiser", hits_max=8)
    gs = make_gs([target])
    r = resolve_catastrophic(target, DiceStub([7]), gs)
    assert r == "burning_hulk"


def test_capital_plasma_drive_overload():
    target = make_ship(id="t", ship_type="cruiser", hits_max=8)
    gs = make_gs([target])
    # roll_2d6=9 → plasma_drive_overload; blast_radius roll_d6(3)=[3,3,3]
    # no nearby ships so no extra dice needed
    r = resolve_catastrophic(target, DiceStub([9, 3, 3, 3]), gs)
    assert r == "plasma_drive_overload"
    assert target.status == "destroyed"
