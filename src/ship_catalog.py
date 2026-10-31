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
            if "add_special_rule" in u.effect:
                d["special_rules"].append(u.effect["add_special_rule"])
            if "add_weapon" in u.effect:
                d["weapons"].append(u.effect["add_weapon"].copy())
            if "stat_delta" in u.effect:
                for stat, delta in u.effect["stat_delta"].items():
                    if stat in d:
                        d[stat] += delta

        return d


# ---------------------------------------------------------------------------
# Catalog registry, built from the booklet
# ---------------------------------------------------------------------------

def _build_catalogs() -> Dict[str, List[ShipClassEntry]]:
    from .booklet_ships import FACTIONS, convert_row, load_rows
    catalogs: Dict[str, List[ShipClassEntry]] = {fid: [] for fid, _, _ in FACTIONS.values()}
    for row in load_rows():
        entry = ShipClassEntry(**convert_row(row))
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
    return _ALIASES.get(ship_class, ship_class.replace(" Class ", " "))


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
