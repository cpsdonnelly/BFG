"""Tests for ordnance utility functions in src/ordnance.py."""
from tests.conftest import make_ship, make_gs, make_marker, make_phenomenon, DiceStub
from src.ordnance import (resolve_mine_contact, check_ordnance_vs_phenomena,
                          compute_torpedo_launch_exempt, launch_torpedoes,
                          launch_attack_craft)
from src.models import OrdnanceMarker


# ── resolve_mine_contact ──────────────────────────────────────────────────────

def test_mine_turret_success_reduces_to_4d6():
    # Target has 2 turrets; DiceStub gives [4,1] → one 4+ → reduces to 4D6
    # Then 4 attack rolls: [5,5,5,5] → armor 5+ → 4 hits
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=2,
                       armor_prow="5+", armor_side="5+", shields_max=0,
                       hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    dice = DiceStub([4, 1, 5, 5, 5, 5])  # turret rolls then attack rolls
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["attack_dice"] == 4
    assert r["hits"] == 4


def test_mine_turret_failure_keeps_8d6():
    # Turrets roll all miss, so mine attacks with full 8D6
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=2,
                       armor_prow="5+", armor_side="5+", shields_max=0,
                       hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    # 2 turret rolls fail, then 8 attack rolls (all miss)
    dice = DiceStub([1, 2, 1, 1, 1, 1, 1, 1, 1, 1])
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["attack_dice"] == 8
    assert r["hits"] == 0


def test_mine_no_turrets_uses_8d6():
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=0,
                       armor_prow="5+", armor_side="5+", shields_max=0,
                       hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    dice = DiceStub([5, 5, 5, 5, 5, 5, 5, 5])
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["attack_dice"] == 8
    assert r["hits"] == 8


def test_mine_hits_apply_damage_with_shields():
    # Mine damage is blocked by shields (unlike torps)
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=0,
                       armor_prow="5+", armor_side="5+",
                       shields_max=2, hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    # 8 attack rolls → 8 hits at 5+; then apply_damage consumes crit-check dice
    dice = DiceStub([5, 5, 5, 5, 5, 5, 5, 5, 1])  # 8 hits, crit check 1
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["hits"] == 8
    # Hull hits = 8 - 2 shields = 6; ship should have taken damage
    t_updated = gs.get_ship_by_id("t")
    assert t_updated.hits_remaining < 8


# ── check_ordnance_vs_phenomena ───────────────────────────────────────────────

def test_torp_in_asteroid_field_auto_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=50, y=0)
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    dice = DiceStub([1])
    destroyed, reason = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is True
    assert reason == "asteroid_field"


def test_torp_in_warp_rift_auto_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=50, y=0)
    p = make_phenomenon("warp_rift", x=50, y=0, width=20, height=20, radius=0)
    dice = DiceStub([1])
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is True


def test_torp_in_planet_auto_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=50, y=0)
    p = make_phenomenon("planet_small", x=50, y=0, radius=20)
    dice = DiceStub([1])
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is True


def test_torp_clear_of_phenomena_not_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=0, y=0)
    p = make_phenomenon("asteroid_field", x=100, y=100, width=20, height=20, radius=0)
    dice = DiceStub([1])
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is False


def test_craft_in_asteroid_on_6_destroyed():
    marker = make_marker(ordnance_type="fighter", x=50, y=0)
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], DiceStub([6]))
    assert destroyed is True


def test_craft_in_asteroid_not_on_6_survives():
    marker = make_marker(ordnance_type="fighter", x=50, y=0)
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], DiceStub([5]))
    assert destroyed is False


def test_craft_in_warp_rift_auto_destroyed():
    marker = make_marker(ordnance_type="bomber", x=50, y=0)
    p = make_phenomenon("warp_rift", x=50, y=0, width=20, height=20, radius=0)
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], DiceStub([1]))
    assert destroyed is True


# ── compute_torpedo_launch_exempt ─────────────────────────────────────────────

def test_launcher_always_exempt():
    launcher = make_ship(id="launcher", x=50, y=50, player=1)
    gs = make_gs([launcher])
    exempt = compute_torpedo_launch_exempt(launcher, gs)
    assert "launcher" in exempt


def test_nearby_friendly_ship_not_exempt_individual_launch():
    # Individual launches only exempt the launcher itself.
    # Combined squadron launches (handled by the ordnance panel) exempt the whole group.
    launcher = make_ship(id="launcher", x=50, y=50, player=1, base_size="small")
    ally = make_ship(id="ally", x=52, y=50, player=1, base_size="small")
    gs = make_gs([launcher, ally])
    exempt = compute_torpedo_launch_exempt(launcher, gs)
    assert "ally" not in exempt
    assert "launcher" in exempt


def test_enemy_ship_not_exempt():
    launcher = make_ship(id="launcher", x=50, y=50, player=1)
    enemy = make_ship(id="enemy", x=52, y=50, player=2)
    gs = make_gs([launcher, enemy])
    exempt = compute_torpedo_launch_exempt(launcher, gs)
    assert "enemy" not in exempt


# ── launch_torpedoes ──────────────────────────────────────────────────────────

def test_launch_torpedoes_creates_marker():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 6, "torpedo_type": "standard", "torpedo_speed": 30}
    marker = launch_torpedoes(ship, weapon, gs)
    assert marker.ordnance_type == "torpedo_standard"
    assert marker.strength == 6
    assert len(gs.ordnance) == 1


def test_launch_guided_torpedo_creates_guided_marker():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 4, "torpedo_type": "guided", "torpedo_speed": 20}
    marker = launch_torpedoes(ship, weapon, gs)
    assert marker.ordnance_type == "torpedo_guided"
    assert marker.can_turn is True


# ── launch_attack_craft ───────────────────────────────────────────────────────

def test_launch_attack_craft_creates_markers():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"name": "Launch Bay", "strength": 2}
    markers = launch_attack_craft(ship, weapon, "fury_fighter", 2, gs)
    assert len(markers) == 2
    for m in markers:
        assert m.ordnance_type == "fighter"
