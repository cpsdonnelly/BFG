"""BFG:XR Ship Catalog — ship classes for the fleet builder, built from the
BFG:XR companion booklet (bfgxr/data/ships.json) by booklet_ships.py."""
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Upgrade entry
# ---------------------------------------------------------------------------

@dataclass
class UpgradeEntry:
    name: str
    description: str
    points_cost: int
    # How the upgrade modifies the ship. Keys may include:
    #   "add_special_rule": str  — appended to special_rules list
    #   "add_weapon": dict       — appended to weapons list
    #   "stat_delta": {field: delta}  — e.g. {"shields_max": 1}
    effect: Dict = field(default_factory=dict)
    # Optional restrictions: "flagship_only", "cruiser_only", "escort_only", etc.
    restrictions: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ship class entry
# ---------------------------------------------------------------------------

@dataclass
class ShipClassEntry:
    ship_class: str
    faction: str
    ship_type: str       # ShipType value: battleship / cruiser / escort / defense
    base_size: str       # BaseSize value: small / large

    speed: int
    turn_angle: int
    shields_max: int
    armor_prow: str      # e.g. "6+", "5+"
    armor_side: str
    turrets: int
    hits_max: int
    leadership: int

    weapons: List[Dict] = field(default_factory=list)
    special_rules: List[str] = field(default_factory=list)
    upgrades_available: List[UpgradeEntry] = field(default_factory=list)
    points_cost: int = 0   # base hull cost before upgrades
    # Booklet ships: Leadership is rolled at game start on this Appendix 4 column
    # (leadership == 0 until then). Empty for homebrew / fixed-Ld ships.
    leadership_table: str = ""
    notes: str = ""                 # booklet Notes cell: special rules, refits, options
    source: str = ""                # sourcebook page reference
    unsupported: List[str] = field(default_factory=list)   # why it can't be played yet
    armor_rear: str = ""            # third Armour value (front/abeam/rear), if any

    @property
    def playable(self) -> bool:
        return not self.unsupported

    def to_ship_dict(self, name: str, player: int, ship_id: Optional[str] = None,
                     upgrades: Optional[List[str]] = None,
                     is_flagship: bool = False,
                     admiral_type: str = "",
                     rerolls_remaining: int = 0,
                     spawn_x: float = 0.0,
                     spawn_y: float = 0.0,
                     spawn_heading: float = 90.0) -> dict:
        """
        Produce a Ship-compatible dict for this class with instance-specific fields.
        Applies any listed upgrades by name from upgrades_available.
        """
        d = {
            "id": ship_id or str(uuid.uuid4())[:8],
            "name": name,
            "ship_class": self.ship_class,
            "faction": self.faction,
            "player": player,
            "ship_type": self.ship_type,
            "base_size": self.base_size,
            "x": spawn_x,
            "y": spawn_y,
            "heading": spawn_heading,
            "speed": self.speed,
            "turn_angle": self.turn_angle,
            "shields_max": self.shields_max,
            "armor_prow": self.armor_prow,
            "armor_side": self.armor_side,
            "armor_rear": self.armor_rear,
            "turrets": self.turrets,
            "hits_max": self.hits_max,
            "leadership": self.leadership,
            "leadership_table": self.leadership_table,
            "weapons": [w.copy() for w in self.weapons],
            "special_rules": list(self.special_rules),
            "upgrades": list(upgrades or []),
            "points_value": self.points_cost,
            "is_flagship": is_flagship,
            "admiral_type": admiral_type,
            "rerolls_remaining": rerolls_remaining,
        }

        upgrade_map = {u.name: u for u in self.upgrades_available}
        for uname in (upgrades or []):
            u = upgrade_map.get(uname)
            if not u:
                continue
            d["points_value"] += u.points_cost
            apply_upgrade_effect(d, u.effect)

        return d



def apply_upgrade_effect(d: dict, effect: dict) -> None:
    """Apply one option's effect to a ship dict (fleet building, and gifts
    rolled at game start such as Vault of Technology)."""
    if "add_special_rule" in effect:
        d["special_rules"].append(effect["add_special_rule"])
    d["special_rules"] += list(effect.get("add_special_rules", []))
    gone = set(effect.get("remove_special_rules", []))
    d["special_rules"] = [r for r in d["special_rules"] if r not in gone]
    if "remove_weapons" in effect:
        gone = set(effect["remove_weapons"])
        d["weapons"] = [w for w in d["weapons"] if w.get("name") not in gone]
    for mod in effect.get("modify_weapons", []):
        # {"match": {"name": ..., "range_cm": ...}, "set": {...}}: change the
        # weapons matching every key (Mercury and Tyrant have two weapons
        # of one name at different ranges)
        # ("name_prefix" matches the start of the name; "add" adds to a value)
        for w in d["weapons"]:
            if all((w.get("name", "").startswith(v) if k == "name_prefix" else w.get(k) == v)
                   for k, v in mod["match"].items()):
                w.update(mod.get("set", {}))
                for k, v in mod.get("add", {}).items():
                    w[k] = w.get(k, 0) + v
    for ctype, speed in effect.get("add_craft", {}).items():
        # "Attack craft: AB 30cm +5pts": the launch bays may also carry it
        for w in d["weapons"]:
            if w.get("weapon_type") == "launch_bay" and ctype not in w.get("craft_types", []):
                w["craft_types"] = list(w.get("craft_types", [])) + [ctype]
                w["craft_speeds"] = {**w.get("craft_speeds", {}), ctype: speed}
                w["craft_speed"] = max(w["craft_speeds"].values())
    if effect.get("set_craft"):
        # every launch bay carries only these craft (Stormbird gunships)
        for w in d["weapons"]:
            if w.get("weapon_type") == "launch_bay":
                w["craft_types"] = list(effect["set_craft"])
                w["craft_speeds"] = dict(effect["set_craft"])
                w["craft_speed"] = max(effect["set_craft"].values())
    if effect.get("halve_bays"):
        for w in d["weapons"]:
            if w.get("weapon_type") == "launch_bay":
                w["strength"] = (w.get("strength", 0) + 1) // 2
    for old, (new, speed) in effect.get("swap_craft", {}).items():
        # one craft type replaced by another in every launch bay (Tiger Sharks)
        for w in d["weapons"]:
            if w.get("weapon_type") == "launch_bay" and old in w.get("craft_types", []):
                w["craft_types"] = [new if c == old else c for c in w["craft_types"]]
                sp = {k: v for k, v in w.get("craft_speeds", {}).items() if k != old}
                sp[new] = speed
                w["craft_speeds"] = sp
                w["craft_speed"] = max(sp.values())
    if "add_weapon" in effect:
        d["weapons"].append(effect["add_weapon"].copy())
    d["weapons"] += [w.copy() for w in effect.get("add_weapons", [])]
    if "stat_delta" in effect:
        for stat, delta in effect["stat_delta"].items():
            if stat in d:
                d[stat] += delta
    d.update(effect.get("set", {}))
    if effect.get("rerolls"):
        d["rerolls_remaining"] = max(d["rerolls_remaining"], effect["rerolls"])
    if effect.get("flagship"):
        d["is_flagship"] = True


# ---------------------------------------------------------------------------
# Catalog registry, built from the booklet
# ---------------------------------------------------------------------------

def _build_catalogs() -> Dict[str, List[ShipClassEntry]]:
    from .booklet_ships import FACTIONS, convert_row, load_rows, venerable_strike_cruiser_rows
    catalogs: Dict[str, List[ShipClassEntry]] = {fid: [] for fid, _, _ in FACTIONS.values()}
    from .booklet_options import options_for
    rows = load_rows()
    for row in rows + venerable_strike_cruiser_rows(rows):
        kw = convert_row(row)
        kw["upgrades_available"] = [UpgradeEntry(**o) for o in options_for(row)]
        entry = ShipClassEntry(**kw)
        catalogs.setdefault(entry.faction, []).append(entry)
    return catalogs


_CATALOGS: Dict[str, List[ShipClassEntry]] = _build_catalogs()

# Names used by the old hand-written catalog (and saved fleets) -> booklet names.
# Other old names differ only by " Class " (e.g. "Gothic Class Cruiser").
_ALIASES = {
    "Hero Class Cruiser": "Hero Starship",
    "Messenger Class Light Cruiser": "Messenger Starship",
}


def _canonical(ship_class: str) -> str:
    # The booklet spells "Defence" (British) since its second update
    name = ship_class.replace("Defense", "Defence")
    return _ALIASES.get(name, name.replace(" Class ", " "))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_factions() -> List[str]:
    """Return all faction identifiers present in the catalog."""
    return list(_CATALOGS.keys())


def get_faction_ships(faction: str, include_unsupported: bool = False) -> List[ShipClassEntry]:
    """Ship classes for a faction (playable only unless include_unsupported)."""
    return [e for e in _CATALOGS.get(faction, []) if include_unsupported or e.playable]


def get_ship_class(faction: str, ship_class: str) -> Optional[ShipClassEntry]:
    """Look up a ship class by name within a faction (old catalog names work too).
    Returns unsupported classes as well; check entry.playable."""
    wanted = {ship_class, _canonical(ship_class)}
    for entry in _CATALOGS.get(faction, []):
        if entry.ship_class in wanted:
            return entry
    return None


def find_ship_class(ship_class: str) -> Optional[ShipClassEntry]:
    """Look up a ship class by name in any faction."""
    for faction in _CATALOGS:
        entry = get_ship_class(faction, ship_class)
        if entry:
            return entry
    return None


def get_upgrades_for_ship(entry: ShipClassEntry) -> List[UpgradeEntry]:
    """Upgrades available to a ship class. Booklet ships have none yet: their
    refits and options are prose in entry.notes, to be added one at a time."""
    return list(entry.upgrades_available)


def faction_display_name(faction: str) -> str:
    """Human-readable name for a faction identifier."""
    from .booklet_ships import FACTIONS
    for fid, display, _ in FACTIONS.values():
        if fid == faction:
            return display
    return faction.replace("_", " ").title()
