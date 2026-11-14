"""BFG:XR Game State - Save/Load/Manage"""
import json
import os
import time
from dataclasses import dataclass, field, fields
from typing import List, Dict, Optional, Tuple
from .models import Ship, OrdnanceMarker, BlastMarker, Phenomenon


_COLLECTIONS = ("ships", "ordnance", "blast_markers", "phenomena", "log")


@dataclass
class GameState:
    # Game info
    game_name: str = "bfg_game"
    turn_number: int = 1
    current_phase: str = "setup"  # setup, movement, shooting, ordnance, end
    active_player: int = 1
    phase_step: str = ""  # sub-step within phase

    # Players
    player1_name: str = "Player 1"
    player2_name: str = "Player 2"
    player1_faction: str = "imperial_navy"
    player2_faction: str = "tau_kororvesh"
    player1_color: str = "red"
    player2_color: str = "blue"

    # Table
    table_width: float = 120.0   # cm
    table_height: float = 120.0  # cm
    sunward_edge: str = "north"  # north/south/east/west

    # Settings
    dice_mode: str = "mixed"  # "manual", "auto", "mixed"
    points_limit: int = 800
    allow_movement_pass: bool = False  # False = strict: must move all ships; True = can skip
    ai_player: Optional[int] = None    # player number controlled by AI (None = hotseat)
    ai_difficulty: str = "normal"      # "easy" | "normal" | "hard" | "expert"
    ai_spectator: bool = False         # True = both players AI (spectator mode)

    # Turn limit and scenario settings
    turn_limit: Optional[int] = None           # None = unlimited turns
    ftl_available_turn: Optional[int] = None   # None = FTL always available
    scenario_mode: str = "standard"            # standard | kill_admiral | destroy_ship | capture_artefact
    scenario_attacker: int = 1                 # player who is "attacker" in asymmetric modes
    attacker_by_rating: bool = False           # booklet scenarios: roll attack ratings (p.78)
    objective_ship_id: Optional[str] = None    # target ship for destroy/protect modes
    artefact_submode: str = "race"             # race | carrier_escape
    artefact_token_pos: Optional[Tuple[float, float]] = None  # board pos when uncarried
    artefact_carrier_id: Optional[str] = None  # ship currently holding artefact
    artefact_owner: Optional[int] = None       # player who holds artefact

    # Optional rules (each independently togglable)
    rule_fighting_sunward: bool = False
    rule_solar_flares: bool = False
    rule_radiation_bursts: bool = False
    rule_boarding: bool = False
    rule_ramming: bool = False
    rule_teleport: bool = False  # note: Tau cannot teleport regardless
    rule_hit_and_run: bool = False
    rule_turret_suppression_remastered: bool = False  # False = XR mode, True = Remastered mode
    contact_margin_cm: float = 0.2  # wiggle room added to base contact distance checks
    blast_marker_rules: str = "standard"  # s.11: standard | modern | remastered (optional_rules)
    rule_remastered_spillover: bool = False  # s.11 Remastered: one round's markers touch <= 2 ships
    rule_remastered_escort_vp: bool = False  # Remastered p.121 escort squadron VP (XR default)
    # s.40 celestial effects (src/celestial.py)
    solar_flare_dice: int = 1
    radiation_burst_dice: int = 1
    solar_flare_done: bool = False
    solar_flare_turn: Optional[List[int]] = None
    radiation_level: int = 0
    radiation_turn: Optional[List[int]] = None
    radiation_deltas: Dict = field(default_factory=dict)
    # Mark of Chaos Undivided (once per game per player): players who have used
    # it, and the boost in force {player: {"turn": n, "deltas": {ship id: +Ld}}}
    first_player: int = 1        # s.2: who moves first (the roll-off winner's choice)
    # Alternate activation (To do 13, optional, outside the booklet): "igougo" (the
    # booklet's turns) or "aa"; aa_settings holds the AARoundConfig fields
    # Necron Deadly Awakening: {player: alert level} (src/necrons.py)
    necron_alert: Dict = field(default_factory=dict)
    # Kill credit: [{"by": ship id, "target": ship id, "kind": "crippled" | "destroyed"}]
    # (combat.apply_damage; Fresh Captain's objective reads it)
    kill_credit: List = field(default_factory=list)
    turn_system: str = "igougo"
    aa_settings: Dict = field(default_factory=dict)
    aa_state: Dict = field(default_factory=dict)
    # Booklet scenarios (src/scenarios.py): e.g. Domination's layout, objective
    # markers and points
    scenario_state: Dict = field(default_factory=dict)
    # Sub-plots (src/subplots.py, p.80-82): rule_subplots rolls one for each
    # player before deployment; subplots holds them {"1": {...}, "2": {...}}
    rule_subplots: bool = False
    subplots: Dict = field(default_factory=dict)
    undivided_used: List[int] = field(default_factory=list)
    undivided_boost: Dict = field(default_factory=dict)
    # Serial for marker / ordnance ids (unique for the game; ids used to end in
    # a random 0-9999 and could collide)
    id_serial: int = 0

    # Collections
    ships: List[Dict] = field(default_factory=list)
    ordnance: List[Dict] = field(default_factory=list)
    blast_markers: List[Dict] = field(default_factory=list)
    phenomena: List[Dict] = field(default_factory=list)

    # Turn log
    log: List[str] = field(default_factory=list)

    def next_serial(self) -> int:
        self.id_serial += 1
        return self.id_serial

    def add_ship(self, ship: Ship):
        self.ships.append(ship.to_dict())

    def get_ships(self) -> List[Ship]:
        return [Ship.from_dict(s) for s in self.ships]

    def get_ship_by_id(self, ship_id: str) -> Optional[Ship]:
        for s in self.ships:
            if s["id"] == ship_id:
                return Ship.from_dict(s)
        return None

    def update_ship(self, ship: Ship):
        for i, s in enumerate(self.ships):
            if s["id"] == ship.id:
                self.ships[i] = ship.to_dict()
                return
        raise ValueError(f"Ship {ship.id} not found")

    def add_ordnance(self, marker: OrdnanceMarker):
        self.ordnance.append(marker.to_dict())

    def get_ordnance(self) -> List[OrdnanceMarker]:
        return [OrdnanceMarker.from_dict(o) for o in self.ordnance]

    def add_blast_marker(self, bm: BlastMarker):
        self.blast_markers.append(bm.to_dict())

    def get_blast_markers(self) -> List[BlastMarker]:
        return [BlastMarker.from_dict(b) for b in self.blast_markers]

    def add_phenomenon(self, p: Phenomenon):
        self.phenomena.append(p.to_dict())

    def get_phenomena(self) -> List[Phenomenon]:
        return [Phenomenon.from_dict(p) for p in self.phenomena]

    def add_log(self, msg: str):
        self.log.append(f"[T{self.turn_number} {self.current_phase}] {msg}")

    def player_ships(self, player: int) -> List[Ship]:
        return [Ship.from_dict(s) for s in self.ships if s["player"] == player]

    # Save/Load
    def save(self, directory: str = None):
        if directory is None:
            directory = os.path.join("saves", self.game_name)
        os.makedirs(directory, exist_ok=True)

        # Main state (without large collections)
        # Every dataclass field but the large collections (a hand-written list
        # here could drift from the fields)
        meta = {}
        for f in fields(self):
            if f.name in _COLLECTIONS:
                continue
            v = getattr(self, f.name)
            if f.name == "artefact_token_pos" and v is not None:
                v = list(v)
            meta[f.name] = v
        meta["timestamp"] = time.time()

        with open(os.path.join(directory, "game_state.json"), "w") as f:
            json.dump(meta, f, indent=2)
        with open(os.path.join(directory, "ships.json"), "w") as f:
            json.dump(self.ships, f, indent=2)
        with open(os.path.join(directory, "ordnance.json"), "w") as f:
            json.dump(self.ordnance, f, indent=2)
        with open(os.path.join(directory, "blast_markers.json"), "w") as f:
            json.dump(self.blast_markers, f, indent=2)
        with open(os.path.join(directory, "phenomena.json"), "w") as f:
            json.dump(self.phenomena, f, indent=2)
        with open(os.path.join(directory, "turn_log.txt"), "w") as f:
            f.write("\n".join(self.log))

    @classmethod
    def load(cls, directory: str) -> "GameState":
        gs = cls()
        with open(os.path.join(directory, "game_state.json")) as f:
            meta = json.load(f)
        for k, v in meta.items():
            if k == "timestamp":
                continue
            if not hasattr(gs, k):
                continue
            if k == "artefact_token_pos" and v is not None:
                v = tuple(v)
            setattr(gs, k, v)

        with open(os.path.join(directory, "ships.json")) as f:
            gs.ships = json.load(f)
        with open(os.path.join(directory, "ordnance.json")) as f:
            gs.ordnance = json.load(f)
        with open(os.path.join(directory, "blast_markers.json")) as f:
            gs.blast_markers = json.load(f)
        with open(os.path.join(directory, "phenomena.json")) as f:
            gs.phenomena = json.load(f)

        log_path = os.path.join(directory, "turn_log.txt")
        if os.path.exists(log_path):
            with open(log_path) as f:
                content = f.read().strip()
                gs.log = content.split("\n") if content else []
        return gs

    def restore_from(self, other: "GameState") -> None:
        """Overwrite this state in place with another's.

        The turn controller, board and panels all hold a reference to the
        same GameState, so a load must mutate it rather than replace it.
        Transient engine scratch stashed as underscore attributes (zzapp
        blast markers once a turn, Demiurg collected markers, spill-over
        touches) is dropped so it can't leak across a load or undo; the UI's
        hooks (plain attributes) stay.
        """
        for f in fields(self):
            setattr(self, f.name, getattr(other, f.name))
        self.clear_transient()

    def clear_transient(self) -> None:
        """Drop engine scratch kept as underscore attributes (not dataclass
        fields, never saved): it describes the state being replaced."""
        names = {f.name for f in fields(self)}
        for k in [k for k in vars(self) if k.startswith("_") and k not in names]:
            del self.__dict__[k]
