"""Tests for src/ordnance.py — pure helper functions."""
import math
from tests.conftest import make_ship, make_torp
from src.ordnance import get_massed_turret_bonus, check_torpedo_contact
from src.geometry import BASE_CONTACT_MARGIN_CM


# ── get_massed_turret_bonus ───────────────────────────────────────────────────

def test_no_allies_gives_zero_bonus():
    s = make_ship(x=0, y=0)
    assert get_massed_turret_bonus(s, [s]) == 0


def test_one_ally_in_base_contact():
    defender = make_ship(id="d", x=0, y=0, base_size="small")   # radius 1.6
    # Ally placed so edge-to-edge distance ≤ BASE_CONTACT_MARGIN_CM
    contact_dist = defender.base_radius + defender.base_radius + BASE_CONTACT_MARGIN_CM - 0.1
    ally = make_ship(id="a", player=1, x=contact_dist, y=0)
    assert get_massed_turret_bonus(defender, [defender, ally]) == 1


def test_ally_too_far_gives_zero():
    defender = make_ship(id="d", x=0, y=0)
    far_ally = make_ship(id="a", player=1, x=50, y=0)
    assert get_massed_turret_bonus(defender, [defender, far_ally]) == 0


def test_crippled_ally_does_not_contribute():
    defender = make_ship(id="d", x=0, y=0)
    # Crippled ally in base contact
    contact_dist = defender.base_radius * 2 + BASE_CONTACT_MARGIN_CM - 0.1
    crippled_ally = make_ship(id="a", player=1, x=contact_dist, y=0,
                               hits_max=8, hits_remaining=4)
    assert crippled_ally.is_crippled
    assert get_massed_turret_bonus(defender, [defender, crippled_ally]) == 0


def test_enemy_ship_does_not_contribute():
    defender = make_ship(id="d", player=1, x=0, y=0)
    enemy = make_ship(id="e", player=2, x=1.0, y=0)
    assert get_massed_turret_bonus(defender, [defender, enemy]) == 0


def test_bonus_capped_at_three():
    defender = make_ship(id="d", x=0, y=0)
    contact_dist = defender.base_radius * 2 + BASE_CONTACT_MARGIN_CM - 0.1
    allies = [
        make_ship(id=f"a{i}", player=1, x=contact_dist, y=float(i) * 0.01)
        for i in range(5)
    ]
    assert get_massed_turret_bonus(defender, [defender] + allies) == 3


def test_destroyed_ally_does_not_contribute():
    defender = make_ship(id="d", x=0, y=0)
    contact_dist = defender.base_radius * 2 + BASE_CONTACT_MARGIN_CM - 0.1
    dead_ally = make_ship(id="a", player=1, x=contact_dist, y=0, hits_remaining=0)
    assert get_massed_turret_bonus(defender, [defender, dead_ally]) == 0


# ── check_torpedo_contact ─────────────────────────────────────────────────────

def test_torpedo_contacts_ship_ahead():
    # Ship at origin (radius 1.6); torpedo heading west (180°) approaching from east
    ship = make_ship(x=0, y=0, base_size="small")
    # Torpedo body half-height along heading = 0.5cm; place it just touching
    torp = make_torp(x=2.0, y=0, heading=180)
    assert check_torpedo_contact(torp, ship)


def test_torpedo_far_from_ship():
    ship = make_ship(x=0, y=0)
    torp = make_torp(x=50, y=50, heading=0)
    assert not check_torpedo_contact(torp, ship)


def test_torpedo_exactly_at_ship_position():
    ship = make_ship(x=10, y=10)
    torp = make_torp(x=10, y=10, heading=0)
    assert check_torpedo_contact(torp, ship)
