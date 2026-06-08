"""BFG:XR Ship Catalog — Static ship class definitions for the fleet builder."""
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
# Imperial Navy — upgrades
# ---------------------------------------------------------------------------

_IN_UPGRADES_CRUISER = [
    UpgradeEntry(
        name="Targeting Matrix",
        description="+1 to hit on Lock On orders (re-roll misses once per weapon).",
        points_cost=10,
        effect={"add_special_rule": "targeting_matrix"},
    ),
    UpgradeEntry(
        name="Extra Armour",
        description="Side armour improved by one step (e.g. 5+ → 4+).",
        points_cost=15,
        effect={"stat_delta": {}},   # handled via special rule
    ),
    UpgradeEntry(
        name="Prow Torpedoes (refit)",
        description="Replace prow weapon with strength-6 torpedo salvo.",
        points_cost=0,
        effect={},
        restrictions=["lunar_only"],
    ),
]

_IN_UPGRADES_ESCORT = [
    UpgradeEntry(
        name="Reinforced Prow",
        description="Prow armour 5+ → 4+ for this escort.",
        points_cost=5,
        effect={"add_special_rule": "reinforced_prow"},
    ),
]

_IN_UPGRADES_FLAGSHIP = [
    UpgradeEntry(
        name="Rear Admiral",
        description="Fleet commander: +1 Ld to self, 1 re-roll per game.",
        points_cost=50,
        effect={"add_special_rule": "admiral_rear"},
        restrictions=["flagship_only"],
    ),
    UpgradeEntry(
        name="Vice Admiral",
        description="Fleet commander: +1 Ld to all IN ships within 15cm, 1 re-roll.",
        points_cost=75,
        effect={"add_special_rule": "admiral_vice"},
        restrictions=["flagship_only"],
    ),
    UpgradeEntry(
        name="Full Admiral",
        description="Fleet commander: +2 Ld to all IN ships within 30cm, 2 re-rolls.",
        points_cost=100,
        effect={"add_special_rule": "admiral_full"},
        restrictions=["flagship_only"],
    ),
]


# ---------------------------------------------------------------------------
# Imperial Navy — ship classes
# ---------------------------------------------------------------------------

_IN = "imperial_navy_gothic"

IMPERIAL_NAVY_CATALOG: List[ShipClassEntry] = [

    # ── Battleships ──────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Emperor Class Battleship",
        faction=_IN, ship_type="battleship", base_size="large",
        speed=20, turn_angle=45,
        shields_max=6, armor_prow="5+", armor_side="5+",
        turrets=4, hits_max=12, leadership=8,
        points_cost=365,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 60, "strength": 8,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 60, "strength": 8,  "arcs": ["right"]},
            {"name": "Port Launch Bays",           "weapon_type": "launch_bay","range_cm": 30, "strength": 3,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Starboard Launch Bays",      "weapon_type": "launch_bay","range_cm": 30, "strength": 3,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Dorsal Lance Battery",       "weapon_type": "lance",     "range_cm": 60, "strength": 2,  "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Retribution Class Battleship",
        faction=_IN, ship_type="battleship", base_size="large",
        speed=15, turn_angle=45,
        shields_max=4, armor_prow="5+", armor_side="6+",
        turrets=4, hits_max=12, leadership=8,
        points_cost=345,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 60, "strength": 10, "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 60, "strength": 10, "arcs": ["right"]},
            {"name": "Prow Weapons Battery",       "weapon_type": "battery",   "range_cm": 30, "strength": 6,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Apocalypse Class Battleship",
        faction=_IN, ship_type="battleship", base_size="large",
        speed=20, turn_angle=45,
        shields_max=4, armor_prow="6+", armor_side="5+",
        turrets=4, hits_max=12, leadership=8,
        points_cost=340,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 8,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 8,  "arcs": ["right"]},
            {"name": "Port Nova Cannon",           "weapon_type": "nova_cannon","range_cm": 150,"strength": 0,  "arcs": ["front"]},
            {"name": "Starboard Nova Cannon",      "weapon_type": "nova_cannon","range_cm": 150,"strength": 0,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    # ── Battlecruisers ────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Mars Class Battlecruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=8,
        points_cost=220,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["right"]},
            {"name": "Port Launch Bays",           "weapon_type": "launch_bay","range_cm": 30, "strength": 2,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Starboard Launch Bays",      "weapon_type": "launch_bay","range_cm": 30, "strength": 2,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Prow Nova Cannon",           "weapon_type": "nova_cannon","range_cm": 150,"strength": 0,  "arcs": ["front"]},
            {"name": "Dorsal Lance Battery",       "weapon_type": "lance",     "range_cm": 60, "strength": 2,  "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Overlord Class Battlecruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=8,
        points_cost=220,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 60, "strength": 6,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 60, "strength": 6,  "arcs": ["right"]},
            {"name": "Dorsal Lance Battery",       "weapon_type": "lance",     "range_cm": 60, "strength": 4,  "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    # ── Cruisers ──────────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Lunar Class Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=7,
        points_cost=180,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["right"]},
            {"name": "Prow Torpedoes",             "weapon_type": "torpedo",   "range_cm": 30, "strength": 6,  "arcs": ["front"]},
            {"name": "Dorsal Lance Battery",       "weapon_type": "lance",     "range_cm": 60, "strength": 2,  "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Gothic Class Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=7,
        points_cost=180,
        weapons=[
            {"name": "Port Lance Battery",        "weapon_type": "lance",     "range_cm": 60, "strength": 2,  "arcs": ["left"]},
            {"name": "Starboard Lance Battery",    "weapon_type": "lance",     "range_cm": 60, "strength": 2,  "arcs": ["right"]},
            {"name": "Prow Torpedoes",             "weapon_type": "torpedo",   "range_cm": 30, "strength": 6,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Dictator Class Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=3, hits_max=8, leadership=7,
        points_cost=220,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["right"]},
            {"name": "Port Launch Bays",           "weapon_type": "launch_bay","range_cm": 30, "strength": 2,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber", "shark_assault_boat"], "craft_speed": 30},
            {"name": "Starboard Launch Bays",      "weapon_type": "launch_bay","range_cm": 30, "strength": 2,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber", "shark_assault_boat"], "craft_speed": 30},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Tyrant Class Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=7,
        points_cost=175,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 60, "strength": 8,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 60, "strength": 8,  "arcs": ["right"]},
            {"name": "Prow Torpedoes",             "weapon_type": "torpedo",   "range_cm": 30, "strength": 4,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Dominator Class Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=7,
        points_cost=190,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 6,  "arcs": ["right"]},
            {"name": "Prow Nova Cannon",           "weapon_type": "nova_cannon","range_cm": 150,"strength": 0,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    # ── Light Cruisers ────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Endeavour Class Light Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=25, turn_angle=45,
        shields_max=1, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=6, leadership=7,
        points_cost=110,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 4,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 4,  "arcs": ["right"]},
            {"name": "Prow Torpedoes",             "weapon_type": "torpedo",   "range_cm": 30, "strength": 3,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Endurance Class Light Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=25, turn_angle=45,
        shields_max=1, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=6, leadership=7,
        points_cost=115,
        weapons=[
            {"name": "Port Weapons Battery",      "weapon_type": "battery",   "range_cm": 45, "strength": 4,  "arcs": ["left"]},
            {"name": "Starboard Weapons Battery",  "weapon_type": "battery",   "range_cm": 45, "strength": 4,  "arcs": ["right"]},
            {"name": "Port Launch Bays",           "weapon_type": "launch_bay","range_cm": 30, "strength": 1,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Starboard Launch Bays",      "weapon_type": "launch_bay","range_cm": 30, "strength": 1,  "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Dauntless Class Light Cruiser",
        faction=_IN, ship_type="cruiser", base_size="small",
        speed=25, turn_angle=45,
        shields_max=1, armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=6, leadership=7,
        points_cost=110,
        weapons=[
            {"name": "Port Lance Battery",        "weapon_type": "lance",     "range_cm": 30, "strength": 1,  "arcs": ["left"]},
            {"name": "Starboard Lance Battery",    "weapon_type": "lance",     "range_cm": 30, "strength": 1,  "arcs": ["right"]},
            {"name": "Prow Torpedoes",             "weapon_type": "torpedo",   "range_cm": 30, "strength": 3,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_FLAGSHIP + _IN_UPGRADES_CRUISER,
    ),

    # ── Escorts ───────────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Sword Class Frigate",
        faction=_IN, ship_type="escort", base_size="small",
        speed=30, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=1, hits_max=1, leadership=7,
        points_cost=40,
        weapons=[
            {"name": "Weapons Battery",           "weapon_type": "battery",   "range_cm": 30, "strength": 2,  "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_ESCORT,
    ),

    ShipClassEntry(
        ship_class="Firestorm Class Frigate",
        faction=_IN, ship_type="escort", base_size="small",
        speed=30, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=1, hits_max=1, leadership=7,
        points_cost=40,
        weapons=[
            {"name": "Prow Lance",                "weapon_type": "lance",     "range_cm": 30, "strength": 1,  "arcs": ["front"]},
            {"name": "Weapons Battery",           "weapon_type": "battery",   "range_cm": 30, "strength": 1,  "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_ESCORT,
    ),

    ShipClassEntry(
        ship_class="Cobra Class Destroyer",
        faction=_IN, ship_type="escort", base_size="small",
        speed=30, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=1, hits_max=1, leadership=7,
        points_cost=30,
        weapons=[
            {"name": "Prow Torpedoes",            "weapon_type": "torpedo",   "range_cm": 30, "strength": 3,  "arcs": ["front"]},
        ],
        special_rules=[],
        upgrades_available=_IN_UPGRADES_ESCORT,
    ),
]


# ---------------------------------------------------------------------------
# Tau Kor'or'vesh — upgrades
# ---------------------------------------------------------------------------

_TAU_UPGRADES_CRUISER = [
    UpgradeEntry(
        name="Kor'O Commander",
        description="Tau fleet admiral: +1 Ld to all Tau ships within 20cm, 2 re-rolls.",
        points_cost=100,
        effect={"add_special_rule": "kor_o"},
        restrictions=["flagship_only"],
    ),
    UpgradeEntry(
        name="Kor'el Commander",
        description="Tau squadron commander: +1 Ld to self, 1 re-roll per game.",
        points_cost=50,
        effect={"add_special_rule": "kor_el"},
        restrictions=["flagship_only"],
    ),
    UpgradeEntry(
        name="Tracking Systems +20cm",
        description="All weapons gain +20cm range.",
        points_cost=20,
        effect={"add_special_rule": "tracking_systems_20"},
    ),
    UpgradeEntry(
        name="Extra Deflector",
        description="Improved deflector field; +1 shield save.",
        points_cost=15,
        effect={"stat_delta": {"shields_max": 1}},
    ),
]

_TAU_UPGRADES_ESCORT = [
    UpgradeEntry(
        name="Gravitic Hook",
        description="This escort can be towed by a capital ship at no movement cost.",
        points_cost=5,
        effect={"add_special_rule": "gravitic_hook"},
    ),
]


# ---------------------------------------------------------------------------
# Tau Kor'or'vesh — ship classes
# ---------------------------------------------------------------------------

_TAU = "tau_kororvesh"

TAU_CATALOG: List[ShipClassEntry] = [

    # ── Battleships ──────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Custodian Class Battleship",
        faction=_TAU, ship_type="battleship", base_size="large",
        speed=20, turn_angle=45,
        shields_max=3, armor_prow="6+", armor_side="5+",
        turrets=4, hits_max=10, leadership=9,
        points_cost=425,
        weapons=[
            {"name": "Port Railgun Battery",      "weapon_type": "battery",        "range_cm": 45, "strength": 6, "arcs": ["left", "front"]},
            {"name": "Starboard Railgun Battery",  "weapon_type": "battery",        "range_cm": 45, "strength": 6, "arcs": ["right", "front"]},
            {"name": "Port Ion Cannon",            "weapon_type": "lance",          "range_cm": 45, "strength": 1, "arcs": ["left", "front"]},
            {"name": "Starboard Ion Cannon",       "weapon_type": "lance",          "range_cm": 45, "strength": 1, "arcs": ["right", "front"]},
            {"name": "Port Launch Bays",           "weapon_type": "launch_bay",     "range_cm": 25, "strength": 3, "arcs": [], "craft_types": ["manta", "barracuda"], "craft_speed": 25},
            {"name": "Starboard Launch Bays",      "weapon_type": "launch_bay",     "range_cm": 25, "strength": 3, "arcs": [], "craft_types": ["manta", "barracuda"], "craft_speed": 25},
            {"name": "Prow Gravitic Launcher",     "weapon_type": "torpedo",          "range_cm": 40,"strength": 8, "arcs": ["front"], "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
        special_rules=["ponderous", "deflector", "tracking_systems_20"],
        upgrades_available=_TAU_UPGRADES_CRUISER,
    ),

    # ── Cruisers ──────────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Hero Class Cruiser",
        faction=_TAU, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="5+", armor_side="5+",
        turrets=3, hits_max=8, leadership=8,
        points_cost=275,
        weapons=[
            {"name": "Port Railgun Battery",      "weapon_type": "battery",        "range_cm": 45, "strength": 6, "arcs": ["left", "front"]},
            {"name": "Starboard Railgun Battery",  "weapon_type": "battery",        "range_cm": 45, "strength": 6, "arcs": ["right", "front"]},
            {"name": "Port Ion Cannon",            "weapon_type": "lance",          "range_cm": 45, "strength": 2, "arcs": ["left", "front"]},
            {"name": "Starboard Ion Cannon",       "weapon_type": "lance",          "range_cm": 45, "strength": 2, "arcs": ["right", "front"]},
            {"name": "Port Launch Bays",           "weapon_type": "launch_bay",     "range_cm": 25, "strength": 2, "arcs": [], "craft_types": ["manta", "barracuda"], "craft_speed": 25},
            {"name": "Starboard Launch Bays",      "weapon_type": "launch_bay",     "range_cm": 25, "strength": 2, "arcs": [], "craft_types": ["manta", "barracuda"], "craft_speed": 25},
        ],
        special_rules=["deflector"],
        upgrades_available=_TAU_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Protector Class Cruiser",
        faction=_TAU, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=45,
        shields_max=2, armor_prow="5+", armor_side="5+",
        turrets=2, hits_max=6, leadership=7,
        points_cost=195,
        weapons=[
            {"name": "Port Railgun Battery",      "weapon_type": "battery",        "range_cm": 45, "strength": 5, "arcs": ["left", "front"]},
            {"name": "Starboard Railgun Battery",  "weapon_type": "battery",        "range_cm": 45, "strength": 5, "arcs": ["right", "front"]},
            {"name": "Prow Gravitic Launcher",     "weapon_type": "torpedo",          "range_cm": 40,"strength": 6, "arcs": ["front"], "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
        special_rules=["deflector"],
        upgrades_available=_TAU_UPGRADES_CRUISER,
    ),

    # ── Light Cruisers ────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Emissary Class Light Cruiser",
        faction=_TAU, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=90,
        shields_max=2, armor_prow="5+", armor_side="5+",
        turrets=2, hits_max=4, leadership=7,
        points_cost=120,
        weapons=[
            {"name": "Port Railgun Battery",      "weapon_type": "battery",        "range_cm": 45, "strength": 4, "arcs": ["left", "front"]},
            {"name": "Starboard Railgun Battery",  "weapon_type": "battery",        "range_cm": 45, "strength": 4, "arcs": ["right", "front"]},
            {"name": "Port Ion Cannon",            "weapon_type": "lance",          "range_cm": 30, "strength": 1, "arcs": ["left", "front"]},
            {"name": "Starboard Ion Cannon",       "weapon_type": "lance",          "range_cm": 30, "strength": 1, "arcs": ["right", "front"]},
            {"name": "Prow Gravitic Launcher",     "weapon_type": "torpedo",          "range_cm": 40,"strength": 3, "arcs": ["front"], "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
        special_rules=["deflector"],
        upgrades_available=_TAU_UPGRADES_CRUISER,
    ),

    ShipClassEntry(
        ship_class="Messenger Class Light Cruiser",
        faction=_TAU, ship_type="cruiser", base_size="small",
        speed=20, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=2, hits_max=4, leadership=7,
        points_cost=85,
        weapons=[
            {"name": "Port Railgun Battery",      "weapon_type": "battery",        "range_cm": 30, "strength": 3, "arcs": ["left", "front"]},
            {"name": "Starboard Railgun Battery",  "weapon_type": "battery",        "range_cm": 30, "strength": 3, "arcs": ["right", "front"]},
            {"name": "Prow Gravitic Launcher",     "weapon_type": "torpedo",          "range_cm": 40,"strength": 3, "arcs": ["front"], "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
        special_rules=["deflector"],
        upgrades_available=_TAU_UPGRADES_CRUISER,
    ),

    # ── Escorts ───────────────────────────────────────────────────────────────

    ShipClassEntry(
        ship_class="Warden Class Gunship",
        faction=_TAU, ship_type="escort", base_size="small",
        speed=25, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=1, hits_max=1, leadership=7,
        points_cost=30,
        weapons=[
            {"name": "Railgun Battery",           "weapon_type": "battery",        "range_cm": 30, "strength": 2, "arcs": ["front"]},
            {"name": "Ion Cannon",                 "weapon_type": "lance",          "range_cm": 30, "strength": 1, "arcs": ["left", "front", "right"]},
        ],
        special_rules=[],
        upgrades_available=_TAU_UPGRADES_ESCORT,
    ),

    ShipClassEntry(
        ship_class="Castellan Class Escort",
        faction=_TAU, ship_type="escort", base_size="small",
        speed=25, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=2, hits_max=1, leadership=7,
        points_cost=45,
        weapons=[
            {"name": "Railgun Battery",           "weapon_type": "battery",        "range_cm": 45, "strength": 2, "arcs": ["left", "front", "right"]},
            {"name": "Gravitic Launcher",          "weapon_type": "torpedo",          "range_cm": 40,"strength": 2, "arcs": ["front"], "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
        special_rules=[],
        upgrades_available=_TAU_UPGRADES_ESCORT,
    ),

    ShipClassEntry(
        ship_class="Orca Class Gunship",
        faction=_TAU, ship_type="escort", base_size="small",
        speed=30, turn_angle=90,
        shields_max=1, armor_prow="5+", armor_side="5+",
        turrets=1, hits_max=1, leadership=7,
        points_cost=35,
        weapons=[
            {"name": "Railgun Battery",           "weapon_type": "battery",        "range_cm": 30, "strength": 1, "arcs": ["front"]},
        ],
        special_rules=["boarding_specialist"],
        upgrades_available=_TAU_UPGRADES_ESCORT,
    ),
]


# ---------------------------------------------------------------------------
# Master catalog registry
# ---------------------------------------------------------------------------

_CATALOGS: Dict[str, List[ShipClassEntry]] = {
    _IN:  IMPERIAL_NAVY_CATALOG,
    _TAU: TAU_CATALOG,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_factions() -> List[str]:
    """Return all faction identifiers present in the catalog."""
    return list(_CATALOGS.keys())


def get_faction_ships(faction: str) -> List[ShipClassEntry]:
    """Return all ship classes available to faction, or [] if unknown."""
    return list(_CATALOGS.get(faction, []))


def get_ship_class(faction: str, ship_class: str) -> Optional[ShipClassEntry]:
    """Look up a specific ship class by name within a faction."""
    for entry in _CATALOGS.get(faction, []):
        if entry.ship_class == ship_class:
            return entry
    return None


def get_upgrades_for_ship(entry: ShipClassEntry) -> List[UpgradeEntry]:
    """Return the list of upgrades available to a given ship class entry."""
    return list(entry.upgrades_available)


def faction_display_name(faction: str) -> str:
    """Human-readable name for a faction identifier."""
    return {
        "imperial_navy_gothic": "Imperial Navy (Gothic)",
        "tau_kororvesh":        "Tau Kor'or'vesh",
    }.get(faction, faction.replace("_", " ").title())
