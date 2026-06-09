"""Fleet list loader — reads fleet JSON files and instantiates Ship objects."""
import datetime
import json
import os
from typing import List, Dict

from .models import Ship

# Keys in fleet JSON that are fleet-file-specific, not Ship dataclass fields.
# spawn_* position keys get mapped to the Ship's x/y/heading fields.
_SPAWN_KEY_MAP = {
    "spawn_x": "x",
    "spawn_y": "y",
    "spawn_heading": "heading",
}

# All keys that must be stripped before passing to Ship(**d).
_FLEET_ONLY_KEYS = set(_SPAWN_KEY_MAP.keys())

# Ship dataclass field names (determined at import time from the class signature).
_SHIP_FIELDS: set = {
    f for f in Ship.__dataclass_fields__  # type: ignore[attr-defined]
}


def load_fleet_file(path: str) -> dict:
    """Load and return raw fleet JSON as a dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fleet_to_ships(fleet_data: dict, player: int) -> List[Ship]:
    """
    Convert a loaded fleet dict into a list of Ship objects assigned to `player`.

    Fleet JSON may contain spawn_x/spawn_y/spawn_heading keys that map to the
    Ship's x/y/heading fields.  Any other unrecognised keys are silently dropped
    so that forward-compatible fleet files don't crash the loader.
    """
    ships: List[Ship] = []
    for raw in fleet_data.get("ships", []):
        d: dict = {}

        # Map spawn_* → x/y/heading; keep the rest if they are real Ship fields.
        for k, v in raw.items():
            if k in _SPAWN_KEY_MAP:
                d[_SPAWN_KEY_MAP[k]] = v
            elif k in _SHIP_FIELDS:
                d[k] = v
            # Drop unrecognised fleet-file-only keys silently.

        d["player"] = player
        ships.append(Ship(**d))

    return ships


def export_fleet_with_damage(ships: List["Ship"], player: int, filepath: str) -> None:
    """Export a fleet JSON including current damage state for campaign/scenario use."""
    fleet_ships = []
    for s in ships:
        if s.player != player or s.is_destroyed:
            continue
        entry: Dict = {
            "ship_class": s.ship_class,
            "name": s.name,
            "faction": s.faction,
            "is_flagship": s.is_flagship,
            "admiral_type": s.admiral_type,
            "rerolls_remaining": s.rerolls_remaining,
            "squadron_id": s.squadron_id,
            "spawn_x": s.x,
            "spawn_y": s.y,
            "spawn_heading": s.heading,
            "points_value": s.points_value,
            "upgrades": list(s.upgrades),
            "weapons": list(s.weapons),
            "special_rules": list(s.special_rules),
            # Damage state
            "hits_remaining": s.hits_remaining,
            "critical_damage": list(s.critical_damage),
            "ordnance_loaded_torps": s.ordnance_loaded_torps,
            "ordnance_loaded_craft": s.ordnance_loaded_craft,
        }
        fleet_ships.append(entry)
    data = {
        "fleet_name": f"Campaign Fleet (Player {player})",
        "exported": datetime.datetime.now().isoformat(timespec="seconds"),
        "ships": fleet_ships,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def find_unofficial_ships(fleet_data: dict) -> List[str]:
    """Return ship_class names in fleet_data that are not in the official or homebrew catalog."""
    from .ship_catalog import get_ship_class
    from .homebrew_catalog import get_homebrew_ship
    unofficial: List[str] = []
    for raw in fleet_data.get("ships", []):
        sc = raw.get("ship_class", "")
        if sc and not get_ship_class(sc) and not get_homebrew_ship(sc):
            unofficial.append(sc)
    return unofficial


def get_available_fleets(fleets_dir: str = "data/fleets") -> List[str]:
    """Return sorted list of absolute paths to all .json fleet files in fleets_dir."""
    if not os.path.isdir(fleets_dir):
        return []
    return sorted(
        os.path.join(fleets_dir, fn)
        for fn in os.listdir(fleets_dir)
        if fn.endswith(".json")
    )


def get_fleet_info(path: str) -> Dict[str, str]:
    """Return a summary dict with fleet_name, faction, description, total_points."""
    try:
        data = load_fleet_file(path)
    except (OSError, json.JSONDecodeError):
        return {"fleet_name": os.path.basename(path), "faction": "unknown",
                "description": "", "total_points": "?"}
    return {
        "fleet_name": data.get("fleet_name", os.path.basename(path)),
        "faction": data.get("faction", "unknown"),
        "description": data.get("description", ""),
        "total_points": str(data.get("total_points", "?")),
    }
