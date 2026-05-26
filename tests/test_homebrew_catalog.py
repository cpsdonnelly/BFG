"""Tests for src/homebrew_catalog.py — save, load, get."""
import json
import os
import pytest
from src.homebrew_catalog import load_homebrew_catalog, get_homebrew_ship, save_homebrew_ship
from src.ship_catalog import ShipClassEntry


def _minimal_entry(ship_class: str = "Test Cruiser") -> ShipClassEntry:
    return ShipClassEntry(
        ship_class=ship_class,
        faction="homebrew",
        ship_type="cruiser",
        base_size="small",
        speed=20,
        turn_angle=45,
        shields_max=2,
        armor_prow="6+",
        armor_side="5+",
        turrets=2,
        hits_max=8,
        leadership=7,
        weapons=[],
        special_rules=["homebrew"],
        upgrades_available=[],
        points_cost=150,
    )


@pytest.fixture
def patched_homebrew_dir(tmp_path, monkeypatch):
    """Redirect the homebrew catalog to a temp directory."""
    import src.homebrew_catalog as hbc
    monkeypatch.setattr(hbc, "_HOMEBREW_DIR", str(tmp_path))
    return tmp_path


# ── save_homebrew_ship ────────────────────────────────────────────────────────

def test_save_creates_json_file(patched_homebrew_dir):
    entry = _minimal_entry("Rogue Cruiser")
    path = save_homebrew_ship(entry)
    assert os.path.exists(path)
    assert path.endswith(".json")


def test_save_strips_homebrew_from_special_rules(patched_homebrew_dir):
    entry = _minimal_entry("Rogue Cruiser")
    path = save_homebrew_ship(entry)
    with open(path) as f:
        data = json.load(f)
    assert "homebrew" not in data["special_rules"]


def test_save_stores_correct_fields(patched_homebrew_dir):
    entry = _minimal_entry("My Test Ship")
    path = save_homebrew_ship(entry)
    with open(path) as f:
        data = json.load(f)
    assert data["ship_class"] == "My Test Ship"
    assert data["speed"] == 20
    assert data["points_cost"] == 150


def test_save_spaces_replaced_with_underscore_in_filename(patched_homebrew_dir):
    entry = _minimal_entry("Heavy Cruiser Alpha")
    path = save_homebrew_ship(entry)
    assert "Heavy_Cruiser_Alpha" in os.path.basename(path)


# ── load_homebrew_catalog ─────────────────────────────────────────────────────

def test_load_empty_dir_returns_empty_list(patched_homebrew_dir):
    entries = load_homebrew_catalog()
    assert entries == []


def test_load_returns_saved_entry(patched_homebrew_dir):
    entry = _minimal_entry("Leviathan Class")
    save_homebrew_ship(entry)
    entries = load_homebrew_catalog()
    assert len(entries) == 1
    assert entries[0].ship_class == "Leviathan Class"


def test_load_adds_homebrew_to_special_rules(patched_homebrew_dir):
    entry = _minimal_entry("Ghost Ship")
    save_homebrew_ship(entry)
    entries = load_homebrew_catalog()
    assert "homebrew" in entries[0].special_rules


def test_load_multiple_entries(patched_homebrew_dir):
    for name in ["Alpha", "Beta", "Gamma"]:
        save_homebrew_ship(_minimal_entry(name))
    entries = load_homebrew_catalog()
    assert len(entries) == 3
    names = {e.ship_class for e in entries}
    assert names == {"Alpha", "Beta", "Gamma"}


def test_load_ignores_invalid_json(patched_homebrew_dir, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json{{{")
    entries = load_homebrew_catalog()
    assert entries == []


# ── get_homebrew_ship ─────────────────────────────────────────────────────────

def test_get_homebrew_ship_found(patched_homebrew_dir):
    save_homebrew_ship(_minimal_entry("Unique Vessel"))
    result = get_homebrew_ship("Unique Vessel")
    assert result is not None
    assert result.ship_class == "Unique Vessel"


def test_get_homebrew_ship_not_found(patched_homebrew_dir):
    result = get_homebrew_ship("Nonexistent Ship")
    assert result is None
