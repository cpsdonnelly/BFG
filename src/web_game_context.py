"""Headless GameContext for the Pyodide / web client.

Replaces the Tkinter panel stack.  All player-decision points call
web_ui_stub instead of messagebox.  All board updates post the full
game state as a JSON message to the JS main thread.
"""
import json
from typing import Optional, List

import js
from pyodide.ffi import to_js

from . import web_ui_stub as _ui

from .models import Ship, SpecialOrder
from .game_state import GameState
from .turn_controller import TurnController
from .dice import DiceRoller
from .movement import (
    MoveCommand, validate_movement, execute_movement, attempt_brace,
)
from .combat import (
    apply_damage, check_weapon_in_arc, check_weapon_in_range,
    check_los_clear, resolve_batteries, resolve_lances,
    resolve_nova_cannon,
)
from .end_phase import (
    resolve_end_phase, get_repair_info, apply_repair_choices,
    resolve_hulk_drift,
)
from .scenario import check_game_end


class WebGameContext:
    """Drives one full game from the web client's perspective."""

    def __init__(self):
        self.gs = GameState()
        self.dice = DiceRoller(mode="auto")
        self.tc = TurnController(self.gs, self.dice, save_dir="/saves/bfg_web")
        self.ai = None
        self._log_buf: List[str] = []

    # ── Logging ──────────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        self.gs.add_log(msg)
        js.postMessage(to_js({"type": "log", "msg": msg}))

    def board_redraw(self) -> None:
        js.postMessage(to_js({"type": "state", "data": self._state_snapshot()}))

    def _state_snapshot(self) -> dict:
        return {
            "turn": self.gs.turn_number,
            "phase": self.gs.current_phase,
            "active_player": self.gs.active_player,
            "player1_name": self.gs.player1_name,
            "player2_name": self.gs.player2_name,
            "player1_color": self.gs.player1_color,
            "player2_color": self.gs.player2_color,
            "table_width": self.gs.table_width,
            "table_height": self.gs.table_height,
            "ships": self.gs.ships,
            "ordnance": self.gs.ordnance,
            "blast_markers": self.gs.blast_markers,
            "phenomena": self.gs.phenomena,
            "scenario_mode": self.gs.scenario_mode,
            "artefact_carrier_id": self.gs.artefact_carrier_id,
            "artefact_token_pos": (list(self.gs.artefact_token_pos)
                                   if self.gs.artefact_token_pos else None),
            "ships_moved": self.tc.ships_moved[:],
            "ships_fired": self.tc.ships_fired[:],
            "log": self.gs.log[-60:],
        }

    # ── Ship destruction ──────────────────────────────────────────────────────

    def check_destruction(self, ship: Ship) -> None:
        ship = self.gs.get_ship_by_id(ship.id)
        if not ship or ship.hits_remaining > 0:
            return
        from .combat import resolve_catastrophic
        result = resolve_catastrophic(ship, self.dice, self.gs)
        self.log(f"  {ship.name}: {result}")
        self.board_redraw()

    # ── Pick helpers ──────────────────────────────────────────────────────────

    def pick_ship(self, ships: list, title: str) -> Optional[Ship]:
        if not ships:
            return None
        if len(ships) == 1:
            return ships[0]
        items = [s.id + "|" + s.name + " (" + s.ship_class + ")" for s in ships]
        raw = _ui.pick_from_list(title, items, max_picks=1)
        ship_id = raw.split("|")[0] if "|" in raw else raw
        return self.gs.get_ship_by_id(ship_id)

    def _pick_repairs(self, ship: Ship, repairable: list, max_repairs: int) -> list:
        if max_repairs >= len(repairable):
            return list(repairable)
        items = repairable
        raw = _ui.pick_from_list(
            f"Repair Choice — {ship.name} (pick up to {max_repairs})",
            items, max_picks=max_repairs)
        try:
            chosen = json.loads(raw)
            if isinstance(chosen, list):
                return chosen[:max_repairs]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    # ── Action dispatch ───────────────────────────────────────────────────────

    def dispatch(self, action: dict) -> None:
        name = action.get("name", "")
        data = action.get("data", {})

        if name == "start_game":
            self._start_game(data)
        elif name == "issue_order":
            self._issue_order(data["ship_id"], data["order"])
        elif name == "move_ship":
            self._move_ship(data["ship_id"], data["commands"])
        elif name == "fire":
            self._fire(data["attacker_id"], data["target_id"],
                       data.get("weapon_indices"))
        elif name == "launch_ordnance":
            self._launch_ordnance(data)
        elif name == "move_ordnance":
            self._move_ordnance()
        elif name == "resolve_end":
            self._resolve_end()
        elif name == "next_phase":
            self._next_phase()
        elif name == "run_ai":
            self._run_ai_phase()
        elif name == "disengage":
            self._disengage(data["ship_id"])
        elif name == "place_ship":
            self._place_ship(data["ship_id"], data["x"], data["y"], data["heading"])
        else:
            self.log(f"[web] Unknown action: {name}")

        self.board_redraw()

    # ── Start game ────────────────────────────────────────────────────────────

    def _start_game(self, config: dict) -> None:
        """Initialise GameState from a config dict (matches gs._state_snapshot format)."""
        gs = self.gs

        # Meta
        gs.game_name = config.get("game_name", "bfg_web")
        gs.player1_name = config.get("player1_name", "Player 1")
        gs.player2_name = config.get("player2_name", "Player 2")
        gs.player1_faction = config.get("player1_faction", "imperial_navy")
        gs.player2_faction = config.get("player2_faction", "imperial_navy")
        gs.player1_color = config.get("player1_color", "red")
        gs.player2_color = config.get("player2_color", "blue")
        gs.table_width = config.get("table_width", 120.0)
        gs.table_height = config.get("table_height", 120.0)
        gs.sunward_edge = config.get("sunward_edge", "north")
        gs.points_limit = config.get("points_limit", 750)
        gs.turn_limit = config.get("turn_limit", None)

        # Rules
        gs.rule_boarding = config.get("rule_boarding", False)
        gs.rule_ramming = config.get("rule_ramming", False)
        gs.rule_teleport = config.get("rule_teleport", False)
        gs.rule_hit_and_run = config.get("rule_hit_and_run", False)

        # AI
        gs.ai_player = config.get("ai_player", 2)
        gs.ai_difficulty = config.get("ai_difficulty", "normal")

        # Ships + terrain
        gs.ships = config.get("ships", [])
        gs.phenomena = config.get("phenomena", [])
        gs.ordnance = []
        gs.blast_markers = []

        # Scenario
        gs.scenario_mode = config.get("scenario_mode", "standard")

        # Restart turn controller
        import os
        os.makedirs("/saves/bfg_web", exist_ok=True)
        self.tc = TurnController(self.gs, self.dice, save_dir="/saves/bfg_web")

        # Wire up AI
        if gs.ai_player:
            from .ai_player import AIPlayer
            self.ai = AIPlayer(gs.ai_player, self.tc, gs, self.dice,
                               gs.ai_difficulty)

        self.tc.start_game()
        self.tc.begin_phase("movement")
        self.log(f"=== Game started: {gs.player1_name} vs {gs.player2_name} ===")
        self.log(f"Turn {gs.turn_number} — {gs.current_phase.upper()} PHASE")

    # ── Special orders ────────────────────────────────────────────────────────

    def _issue_order(self, ship_id: str, order: str) -> None:
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return
        res = self.tc.issue_special_order(ship, order)
        if res.get("success"):
            self.log(f"{ship.name}: {order} PASSED "
                     f"(rolled {res['roll']} vs Ld {res['needed']})")
            # Offer fleet re-roll if failed would have happened here
        else:
            self.log(f"{ship.name}: {order} FAILED — {res.get('error', '')}")
            rerolls = self.tc.get_fleet_rerolls(ship.player)
            if rerolls > 0:
                want = _ui.askyesno(
                    "Re-roll?",
                    f"{ship.name}: {order} FAILED.\n"
                    f"Use a fleet commander re-roll? ({rerolls} remaining)")
                if want:
                    rr = self.tc.attempt_reroll_command_check(ship, order)
                    if rr.get("success"):
                        self.log(f"  Re-roll PASSED ({rr['roll']} vs Ld {rr['needed']})")
                    else:
                        self.log(f"  Re-roll FAILED ({rr['roll']} vs Ld {rr['needed']})")

    # ── Movement ──────────────────────────────────────────────────────────────

    def _move_ship(self, ship_id: str, commands_raw: list) -> None:
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return
        if ship_id in self.tc.ships_moved:
            self.log(f"{ship.name} has already moved this turn")
            return

        commands = [MoveCommand(c["type"], c["value"]) for c in commands_raw]

        aaf_bonus = 0
        order = ship.special_order or ""
        if order == SpecialOrder.ALL_AHEAD_FULL.value:
            from .movement import resolve_aaf_speed
            aaf_bonus = resolve_aaf_speed(ship, self.dice)

        res = validate_movement(
            ship, commands,
            special_order=order,
            aaf_bonus=aaf_bonus,
            blast_markers=self.gs.get_blast_markers(),
            table_width=self.gs.table_width,
            table_height=self.gs.table_height,
        )

        if not res.valid:
            self.log(f"{ship.name}: invalid movement — {'; '.join(res.errors)}")
            return

        execute_movement(ship, res, self.gs)
        self.tc.mark_ship_moved(ship_id)

        ship = self.gs.get_ship_by_id(ship_id)
        self.log(f"{ship.name} moved to ({ship.x:.0f},{ship.y:.0f})")

        # Boarding offer
        if self.gs.rule_boarding:
            self._offer_boarding(ship)

    def _offer_boarding(self, ship: Ship) -> None:
        if ship.has_boarded or ship.is_grappled:
            return
        from .boarding import ships_in_base_contact
        enemies = [s for s in self.gs.get_ships()
                   if s.player != ship.player and not s.is_destroyed
                   and not s.is_disengaged
                   and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
        contacted = [e for e in enemies if ships_in_base_contact(ship, e)]
        if not contacted:
            return
        want = _ui.askyesno(
            "Board Enemy?",
            f"{ship.name} is in base contact with "
            f"{', '.join(e.name for e in contacted)}.\nDeclare boarding action?")
        if not want:
            return
        target = contacted[0]
        if len(contacted) > 1:
            target = self.pick_ship(contacted, "Select boarding target")
            if not target:
                return
        ship.boarding_target_id = target.id
        ship.has_boarded = True
        self.gs.update_ship(ship)
        self.log(f"{ship.name} declares boarding against {target.name}")

    # ── Combat ────────────────────────────────────────────────────────────────

    def _fire(self, attacker_id: str, target_id: str,
              weapon_indices: Optional[list]) -> None:
        attacker = self.gs.get_ship_by_id(attacker_id)
        target = self.gs.get_ship_by_id(target_id)
        if not attacker or not target:
            return

        weapons = attacker.weapons
        if weapon_indices is None:
            weapon_indices = list(range(len(weapons)))

        blast_markers = self.gs.get_blast_markers()
        phenomena = self.gs.get_phenomena()
        lock_on = attacker.special_order == SpecialOrder.LOCK_ON.value

        total_hits = 0
        for wi in weapon_indices:
            if wi >= len(weapons):
                continue
            weapon = weapons[wi]
            wtype = weapon.get("weapon_type", "")

            if not check_weapon_in_arc(attacker, weapon, target.x, target.y):
                self.log(f"  {weapon['name']}: target not in arc")
                continue
            if not check_weapon_in_range(attacker, weapon, target.x, target.y):
                self.log(f"  {weapon['name']}: target out of range")
                continue

            los = check_los_clear(attacker, target, phenomena, blast_markers)
            if not los.get("clear", True):
                self.log(f"  {weapon['name']}: LoS blocked ({los.get('reason', '')})")
                continue

            if wtype == "battery":
                result = resolve_batteries(
                    attacker, target, weapon, self.dice, blast_markers,
                    lock_on=lock_on, phenomena=phenomena,
                    all_ships=self.gs.ships)
            elif wtype == "lance":
                result = resolve_lances(attacker, target, weapon, self.dice,
                                        lock_on=lock_on)
            elif wtype == "nova_cannon":
                result = resolve_nova_cannon(attacker, weapon, target.x, target.y,
                                             self.dice, self.gs)
            else:
                continue

            self.log(f"  {result.description}")
            total_hits += result.hits

        if total_hits > 0:
            self._apply_hits(attacker, target, total_hits)

        attacker = self.gs.get_ship_by_id(attacker_id)
        attacker.has_fired = True
        self.gs.update_ship(attacker)
        if attacker_id not in self.tc.ships_fired:
            self.tc.mark_ship_fired(attacker_id)

    def _apply_hits(self, attacker: Ship, target: Ship, total_hits: int) -> None:
        brace = False
        target_player = target.player

        if target_player == self.gs.ai_player:
            from .ai_player import ai_should_brace
            if (ai_should_brace(self.gs, target, total_hits, attacker)
                    and attacker.id not in (target.brace_failed_vs or [])):
                check = attempt_brace(target, self.gs, self.dice)
                if check["passed"]:
                    brace = True
                    self.log(f"  [AI] {target.name} braces — PASSED")
                else:
                    failed_list = list(target.brace_failed_vs or [])
                    failed_list.append(attacker.id)
                    target.brace_failed_vs = failed_list
                    self.gs.update_ship(target)
                    self.log(f"  [AI] {target.name} brace FAILED")
        elif attacker.id not in (target.brace_failed_vs or []):
            want = _ui.askyesno(
                "Brace For Impact?",
                f"{target.name} is taking {total_hits} hits from {attacker.name}.\n"
                f"Attempt Brace For Impact? (Ld test; success = 4+ save per hull hit)\n"
                f"If failed: cannot brace vs {attacker.name} again this phase.")
            if want:
                check = attempt_brace(target, self.gs, self.dice)
                if check["passed"]:
                    brace = True
                    self.log(f"  {target.name} braces — PASSED "
                             f"({check['roll']} vs Ld {check['needed']})")
                else:
                    failed_list = list(target.brace_failed_vs or [])
                    failed_list.append(attacker.id)
                    target.brace_failed_vs = failed_list
                    self.gs.update_ship(target)
                    self.log(f"  {target.name} brace FAILED "
                             f"({check['roll']} vs Ld {check['needed']})")

        dmg = apply_damage(target, total_hits, self.dice, self.gs,
                           target_braced=brace)
        self.log(f"  Shields: {dmg['shield_hits']}, Hull: {dmg['hull_hits']}, "
                 f"Saves: {dmg['brace_saves']}")
        if dmg.get("crits"):
            for crit in dmg["crits"]:
                self.log(f"  CRITICAL: {crit}")
        if dmg.get("crippled"):
            self.log(f"  {target.name} is CRIPPLED!")
        if dmg.get("destroyed"):
            self.log(f"  {target.name} DESTROYED!")

        self.check_destruction(target)

    # ── Ordnance ──────────────────────────────────────────────────────────────

    def _move_ordnance(self) -> None:
        from .ordnance import move_ordnance
        logs = move_ordnance(self.gs, self.dice)
        for line in logs:
            self.log(line)

    def _launch_ordnance(self, data: dict) -> None:
        ship_id = data["ship_id"]
        weapon_index = data.get("weapon_index", 0)
        heading = data.get("heading", 0.0)
        strength = data.get("strength", 1)
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return

        weapons = ship.weapons
        if weapon_index >= len(weapons):
            return
        weapon = weapons[weapon_index]
        wtype = weapon.get("weapon_type", "")

        if wtype == "torpedo":
            from .ordnance import launch_torpedoes
            logs = launch_torpedoes(ship, weapon, heading, strength, self.gs)
        elif wtype == "launch_bay":
            from .ordnance import launch_attack_craft
            craft_type = data.get("craft_type", "fighter")
            logs = launch_attack_craft(ship, weapon, heading, strength,
                                       craft_type, self.gs)
        else:
            self.log(f"Cannot launch from weapon type '{wtype}'")
            return

        for line in logs:
            self.log(line)

    # ── End phase ─────────────────────────────────────────────────────────────

    def _resolve_end(self) -> None:
        # Hulk drift first (start of next movement; run here after end actions)
        drift_logs = resolve_hulk_drift(self.gs, self.dice)
        for line in drift_logs:
            self.log(line)

        # Core auto end phase
        logs = resolve_end_phase(self.gs, self.dice, self.gs.active_player)
        for line in logs:
            self.log(line)

        # Interactive: repair choices
        for ship in self.gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            info = get_repair_info(ship, self.dice, self.gs)
            if info["sixes"] > 0 and info["repairable"]:
                if ship.player == self.gs.ai_player:
                    apply_repair_choices(ship, info["repairable"][:info["sixes"]],
                                         self.gs)
                else:
                    choices = self._pick_repairs(ship, info["repairable"],
                                                 info["sixes"])
                    repair_logs = apply_repair_choices(ship, choices, self.gs)
                    for line in repair_logs:
                        self.log(line)

        # Check victory
        result = check_game_end(self.gs)
        if result:
            self.log(f"=== GAME OVER: {result} ===")
            js.postMessage(to_js({"type": "game_over", "result": result}))

        self.board_redraw()

    # ── Phase advancement ─────────────────────────────────────────────────────

    def _next_phase(self) -> None:
        self.tc.end_phase()
        self.tc.advance_phase()
        phase = self.gs.current_phase
        self.log(f"--- {phase.upper()} PHASE (Turn {self.gs.turn_number}) ---")

        if phase == "movement":
            # Check if active player is AI → run AI movement
            if self.gs.active_player == self.gs.ai_player and self.ai:
                self._run_ai_phase()

    # ── AI ────────────────────────────────────────────────────────────────────

    def _run_ai_phase(self) -> None:
        if not self.ai:
            self.log("[web] No AI configured")
            return

        phase = self.gs.current_phase
        self.log(f"[AI] Running {phase} phase for player {self.gs.active_player}")

        if phase == "movement":
            self.ai.run_movement_phase()
        elif phase == "shooting":
            self.ai.run_shooting_phase()
        elif phase == "ordnance":
            self.ai.run_ordnance_phase()
        elif phase == "end":
            self._resolve_end()
            return

        self.log(f"[AI] {phase} phase complete")
        self.board_redraw()

    # ── Ship placement (deployment) ───────────────────────────────────────────

    def _place_ship(self, ship_id: str, x: float, y: float, heading: float) -> None:
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return
        ship.x = x
        ship.y = y
        ship.heading = heading
        self.gs.update_ship(ship)
        self.log(f"{ship.name} placed at ({x:.0f},{y:.0f}) heading {heading:.0f}°")

    # ── Disengage ─────────────────────────────────────────────────────────────

    def _disengage(self, ship_id: str) -> None:
        from .disengage import attempt_disengage
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return
        result = attempt_disengage(ship, self.gs, self.dice, self.tc)
        self.log(f"{ship.name} disengage: {result.get('description', '')}")
