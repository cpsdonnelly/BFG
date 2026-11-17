"""Tests for src/terrain_effects.py."""
from tests.conftest import make_ship, make_gs, make_phenomenon, DiceStub
from src.terrain_effects import (check_ship_terrain_contact, get_phenomenon_effects,
                                  resolve_asteroid_navigation,
                                  resolve_warp_rift_navigation,
                                  resolve_gas_dust_contact)


# ── check_ship_terrain_contact ────────────────────────────────────────────────

def test_ship_in_asteroid_field_detected():
    ship = make_ship(id="s", x=50, y=50)
    p = make_phenomenon("asteroid_field", x=50, y=50, width=20, height=20, radius=0)
    contacts = check_ship_terrain_contact(ship, [p])
    assert len(contacts) == 1
    assert contacts[0]["type"] == "asteroid_field"


def test_ship_clear_of_asteroid_no_contact():
    ship = make_ship(id="s", x=0, y=0)
    p = make_phenomenon("asteroid_field", x=100, y=100, width=10, height=10, radius=0)
    contacts = check_ship_terrain_contact(ship, [p])
    assert len(contacts) == 0


def test_ship_on_planet_detected():
    # Ship at (20,0), planet at (0,0) radius=20 → ship is in contact
    ship = make_ship(id="s", x=20, y=0)
    p = make_phenomenon("planet_small", x=0, y=0, radius=20)
    contacts = check_ship_terrain_contact(ship, [p])
    assert len(contacts) == 1


def test_ship_multiple_terrain_types():
    ship = make_ship(id="s", x=50, y=50)
    asteroid = make_phenomenon("asteroid_field", x=50, y=50, width=20, height=20,
                                radius=0, id="p1")
    dust = make_phenomenon("gas_dust_cloud", x=50, y=50, width=20, height=20,
                            radius=0, id="p2")
    contacts = check_ship_terrain_contact(ship, [asteroid, dust])
    assert len(contacts) == 2


# ── get_phenomenon_effects ────────────────────────────────────────────────────

def test_asteroid_field_effects():
    p = make_phenomenon("asteroid_field")
    e = get_phenomenon_effects(p)
    assert e["blocks_los"] is True
    assert e["navigation_test"] is True
    assert e["half_firepower"] is True
    assert e["max_fire_range"] == 10


def test_gas_dust_effects():
    p = make_phenomenon("gas_dust_cloud")
    e = get_phenomenon_effects(p)
    assert e["speed_reduction"] == 5
    assert e["shields_as_blast"] is True
    assert e["blocks_los"] is False


def test_warp_rift_effects():
    p = make_phenomenon("warp_rift")
    e = get_phenomenon_effects(p)
    assert e["blocks_los"] is True
    assert e["destroys_attack_craft"] is True
    assert e["damage_on_fail"] == "lost_in_warp"


def test_planet_effects():
    p = make_phenomenon("planet_small")
    e = get_phenomenon_effects(p)
    assert e["blocks_los"] is True
    assert e["blocks_torpedoes"] is True


# ── resolve_asteroid_navigation ───────────────────────────────────────────────

def test_asteroid_navigation_pass():
    ship = make_ship(id="s", leadership=8, ship_type="cruiser", shields_max=2, hits_max=8)
    gs = make_gs([ship])
    # 2D6 roll = 7 ≤ Ld 8 → pass
    r = resolve_asteroid_navigation(ship, DiceStub([3, 4]), gs)
    assert r["passed"] is True
    assert r["damage"] == 0


def test_asteroid_navigation_fail_takes_d6_damage():
    # Use shields_max=0 so damage goes directly to hull
    ship = make_ship(id="s", leadership=6, ship_type="cruiser",
                     shields_max=0, hits_max=8)
    gs = make_gs([ship])
    # 2D6 = 9 > Ld 6 → fail; then D6=4 damage
    r = resolve_asteroid_navigation(ship, DiceStub([4, 5, 4]), gs)
    assert r["passed"] is False
    assert r["damage"] == 4
    assert ship.hits_remaining == 4


def test_escort_rerolls_on_fail():
    # First roll fails, second succeeds
    ship = make_ship(id="s", leadership=6, ship_type="escort",
                     shields_max=2, hits_max=4)
    gs = make_gs([ship])
    # Roll 1: 2D6=9>6 fail; Roll 2: 2D6=5≤6 pass
    r = resolve_asteroid_navigation(ship, DiceStub([4, 5, 2, 3]), gs)
    assert r["passed"] is True


# ── resolve_warp_rift_navigation ──────────────────────────────────────────────

def test_warp_rift_pass_repositions():
    ship = make_ship(id="s", leadership=8, ship_type="cruiser",
                     x=50, y=50, hits_max=8)
    gs = make_gs([ship])
    # 3D6 = 3+1+2 = 6 ≤ Ld 8 → pass; then 2D6 × 10cm reposition
    r = resolve_warp_rift_navigation(ship, DiceStub([2, 2, 2, 3, 3]), gs)
    assert r["passed"] is True
    assert "new_position" in r


def test_warp_rift_fail_ship_lost():
    ship = make_ship(id="s", leadership=5, ship_type="cruiser",
                     x=50, y=50, hits_max=8)
    gs = make_gs([ship])
    # 3D6 = 6+6+6=18 > Ld 5 → fail
    r = resolve_warp_rift_navigation(ship, DiceStub([6, 6, 6]), gs)
    assert r["passed"] is False
    updated = gs.get_ship_by_id("s")
    assert updated.is_disengaged is True


# ── resolve_gas_dust_contact ──────────────────────────────────────────────────

def test_gas_dust_no_damage_with_shields():
    ship = make_ship(id="s", shields_max=2, hits_max=8)
    gs = make_gs([ship])
    # Ship has shields → no damage roll
    r = resolve_gas_dust_contact(ship, DiceStub([6]), gs)
    assert r["damage"] == 0
    assert r["speed_penalty"] == 5


def test_gas_dust_damage_on_6_with_no_shields():
    ship = make_ship(id="s", shields_max=0, hits_max=8)
    gs = make_gs([ship])
    r = resolve_gas_dust_contact(ship, DiceStub([6]), gs)
    assert r["damage"] == 1
    assert ship.hits_remaining == 7


def test_gas_dust_no_damage_on_non_6_without_shields():
    ship = make_ship(id="s", shields_max=0, hits_max=8)
    gs = make_gs([ship])
    r = resolve_gas_dust_contact(ship, DiceStub([5]), gs)
    assert r["damage"] == 0
    assert ship.hits_remaining == 8
