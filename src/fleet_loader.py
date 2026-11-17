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
            "own_rerolls": s.own_rerolls,
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
            "ordnance_loaded_mines": s.ordnance_loaded_mines,
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
    from .ship_catalog import find_ship_class
    from .homebrew_catalog import get_homebrew_ship
    unofficial: List[str] = []
    for raw in fleet_data.get("ships", []):
        sc = raw.get("ship_class", "")
        if sc and not find_ship_class(sc) and not get_homebrew_ship(sc):
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


def roll_starting_leadership(gs, dice, ai_dice=None) -> List[str]:
    """Core rules s.3 / Appendix 4: before the game, each booklet ship rolls a
    D6 on its faction's Leadership column. Escorts roll once per squadron and
    share the result; capital ships always roll individually. Ships without a
    Leadership table (homebrew, older fleet files) keep their saved value.

    ai_dice: roller for AI-controlled ships (so the human isn't asked to roll
    for them in manual or mixed dice mode); defaults to `dice`.
    """
    from .booklet_ships import LEADERSHIP_TABLES
    groups: Dict[tuple, List[int]] = {}
    for i, s in enumerate(gs.ships):
        # Chaos Space Marine crews: the Astartes column, or +1 to a commander's
        # fixed Leadership (max 10) (Veterans of the Long War)
        if "csm_crew" in s.get("special_rules", []):
            if s.get("leadership_table"):
                s["leadership_table"] = "Astartes"
            elif s.get("leadership"):
                s["leadership"] = min(10, s["leadership"] + 1)
        if not s.get("leadership_table"):
            continue
        if s.get("ship_type") == "escort" and s.get("squadron_id"):
            key = (s["player"], "squadron", s["squadron_id"])
        else:
            key = (s["player"], "ship", s["id"])
        groups.setdefault(key, []).append(i)

    logs = []
    for (player, _, _), indices in groups.items():
        first = gs.ships[indices[0]]
        tables = [gs.ships[i]["leadership_table"] for i in indices]
        # Dominion: rapid strike vessels squadroned with Space Marine escorts use
        # the Space Marine table
        key = "Astartes" if "Astartes" in tables else first["leadership_table"]
        table = LEADERSHIP_TABLES.get(key, LEADERSHIP_TABLES["Default"])
        ai = gs.ai_spectator or gs.ai_player == player
        roller = ai_dice if (ai and ai_dice is not None) else dice
        names = ", ".join(gs.ships[i]["name"] for i in indices)
        roll = roller.roll_d6(1, f"Starting Leadership for {names} "
                                 f"({key} table)")[0]
        ld = table[roll - 1]
        # A Freebooter Kaptin adds +1 to the rolled Ld of the ship or
        # squadron he leads (owner ruling)
        # ... and a secondary commander adds +1 to a maximum ("ld_bonus:1:9")
        bonuses = [r.split(":") for i in indices
                   for r in gs.ships[i].get("special_rules", []) if r.startswith("ld_bonus:")]
        if bonuses:
            b = max(bonuses, key=lambda x: int(x[1]))
            cap = int(b[2]) if len(b) > 2 else 10
            ld = max(ld, min(cap, ld + int(b[1])))
        # Imperial Renegade cruisers subtract 1 from their rolled Leadership
        ld -= sum(-int(r.split(":")[1]) for i in indices[:1]
                  for r in gs.ships[i].get("special_rules", []) if r.startswith("ld_rolled:"))
        ld = max(0, ld)
        for i in indices:
            gs.ships[i]["leadership"] = ld
        logs.append(f"{names}: Leadership {ld} (rolled {roll})")
    # "+1 Ld at all times (max 10)": Sensors (Emperor, Oberon) and the grand
    # cruisers' Comms Uplink, added after the roll or a commander's own Ld
    for s in gs.ships:
        bonus = sum(int(r.split(":")[1]) for r in s.get("special_rules", [])
                    if r.startswith("ld_always:"))
        if bonus:
            s["leadership"] = min(10, s["leadership"] + bonus)
            logs.append(f"{s['name']}: Leadership {s['leadership']} (+{bonus} at all times)")
    return logs
