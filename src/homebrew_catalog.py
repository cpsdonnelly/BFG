"""BFG:XR Homebrew Catalog — persistence layer for custom ship classes."""
import glob
import json
import os
from typing import List, Optional

from .ship_catalog import ShipClassEntry, UpgradeEntry

# Resolved relative to this file's location (src/), two levels up → project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOMEBREW_DIR = os.path.join(_PROJECT_ROOT, "data", "homebrew")


def _entry_from_dict(d: dict) -> ShipClassEntry:
    upgrades = [
        UpgradeEntry(
            name=u["name"],
            description=u.get("description", ""),
            points_cost=u.get("points_cost", 0),
            effect=u.get("effect", {}),
            restrictions=u.get("restrictions", []),
        )
        for u in d.get("upgrades_available", [])
    ]
    rules = list(d.get("special_rules", []))
    if "homebrew" not in rules:
        rules.append("homebrew")
    return ShipClassEntry(
        ship_class=d["ship_class"],
        faction=d.get("faction", "homebrew"),
        ship_type=d.get("ship_type", "cruiser"),
        base_size=d.get("base_size", "small"),
        speed=int(d.get("speed", 20)),
        turn_angle=int(d.get("turn_angle", 45)),
        shields_max=int(d.get("shields_max", 2)),
        armor_prow=str(d.get("armor_prow", "6+")),
        armor_side=str(d.get("armor_side", "5+")),
        turrets=int(d.get("turrets", 2)),
        hits_max=int(d.get("hits_max", 8)),
        leadership=int(d.get("leadership", 7)),
        weapons=list(d.get("weapons", [])),
        special_rules=rules,
        upgrades_available=upgrades,
        points_cost=int(d.get("points_cost", 0)),
    )


def load_homebrew_catalog() -> List[ShipClassEntry]:
    """Load all homebrew ship definitions from data/homebrew/."""
    entries: List[ShipClassEntry] = []
    if not os.path.isdir(_HOMEBREW_DIR):
        return entries
    for path in sorted(glob.glob(os.path.join(_HOMEBREW_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            entries.append(_entry_from_dict(d))
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    return entries


def get_homebrew_ship(ship_class: str) -> Optional[ShipClassEntry]:
    """Look up a homebrew ship by class name. Returns None if not found."""
    for entry in load_homebrew_catalog():
        if entry.ship_class == ship_class:
            return entry
    return None


def save_homebrew_ship(entry: ShipClassEntry) -> str:
    """Persist a homebrew ShipClassEntry to data/homebrew/. Returns the saved path."""
    os.makedirs(_HOMEBREW_DIR, exist_ok=True)
    filename = entry.ship_class.replace(" ", "_").replace("/", "-") + ".json"
    path = os.path.join(_HOMEBREW_DIR, filename)
    data = {
        "ship_class":   entry.ship_class,
        "faction":      entry.faction,
        "homebrew":     True,
        "ship_type":    entry.ship_type,
        "base_size":    entry.base_size,
        "speed":        entry.speed,
        "turn_angle":   entry.turn_angle,
        "shields_max":  entry.shields_max,
        "armor_prow":   entry.armor_prow,
        "armor_side":   entry.armor_side,
        "turrets":      entry.turrets,
        "hits_max":     entry.hits_max,
        "leadership":   entry.leadership,
        "weapons":      list(entry.weapons),
        "special_rules": [r for r in entry.special_rules if r != "homebrew"],
        "upgrades_available": [
            {
                "name":        u.name,
                "description": u.description,
                "points_cost": u.points_cost,
                "effect":      u.effect,
                "restrictions": u.restrictions,
            }
            for u in entry.upgrades_available
        ],
        "points_cost": entry.points_cost,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path
