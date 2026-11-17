"""Tests for src/los.py — line-of-sight checking."""
from tests.conftest import make_ship, make_phenomenon, make_blast
from src.los import check_los, check_los_ships


# ── clear LoS ────────────────────────────────────────────────────────────────

def test_clear_los_no_phenomena():
    r = check_los(0, 0, 100, 0, phenomena=[], blast_markers=[])
    assert r["clear"] is True
    assert r["blocked_by"] is None
    assert r["column_shifts"] == 0


def test_check_los_ships_wrapper_clear():
    a = make_ship(id="a", x=0, y=0)
    t = make_ship(id="t", x=50, y=0)
    r = check_los_ships(a, t, phenomena=[])
    assert r["clear"] is True


# ── planet blocks LoS ────────────────────────────────────────────────────────

def test_planet_blocks_los():
    # Planet at (50, 0) radius 15 — directly on line from (0,0)→(100,0)
    p = make_phenomenon("planet_small", x=50, y=0, radius=15)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["clear"] is False
    assert "Planet" in (r["blocked_by"] or "")


def test_planet_off_line_does_not_block():
    # Planet well above the line
    p = make_phenomenon("planet_small", x=50, y=50, radius=10)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["clear"] is True


# ── asteroid field blocks LoS ─────────────────────────────────────────────────

def test_asteroid_field_blocks_los():
    # Asteroid at (50, 0), 20×20cm — straddles the line
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["clear"] is False
    assert "Asteroid" in (r["blocked_by"] or "")


def test_asteroid_field_off_line_clear():
    p = make_phenomenon("asteroid_field", x=50, y=40, width=20, height=20, radius=0)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["clear"] is True


# ── warp rift blocks LoS ──────────────────────────────────────────────────────

def test_warp_rift_blocks_los():
    p = make_phenomenon("warp_rift", x=50, y=0, width=20, height=20, radius=0)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["clear"] is False
    assert "Warp" in (r["blocked_by"] or "")


# ── gas/dust cloud causes shift but does not block ────────────────────────────

def test_gas_dust_does_not_block_los():
    p = make_phenomenon("gas_dust_cloud", x=50, y=0, width=20, height=20, radius=0)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["clear"] is True
    assert r["dust_clouds_crossed"] == 1
    assert r["column_shifts"] >= 1


def test_gas_dust_off_line_no_shift():
    p = make_phenomenon("gas_dust_cloud", x=50, y=50, width=10, height=10, radius=0)
    r = check_los(0, 0, 100, 0, phenomena=[p])
    assert r["column_shifts"] == 0


# ── blast markers cause shift (capped at +1) ──────────────────────────────────

def test_blast_marker_on_line_adds_shift():
    bm = make_blast(x=50, y=0, heading=0)
    r = check_los(0, 0, 100, 0, phenomena=[], blast_markers=[bm])
    assert r["blast_markers_crossed"] >= 1
    assert r["column_shifts"] >= 1


def test_blast_marker_far_from_line_no_shift():
    bm = make_blast(x=50, y=50)
    r = check_los(0, 0, 100, 0, phenomena=[], blast_markers=[bm])
    assert r["blast_markers_crossed"] == 0
    assert r["column_shifts"] == 0


def test_multiple_blast_markers_capped_at_one_shift():
    bm1 = make_blast(x=30, y=0, heading=0, bid="bm1")
    bm2 = make_blast(x=70, y=0, heading=0, bid="bm2")
    r = check_los(0, 0, 100, 0, phenomena=[], blast_markers=[bm1, bm2])
    # blast_markers_crossed may be 1 (capped by blast_crossed flag), shift also capped
    assert r["column_shifts"] == 1
