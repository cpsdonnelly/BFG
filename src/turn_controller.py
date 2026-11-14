"""BFG:XR Turn Controller - Game loop, snapshots, action recording"""
import json
import os
import copy
import time
import zipfile
from typing import List, Dict, Optional
from .game_state import GameState
from .models import Ship, SpecialOrder
from .dice import DiceRoller


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



def _standby(gs, ship) -> bool:
    from .scenarios import on_standby
    return on_standby(gs, ship)


class TurnController:
    """
    Manages game flow: phases, turn order, snapshots, and action recording.
    """

    PHASES = ["movement", "shooting", "ordnance", "end"]

    def __init__(self, game_state: GameState, dice: DiceRoller,
                 save_dir: str = None):
        self.gs = game_state
        self.dice = dice
        from .optional_rules import set_blast_rules, set_ship_source
        set_blast_rules(getattr(game_state, "blast_marker_rules", "standard"))
        from .eldar import set_sunward_edge
        set_sunward_edge(getattr(game_state, "sunward_edge", "north"))
        from .optional_rules import set_suppression_rules
        set_suppression_rules(getattr(game_state, "rule_turret_suppression_remastered", False))
        from .optional_rules import set_sunward
        set_sunward(getattr(game_state, "rule_fighting_sunward", False),
                    getattr(game_state, "sunward_edge", "north"))
        set_ship_source(game_state.get_ships)
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
        self.gs.phenomena = snapshot.get("phenomena", [])
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

    def reset_after_load(self):
        """Clear per-phase tracking after the game state was replaced by a load,
        and re-anchor undo so it can't roll back into the pre-load game."""
        self.ships_moved.clear()
        self.ships_fired.clear()
        self.command_check_failed = False
        self._save_phase_start()

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
                        self.gs.ships[i]["crossed_blast_this_turn"] = False
                        self.gs.ships[i]["distance_since_last_turn"] = 0.0
                        # Demiurg absorber fields: blast markers collected on the
                        # undone move go back on the table
                        back = self.gs.__dict__.get("_bm_collected", {}).pop(
                            (self.gs.turn_number, ship_id), [])
                        if back:
                            have = {b["id"] for b in self.gs.blast_markers}
                            self.gs.blast_markers += [b for b in back if b["id"] not in have]
                            self.gs.ships[i]["collected_blast_markers"] = old_ship_data.get(
                                "collected_blast_markers", 0)
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
        # s.2: the roll-off winner's choice (GamePanel._first_turn_roll_off)
        self.gs.active_player = getattr(self.gs, "first_player", 1) or 1
        self.save_snapshot("t1_start")
        self.record_action("game_start", description="Game begins")

    def _necron_awakening(self, player: int) -> None:
        """Each Necron capital ship conserving power whose Ld, with the modifiers
        of its command checks (Enemy Contacts), meets the alert level's
        threshold awakens for the rest of the game (Xenos p.39)."""
        from .necrons import AWAKEN_LD, starting_alert
        mine = [s for s in self.gs.get_ships() if s.player == player
                and "necron" in s.special_rules and s.ship_type != "escort"
                and not s.is_destroyed and not s.is_disengaged]
        if not mine:
            return
        al = dict(self.gs.necron_alert or {})
        key = str(player)
        if key not in al:
            def worth(p):
                return sum(s.points_value or 0 for s in self.gs.get_ships()
                           if s.player == p and not s.is_destroyed)
            al[key] = starting_alert(worth(3 - player), worth(player))
            self.gs.necron_alert = al
        need = AWAKEN_LD[al[key]]
        contacts = any(e.player != player and e.special_order not in ("none", "")
                       and not e.is_destroyed for e in self.gs.get_ships())
        for s in mine:
            if "necron_awake" in s.special_rules:
                continue
            if s.leadership + (1 if contacts else 0) >= need:
                s.special_rules = list(s.special_rules) + ["necron_awake"]
                self.gs.update_ship(s)
                self.gs.add_log(f"{s.name} awakens (alert level {al[key]}: Ld {need}+)")

    def begin_phase(self, phase: str):
        """Start a new phase."""
        self.gs.current_phase = phase
        self._save_phase_start()
        # A ship's turrets defend against attack craft or against torpedoes and
        # mines "in the same phase" (s.28): the split lasts one phase, every ship
        for i in range(len(self.gs.ships)):
            self.gs.ships[i]["turrets_used_vs"] = ""

        if phase == "movement":
            self.ships_moved.clear()
            self.command_check_failed = False
            # Remove previous special orders (except Brace)
            self._clear_previous_orders()
            # Abaddon's Supreme Leadership: one re-roll a turn, never saved
            for sd in self.gs.ships:
                if sd["player"] == self.gs.active_player and "abaddon" in sd.get(
                        "special_rules", []) and sd.get("status") == "active":
                    sd["rerolls_remaining"] = 1
            # Necron Deadly Awakening (Xenos p.39): at the start of each Necron turn
            self._necron_awakening(self.gs.active_player)
            # Booklet scenarios' start-of-turn effects (The Raiders' alert)
            from .scenarios import turn_start as _scenario_turn_start
            _scenario_turn_start(self.gs, self.dice)
            # s.40: solar flares and radiation bursts at the start of each turn
            from .celestial import start_of_turn as _celestial_start
            _celestial_start(self.gs, self.dice)
            for s in self.gs.get_ships():
                if (s.player == self.gs.active_player and s.must_flee
                        and not s.is_destroyed and not s.is_disengaged):
                    self.gs.add_log(f"{s.name} must move as fast as possible towards the "
                                    f"nearest table edge (failed a forced disengage test)")

        elif phase == "shooting":
            self.ships_fired.clear()

        label = f"t{self.gs.turn_number}_{phase}"
        self.save_snapshot(label)
        self.record_action("phase_start",
                          description=f"=== {phase.upper()} PHASE ===")

    def end_phase(self):
        """End current phase and advance to next."""
        current = self.gs.current_phase
        if current == "movement":
            # Remember how far each of the moving player's ships went: a ship
            # that moved under 5cm counts as Defenses when shot at
            for s_dict in self.gs.ships:
                if s_dict["player"] == self.gs.active_player:
                    s_dict["last_move_cm"] = s_dict.get("distance_moved_this_turn", 0.0)
            # Escort squadrons that lost a ship off the table keep trying to leave
            from .disengage import forced_disengage_tests
            forced_disengage_tests(self.gs, self.dice, self.gs.active_player)
            # Navigate the Storm: materialising ships return to normal
            from .navigate_storm import end_of_movement as _storm_moved
            _storm_moved(self.gs, self.gs.active_player, self.dice)
            # Convoy (narrative): contact markers the defender came near
            from .convoy_narrative import end_of_defender_movement as _cn_moved
            _cn_moved(self.gs, self.gs.active_player, self.dice)
        if current == "end":
            # Booklet scenarios scoring at the end of a player's turn (Domination)
            from .scenarios import score_end_of_turn
            score_end_of_turn(self.gs, self.gs.active_player)
            # Escalating Engagement: the player places its next contact marker
            from .scenarios import _dice_for
            from .escalating import end_of_turn as _ee_end
            _ee_end(self.gs, self.gs.active_player,
                    _dice_for(self.gs, self.gs.active_player, self.dice))
            # Navigate the Storm: ships lost in the warp try to come back, and
            # a returned ship's halved armament ends with the turn
            from .navigate_storm import end_phase as _storm_end, clear_half_armament
            _storm_end(self.gs, self.gs.active_player,
                       _dice_for(self.gs, self.gs.active_player, self.dice))
            clear_half_armament(self.gs, self.gs.active_player)
            # Mark of Chaos Undivided lasts until the end of the turn
            from .chaos_undivided import end_turn as _undivided_end
            _undivided_end(self.gs, self.gs.active_player)
            from .celestial import end_of_turn as _celestial_end
            _celestial_end(self.gs, self.gs.active_player)
        if current == "ordnance":
            # Torpedo bomber salvos have limited fuel (s.21)
            from .ordnance import remove_spent_salvos
            remove_spent_salvos(self.gs)
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
                # The order a braced ship was on before bracing (e.g. All Ahead
                # Full) only affected the move it had already made (s.7)
                self.gs.ships[i]["previous_order"] = SpecialOrder.NONE.value
                # Reset per-turn flags
                self.gs.ships[i]["moved_this_turn"] = False
                # (the movement panel resets these too; alternate activation
                # has no panel phase start, and Planet Strike's bombardment
                # reads them at the end of the turn)
                self.gs.ships[i]["distance_moved_this_turn"] = 0.0
                self.gs.ships[i]["turns_used_this_turn"] = 0
                self.gs.ships[i]["net_rotation_this_turn"] = 0.0
                self.gs.ships[i]["distance_since_last_turn"] = 0.0
                self.gs.ships[i]["collected_blast_markers"] = 0   # unused markers are lost
                self.gs.ships[i]["has_fired"] = False
                self.gs.ships[i]["disengage_failed_this_turn"] = False
                self.gs.ships[i]["weapons_fired_indices"] = []
                self.gs.ships[i]["weapons_remaining"] = {}
                self.gs.ships[i]["weapon_pool_mode"] = {}
                self.gs.ships[i]["turrets_used_vs"] = ""
                self.gs.ships[i]["brace_failed_vs"] = []
                self.gs.ships[i]["target_priority_turn"] = -1
                self.gs.ships[i]["machine_spirit_used_vs"] = []
                # Clear per-turn boarding flags (grapple state persists across turns)
                self.gs.ships[i]["has_boarded"] = False
                self.gs.ships[i]["aa_locked"] = False
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
        from .scenarios import orders_forbidden
        if orders_forbidden(self.gs, ship):
            return False
        return True

    def issue_special_order(self, ship: Ship, order: str) -> Dict:
        """
        Attempt to issue a special order to a ship.
        Returns dict with success status and details.
        """
        from .movement import do_command_check

        result = {"success": False, "order": order, "roll": 0, "needed": 0}

        from .scenarios import orders_forbidden
        why = orders_forbidden(self.gs, ship)
        if why:
            result["error"] = why
            return result
        if "immobile" in ship.special_rules and order in (
                SpecialOrder.ALL_AHEAD_FULL.value, SpecialOrder.BURN_RETROS.value,
                SpecialOrder.COME_TO_NEW_HEADING.value):
            result["error"] = ("Defences can't use All Ahead Full, Burn Retros or Come to "
                               "New Heading (Support Assets)")
            return result

        if (order == SpecialOrder.ALL_AHEAD_FULL.value and any(
                c.get("crit_type") == "inertialess_drive" for c in ship.critical_damage)):
            result["error"] = "Inertialess Drive Damaged: no All Ahead Full until repaired"
            return result
        if order == SpecialOrder.RELOAD_ORDNANCE.value and "necron" in ship.special_rules \
                and "tomb_complex" not in ship.special_rules:
            result["error"] = "Necron ships may not use Reload Ordnance (Xenos p.39)"
            return result
        if order == SpecialOrder.BURN_RETROS.value and "eldar_mms" in ship.special_rules:
            result["error"] = "Eldar may not use Burn Retros (MMS p.3)"
            return result
        if not self.can_issue_special_order(ship):
            result["error"] = "Cannot issue orders (check already failed or ship braced)"
            return result

        # Check ponderous restriction
        if order == SpecialOrder.COME_TO_NEW_HEADING.value:
            if "ponderous" in ship.special_rules:
                result["error"] = "Ponderous ships cannot use Come to New Heading"
                return result

        # Demiurg: markers in contact as it begins its move are collected first
        # (no Under Fire for a movement-phase order); Brace is checked normally
        if order != SpecialOrder.BRACE_FOR_IMPACT.value and self.gs.current_phase == "movement":
            from .movement import collect_blast_markers
            if collect_blast_markers(ship, self.gs):
                self.gs.update_ship(ship)
        # Determine Ld modifiers
        blast_markers = self.gs.get_blast_markers()
        from .geometry import count_blast_markers_touching
        in_blast = count_blast_markers_touching(ship, blast_markers) > 0
        enemy_on_special = any(
            s.get("special_order", "none") != "none"
            for s in self.gs.ships
            if s["player"] != ship.player and not Ship.from_dict(s).is_destroyed
        )

        check = do_command_check(ship, order, self.dice,
                                  enemy_on_special, in_blast, gs=self.gs)
        passed = check["passed"]
        roll_val = check["roll"]
        needed = check["needed"]

        result["roll"] = roll_val
        result["needed"] = needed

        if passed:
            self.apply_passed_order(ship, order)
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

        from .squadron import partition_by_coherency
        in_coh, out_coh = partition_by_coherency(ships)
        for s in out_coh:
            self.gs.add_log(
                f"  {s.name}: out of squadron coherency — must use individual order "
                f"(own Ld {s.leadership})")
        ships = in_coh
        if not ships:
            return {"success": False,
                    "error": "No ships in squadron coherency — cannot issue a squadron order."}

        leader = max(ships, key=lambda s: s.leadership)

        if order == SpecialOrder.COME_TO_NEW_HEADING.value:
            ponderous = [s for s in ships if "ponderous" in s.special_rules]
            if ponderous:
                return {"success": False,
                        "error": ("Ponderous ships cannot use Come to New Heading: "
                                  + ", ".join(s.name for s in ponderous))}

        blast_markers = self.gs.get_blast_markers()
        if order != SpecialOrder.BRACE_FOR_IMPACT.value and self.gs.current_phase == "movement":
            from .movement import collect_blast_markers
            if collect_blast_markers(leader, self.gs):
                self.gs.update_ship(leader)
            blast_markers = self.gs.get_blast_markers()
        from .geometry import count_blast_markers_touching
        in_blast = count_blast_markers_touching(leader, blast_markers) > 0
        enemy_on_special = any(
            s.get("special_order", "none") != "none"
            for s in self.gs.ships
            if s["player"] != leader.player and not Ship.from_dict(s).is_destroyed
        )

        check = do_command_check(leader, order, self.dice, enemy_on_special, in_blast,
                                 gs=self.gs)
        passed = check["passed"]
        roll_val = check["roll"]
        needed = check["needed"]

        result: Dict = {"success": passed, "leader": leader.name,
                        "roll": roll_val, "needed": needed,
                        "order": order, "ships_affected": []}

        if passed:
            for ship in ships:
                if ship.special_order != SpecialOrder.BRACE_FOR_IMPACT.value:
                    self.apply_passed_order(ship, order)
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
        for s in self.gs.player_ships(player):
            if s.is_flagship:
                return s
        return None

    def apply_passed_order(self, ship: Ship, order: str) -> None:
        """Put a ship on an order whose command check passed.

        Re-reads the ship from game state first: if it is the flagship that
        just spent a re-roll, the caller's copy still has the old count.
        """
        ship = self.gs.get_ship_by_id(ship.id) or ship
        ship.special_order = order
        if order == SpecialOrder.RELOAD_ORDNANCE.value:
            from .ordnance import reload_ship_ordnance
            for line in reload_ship_ordnance(ship):
                self.gs.add_log(line)
        self.gs.update_ship(ship)

    def _own_reroll_holder(self, ship: Optional[Ship]) -> Optional[Ship]:
        """A secondary commander with re-rolls left on this ship or in its
        squadron (usable only for that ship or squadron, s.5); lost if its
        ship suffers Bridge Smashed or is destroyed."""
        if ship is None:
            return None
        for s in self.gs.get_ships():
            if s.own_rerolls <= 0 or s.player != ship.player or s.is_destroyed:
                continue
            if any(c.get("crit_type") == "bridge_smashed" for c in s.critical_damage):
                continue
            if s.id == ship.id or (ship.squadron_id and s.squadron_id == ship.squadron_id):
                return s
        return None

    def get_fleet_rerolls(self, player: int, ship: Optional[Ship] = None) -> int:
        """Re-rolls available: the fleet commander's, plus a secondary
        commander's own when `ship` is his ship or in his squadron."""
        holder = self._own_reroll_holder(ship)
        own = holder.own_rerolls if holder else 0
        fleet = 0 if self._radiation_blocks(player, ship) else self._commander_rerolls(player)
        return own + fleet + self._war_host_rerolls(player, ship)

    def _war_host_rerolls(self, player: int, ship: Optional[Ship]) -> int:
        """Demiurg War Host re-rolls: usable by any Demiurg vessel, not lost
        with the ship they were bought on."""
        if ship is None or "demiurg_commerce" not in ship.special_rules:
            return 0
        return sum(s.war_host_rerolls for s in self.gs.get_ships() if s.player == player)

    def _commander_rerolls(self, player: int) -> int:
        flagship = self.get_flagship(player)
        if not flagship:
            return 0
        # Bridge Smashed on flagship = all re-rolls lost
        for crit in flagship.critical_damage:
            if crit.get("crit_type") == "bridge_smashed":
                return 0
        # Re-rolls are lost if the commander's ship suffers Bridge Smashed or
        # is destroyed (booklet update 33, owner ruling)
        if flagship.is_destroyed:
            return 0
        return flagship.rerolls_remaining

    def _radiation_blocks(self, player: int, ship) -> bool:
        """s.40: during a radiation burst fleet commanders may only use their
        re-rolls for their own ship or squadron."""
        from .celestial import radiation_active
        if ship is None or not radiation_active(self.gs):
            return False
        flag = self.get_flagship(player)
        if flag is None or ship.id == flag.id:
            return False
        return not (flag.squadron_id and ship.squadron_id == flag.squadron_id)

    def use_fleet_reroll(self, player: int, ship: Optional[Ship] = None) -> bool:
        """
        Use one re-roll: a secondary commander's own first (when `ship` is his
        ship or squadron), else the fleet commander's.
        Returns True if successful, False if none available.
        """
        holder = self._own_reroll_holder(ship)
        if holder is not None:
            holder.own_rerolls -= 1
            self.gs.update_ship(holder)
            self.gs.add_log(f"{holder.name}'s commander re-roll used "
                            f"({holder.own_rerolls} left)")
            return True
        flagship = self.get_flagship(player)
        if (not flagship or flagship.rerolls_remaining <= 0) and self._war_host_rerolls(player, ship):
            pool = next(s for s in self.gs.get_ships()
                        if s.player == player and s.war_host_rerolls > 0)
            pool.war_host_rerolls -= 1
            self.gs.update_ship(pool)
            self.gs.add_log(f"War Host re-roll used ({self._war_host_rerolls(player, ship)} left)")
            return True
        if not flagship or flagship.rerolls_remaining <= 0:
            return False
        # Check bridge smashed
        for crit in flagship.critical_damage:
            if crit.get("crit_type") == "bridge_smashed":
                self.gs.add_log(
                    f"Re-roll unavailable: {flagship.name} bridge is smashed!")
                return False
        if flagship.is_destroyed:
            return False                 # the commander is lost with his ship
        if self._radiation_blocks(player, ship):
            self.gs.add_log("Radiation burst: the fleet commander's re-rolls are only for "
                            "his own ship or squadron this turn")
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

        if not self.use_fleet_reroll(ship.player, ship):
            return {"success": False, "error": "No re-rolls available"}

        # Recalculate modifiers
        blast_markers = self.gs.get_blast_markers()
        from .geometry import count_blast_markers_touching
        in_blast = count_blast_markers_touching(ship, blast_markers) > 0
        enemy_on_special = any(
            s.get("special_order", "none") != "none"
            for s in self.gs.ships
            if s["player"] != ship.player and not Ship.from_dict(s).is_destroyed
        )

        check = do_command_check(ship, order, self.dice,
                                  enemy_on_special, in_blast, gs=self.gs)
        passed = check["passed"]
        roll_val = check["roll"]
        needed = check["needed"]

        result = {"success": passed, "roll": roll_val, "needed": needed,
                  "order": order, "rerolled": True}

        if passed:
            self.apply_passed_order(ship, order)
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

    # Alternate activation: during a human's activation only the ships of the
    # unit being activated may act (set by AAPanelMixin; None otherwise)
    aa_allowed = None

    def _aa_ok(self, s) -> bool:
        return self.aa_allowed is None or self.aa_allowed(s)

    def get_unmoved_ships(self) -> List[Ship]:
        """Get ships belonging to active player that haven't moved yet."""
        return [s for s in self.gs.player_ships(self.gs.active_player)
                if (not s.is_destroyed and not s.is_disengaged
                    and s.id not in self.ships_moved and self._aa_ok(s)
                    and "immobile" not in s.special_rules       # defences never move
                    and not _standby(self.gs, s))]              # Surprise Attack

    def get_unfired_ships(self) -> List[Ship]:
        """Get active player ships that haven't fired yet."""
        return [s for s in self.gs.player_ships(self.gs.active_player)
                if (not s.is_destroyed and not s.is_disengaged
                    and s.id not in self.ships_fired and self._aa_ok(s)
                    and not _standby(self.gs, s))]

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
