"""BFG:XR Data Models - Ships, Ordnance, Terrain, Blast Markers"""
import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from enum import Enum


class ShipType(str, Enum):
    BATTLESHIP = "battleship"
    CRUISER = "cruiser"
    ESCORT = "escort"
    DEFENSE = "defense"


class BaseSize(str, Enum):
    SMALL = "small"   # 32mm
    LARGE = "large"   # 60mm

    @property
    def radius_cm(self):
        # Convert mm diameter to cm radius
        return 1.6 if self == BaseSize.SMALL else 3.0


class SpecialOrder(str, Enum):
    NONE = "none"
    ALL_AHEAD_FULL = "all_ahead_full"
    BURN_RETROS = "burn_retros"
    COME_TO_NEW_HEADING = "come_to_new_heading"
    LOCK_ON = "lock_on"
    RELOAD_ORDNANCE = "reload_ordnance"
    BRACE_FOR_IMPACT = "brace_for_impact"


class WeaponType(str, Enum):
    BATTERY = "battery"
    LANCE = "lance"
    NOVA_CANNON = "nova_cannon"
    TORPEDO = "torpedo"
    LAUNCH_BAY = "launch_bay"
    GRAVITIC_LAUNCHER = "gravitic_launcher"
    MINE_LAUNCHER = "mine_launcher"


class Arc(str, Enum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"
    REAR = "rear"


class OrdnanceType(str, Enum):
    TORPEDO_STANDARD = "torpedo_standard"
    TORPEDO_GUIDED = "torpedo_guided"             # Tau missiles
    TORPEDO_BOARDING_GUIDED = "torpedo_boarding_guided"  # boarding torp w/ guidance
    FIGHTER = "fighter"
    BOMBER = "bomber"
    ASSAULT_BOAT = "assault_boat"
    TORPEDO_BOMBER = "torpedo_bomber"
    MANTA = "manta"           # Tau: resilient bomber (NOT a fighter)
    BARRACUDA = "barracuda"   # Tau: fighter
    MINE_FIELD = "mine_field" # Static hazard; detonates on ship contact


class PhenomenonType(str, Enum):
    ASTEROID_FIELD = "asteroid_field"
    GAS_DUST_CLOUD = "gas_dust_cloud"
    PLANET_SMALL = "planet_small"
    PLANET_MEDIUM = "planet_medium"
    PLANET_LARGE = "planet_large"
    MOON = "moon"
    WARP_RIFT = "warp_rift"
    RING = "ring"



@dataclass
class Ship:
    # Identity
    id: str
    name: str
    ship_class: str         # e.g. "Mars Class Battlecruiser"
    faction: str            # e.g. "imperial_navy", "tau_kororvesh"
    player: int             # 1 or 2
    ship_type: str          # ShipType value
    base_size: str          # BaseSize value

    # Position
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0    # degrees, 0 = right/east, 90 = up/north

    # Base stats
    speed: int = 20
    turn_angle: int = 45    # max turn in degrees
    shields_max: int = 2
    armor_prow: str = "6+"  # e.g. "6+", "5+"
    armor_side: str = "5+"
    turrets: int = 2
    hits_max: int = 8
    leadership: int = 7

    # Current state
    # None = uninitialized (post_init sets to hits_max). Stored as 0 for
    # destroyed ships so from_dict never resets it back to hits_max.
    hits_remaining: Optional[int] = None
    special_order: str = "none"
    moved_this_turn: bool = False
    has_fired: bool = False
    ordnance_loaded_torps: bool = True
    ordnance_loaded_craft: bool = True
    command_check_failed_this_turn: bool = False

    # Points and game status
    points_value: int = 0         # fleet list points cost (including upgrades)
    is_disengaged: bool = False   # voluntarily left the battle
    status: str = "active"        # active, disengaged, destroyed, drifting_hulk, burning_hulk
    disengage_failed_this_turn: bool = False  # failed disengage = no fire/orders this turn
    brace_set_on_turn: int = 0  # turn number when brace was applied (0 = not set)
    previous_order: str = "none"  # order that was active before bracing

    # Tracking fields for per-phase restrictions
    turrets_used_vs: str = ""  # "craft" or "torp" - turrets can only fire at one type per phase
    brace_failed_vs: List[str] = field(default_factory=list)  # ship IDs that brace failed against

    # Staged movement tracking (reset at movement phase start)
    distance_moved_this_turn: float = 0.0   # cm already moved this phase
    turns_used_this_turn: int = 0           # turns already consumed this phase
    net_rotation_this_turn: float = 0.0     # net signed rotation (+ = anticlockwise)

    # Weapons fired tracking
    # Dict of {weapon_index: remaining_strength} for weapons partially or fully fired
    # If a weapon index is not in this dict, it hasn't been fired at all
    # If remaining is 0, the weapon is fully spent
    weapons_fired_indices: List[int] = field(default_factory=list)
    weapons_remaining: Dict = field(default_factory=dict)  # {str(idx): remaining_str}

    # Weapons
    weapons: List[Dict] = field(default_factory=list)

    # Critical damage
    critical_damage: List[Dict] = field(default_factory=list)

    # Special rules
    special_rules: List[str] = field(default_factory=list)
    # e.g. ["ponderous", "tracking_systems_20", "deflector"]

    # Upgrades
    upgrades: List[str] = field(default_factory=list)

    # Squadron
    squadron_id: str = ""

    # Towed escorts (ship IDs in gravitic hooks)
    towed_escorts: List[str] = field(default_factory=list)

    # Admiral/commander
    is_flagship: bool = False
    admiral_type: str = ""  # e.g. "vice_admiral", "kor_o"
    rerolls_remaining: int = 0

    def __post_init__(self):
        if self.hits_remaining is None:
            self.hits_remaining = self.hits_max

    @property
    def base_radius(self):
        return BaseSize(self.base_size).radius_cm

    @property
    def is_crippled(self):
        return self.hits_remaining <= self.hits_max // 2 and self.hits_remaining > 0

    @property
    def is_destroyed(self):
        return self.hits_remaining <= 0 or self.status in ("destroyed",)

    @property
    def armor_prow_value(self):
        return int(self.armor_prow.replace("+", ""))

    @property
    def armor_side_value(self):
        return int(self.armor_side.replace("+", ""))

    @property
    def effective_speed(self):
        spd = self.speed
        if self.is_crippled:
            spd -= 5
        # Thrusters damaged: -10cm total (not cumulative, but all must be repaired)
        has_thrusters_crit = any(
            c.get("crit_type") == "thrusters_damaged"
            for c in self.critical_damage)
        if has_thrusters_crit:
            spd -= 10
        return max(0, spd)

    @property
    def effective_shields(self):
        s = self.shields_max
        if self.is_crippled:
            s = (s + 1) // 2  # halve rounding up
        # Check for shields collapse crit
        for c in self.critical_damage:
            if c.get("crit_type") == "shields_collapse":
                return 0
        return s

    @property
    def effective_turrets(self):
        t = self.turrets
        if self.is_crippled:
            t = (t + 1) // 2
        return t

    def has_armament_slot(self, crit_type: str) -> bool:
        """Check if this ship has weapons that would be affected by an armament crit.
        Used for crit cascade: if a ship has no prow weapons, a prow armament
        crit cascades to the next highest result."""
        slot_to_arcs = {
            "dorsal_armament": None,    # dorsal = weapons with left+front+right arcs
            "starboard_armament": "right",
            "port_armament": "left",
            "prow_armament": "front",
        }
        if crit_type not in slot_to_arcs:
            return True  # non-armament crits always apply

        target_arc = slot_to_arcs[crit_type]
        for w in self.weapons:
            arcs = w.get("arcs", [])
            if target_arc is None:
                # Dorsal: weapons that cover left, front, and right
                if "left" in arcs and "front" in arcs and "right" in arcs:
                    return True
            else:
                if target_arc in arcs:
                    return True
        return False

    def distance_to(self, other):
        """Distance in cm between ship stems"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def bearing_to(self, target_x, target_y):
        """Bearing from this ship to a point, in degrees (0=east, 90=north)"""
        dx = target_x - self.x
        dy = target_y - self.y
        return math.degrees(math.atan2(dy, dx)) % 360

    def get_arc_for_bearing(self, bearing):
        """Given a bearing FROM this ship, determine which fire arc it's in"""
        # Normalize relative to heading
        relative = (bearing - self.heading + 360) % 360
        # Front: -45 to 45 (i.e. 315-360 or 0-45)
        if relative <= 45 or relative > 315:
            return Arc.FRONT
        elif 45 < relative <= 135:
            return Arc.LEFT  # port
        elif 135 < relative <= 225:
            return Arc.REAR
        else:
            return Arc.RIGHT  # starboard

    def get_target_arc(self, target_x, target_y):
        """What arc of THIS ship is the target in?"""
        bearing = self.bearing_to(target_x, target_y)
        return self.get_arc_for_bearing(bearing)

    def get_target_orientation(self, target_ship):
        """What orientation is the target presenting to us? (closing/abeam/moving_away)"""
        # Place bearing compass on TARGET, see which quadrant faces us
        bearing_from_target = target_ship.bearing_to(self.x, self.y)
        arc = target_ship.get_arc_for_bearing(bearing_from_target)
        if arc == Arc.FRONT:
            return "closing"
        elif arc == Arc.REAR:
            return "moving_away"
        else:  # LEFT or RIGHT
            return "abeam"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class OrdnanceMarker:
    id: str
    ordnance_type: str      # OrdnanceType value
    owner_player: int
    launched_by: str        # ship ID
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    strength: int = 6       # for torpedoes
    speed: float = 30.0
    launched_turn: int = 0
    wave_id: str = ""
    cap_ship_id: str = ""   # on CAP for this ship
    resilient_save: int = 0 # 0 = not resilient, 4 = 4+ save
    resilient_used: bool = False
    can_turn: bool = False
    turn_angle: int = 0
    special_rules: List[str] = field(default_factory=list)
    moved_this_phase: bool = False  # Tau missiles: True once moved this ordnance phase
    # Friendly ships that were in base contact with the launcher when this
    # marker was created.  These ships are immune to friendly fire from this
    # marker (torpedoes only).  Captured once at launch and stays fixed.
    launch_exempt_ships: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class BlastMarker:
    id: str
    x: float
    y: float
    source: str = ""  # what caused it
    heading: float = 0.0  # degrees; determines trefoil lobe orientation

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d.setdefault("heading", 0.0)
        return cls(**d)


@dataclass
class Phenomenon:
    id: str
    phenomenon_type: str  # PhenomenonType value
    x: float = 0.0
    y: float = 0.0
    width: float = 10.0   # in cm
    height: float = 10.0  # in cm
    radius: float = 0.0   # for planets/moons (diameter/2)
    rotation: float = 0.0  # rotation in degrees
    special_rules: List[str] = field(default_factory=list)

    @property
    def gravity_well_radius(self):
        """Returns gravity well radius for planets, 0 for non-planets"""
        if self.phenomenon_type == PhenomenonType.PLANET_SMALL.value:
            return self.radius + 10
        elif self.phenomenon_type == PhenomenonType.PLANET_MEDIUM.value:
            return self.radius + 15
        elif self.phenomenon_type == PhenomenonType.PLANET_LARGE.value:
            return self.radius + 30
        return 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)
