"""Tests for src/ship_catalog.py — ship classes built from the BFG:XR booklet."""
import json

from src.booklet_ships import SHIPS_JSON, LEADERSHIP_TABLES
from src.ship_catalog import (
    list_factions, get_faction_ships, get_ship_class, find_ship_class,
    get_upgrades_for_ship, faction_display_name,
)

BOOKLET = {r["name"]: r for r in json.load(open(SHIPS_JSON))["ships"]}


def _weapon(entry, name):
    return next(w for w in entry.weapons if w["name"] == name)


# ── Factions ─────────────────────────────────────────────────────────────────

def test_all_nine_booklet_factions_present():
    assert len(list_factions()) == 9
    assert "imperial_navy_gothic" in list_factions()      # id kept for saved fleets
    assert "tau_kororvesh" in list_factions()


def test_every_booklet_ship_is_in_the_catalog():
    total = sum(len(get_faction_ships(f, include_unsupported=True)) for f in list_factions())
    assert total == len(BOOKLET) == 174


def test_display_names_follow_the_booklet():
    assert faction_display_name("imperial_navy_gothic") == "Imperial Navy"
    assert faction_display_name("tau_kororvesh") == "Tau & Allies"
    assert faction_display_name("orks") == "Orks"
    assert faction_display_name("some_unknown_faction") == "Some Unknown Faction"


# ── Stats come straight from the booklet ─────────────────────────────────────

def test_lunar_stats_match_booklet():
    e = get_ship_class("imperial_navy_gothic", "Lunar Cruiser")
    b = BOOKLET["Lunar Cruiser"]
    assert (e.points_cost, e.hits_max, e.speed, e.turn_angle, e.shields_max, e.turrets) == \
        (b["points"], b["hits"], b["speed_cm"], b["turn_deg"], b["shields"], b["turrets"])
    assert (e.armor_prow, e.armor_side) == ("6+", "5+")
    assert (e.ship_type, e.base_size) == ("cruiser", "small")


def test_lunar_weapons_one_entry_per_mount():
    e = get_ship_class("imperial_navy_gothic", "Lunar Cruiser")
    assert _weapon(e, "Port Lances") == {"name": "Port Lances", "weapon_type": "lance",
                                         "range_cm": 30, "strength": 2, "arcs": ["left"]}
    assert _weapon(e, "Starboard Macrobatteries")["arcs"] == ["right"]
    torps = _weapon(e, "Prow Torps")
    assert (torps["weapon_type"], torps["strength"], torps["torpedo_speed"],
            torps["torpedo_type"], torps["arcs"]) == ("torpedo", 6, 30, "standard", ["front"])


def test_battleship_type_and_large_base():
    e = get_ship_class("imperial_navy_gothic", "Emperor Battleship")
    assert (e.ship_type, e.base_size) == ("battleship", "large")
    assert "ponderous" in e.special_rules


def test_carrier_launch_bays_use_imperial_craft_and_booklet_speeds():
    e = get_ship_class("imperial_navy_gothic", "Emperor Battleship")
    bays = [w for w in e.weapons if w["weapon_type"] == "launch_bay"]
    assert [b["name"] for b in bays] == ["Port Launch Bays", "Starboard Launch Bays"]
    assert bays[0]["strength"] == 4
    assert bays[0]["craft_speeds"]["fury_fighter"] == 30
    assert bays[0]["craft_speeds"]["starhawk_bomber"] == 20


def test_nova_cannon_conversion():
    e = get_ship_class("imperial_navy_gothic", "Apocalypse Battleship")
    nova = next(w for w in e.weapons if w["weapon_type"] == "nova_cannon")
    assert (nova["range_cm"], nova["min_range_cm"], nova["arcs"]) == (150, 30, ["front"])


def test_tau_terms_follow_tau_rules():
    e = get_ship_class("tau_kororvesh", "Custodian Battleship")
    assert _weapon(e, "Port Railguns")["weapon_type"] == "battery"       # Railguns = macrobatteries
    assert _weapon(e, "Port Railguns")["arcs"] == ["left", "front"]
    assert _weapon(e, "Port Ion Cannons")["weapon_type"] == "lance"      # Ion Cannon = lance
    launcher = _weapon(e, "Prow Gravitic Launcher")
    assert (launcher["torpedo_type"], launcher["torpedo_speed"],
            launcher.get("torpedo_speed_min")) == ("guided", 40, 20)
    bay = next(w for w in e.weapons if w["weapon_type"] == "launch_bay")
    assert bay["craft_speeds"] == {"manta": 20, "barracuda": 25}
    assert e.playable                                                    # gravitic hooks: no battle effect


def test_towed_escort_is_marked():
    e = get_ship_class("tau_kororvesh", "Warden Gunship")
    assert e.ship_type == "escort" and "towed" in e.special_rules and e.playable


def test_boarding_torpedo_option_is_kept():
    e = get_ship_class("space_marines", "Vanguard Cruiser")
    torps = next(w for w in e.weapons if w["weapon_type"] == "torpedo")
    assert torps.get("boarding_torpedoes") is True


# ── Old catalog names and owner rulings ──────────────────────────────────────

def test_old_catalog_names_still_resolve():
    assert get_ship_class("imperial_navy_gothic", "Gothic Class Cruiser").ship_class == "Gothic Cruiser"
    assert find_ship_class("Endeavour Class Light Cruiser").ship_class == "Endeavour Light Cruiser"


def test_hero_and_messenger_map_to_booklet_starships():
    assert find_ship_class("Hero Class Cruiser").ship_class == "Hero Starship"
    messenger = find_ship_class("Messenger Class Light Cruiser")
    assert (messenger.ship_class, messenger.ship_type) == ("Messenger Starship", "escort")


def test_wrong_faction_or_unknown_name_returns_none():
    assert get_ship_class("imperial_navy_gothic", "Custodian Battleship") is None
    assert find_ship_class("Nonexistent Class") is None
    assert get_faction_ships("made_up_faction") == []


# ── Unsupported ships are listed with reasons ────────────────────────────────

def test_ork_ships_listed_with_reasons_when_not_playable():
    # Gunz and Heavy Gunz are playable; dice-based firepower is not yet
    assert sorted(e.ship_class for e in get_faction_ships("orks")) == [
        "Brute Ramship", "Grunt Assault Ship", "Savage Gunship"]
    orks = get_faction_ships("orks", include_unsupported=True)
    assert len(orks) == 15
    blocked = [e for e in orks if not e.playable]
    assert len(blocked) == 12 and all(e.unsupported for e in blocked)
    reasons = {r for e in orks for r in e.unsupported}
    assert "Gunz not modelled yet" not in reasons
    assert "Heavy Gunz not modelled yet" not in reasons
    assert "Zzapp Gunz not modelled yet" in reasons        # crude lances, own rules
    assert any("variable firepower (D6+6)" in r for e in orks for r in e.unsupported)


def test_every_playable_ship_has_complete_stats():
    for f in list_factions():
        for e in get_faction_ships(f):
            assert e.ship_type in ("battleship", "cruiser", "escort", "defense"), e.ship_class
            assert e.speed > 0 and e.turn_angle > 0 and e.hits_max > 0, e.ship_class
            assert e.armor_prow.endswith("+") and e.armor_side.endswith("+"), e.ship_class
            assert e.weapons, e.ship_class


# ── Leadership and upgrades ──────────────────────────────────────────────────

def test_leadership_is_rolled_on_the_faction_table():
    assert get_ship_class("imperial_navy_gothic", "Lunar Cruiser").leadership_table == "Default"
    assert get_faction_ships("adeptus_mechanicus")[0].leadership_table == "Mechanicus"
    assert get_faction_ships("space_marines")[0].leadership_table == "Astartes"
    assert get_faction_ships("orks", True)[0].leadership_table == "Orks"
    assert LEADERSHIP_TABLES["Default"] == [6, 7, 7, 8, 8, 9]


def test_to_ship_dict_carries_leadership_table_and_booklet_points():
    e = get_ship_class("imperial_navy_gothic", "Lunar Cruiser")
    d = e.to_ship_dict(name="INS Test", player=1)
    assert (d["ship_class"], d["points_value"], d["leadership"], d["leadership_table"]) == \
        ("Lunar Cruiser", 180, 0, "Default")


def test_booklet_ships_have_no_upgrades_yet():
    assert get_upgrades_for_ship(get_ship_class("imperial_navy_gothic", "Lunar Cruiser")) == []


def test_old_defense_spelling_still_resolves():
    from src.ship_catalog import find_ship_class
    e = find_ship_class("Defense Monitor")
    assert e is not None and e.ship_class == "Defence Monitor"
