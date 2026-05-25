"""Tests for fleet_builder.fleet_list_to_ships — the tkinter-free converter."""
import sys
import unittest.mock

# Guard against headless environments: mock tkinter if not importable
try:
    import tkinter  # noqa: F401
except (ImportError, ModuleNotFoundError):
    for _mod in ["tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog"]:
        sys.modules.setdefault(_mod, unittest.mock.MagicMock())

from src.fleet_builder import fleet_list_to_ships  # noqa: E402 (after conditional mock)


# ── catalog path ─────────────────────────────────────────────────────────────

def test_catalog_ship_gets_stats_from_catalog():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{
            "ship_class": "Lunar Class Cruiser",
            "name": "Sword of Terra",
            "upgrades": [], "is_flagship": False,
            "spawn_x": 10, "spawn_y": 20, "spawn_heading": 90,
        }]
    }
    result = fleet_list_to_ships(fleet, player=1)
    assert len(result) == 1
    s = result[0]
    assert s["name"] == "Sword of Terra"
    assert s["player"] == 1
    assert s["speed"] == 20      # from catalog, not raw dict
    assert s["hits_max"] == 8


def test_catalog_ship_player_set_correctly():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{"ship_class": "Lunar Class Cruiser", "name": "X"}],
    }
    result = fleet_list_to_ships(fleet, player=2)
    assert result[0]["player"] == 2


def test_catalog_ship_upgrades_applied():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{
            "ship_class": "Lunar Class Cruiser",
            "name": "X",
            "upgrades": ["Targeting Matrix"],
        }],
    }
    result = fleet_list_to_ships(fleet, player=1)
    assert "targeting_matrix" in result[0]["special_rules"]
    assert result[0]["points_value"] == 180 + 10


# ── fall-through path ─────────────────────────────────────────────────────────

def test_unknown_ship_class_uses_raw_stats():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{
            "ship_class": "Unknown Prototype XR-7",
            "name": "Prototype",
            "speed": 99,
            "hits_max": 25,
        }],
    }
    result = fleet_list_to_ships(fleet, player=1)
    assert len(result) == 1
    assert result[0]["speed"] == 99
    assert result[0]["hits_max"] == 25


def test_unknown_ship_player_injected():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{"ship_class": "Mystery Ship", "name": "M"}],
    }
    result = fleet_list_to_ships(fleet, player=2)
    assert result[0]["player"] == 2


def test_unknown_ship_id_generated_if_missing():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{"ship_class": "Ghost Frigate"}],
    }
    result = fleet_list_to_ships(fleet, player=1)
    assert "id" in result[0] and result[0]["id"]


# ── spawn key mapping ─────────────────────────────────────────────────────────

def test_spawn_keys_mapped_to_game_keys_catalog():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{
            "ship_class": "Lunar Class Cruiser",
            "name": "X",
            "spawn_x": 55, "spawn_y": 77, "spawn_heading": 270,
        }],
    }
    result = fleet_list_to_ships(fleet, player=1)
    s = result[0]
    assert s["x"] == 55
    assert s["y"] == 77
    assert s["heading"] == 270


def test_spawn_keys_mapped_to_game_keys_fallthrough():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [{
            "ship_class": "Custom Ship",
            "spawn_x": 10, "spawn_y": 20, "spawn_heading": 45,
        }],
    }
    result = fleet_list_to_ships(fleet, player=1)
    s = result[0]
    assert s["x"] == 10
    assert s["y"] == 20
    assert s["heading"] == 45
    assert "spawn_x" not in s


# ── edge cases ────────────────────────────────────────────────────────────────

def test_empty_fleet_returns_empty_list():
    fleet = {"faction": "imperial_navy_gothic", "ships": []}
    assert fleet_list_to_ships(fleet, player=1) == []


def test_missing_faction_still_works():
    fleet = {
        "ships": [{"ship_class": "Unknown Ship", "speed": 10}],
    }
    result = fleet_list_to_ships(fleet, player=1)
    assert len(result) == 1
    assert result[0]["speed"] == 10


def test_multiple_ships_all_returned():
    fleet = {
        "faction": "imperial_navy_gothic",
        "ships": [
            {"ship_class": "Lunar Class Cruiser", "name": "Alpha"},
            {"ship_class": "Gothic Class Cruiser", "name": "Beta"},
        ],
    }
    result = fleet_list_to_ships(fleet, player=1)
    assert len(result) == 2
    names = [s["name"] for s in result]
    assert "Alpha" in names
    assert "Beta" in names
