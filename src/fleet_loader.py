"""Fleet list loader — reads fleet JSON files and instantiates Ship objects."""
import json
import os
from typing import List, Dict, Optional

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
