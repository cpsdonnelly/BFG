"""Tests for fleet_builder.fleet_list_to_ships — the tkinter-free converter."""
import json
import os
import sys
import tempfile
import unittest.mock

# Guard against headless environments: mock tkinter if not importable
try:
    import tkinter  # noqa: F401
except (ImportError, ModuleNotFoundError):
    for _mod in ["tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog"]:
        sys.modules.setdefault(_mod, unittest.mock.MagicMock())

from src.fleet_builder import fleet_list_to_ships  # noqa: E402 (after conditional mock)
from src.fleet_loader import export_fleet_with_damage, fleet_to_ships
from tests.conftest import make_ship


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


# ── export_fleet_with_damage ──────────────────────────────────────────────────

def test_export_fleet_with_damage_writes_json(tmp_path):
    s = make_ship(id="s1", player=1, hits_remaining=4,
                  ordnance_loaded_torps=False,
                  critical_damage=[{"effect": "Drive Damaged"}])
    fp = str(tmp_path / "campaign.json")
    export_fleet_with_damage([s], player=1, filepath=fp)
    assert os.path.exists(fp)
    with open(fp) as f:
        data = json.load(f)
    assert "ships" in data
    assert len(data["ships"]) == 1


def test_export_fleet_with_damage_includes_damage_fields(tmp_path):
    s = make_ship(id="s1", player=1, hits_remaining=4,
                  ordnance_loaded_torps=False,
                  critical_damage=[{"effect": "Drive Damaged"}])
    fp = str(tmp_path / "campaign.json")
    export_fleet_with_damage([s], player=1, filepath=fp)
    with open(fp) as f:
        entry = json.load(f)["ships"][0]
    assert entry["hits_remaining"] == 4
    assert entry["ordnance_loaded_torps"] is False
    assert entry["critical_damage"] == [{"effect": "Drive Damaged"}]


def test_export_fleet_with_damage_skips_destroyed(tmp_path):
    alive = make_ship(id="s1", player=1, hits_remaining=5)
    dead  = make_ship(id="s2", player=1, hits_remaining=0)
    fp = str(tmp_path / "campaign.json")
    export_fleet_with_damage([alive, dead], player=1, filepath=fp)
    with open(fp) as f:
        ships = json.load(f)["ships"]
    assert len(ships) == 1
    assert ships[0]["hits_remaining"] == 5


def test_export_fleet_with_damage_skips_other_player(tmp_path):
    s1 = make_ship(id="s1", player=1)
    s2 = make_ship(id="s2", player=2)
    fp = str(tmp_path / "campaign.json")
    export_fleet_with_damage([s1, s2], player=1, filepath=fp)
    with open(fp) as f:
        ships = json.load(f)["ships"]
    assert len(ships) == 1


# ── damage field round-trip through fleet_to_ships ────────────────────────────

_BASE_SHIP = {
    "id": "test-1", "name": "Battered",
    "ship_class": "Custom Ship", "faction": "imperial_navy_gothic",
    "ship_type": "cruiser", "base_size": "large",
    "hits_max": 8,
}


def test_fleet_to_ships_respects_hits_remaining():
    fleet = {"ships": [{**_BASE_SHIP, "hits_remaining": 3}]}
    ships = fleet_to_ships(fleet, player=1)
    assert ships[0].hits_remaining == 3


def test_fleet_to_ships_respects_critical_damage():
    fleet = {"ships": [{**_BASE_SHIP,
                        "critical_damage": [{"effect": "Drive Damaged"}]}]}
    ships = fleet_to_ships(fleet, player=1)
    assert ships[0].critical_damage == [{"effect": "Drive Damaged"}]


def test_fleet_to_ships_respects_ordnance_flags():
    fleet = {"ships": [{**_BASE_SHIP,
                        "ordnance_loaded_torps": False,
                        "ordnance_loaded_craft": False}]}
    ships = fleet_to_ships(fleet, player=1)
    assert ships[0].ordnance_loaded_torps is False
    assert ships[0].ordnance_loaded_craft is False
