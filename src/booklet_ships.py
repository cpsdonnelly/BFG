"""BFG:XR ship catalog built from the companion booklet (bfgxr/data/ships.json).

Converts each booklet roster row into the engine's ship class format. Ships
that use rules the engine can't play yet are still converted, with the reasons
listed in `unsupported`, so the fleet builder can show them greyed out.
Nothing here invents stats: every number comes from ships.json.
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple

SHIPS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "bfgxr", "data", "ships.json")

# Booklet faction -> (faction id, display name, Appendix 4 Leadership column).
# The Imperial Navy and Tau ids predate the booklet and are kept so saved
# fleets still match.
FACTIONS: Dict[str, Tuple[str, str, str]] = {
    "Imperial Navy": ("imperial_navy_gothic", "Imperial Navy", "Default"),
    "Adeptus Mechanicus": ("adeptus_mechanicus", "Adeptus Mechanicus", "Mechanicus"),
    "Space Marines": ("space_marines", "Space Marines", "Astartes"),
    "Inquisition & Grey Knights": ("inquisition_grey_knights", "Inquisition & Grey Knights", "Default"),
    "Rogue Traders": ("rogue_traders", "Rogue Traders", "Default"),
    "Support Assets": ("support_assets", "Support Assets", "Default"),
    "Chaos": ("chaos", "Chaos", "Default"),
    "Orks": ("orks", "Orks", "Orks"),
    "Tau & Allies": ("tau_kororvesh", "Tau & Allies", "Default"),
}

# Appendix 4 - Leadership Tables: D6 roll -> Leadership, per column.
LEADERSHIP_TABLES: Dict[str, List[int]] = {
    "Default":    [6, 7, 7, 8, 8, 9],
    "Mechanicus": [7, 8, 8, 9, 9, 9],
    "Astartes":   [8, 8, 9, 9, 10, 10],
    "Orks":       [5, 6, 6, 7, 7, 8],
    "Eldar":      [7, 8, 8, 9, 9, 10],
}

# Booklet weapon name -> engine weapon_type. Tau terms per the Tau faction rules:
# Railguns = macrobatteries, Ion Cannon = lance, Gravitic Launcher = missile launcher.
WEAPON_TYPES = {
    "Macrobatteries": "battery", "Macrobattery": "battery",
    "Railguns": "battery", "Railgun": "battery",
    "Lances": "lance", "Lance": "lance",
    "Ion Cannons": "lance", "Ion Cannon": "lance",
    "Torps": "torpedo", "Gravitic Launcher": "torpedo",
    # Ork faction rules: Gunz follow all the usual macrobattery rules; Heavy Gunz are
    # macrobatteries with a second firepower used within 15cm, e.g. FP6(10)
    "Gunz": "battery", "Heavy Gunz": "battery",
    "Nova Cannon": "nova_cannon",
}

ARC_CODES = {"L": ["left"], "R": ["right"], "F": ["front"], "Rear": ["rear"],
             "All Round": ["front", "left", "right", "rear"]}

# Attack craft: booklet code -> engine craft type, per faction where the faction
# rules name them (Imperial Navy: Fury, Starhawk, Shark; Tau: Barracuda, Manta).
_IN_CRAFT = {"ASF": "fury_fighter", "BMR": "starhawk_bomber", "AB": "shark_assault_boat"}
_TAU_CRAFT = {"ASF": "barracuda", "BMR": "manta"}
GENERIC_CRAFT = {"ASF": "fighter", "BMR": "bomber", "AB": "assault_boat"}


def _ship_type(row: dict) -> Optional[str]:
    """Engine hull type from the booklet's hull type, name or roster group."""
    hull = (row.get("hull_type") or "").lower()
    if hull:
        if "escort" in hull:
            return "escort"
        if "battleship" in hull:
            return "battleship"
        if "defen" in hull:
            return "defense"
        if "cruiser" in hull:
            return "cruiser"
    for text in (row["name"].lower(), (row.get("roster_group") or "").lower()):
        if "battleship" in text or "battle barge" in text:
            return "battleship"
        if "cruiser" in text or "kroozer" in text:
            return "cruiser"
        if "escort" in text or "frigate" in text or "destroyer" in text:
            return "escort"
        if "defen" in text:
            return "defense"
    return None


def _armour(row: dict) -> Optional[Tuple[str, str]]:
    a = row.get("armour")
    if not a or a.get("front") is None or a.get("other") is None:
        return None
    return f"{a['front']}+", f"{a['other']}+"


def _mount_name(weapon: dict, arcs: List[str], n_mounts: int) -> str:
    base = weapon["name"]
    if weapon.get("location"):
        return f"{weapon['location']} {base}"
    if n_mounts > 1 and arcs and arcs[0] == "L":
        return f"Port {base}"
    if n_mounts > 1 and arcs and arcs[0] == "R":
        return f"Starboard {base}"
    return base


def _convert_weapon(w: dict, craft_map: Dict[str, str],
                    problems: List[str]) -> List[dict]:
    if w["kind"] == "gravitic_hooks":
        return []   # tow escorts into battle: fleet building only, no battle effect
    if w["kind"] == "unparsed":
        problems.append(f"weapon not parsed: {w['raw']}")
        return []
    if w["kind"] == "launch_bays":
        out = []
        craft_types, speeds = [], {}
        for c in w["craft"]:
            ctype = craft_map.get(c["type"]) or GENERIC_CRAFT.get(c["type"])
            if not ctype:
                problems.append(f"{c['type']} attack craft not modelled yet")
                continue
            craft_types.append(ctype)
            speeds[ctype] = c["speed_cm"]
        for bay in w["bays"]:
            side = {"port": "Port", "stbd": "Starboard", "prow": "Prow",
                    "dorsal": "Dorsal"}.get(bay.get("side") or "", "")
            try:
                strength = int(bay["strength"])
            except (TypeError, ValueError):
                problems.append(f"launch bay strength {bay['strength']} not modelled yet")
                continue
            out.append({"name": f"{side} Launch Bays".strip(), "weapon_type": "launch_bay",
                        "range_cm": 30, "strength": strength, "arcs": [],
                        "craft_types": list(craft_types), "craft_speeds": dict(speeds),
                        "craft_speed": max(speeds.values()) if speeds else 0})
        return out

    wtype = WEAPON_TYPES.get(w["name"])
    if not wtype:
        problems.append(f"{w['name']} not modelled yet")
        return []
    if w.get("per_face") or w.get("per_quadrant") or w.get("group"):
        problems.append("fortress weapons not modelled yet")
        return []
    strength = w.get("value_int")
    strength_close = None
    if w["name"] == "Heavy Gunz":
        m = re.fullmatch(r"(\d+)\((\d+)\)", (w.get("value") or "").replace(" ", ""))
        if m:
            strength, strength_close = int(m.group(1)), int(m.group(2))
    strength_dice = None
    if strength is None and wtype in ("battery", "lance", "torpedo"):
        from .combat import is_dice_value, dice_value_average
        if is_dice_value(w.get("value") or ""):
            # Owner ruling: random Ork values are rolled when used
            strength_dice = w["value"].replace(" ", "").upper()
            strength = dice_value_average(strength_dice)
    if wtype != "nova_cannon" and strength is None:
        problems.append(f"variable firepower ({w['value']}) not modelled yet")
        return []

    mounts = w.get("mounts") or [{"arcs": ["F"]}]
    out = []
    for m in mounts:
        arcs = [a for code in m["arcs"] for a in ARC_CODES.get(code, [])]
        d = {"name": _mount_name(w, m["arcs"], len(mounts)), "weapon_type": wtype,
             "range_cm": w.get("range_max_cm") or 0, "strength": strength or 0,
             "arcs": arcs}
        if strength_close is not None:
            d["strength_close"] = strength_close   # firepower within 15cm
        if strength_dice:
            d["strength_dice"] = strength_dice     # rolled when used; strength = average
        if wtype == "nova_cannon":
            d.update(range_cm=w.get("range_max_cm") or 150,
                     min_range_cm=w.get("range_min_cm") or 30, strength=0)
        elif wtype == "torpedo":
            guided = w["name"] == "Gravitic Launcher"
            d["torpedo_type"] = "guided" if guided else "standard"
            d["torpedo_speed"] = w.get("range_max_cm") or 30
            if guided and w.get("range_min_cm"):
                d["torpedo_speed_min"] = w["range_min_cm"]
            if w.get("qualifier") and "boarding" in w["qualifier"]:
                d["boarding_torpedoes"] = True
        out.append(d)
    return out


def convert_row(row: dict) -> dict:
    """One booklet roster row -> keyword arguments for ShipClassEntry, plus
    'unsupported' (reasons the engine can't play it yet; empty if playable)."""
    faction_id, _, ld_table = FACTIONS.get(row["faction"],
                                           (row["faction"].lower(), row["faction"], "Default"))
    problems: List[str] = []

    ship_type = _ship_type(row)
    if not ship_type:
        problems.append("hull type not recognised")
    armour = _armour(row)
    if not armour:
        problems.append(f"armour profile {row.get('armour_raw')} not modelled yet")
    if row.get("speed_cm") is None or row.get("turn_deg") is None:
        problems.append(f"special movement ({row.get('speed_raw')}, "
                        f"{row.get('turn_raw')}) not modelled yet")
    if row.get("points") is None:
        problems.append(f"points cost '{row.get('points_raw')}' is not a fixed number")
    if not row["weapons"]:
        problems.append(f"no weapon profile ({row.get('armament_raw')})")

    if row["faction"] == "Imperial Navy":
        craft_map = _IN_CRAFT
    elif row["faction"] == "Tau & Allies" and "demiurg" not in (row.get("roster_group") or "").lower():
        craft_map = _TAU_CRAFT
    else:
        craft_map = {}
    weapons = [d for w in row["weapons"] for d in _convert_weapon(w, craft_map, problems)]

    notes = row.get("notes") or ""
    special_rules = ["ponderous"] if re.search(r"\bponderous\b", notes, re.I) else []
    if "towed" in (row.get("hull_type") or "").lower():
        special_rules.append("towed")

    return {
        "ship_class": row["name"],
        "faction": faction_id,
        "ship_type": ship_type or "cruiser",
        "base_size": "large" if row.get("base") == "60mm" else "small",
        "speed": row.get("speed_cm") or 0,
        "turn_angle": row.get("turn_deg") or 0,
        "shields_max": row.get("shields") or 0,
        "armor_prow": armour[0] if armour else "",
        "armor_side": armour[1] if armour else "",
        "turrets": row.get("turrets") or 0,
        "hits_max": row.get("hits") or 0,
        "leadership": 0,                 # rolled at game start (Appendix 4)
        "weapons": weapons,
        "special_rules": special_rules,
        "points_cost": row.get("points") or 0,
        "leadership_table": ld_table,
        "notes": "" if notes == "-" else notes,
        "source": row.get("source") or "",
        "unsupported": sorted(set(problems)),
    }


def load_rows(path: str = SHIPS_JSON) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["ships"]
