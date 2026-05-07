"""BFG:XR Game State - Save/Load/Manage"""
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from .models import Ship, OrdnanceMarker, BlastMarker, Phenomenon


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

    # Optional rules (each independently togglable)
    rule_fighting_sunward: bool = False
    rule_solar_flares: bool = False
    rule_radiation_bursts: bool = False
    rule_boarding: bool = False
    rule_ramming: bool = False
    rule_teleport: bool = False  # note: Tau cannot teleport regardless
    rule_hit_and_run: bool = False
    rule_turret_suppression_remastered: bool = False  # False = XR mode, True = Remastered mode

    # Collections
    ships: List[Dict] = field(default_factory=list)
    ordnance: List[Dict] = field(default_factory=list)
    blast_markers: List[Dict] = field(default_factory=list)
    phenomena: List[Dict] = field(default_factory=list)

    # Turn log
    log: List[str] = field(default_factory=list)

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
        meta = {
            "game_name": self.game_name,
            "turn_number": self.turn_number,
            "current_phase": self.current_phase,
            "active_player": self.active_player,
            "phase_step": self.phase_step,
            "player1_name": self.player1_name,
            "player2_name": self.player2_name,
            "player1_faction": self.player1_faction,
            "player2_faction": self.player2_faction,
            "player1_color": self.player1_color,
            "player2_color": self.player2_color,
            "table_width": self.table_width,
            "table_height": self.table_height,
            "sunward_edge": self.sunward_edge,
            "dice_mode": self.dice_mode,
            "points_limit": self.points_limit,
            "rule_fighting_sunward": self.rule_fighting_sunward,
            "rule_solar_flares": self.rule_solar_flares,
            "rule_radiation_bursts": self.rule_radiation_bursts,
            "rule_boarding": self.rule_boarding,
            "rule_ramming": self.rule_ramming,
            "rule_teleport": self.rule_teleport,
            "rule_hit_and_run": self.rule_hit_and_run,
            "rule_turret_suppression_remastered": self.rule_turret_suppression_remastered,
            "allow_movement_pass": self.allow_movement_pass,
            "timestamp": time.time(),
        }

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
            if k != "timestamp" and hasattr(gs, k):
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
