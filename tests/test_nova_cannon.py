"""Tests for resolve_nova_cannon in src/combat.py."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import resolve_nova_cannon
from src.models import SpecialOrder


def _attacker():
    return make_ship(id="a", x=0, y=0, heading=0, ship_type="cruiser")


# ── restrictions ──────────────────────────────────────────────────────────────

def test_crippled_cannot_fire():
    a = make_ship(id="a", x=0, y=0, hits_max=8, hits_remaining=4)
    gs = make_gs([a])
    r = resolve_nova_cannon(a, 60, 0, DiceStub([1]), gs)
    assert "error" in r
    assert "crippled" in r["error"].lower()


def test_invalid_order_cannot_fire():
    a = _attacker()
    a.special_order = SpecialOrder.BURN_RETROS.value
    gs = make_gs([a])
    r = resolve_nova_cannon(a, 60, 0, DiceStub([1]), gs)
    assert "error" in r


def test_target_too_close_error():
    a = _attacker()
    gs = make_gs([a])
    # Target only 20cm away (min is 30cm)
    r = resolve_nova_cannon(a, 20, 0, DiceStub([1]), gs)
    assert "error" in r
    assert "range" in r["error"].lower()


def test_target_too_far_error():
    a = _attacker()
    gs = make_gs([a])
    r = resolve_nova_cannon(a, 160, 0, DiceStub([1]), gs)
    assert "error" in r


# ── hit (no scatter) ─────────────────────────────────────────────────────────

def test_direct_hit_template_stays_at_target():
    a = _attacker()
    gs = make_gs([a])
    # DiceStub([1]) → roll_scatter returns bool(1)=True → HIT (no scatter)
    r = resolve_nova_cannon(a, 60, 0, DiceStub([1]), gs)
    assert "error" not in r
    assert r["template_x"] == 60
    assert r["template_y"] == 0


def test_hit_with_no_ships_in_template_places_blast_marker():
    a = _attacker()
    gs = make_gs([a])
    r = resolve_nova_cannon(a, 60, 0, DiceStub([1]), gs)
    assert len(r["blast_markers"]) == 1


def test_hit_ship_in_template_ring_gives_one_auto_hit():
    a = _attacker()
    # Target ship very close to template center (60, 0) — in the outer ring
    t = make_ship(id="t", x=60, y=4, player=2, hits_max=8)
    gs = make_gs([a, t])
    # Hit (1 → True), then DiceStub cycling for D6 hits if needed
    r = resolve_nova_cannon(a, 60, 0, DiceStub([1, 3]), gs)
    assert "t" in r["ship_hits"]
    assert r["ship_hits"]["t"]["hits"] >= 1
    assert r["ship_hits"]["t"]["ignores_armor"] is True


# ── miss (scatter) ────────────────────────────────────────────────────────────

def test_miss_moves_template():
    a = _attacker()
    gs = make_gs([a])
    # roll_scatter(0) → bool(0)=False → miss; then scatter_roll for distance
    # At 60cm dist ≤ 60 → 2 scatter dice
    r = resolve_nova_cannon(a, 60, 0, DiceStub([0, 3, 4]), gs)
    # Template should have moved from (60,0) by scatter distance in direction 0.0°
    scatter_dist = 7  # 3+4
    assert abs(r["template_x"] - (60 + scatter_dist)) < 0.1
    assert r["scatter_distance"] == scatter_dist


# ── lock on (still allowed) ───────────────────────────────────────────────────

def test_lock_on_order_allowed():
    a = _attacker()
    a.special_order = SpecialOrder.LOCK_ON.value
    gs = make_gs([a])
    r = resolve_nova_cannon(a, 60, 0, DiceStub([1]), gs)
    assert "error" not in r
