"""Tests for src/end_phase.py — fire damage, damage control, blast removal."""
from tests.conftest import make_ship, make_gs, make_blast, DiceStub
from src.end_phase import (resolve_fire_damage, resolve_damage_control,
                            get_repair_info, apply_repair_choices,
                            remove_blast_markers, remove_brace_orders,
                            resolve_hulk_drift)
from src.models import SpecialOrder


# ── resolve_fire_damage ───────────────────────────────────────────────────────

def test_fire_crit_deals_one_damage():
    ship = make_ship(id="s", shields_max=0, hits_max=8, hits_remaining=8,
                     critical_damage=[{"crit_type": "fire", "description": "Fire!",
                                       "repairable": True}])
    gs = make_gs([ship])
    logs = resolve_fire_damage(ship, DiceStub([1]), gs)
    assert ship.hits_remaining == 7
    assert any("fire" in l.lower() for l in logs)


def test_no_fire_crit_no_damage():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "engine_room",
                                       "description": "Engine Room",
                                       "repairable": True}])
    gs = make_gs([ship])
    logs = resolve_fire_damage(ship, DiceStub([1]), gs)
    assert ship.hits_remaining == 8
    assert logs == []


def test_two_fires_deal_two_damage():
    ship = make_ship(id="s", shields_max=0, hits_max=8, hits_remaining=8,
                     critical_damage=[
                         {"crit_type": "fire", "description": "Fire! 1", "repairable": True},
                         {"crit_type": "fire", "description": "Fire! 2", "repairable": True},
                     ])
    gs = make_gs([ship])
    resolve_fire_damage(ship, DiceStub([1]), gs)
    assert ship.hits_remaining == 6


# ── resolve_damage_control ────────────────────────────────────────────────────

def test_damage_control_six_repairs_crit():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "engine_room",
                                       "description": "Engine Room",
                                       "repairable": True}])
    gs = make_gs([ship])
    # 8 dice rolls; need a 6
    dice = DiceStub([1, 1, 1, 1, 1, 1, 1, 6])
    resolve_damage_control(ship, dice, gs)
    assert ship.critical_damage == []


def test_damage_control_no_six_no_repair():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "engine_room",
                                       "description": "Engine Room",
                                       "repairable": True}])
    gs = make_gs([ship])
    dice = DiceStub([1, 2, 3, 4, 5, 4, 3, 2])  # no 6s
    resolve_damage_control(ship, dice, gs)
    assert len(ship.critical_damage) == 1


def test_damage_control_with_repair_choices():
    crits = [
        {"crit_type": "engine_room", "description": "Engine Room", "repairable": True},
        {"crit_type": "fire", "description": "Fire!", "repairable": True},
    ]
    ship = make_ship(id="s", shields_max=0, hits_max=8, critical_damage=crits)
    gs = make_gs([ship])
    # 2 sixes = 2 repairs available; player picks Fire! first
    dice = DiceStub([6, 6, 1, 1, 1, 1])
    resolve_damage_control(ship, dice, gs, repair_choices=["Fire!"])
    remaining = [c["description"] for c in ship.critical_damage]
    assert "Fire!" not in remaining


def test_damage_control_halved_by_blast_marker():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "fire", "description": "Fire!",
                                       "repairable": True}])
    gs = make_gs([ship])
    # Place blast marker touching the ship (at ship position)
    bm = make_blast(x=0.0, y=0.0)
    gs.add_blast_marker(bm)
    dice = DiceStub([6])  # only 1 die rolled (halved from 8, rounded up = 4; but first 6 repairs)
    logs = resolve_damage_control(ship, dice, gs)
    assert any("halved" in l.lower() or "blast" in l.lower() for l in logs)


# ── get_repair_info ───────────────────────────────────────────────────────────

def test_get_repair_info_returns_sixes_count():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "fire", "description": "Fire!",
                                       "repairable": True}])
    gs = make_gs([ship])
    info = get_repair_info(ship, DiceStub([6, 1, 1, 1, 1, 1, 1, 1]), gs)
    assert info["sixes"] == 1
    assert "Fire!" in info["repairable"]


def test_get_repair_info_no_crits_returns_empty():
    ship = make_ship(id="s", shields_max=0, hits_max=8, critical_damage=[])
    gs = make_gs([ship])
    info = get_repair_info(ship, DiceStub([6]), gs)
    assert info["sixes"] == 0
    assert info["repairable"] == []


# ── apply_repair_choices ──────────────────────────────────────────────────────

def test_apply_repair_choices_removes_crit():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "fire", "description": "Fire!",
                                       "repairable": True}])
    gs = make_gs([ship])
    apply_repair_choices(ship, ["Fire!"], gs)
    assert ship.critical_damage == []


def test_apply_repair_choices_ignores_non_repairable():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     critical_damage=[{"crit_type": "bridge_smashed",
                                       "description": "Bridge Smashed",
                                       "repairable": False}])
    gs = make_gs([ship])
    apply_repair_choices(ship, ["Bridge Smashed"], gs)
    assert len(ship.critical_damage) == 1  # still there


# ── remove_blast_markers ──────────────────────────────────────────────────────

def test_remove_blast_markers_removes_free_markers():
    gs = make_gs([])
    # Place 3 blast markers far from any ship
    for i in range(3):
        gs.add_blast_marker(make_blast(x=float(100 + i*10), y=100, bid=f"bm{i}"))
    dice = DiceStub([3])  # roll 3 → remove 3
    remove_blast_markers(gs, dice)
    assert len(gs.blast_markers) == 0


def test_remove_blast_markers_leaves_ship_touching():
    ship = make_ship(id="s", x=50, y=50, hits_max=8)
    gs = make_gs([ship])
    # Blast marker at ship position (touching)
    gs.add_blast_marker(make_blast(x=50, y=50, bid="bm_touch"))
    # Free marker far away
    gs.add_blast_marker(make_blast(x=0, y=0, bid="bm_free"))
    dice = DiceStub([6])  # remove up to 6 free markers
    remove_blast_markers(gs, dice)
    # The free one should be gone, the touching one should remain
    remaining_ids = [b["id"] for b in gs.blast_markers]
    assert "bm_touch" in remaining_ids
    assert "bm_free" not in remaining_ids


# ── remove_brace_orders ───────────────────────────────────────────────────────

def test_remove_brace_orders_expires_old_brace():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     special_order=SpecialOrder.BRACE_FOR_IMPACT.value,
                     brace_set_on_turn=1)
    gs = make_gs([ship])
    gs.turn_number = 2  # brace was set on turn 1, now it's turn 2 → expire
    logs = remove_brace_orders(gs)
    updated = gs.get_ship_by_id("s")
    assert updated.special_order != SpecialOrder.BRACE_FOR_IMPACT.value


def test_remove_brace_orders_keeps_brace_set_this_turn():
    ship = make_ship(id="s", shields_max=0, hits_max=8,
                     special_order=SpecialOrder.BRACE_FOR_IMPACT.value,
                     brace_set_on_turn=2)
    gs = make_gs([ship])
    gs.turn_number = 2  # brace set this turn → persists
    remove_brace_orders(gs)
    updated = gs.get_ship_by_id("s")
    assert updated.special_order == SpecialOrder.BRACE_FOR_IMPACT.value


def test_remove_brace_clears_brace_failed_vs():
    ship = make_ship(id="s", shields_max=0, hits_max=8, brace_failed_vs=["enemy1"])
    gs = make_gs([ship])
    remove_brace_orders(gs)
    updated = gs.get_ship_by_id("s")
    assert updated.brace_failed_vs == []


# ── resolve_hulk_drift ────────────────────────────────────────────────────────

def test_hulk_drift_moves_forward():
    ship = make_ship(id="s", x=50, y=50, heading=0, status="drifting_hulk",
                     ship_type="cruiser", hits_max=8)
    ship.status = "drifting_hulk"
    gs = make_gs([ship])
    gs.ships[0]["status"] = "drifting_hulk"
    dice = DiceStub([3, 3, 3, 3, 5])  # 4D6 drift = 12cm; then 2d6 if burning
    resolve_hulk_drift(gs, dice)
    updated = gs.get_ship_by_id("s")
    assert updated.x > 50  # moved in heading 0 direction


def test_burning_hulk_rerrolls_catastrophic():
    ship = make_ship(id="s", x=50, y=50, heading=0, status="burning_hulk",
                     ship_type="cruiser", hits_max=8)
    gs = make_gs([ship])
    gs.ships[0]["status"] = "burning_hulk"
    # 4D6 drift, then 2D6 for catastrophic re-roll → 6 = drifting_hulk (fire burns out)
    dice = DiceStub([2, 2, 2, 2, 6])
    resolve_hulk_drift(gs, dice)
    updated = gs.get_ship_by_id("s")
    # Roll 6 is < 7 → drifting_hulk range (2-6)
    assert updated.status == "drifting_hulk"
