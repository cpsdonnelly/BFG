"""Tests for src/ship_catalog.py — static ship class registry."""
from src.ship_catalog import (
    list_factions,
    get_faction_ships,
    get_ship_class,
    get_upgrades_for_ship,
    faction_display_name,
    ShipClassEntry,
)


# ── list_factions ─────────────────────────────────────────────────────────────

def test_list_factions_nonempty():
    factions = list_factions()
    assert len(factions) >= 2


def test_list_factions_contains_imperial():
    assert "imperial_navy_gothic" in list_factions()


def test_list_factions_contains_tau():
    assert "tau_kororvesh" in list_factions()


# ── get_faction_ships ─────────────────────────────────────────────────────────

def test_get_faction_ships_imperial_nonempty():
    ships = get_faction_ships("imperial_navy_gothic")
    assert len(ships) > 0


def test_get_faction_ships_tau_nonempty():
    ships = get_faction_ships("tau_kororvesh")
    assert len(ships) > 0


def test_get_faction_ships_unknown_returns_empty():
    assert get_faction_ships("made_up_faction") == []


def test_get_faction_ships_returns_ship_class_entries():
    ships = get_faction_ships("imperial_navy_gothic")
    assert all(isinstance(s, ShipClassEntry) for s in ships)


def test_imperial_catalog_has_lunar():
    classes = [s.ship_class for s in get_faction_ships("imperial_navy_gothic")]
    assert "Lunar Class Cruiser" in classes


def test_tau_catalog_has_custodian():
    classes = [s.ship_class for s in get_faction_ships("tau_kororvesh")]
    assert "Custodian Class Battleship" in classes


# ── get_ship_class ────────────────────────────────────────────────────────────

def test_get_ship_class_found():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    assert entry is not None
    assert entry.ship_class == "Lunar Class Cruiser"


def test_get_ship_class_stats_correct():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    assert entry.speed == 20
    assert entry.hits_max == 8
    assert entry.shields_max == 2
    assert entry.leadership == 7
    assert entry.points_cost == 180


def test_get_ship_class_not_found_returns_none():
    assert get_ship_class("imperial_navy_gothic", "Nonexistent Class") is None


def test_get_ship_class_wrong_faction_returns_none():
    # Custodian exists in tau catalog, not imperial
    assert get_ship_class("imperial_navy_gothic", "Custodian Class Battleship") is None


def test_get_ship_class_tau_found():
    entry = get_ship_class("tau_kororvesh", "Custodian Class Battleship")
    assert entry is not None
    assert entry.ship_type == "battleship"


# ── to_ship_dict ──────────────────────────────────────────────────────────────

def test_to_ship_dict_basic_fields():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("Sword of Terra", player=1)
    assert d["name"] == "Sword of Terra"
    assert d["player"] == 1
    assert d["ship_class"] == "Lunar Class Cruiser"
    assert d["faction"] == "imperial_navy_gothic"
    assert d["speed"] == 20
    assert d["points_value"] == 180


def test_to_ship_dict_spawn_position():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=2, spawn_x=50, spawn_y=75, spawn_heading=270)
    assert d["x"] == 50
    assert d["y"] == 75
    assert d["heading"] == 270


def test_to_ship_dict_upgrade_adds_cost():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=1, upgrades=["Targeting Matrix"])
    assert d["points_value"] == 180 + 10


def test_to_ship_dict_upgrade_adds_special_rule():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=1, upgrades=["Targeting Matrix"])
    assert "targeting_matrix" in d["special_rules"]


def test_to_ship_dict_unknown_upgrade_ignored():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=1, upgrades=["Nonexistent Upgrade"])
    assert d["points_value"] == 180   # no change


def test_to_ship_dict_flagship():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=1, is_flagship=True,
                            admiral_type="vice_admiral", rerolls_remaining=1)
    assert d["is_flagship"] is True
    assert d["admiral_type"] == "vice_admiral"
    assert d["rerolls_remaining"] == 1


def test_to_ship_dict_id_generated():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=1)
    assert "id" in d and len(d["id"]) > 0


def test_to_ship_dict_weapons_copied():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    d = entry.to_ship_dict("X", player=1)
    assert len(d["weapons"]) == len(entry.weapons)
    # Mutations to the dict copy must not affect the catalog entry
    d["weapons"].clear()
    assert len(entry.weapons) > 0


# ── get_upgrades_for_ship ─────────────────────────────────────────────────────

def test_get_upgrades_for_ship_nonempty():
    entry = get_ship_class("imperial_navy_gothic", "Lunar Class Cruiser")
    upgrades = get_upgrades_for_ship(entry)
    assert len(upgrades) > 0


def test_get_upgrades_for_ship_escort():
    entry = get_ship_class("imperial_navy_gothic", "Cobra Class Destroyer")
    upgrades = get_upgrades_for_ship(entry)
    names = [u.name for u in upgrades]
    assert "Reinforced Prow" in names


# ── faction_display_name ──────────────────────────────────────────────────────

def test_display_name_imperial():
    assert faction_display_name("imperial_navy_gothic") == "Imperial Navy (Gothic)"


def test_display_name_tau():
    assert faction_display_name("tau_kororvesh") == "Tau Kor'or'vesh"


def test_display_name_unknown_titlecases():
    result = faction_display_name("some_unknown_faction")
    assert isinstance(result, str)
    assert len(result) > 0
