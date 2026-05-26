"""BFG:XR Turn Controller - Game loop, snapshots, action recording"""
import json
import math
import os
import copy
import time
import zipfile
from typing import List, Dict, Optional
from .game_state import GameState
from .models import Ship, SpecialOrder
from .dice import DiceRoller
from .geometry import circle_touches_trefoil


class ActionRecord:
    """A single recorded game action for replay."""
    def __init__(self, turn: int, phase: str, player: int,
                 action_type: str, ship_id: str = "",
                 details: Dict = None, result: Dict = None,
                 description: str = ""):
        self.turn = turn
        self.phase = phase
        self.player = player
        self.action_type = action_type
        self.ship_id = ship_id
        self.details = details or {}
        self.result = result or {}
        self.description = description
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "turn": self.turn,
            "phase": self.phase,
            "player": self.player,
            "action_type": self.action_type,
            "ship_id": self.ship_id,
            "details": self.details,
            "result": self.result,
            "description": self.description,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d):
        ar = cls(d["turn"], d["phase"], d["player"],
                 d["action_type"], d.get("ship_id", ""),
                 d.get("details"), d.get("result"),
                 d.get("description", ""))
        ar.timestamp = d.get("timestamp", 0)
        return ar


class TurnController:
    """
    Manages game flow: phases, turn order, snapshots, and action recording.
    """

    PHASES = ["movement", "shooting", "ordnance", "end"]

    def __init__(self, game_state: GameState, dice: DiceRoller,
                 save_dir: str = None):
        self.gs = game_state
        self.dice = dice
        self.save_dir = save_dir or os.path.join("saves", game_state.game_name)
        self.snapshots_dir = os.path.join(self.save_dir, "snapshots")
        os.makedirs(self.snapshots_dir, exist_ok=True)

        # Action recording
        self.actions: List[ActionRecord] = []

        # Phase tracking
        self.command_check_failed = False  # tracks if any check failed this turn
        self.ships_moved: List[str] = []   # ship IDs moved this movement phase
        self.ships_fired: List[str] = []   # ship IDs that fired this shooting phase

        # Undo support: snapshot of state at phase start
        self._phase_start_snapshot: Optional[Dict] = None

    # --- Snapshot System ---

    def save_snapshot(self, label: str):
        """Save current game state as a named snapshot."""
        path = os.path.join(self.snapshots_dir, f"{label}.json")
        # Deep copy the entire state as a dict
        snapshot = {
            "label": label,
            "turn": self.gs.turn_number,
            "phase": self.gs.current_phase,
            "active_player": self.gs.active_player,
            "ships": copy.deepcopy(self.gs.ships),
            "ordnance": copy.deepcopy(self.gs.ordnance),
            "blast_markers": copy.deepcopy(self.gs.blast_markers),
            "phenomena": copy.deepcopy(self.gs.phenomena),
            "timestamp": time.time(),
        }
        with open(path, "w") as f:
            json.dump(snapshot, f, indent=2)
        return path

    def load_snapshot(self, label: str) -> bool:
        """Load a snapshot, restoring game state."""
        path = os.path.join(self.snapshots_dir, f"{label}.json")
        if not os.path.exists(path):
            return False
        with open(path) as f:
            snapshot = json.load(f)
        self.gs.ships = snapshot["ships"]
        self.gs.ordnance = snapshot["ordnance"]
        self.gs.blast_markers = snapshot["blast_markers"]
        self.gs.turn_number = snapshot["turn"]
        self.gs.current_phase = snapshot["phase"]
        self.gs.active_player = snapshot["active_player"]
        return True

    def list_snapshots(self) -> List[str]:
        """List all snapshot labels in chronological order."""
        if not os.path.exists(self.snapshots_dir):
            return []
        files = sorted(os.listdir(self.snapshots_dir))
        return [f.replace(".json", "") for f in files if f.endswith(".json")]

    def _save_phase_start(self):
        """Save internal snapshot for undo within current phase."""
        self._phase_start_snapshot = {
            "ships": copy.deepcopy(self.gs.ships),
            "ordnance": copy.deepcopy(self.gs.ordnance),
            "blast_markers": copy.deepcopy(self.gs.blast_markers),
        }

    def undo_to_phase_start(self) -> bool:
        """Undo all changes in current phase, restoring to phase start."""
        if self._phase_start_snapshot is None:
            return False
        self.gs.ships = self._phase_start_snapshot["ships"]
        self.gs.ordnance = self._phase_start_snapshot["ordnance"]
        self.gs.blast_markers = self._phase_start_snapshot["blast_markers"]
        self.ships_moved.clear()
        self.ships_fired.clear()
        self.command_check_failed = False
        return True

    def undo_ship_movement(self, ship_id: str) -> bool:
        """Undo a single ship's movement (revert to phase start position)."""
        if self._phase_start_snapshot is None:
            return False
        # Find the ship in the phase start snapshot
        for old_ship_data in self._phase_start_snapshot["ships"]:
            if old_ship_data["id"] == ship_id:
                # Replace in current state
                for i, s in enumerate(self.gs.ships):
                    if s["id"] == ship_id:
                        # Restore position and heading only
                        self.gs.ships[i]["x"] = old_ship_data["x"]
                        self.gs.ships[i]["y"] = old_ship_data["y"]
                        self.gs.ships[i]["heading"] = old_ship_data["heading"]
                        self.gs.ships[i]["special_order"] = old_ship_data["special_order"]
                        self.gs.ships[i]["moved_this_turn"] = False
                        self.gs.ships[i]["distance_moved_this_turn"] = 0.0
                        self.gs.ships[i]["turns_used_this_turn"] = 0
                        self.gs.ships[i]["net_rotation_this_turn"] = 0.0
                        if ship_id in self.ships_moved:
                            self.ships_moved.remove(ship_id)
                        return True
        return False

    # --- Action Recording ---

    def record_action(self, action_type: str, ship_id: str = "",
                      details: Dict = None, result: Dict = None,
                      description: str = ""):
        """Record a game action."""
        action = ActionRecord(
            turn=self.gs.turn_number,
            phase=self.gs.current_phase,
            player=self.gs.active_player,
            action_type=action_type,
            ship_id=ship_id,
            details=details,
            result=result,
            description=description,
        )
        self.actions.append(action)
        if description:
            self.gs.add_log(description)

    def save_actions_log(self):
        """Save all actions to disk."""
        path = os.path.join(self.save_dir, "actions_log.json")
        with open(path, "w") as f:
            json.dump([a.to_dict() for a in self.actions], f, indent=2)

    def load_actions_log(self) -> bool:
        """Load actions from disk."""
        path = os.path.join(self.save_dir, "actions_log.json")
        if not os.path.exists(path):
            return False
        with open(path) as f:
            data = json.load(f)
        self.actions = [ActionRecord.from_dict(d) for d in data]
        return True

    # --- Turn Flow ---

    def start_game(self):
        """Initialize the game, save first snapshot."""
        self.gs.turn_number = 1
        self.gs.current_phase = "movement"
        self.gs.active_player = 1  # determined by scenario or coin toss
        self.save_snapshot("t1_start")
        self.record_action("game_start", description="Game begins")

    def begin_phase(self, phase: str):
        """Start a new phase."""
        self.gs.current_phase = phase
        self._save_phase_start()

        if phase == "movement":
            self.ships_moved.clear()
            self.command_check_failed = False
            # Remove previous special orders (except Brace)
            self._clear_previous_orders()

        elif phase == "shooting":
            self.ships_fired.clear()

        label = f"t{self.gs.turn_number}_{phase}"
        self.save_snapshot(label)
        self.record_action("phase_start",
                          description=f"=== {phase.upper()} PHASE ===")

    def end_phase(self):
        """End current phase and advance to next."""
        current = self.gs.current_phase
        label = f"t{self.gs.turn_number}_{current}_end"
        self.save_snapshot(label)
        self.save_actions_log()
        self.gs.save(self.save_dir)

    def advance_phase(self):
        """Move to the next phase, or next turn if at end phase."""
        current = self.gs.current_phase
        idx = self.PHASES.index(current) if current in self.PHASES else -1

        if idx < len(self.PHASES) - 1:
            # Next phase
            next_phase = self.PHASES[idx + 1]
            self.begin_phase(next_phase)
        else:
            # End of turn, advance to next turn
            self._advance_turn()

    def _advance_turn(self):
        """Move to the next turn."""
        self.gs.turn_number += 1
        # Swap active player
        self.gs.active_player = 2 if self.gs.active_player == 1 else 1

        label = f"t{self.gs.turn_number}_start"
        self.save_snapshot(label)
        self.record_action("turn_start",
                          description=f"=== TURN {self.gs.turn_number} "
                          f"({self._player_name()}) ===")
        self.begin_phase("movement")

    def _clear_previous_orders(self):
        """Remove special orders from start of movement phase (except Brace)."""
        for i, s_dict in enumerate(self.gs.ships):
            if s_dict["player"] == self.gs.active_player:
                if s_dict.get("special_order") != SpecialOrder.BRACE_FOR_IMPACT.value:
                    self.gs.ships[i]["special_order"] = SpecialOrder.NONE.value
                # Reset per-turn flags
                self.gs.ships[i]["moved_this_turn"] = False
                self.gs.ships[i]["has_fired"] = False
                self.gs.ships[i]["disengage_failed_this_turn"] = False
                self.gs.ships[i]["weapons_fired_indices"] = []
                self.gs.ships[i]["weapons_remaining"] = {}
                self.gs.ships[i]["turrets_used_vs"] = ""
                self.gs.ships[i]["brace_failed_vs"] = []
                # Clear per-turn boarding flags (grapple state persists across turns)
                self.gs.ships[i]["has_boarded"] = False
                if not self.gs.ships[i].get("is_grappled", False):
                    self.gs.ships[i]["boarding_target_id"] = None

    def _player_name(self) -> str:
        if self.gs.active_player == 1:
            return self.gs.player1_name
        return self.gs.player2_name

    # --- Movement Phase Helpers ---

    def can_issue_special_order(self, ship: Ship) -> bool:
        """Check if this ship can attempt a special order."""
        if self.command_check_failed:
            return False  # a check already failed this turn
        if ship.player != self.gs.active_player:
            return False
        if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
            return False  # Brace persists, can't override with another order
        return True

    def issue_special_order(self, ship: Ship, order: str) -> Dict:
        """
        Attempt to issue a special order to a ship.
        Returns dict with success status and details.
        """
        from .movement import do_command_check

        result = {"success": False, "order": order, "roll": 0, "needed": 0}

        if not self.can_issue_special_order(ship):
            result["error"] = "Cannot issue orders (check already failed or ship braced)"
            return result

        # Check ponderous restriction
        if order == SpecialOrder.COME_TO_NEW_HEADING.value:
            if "ponderous" in ship.special_rules:
                result["error"] = "Ponderous ships cannot use Come to New Heading"
                return result

        # Determine Ld modifiers
        blast_markers = self.gs.get_blast_markers()
        in_blast = any(
            circle_touches_trefoil(ship.x, ship.y, ship.base_radius,
                                   bm.x, bm.y, bm.heading)
            for bm in blast_markers
        )
        enemy_on_special = any(
            s.get("special_order", "none") != "none"
            for s in self.gs.ships
            if s["player"] != ship.player and not Ship.from_dict(s).is_destroyed
        )

        check = do_command_check(ship, order, self.dice,
                                  enemy_on_special, in_blast)
        passed = check["passed"]
        roll_val = check["roll"]
        needed = check["needed"]

        result["roll"] = roll_val
        result["needed"] = needed

        if passed:
            ship.special_order = order
            if order == SpecialOrder.RELOAD_ORDNANCE.value:
                from .ordnance import reload_ship_ordnance
                for line in reload_ship_ordnance(ship):
                    self.gs.add_log(line)
            self.gs.update_ship(ship)
            result["success"] = True
            self.gs.add_log(
                f"{ship.name}: {order} PASSED (rolled {roll_val} vs Ld {needed})")
            self.record_action(
                "special_order", ship.id,
                details={"order": order, "passed": True,
                         "roll": roll_val, "needed": needed},
                description=f"{ship.name}: {order} PASSED "
                           f"(rolled {roll_val} vs Ld {needed})")
        else:
            self.command_check_failed = True
            result["success"] = False
            result["error"] = (f"{order} FAILED (rolled {roll_val} vs Ld {needed}). "
                              f"No more orders this turn.")
            self.gs.add_log(
                f"{ship.name}: {order} FAILED (rolled {roll_val} vs Ld {needed})")
            self.record_action(
                "special_order", ship.id,
                details={"order": order, "passed": False,
                         "roll": roll_val, "needed": needed},
                description=f"{ship.name}: {order} FAILED "
                           f"(rolled {roll_val} vs Ld {needed})")

        return result

    def issue_squadron_order(self, ships: List[Ship], order: str) -> Dict:
        """
        Roll once (using the highest-Ld ship) to issue the same special order
        to every ship in a squadron.  Returns same result shape as issue_special_order,
        plus 'leader' and 'ships_affected' keys.
        """
        from .movement import do_command_check

        if self.command_check_failed:
            return {"success": False,
                    "error": "A command check already failed this turn."}

        leader = max(ships, key=lambda s: s.leadership)

        if order == SpecialOrder.COME_TO_NEW_HEADING.value:
            ponderous = [s for s in ships if "ponderous" in s.special_rules]
            if ponderous:
                return {"success": False,
                        "error": ("Ponderous ships cannot use Come to New Heading: "
                                  + ", ".join(s.name for s in ponderous))}

        blast_markers = self.gs.get_blast_markers()
        in_blast = any(
            circle_touches_trefoil(leader.x, leader.y, leader.base_radius,
                                   bm.x, bm.y, bm.heading)
            for bm in blast_markers
        )
        enemy_on_special = any(
            s.get("special_order", "none") != "none"
            for s in self.gs.ships
            if s["player"] != leader.player and not Ship.from_dict(s).is_destroyed
        )

        check = do_command_check(leader, order, self.dice, enemy_on_special, in_blast)
        passed = check["passed"]
        roll_val = check["roll"]
        needed = check["needed"]

        result: Dict = {"success": passed, "leader": leader.name,
                        "roll": roll_val, "needed": needed,
                        "order": order, "ships_affected": []}

        if passed:
            for ship in ships:
                if ship.special_order != SpecialOrder.BRACE_FOR_IMPACT.value:
                    ship.special_order = order
                    if order == SpecialOrder.RELOAD_ORDNANCE.value:
                        from .ordnance import reload_ship_ordnance
                        for line in reload_ship_ordnance(ship):
                            self.gs.add_log(line)
                    self.gs.update_ship(ship)
                    result["ships_affected"].append(ship.name)
                    self.gs.add_log(f"  {ship.name}: {order} (squadron order)")
            self.gs.add_log(
                f"Squadron {order} PASSED via {leader.name} "
                f"(rolled {roll_val} vs Ld {needed})")
            self.record_action(
                "squadron_order", leader.id,
                details={"order": order, "passed": True,
                         "roll": roll_val, "needed": needed,
                         "ships": [s.name for s in ships]},
                description=(f"Squadron {order} PASSED via {leader.name} "
                             f"(rolled {roll_val} vs Ld {needed})"))
        else:
            self.command_check_failed = True
            result["error"] = (f"Squadron order FAILED via {leader.name} "
                               f"(rolled {roll_val} vs Ld {needed}). "
                               f"No more orders this turn.")
            self.gs.add_log(
                f"Squadron {order} FAILED via {leader.name} "
                f"(rolled {roll_val} vs Ld {needed})")
            self.record_action(
                "squadron_order", leader.id,
                details={"order": order, "passed": False,
                         "roll": roll_val, "needed": needed},
                description=(f"Squadron {order} FAILED via {leader.name} "
                             f"(rolled {roll_val} vs Ld {needed})"))

        return result

    # --- Fleet Commander Re-rolls ---

    def get_flagship(self, player: int) -> Optional[Ship]:
        """Get the flagship for a player."""
        for s_dict in self.gs.ships:
            if s_dict["player"] == player and s_dict.get("is_flagship", False):
                return Ship.from_dict(s_dict)
        return None

    def get_fleet_rerolls(self, player: int) -> int:
        """Get remaining re-rolls for a player's fleet commander."""
        flagship = self.get_flagship(player)
        if not flagship:
            return 0
        # Bridge Smashed on flagship = all re-rolls lost
        for crit in flagship.critical_damage:
            if crit.get("crit_type") == "bridge_smashed":
                return 0
        if flagship.is_destroyed or flagship.is_disengaged:
            return 0
        return flagship.rerolls_remaining

    def use_fleet_reroll(self, player: int) -> bool:
        """
        Use one fleet commander re-roll.
        Returns True if successful, False if none available.
        """
        flagship = self.get_flagship(player)
        if not flagship or flagship.rerolls_remaining <= 0:
            return False
        # Check bridge smashed
        for crit in flagship.critical_damage:
            if crit.get("crit_type") == "bridge_smashed":
                self.gs.add_log(
                    f"Re-roll unavailable: {flagship.name} bridge is smashed!")
                return False
        if flagship.is_destroyed or flagship.is_disengaged:
            return False

        flagship.rerolls_remaining -= 1
        self.gs.update_ship(flagship)
        self.gs.add_log(
            f"Fleet commander re-roll used! "
            f"({flagship.rerolls_remaining} remaining)")
        self.record_action(
            "use_reroll", flagship.id,
            details={"remaining": flagship.rerolls_remaining},
            description=f"Fleet re-roll used ({flagship.rerolls_remaining} left)")
        return True

    def attempt_reroll_command_check(self, ship: Ship, order: str) -> Dict:
        """
        Re-roll a failed command check using a fleet commander re-roll.
        Returns new check result dict.
        """
        from .movement import do_command_check

        if not self.use_fleet_reroll(ship.player):
            return {"success": False, "error": "No re-rolls available"}

        # Recalculate modifiers
        blast_markers = self.gs.get_blast_markers()
        in_blast = any(
            circle_touches_trefoil(ship.x, ship.y, ship.base_radius,
                                   bm.x, bm.y, bm.heading)
            for bm in blast_markers
        )
        enemy_on_special = any(
            s.get("special_order", "none") != "none"
            for s in self.gs.ships
            if s["player"] != ship.player and not Ship.from_dict(s).is_destroyed
        )

        check = do_command_check(ship, order, self.dice,
                                  enemy_on_special, in_blast)
        passed = check["passed"]
        roll_val = check["roll"]
        needed = check["needed"]

        result = {"success": passed, "roll": roll_val, "needed": needed,
                  "order": order, "rerolled": True}

        if passed:
            ship.special_order = order
            self.gs.update_ship(ship)
            # Undo the command_check_failed flag since re-roll succeeded
            self.command_check_failed = False
            self.gs.add_log(
                f"{ship.name}: RE-ROLL {order} PASSED "
                f"(rolled {roll_val} vs Ld {needed})")
        else:
            # Still failed even after re-roll
            result["error"] = (
                f"RE-ROLL {order} FAILED (rolled {roll_val} vs Ld {needed}). "
                f"No more orders this turn.")
            self.gs.add_log(
                f"{ship.name}: RE-ROLL {order} FAILED "
                f"(rolled {roll_val} vs Ld {needed})")

        return result

    def get_unmoved_ships(self) -> List[Ship]:
        """Get ships belonging to active player that haven't moved yet."""
        ships = []
        for s_dict in self.gs.ships:
            if s_dict["player"] == self.gs.active_player:
                s = Ship.from_dict(s_dict)
                if (not s.is_destroyed and not s.is_disengaged
                        and s.id not in self.ships_moved):
                    ships.append(s)
        return ships

    def get_unfired_ships(self) -> List[Ship]:
        """Get active player ships that haven't fired yet."""
        ships = []
        for s_dict in self.gs.ships:
            if s_dict["player"] == self.gs.active_player:
                s = Ship.from_dict(s_dict)
                if not s.is_destroyed and not s.is_disengaged and s.id not in self.ships_fired:
                    ships.append(s)
        return ships

    def mark_ship_moved(self, ship_id: str):
        self.ships_moved.append(ship_id)

    def mark_ship_fired(self, ship_id: str):
        self.ships_fired.append(ship_id)

    # --- Export / Import ---

    def export_match(self, filepath: str = None) -> str:
        """
        Export entire match as a single .bfg file (ZIP archive).
        """
        if filepath is None:
            filepath = os.path.join(self.save_dir,
                                    f"{self.gs.game_name}.bfg")

        # Save current state first
        self.gs.save(self.save_dir)
        self.save_actions_log()

        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.save_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.save_dir)
                    zf.write(file_path, arcname)

        return filepath

    @classmethod
    def import_match(cls, filepath: str, extract_dir: str = None) -> 'TurnController':
        """
        Import a match from a .bfg file.
        """
        if extract_dir is None:
            name = os.path.splitext(os.path.basename(filepath))[0]
            extract_dir = os.path.join("saves", name)

        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(filepath, 'r') as zf:
            zf.extractall(extract_dir)

        gs = GameState.load(extract_dir)
        dice = DiceRoller(mode=gs.dice_mode)
        tc = cls(gs, dice, extract_dir)
        tc.load_actions_log()
        return tc

    # --- Replay ---

    def get_actions_for_turn(self, turn: int) -> List[ActionRecord]:
        return [a for a in self.actions if a.turn == turn]

    def get_actions_for_phase(self, turn: int, phase: str) -> List[ActionRecord]:
        return [a for a in self.actions
                if a.turn == turn and a.phase == phase]

    def get_snapshot_list(self) -> List[Dict]:
        """Get list of all snapshots with metadata for replay navigation."""
        result = []
        for label in self.list_snapshots():
            path = os.path.join(self.snapshots_dir, f"{label}.json")
            with open(path) as f:
                data = json.load(f)
            result.append({
                "label": label,
                "turn": data.get("turn", 0),
                "phase": data.get("phase", ""),
                "timestamp": data.get("timestamp", 0),
            })
        return result
