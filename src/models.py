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
    MINE_LAUNCHER = "mine_launcher"


class Arc(str, Enum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"
    REAR = "rear"


class OrdnanceType(str, Enum):
    TORPEDO_STANDARD = "torpedo_standard"
    TORPEDO_GUIDED = "torpedo_guided"             # Tau missiles
    TORPEDO_BOARDING = "torpedo_boarding"         # one hit-and-run raid per hit (s.31)
    TORPEDO_BOARDING_GUIDED = "torpedo_boarding_guided"  # boarding torp w/ guidance
    TORPEDO_SHORT_BURN = "torpedo_short_burn"     # 40cm; out of fuel on a 6 (s.16)
    TORPEDO_BARRAGE = "torpedo_barrage"           # barrage bombs: hits stopped by shields (s.16)
    TORPEDO_GUIDED_LD = "torpedo_guided_ld"       # guided: turn 45° on a Leadership test (s.16)
    TORPEDO_SEEKING = "torpedo_seeking"           # turn 45° at the nearest enemy (s.16)
    TORPEDO_MELTA = "torpedo_melta"               # each hit: a Fire crit, no damage (s.16)
    TORPEDO_VORTEX = "torpedo_vortex"             # each hit: 1 damage + automatic crit (s.16)
    FIGHTER = "fighter"
    BOMBER = "bomber"
    ASSAULT_BOAT = "assault_boat"
    TORPEDO_BOMBER = "torpedo_bomber"
    # Multi-role attack craft (s.24); roles in ordnance.MR_ROLES
    THUNDERHAWK = "thunderhawk"           # Space Marines / Grey Knights
    GUN_CUTTER = "gun_cutter"             # Inquisition
    FIGHTA_BOMMER = "fighta_bommer"       # Orks
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


def parse_armor(armor_str, default: int = 5) -> int:
    """Parse an armor string like '5+' to its numeric value, with fallback."""
    try:
        return int(str(armor_str).rstrip("+"))
    except (ValueError, AttributeError, TypeError):
        return default


def bearing_between(x1: float, y1: float, x2: float, y2: float) -> float:
    """Bearing from (x1, y1) to (x2, y2) in degrees (0=east, 90=north)."""
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 360


def signed_angle_diff(angle: float, reference: float) -> float:
    """Signed difference angle - reference, normalized to [-180, 180)."""
    return (angle - reference + 180) % 360 - 180


def arc_name_for_bearing(bearing: float, heading: float) -> str:
    """Which fire arc ('front'/'left'/'rear'/'right') a bearing falls in,
    relative to a facing of `heading`. Front spans ±45°."""
    relative = (bearing - heading + 360) % 360
    if relative <= 45 or relative > 315:
        return "front"
    if relative <= 135:
        return "left"  # port
    if relative <= 225:
        return "rear"
    return "right"  # starboard


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
    # Ships with three Armour values (e.g. Ork cruisers 6+/5+/4+): front /
    # abeam / rear. Empty for the usual two values (rear uses armor_side).
    armor_rear: str = ""
    turrets: int = 2
    hits_max: int = 8
    leadership: int = 7
    leadership_table: str = ""   # Appendix 4 column if Ld is rolled at game start

    # Current state
    # None = uninitialized (post_init sets to hits_max). Stored as 0 for
    # destroyed ships so from_dict never resets it back to hits_max.
    hits_remaining: Optional[int] = None
    special_order: str = "none"
    moved_this_turn: bool = False
    has_fired: bool = False
    ordnance_loaded_torps: bool = True
    ordnance_loaded_craft: bool = True
    # Mines reload separately from attack craft (s.15: launching one type of
    # ordnance does not affect the other)
    ordnance_loaded_mines: bool = True
    # Ordnance markers this ship touched during its own move, waiting to attack
    # it (s.15); cleared once resolved
    pending_ordnance_contacts: List[str] = field(default_factory=list)
    # Heed the Machine Spirit used against these attackers this turn
    machine_spirit_used_vs: List[str] = field(default_factory=list)
    # A ship takes each leadership test once a turn (s.7): its target priority
    # result stands for the rest of the turn
    target_priority_turn: int = -1
    target_priority_passed: bool = False
    command_check_failed_this_turn: bool = False

    # Points and game status
    points_value: int = 0         # fleet list points cost (including upgrades)
    is_disengaged: bool = False   # voluntarily left the battle
    status: str = "active"        # active, disengaged, destroyed, drifting_hulk, burning_hulk
    disengage_failed_this_turn: bool = False  # failed disengage = no fire/orders this turn
    must_disengage: bool = False             # escort squadron that lost a ship off the table
    must_disengage_tested_turn: int = 0      # turn of its last forced disengage test
    must_flee: bool = False                  # failed a forced test: heads for the nearest edge
    brace_set_on_turn: int = 0  # turn number when brace was applied (0 = not set)
    previous_order: str = "none"  # order that was active before bracing

    # Tracking fields for per-phase restrictions
    once_torps_used: List[str] = field(default_factory=list)  # seeking/melta/vortex fired (one salvo per game)
    turrets_halved_turn: int = -1  # Promethean Unguents: next ordnance attack this turn faces half turrets
    turrets_used_vs: str = ""  # "craft" or "torp" - turrets can only fire at one type per phase
    brace_failed_vs: List[str] = field(default_factory=list)  # ship IDs that brace failed against

    # Staged movement tracking (reset at movement phase start)
    distance_moved_this_turn: float = 0.0   # cm already moved this phase
    turns_used_this_turn: int = 0           # turns already consumed this phase
    net_rotation_this_turn: float = 0.0     # net signed rotation (+ = anticlockwise)
    crossed_blast_this_turn: bool = False   # moved through blast markers this phase
    distance_since_last_turn: float = 0.0   # forward movement since its last turn this phase
    # Distance moved in its own most recent movement phase; None until it has had
    # one. Under 5cm counts as Defenses on the Gunnery table.
    last_move_cm: Optional[float] = None

    # Weapons fired tracking
    # Dict of {weapon_index: remaining_strength} for weapons partially or fully fired
    # If a weapon index is not in this dict, it hasn't been fired at all
    # If remaining is 0, the weapon is fully spent
    weapons_fired_indices: List[int] = field(default_factory=list)
    weapons_remaining: Dict = field(default_factory=dict)  # {str(idx): remaining_str}
    # Heavy Gunz split this turn: {str(idx): "close" | "long"} (combat.weapon_fire_pool)
    weapon_pool_mode: Dict = field(default_factory=dict)

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

    # Ramming (set when ramming intent declared on AAF)
    ramming_target_id: Optional[str] = None

    # Boarding actions
    boarding_target_id: Optional[str] = None  # declared during movement
    has_boarded: bool = False                  # blocks fire and ordnance same turn
    is_grappled: bool = False                  # draw — ship cannot move/fire/ordnance
    aa_locked: bool = False                    # AA: target of a boarding action this round
    grappled_with_id: Optional[str] = None    # peer ship in the grapple

    # Admiral/commander
    is_flagship: bool = False
    admiral_type: str = ""  # e.g. "vice_admiral", "kor_o"
    rerolls_remaining: int = 0
    own_rerolls: int = 0       # a secondary commander's re-rolls: this ship / squadron only (s.5)
    collected_blast_markers: int = 0  # Demiurg absorber fields: collected this turn (cutting beam)
    war_host_rerolls: int = 0  # Demiurg War Host re-rolls bought on this ship: any Demiurg vessel, never lost

    def __post_init__(self):
        if self.hits_remaining is None:
            self.hits_remaining = self.hits_max

    @property
    def base_radius(self):
        return BaseSize(self.base_size).radius_cm

    @property
    def is_crippled(self):
        """Crippled for play: by damage, or a Necron capital ship conserving
        power (Deadly Awakening: crippled for all purposes but scoring)."""
        if self.damage_crippled:
            return True
        return ("necron" in self.special_rules and self.ship_type != "escort"
                and "necron_awake" not in self.special_rules and self.hits_remaining > 0
                and self.status == "active")

    @property
    def damage_crippled(self):
        """Crippled by damage (half its hits or fewer left): what scoring uses."""
        return self.hits_remaining <= self.hits_max // 2 and self.hits_remaining > 0

    @property
    def is_destroyed(self):
        return self.hits_remaining <= 0 or self.status in ("destroyed",)

    @property
    def is_hulk(self):
        """A drifting or burning hulk: out of action (is_destroyed) but still on
        the table, where enemies may fire on it (s.34)."""
        return self.status in ("drifting_hulk", "burning_hulk")

    @property
    def armor_prow_value(self):
        return int(self.armor_prow.replace("+", ""))

    @property
    def armor_side_value(self):
        return int(self.armor_side.replace("+", ""))

    @property
    def armor_rear_value(self):
        return int((self.armor_rear or self.armor_side).replace("+", ""))

    def armor_for_arc(self, arc) -> int:
        """Armour against an attack from this arc of the ship (s.9 bearing
        compass): prow armour from the front quadrant, rear armour (if the
        ship has three values) from the rear, side armour otherwise."""
        a = getattr(arc, "value", arc)
        if "necron" in self.special_rules:
            # Necrons (Xenos p.40): bracing compromises their stealth, and so
            # does becoming a hulk (Without a Trace): Armour 4+
            if (self.special_order == "brace_for_impact"
                    or self.status in ("drifting_hulk", "burning_hulk")):
                return 4
        if a == "front":
            return self.armor_prow_value
        if a == "rear":
            return self.armor_rear_value
        return self.armor_side_value

    def armor_vs(self, x: float, y: float) -> int:
        """Armour facing an attacker or marker at (x, y)."""
        return self.armor_for_arc(self.get_arc_for_bearing(self.bearing_to(x, y)))

    @property
    def lowest_armor_value(self) -> int:
        return min(self.armor_prow_value, self.armor_side_value, self.armor_rear_value)

    def mark_launched(self, kind: str) -> None:
        """A ship has launched torpedoes ("torps"), attack craft ("craft") or
        mines ("mines"). A Demiurg Bastion's modular bays carry one or the
        other each ordnance phase (owner ruling), and mines are a third mode of
        the same bays when bought (Xenos, Bastion), so launching any uses all
        of them up."""
        modular = "modular_bays" in self.special_rules
        if kind == "torps" or modular:
            self.ordnance_loaded_torps = False
        if kind == "craft" or modular:
            self.ordnance_loaded_craft = False
        if kind == "mines" or modular:
            self.ordnance_loaded_mines = False

    def crippled_value(self, value: int) -> int:
        """A shield, turret or weapon value while crippled: half, rounding up;
        Emergency Energy Reserves (Mechanicus Gift) lose 25% instead, the
        loss rounded down."""
        if "emergency_energy_reserves" in self.special_rules:
            return value - value // 4
        return (value + 1) // 2

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
        if any(c.get("crit_type") == "impulse_power" for c in self.critical_damage):
            spd -= 5                         # Necron Impulse Power Disrupted
        if self.is_crippled and "emergency_energy_reserves" in self.special_rules:
            spd = max(spd, min(15, self.speed))      # can't drop below 15cm
        return max(0, spd)

    @property
    def effective_shields(self):
        s = self.shields_max
        if self.is_crippled:
            s = self.crippled_value(s)  # halve rounding up
        # Check for shields collapse crit
        for c in self.critical_damage:
            if c.get("crit_type") == "shields_collapse":
                return 0
        if any(c.get("crit_type") == "station_reactors" for c in self.critical_damage):
            s = (s + 1) // 2           # Space Station Reactors Damaged: halved, round up
        return s

    @property
    def effective_turrets(self):
        if self.status in ("drifting_hulk", "burning_hulk"):
            return 0                   # hulks have no turrets (s.34)
        t = self.turrets
        if self.is_crippled:
            t = self.crippled_value(t)
        if any(c.get("crit_type") == "station_reactors" for c in self.critical_damage):
            t = (t + 1) // 2           # Space Station Reactors Damaged: halved, round up
        return t

    def has_armament_slot(self, crit_type: str) -> bool:
        """Check if this ship has weapons that would be affected by an armament crit.
        Used for crit cascade: if a ship has no prow weapons, a prow armament
        crit cascades to the next highest result."""
        station = {"station_lances": ("lance",), "station_batteries": ("battery",),
                   "station_bays": ("launch_bay", "torpedo", "mine_launcher")}
        if crit_type in station:
            return any(w.get("weapon_type") in station[crit_type] for w in self.weapons)
        if crit_type not in ("dorsal_armament", "starboard_armament", "port_armament",
                             "prow_armament", "keel_armament"):
            return True  # non-armament crits always apply
        # The same location test that decides which weapons the crit disables
        # (combat.weapon_in_crit_slot: by name, then by arcs), so a crit that
        # would disable nothing cascades instead (a dorsal L/F/R weapon used to
        # count as a prow slot)
        from .combat import weapon_in_crit_slot
        return any(weapon_in_crit_slot(w, crit_type) for w in self.weapons)

    def distance_to(self, other):
        """Distance in cm between ship stems"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def bearing_to(self, target_x, target_y):
        """Bearing from this ship to a point, in degrees (0=east, 90=north)"""
        return bearing_between(self.x, self.y, target_x, target_y)

    def get_arc_for_bearing(self, bearing):
        """Given a bearing FROM this ship, determine which fire arc it's in"""
        return Arc(arc_name_for_bearing(bearing, self.heading))

    def get_target_arc(self, target_x, target_y):
        """What arc of THIS ship is the target in?"""
        bearing = self.bearing_to(target_x, target_y)
        return self.get_arc_for_bearing(bearing)

    def get_target_orientation(self, target_ship):
        """What orientation is the target presenting to us? (closing/abeam/moving_away)"""
        if "fraal_targeting" in self.special_rules:
            return "closing"           # Fra'al targeting matrix: every gunnery target closes
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
    wave_id: str = ""        # waves of attack craft (s.25): markers sharing an id
    wave_order: int = 0      # 0 = the lead marker
    wave_formation: str = "" # "close" or "loose"
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
    # Attack craft: id of the ship or ordnance marker the squadron is flying at
    # (s.18: craft turn freely and move in any direction). Empty = straight on.
    craft_target_id: str = ""
    # Torpedoes: {ship id: turn number} of each attack. A salvo may never
    # attack the same ship more than once per full turn (s.16).
    attacked_turns: Dict[str, int] = field(default_factory=dict)
    # Torpedoes that can turn: the ship the AI planned the salvo against (its
    # in-flight turns follow ai_hazards.salvo_approach). Empty = nearest enemy.
    torp_target_id: str = ""

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
        for r in self.special_rules or []:
            if r.startswith("well:"):          # e.g. a craftworld's own well
                return self.radius + float(r.split(":")[1])
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
