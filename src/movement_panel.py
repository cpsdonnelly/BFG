"""BFG:XR — MovementPanel: ship movement UI and drag-drop callbacks."""
import tkinter as tk
from tkinter import messagebox
import math

from .models import Ship, SpecialOrder
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE)
from .game_context import GameContext
from .special_orders_ui import SpecialOrderMixin
from .movement_dialog import MovementDialogMixin


class MovementPanel(SpecialOrderMixin, MovementDialogMixin):

    def _resolve_post_move_terrain(self, ship_id: str, on_aaf: bool):
        """Run asteroid/warp-rift/dust-cloud navigation tests flagged during
        movement, log the results, and clear the flags from the ship."""
        from .terrain_effects import (resolve_asteroid_navigation,
                                      resolve_warp_rift_navigation,
                                      resolve_gas_dust_contact)

        def _clear_flag(flag):
            u = self.ctx.gs.get_ship_by_id(ship_id)
            if u:
                u.special_rules = [r for r in u.special_rules if r != flag]
                self.ctx.gs.update_ship(u)
            return u

        updated = self.ctx.gs.get_ship_by_id(ship_id)
        if not updated or updated.is_disengaged:
            return
        if "in_asteroid_field" in (updated.special_rules or []):
            nav = resolve_asteroid_navigation(
                updated, self.ctx.dice, self.ctx.gs, on_aaf)
            if not nav["passed"]:
                self.ctx.log(
                    f"  {updated.name}: asteroid damage {nav['damage']} HP!")
                self.ctx.check_destruction(updated)
            updated = _clear_flag("in_asteroid_field")
        if updated and "in_warp_rift" in (updated.special_rules or []):
            nav = resolve_warp_rift_navigation(updated, self.ctx.dice, self.ctx.gs)
            if not nav["passed"]:
                self.ctx.log(f"  {updated.name}: LOST IN THE WARP!")
            else:
                pos = nav.get("new_position", (0, 0))
                self.ctx.log(
                    f"  {updated.name}: emerged at ({pos[0]:.0f}, {pos[1]:.0f})")
            updated = _clear_flag("in_warp_rift")
        if updated and "in_dust_cloud" in (updated.special_rules or []):
            resolve_gas_dust_contact(updated, self.ctx.dice, self.ctx.gs)
            _clear_flag("in_dust_cloud")
    """Handles all ship movement UI: drag-drop, dialog, M-key, scroll-wheel."""

    def __init__(self, ctx: GameContext):
        self.ctx = ctx
        self._pending_turn: dict = {}
        self._board_scroll_fn = None

    def wire_drag_callbacks(self):
        """Connect board_view drag-and-drop hooks to game panel movement logic."""

        def can_drag(ship):
            if self.ctx.gs.current_phase != "movement":
                return False
            if ship.player != self.ctx.gs.active_player:
                return False
            unmoved_ids = {s.id for s in self.ctx.tc.get_unmoved_ships()}
            return ship.id in unmoved_ids

        def commit_drag(ship, commands):
            from .movement import validate_movement, execute_movement, resolve_aaf_speed
            order = ship.special_order
            aaf_bonus = 0
            if order == "all_ahead_full":
                aaf_bonus = resolve_aaf_speed(ship, self.ctx.dice)
                self.ctx.log(f"{ship.name} AAF speed bonus: +{aaf_bonus}cm")
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.ctx.gs.get_blast_markers(),
                self.ctx.gs.table_width, self.ctx.gs.table_height,
                turns_already_used=ship.turns_used_this_turn)
            if not result.valid:
                return  # path became invalid between preview and release — discard
            execute_movement(ship, result, self.ctx.gs)
            self._resolve_post_move_terrain(ship.id, order == "all_ahead_full")

            # Update staged tracking fields
            final_ship = self.ctx.gs.get_ship_by_id(ship.id)
            if final_ship:
                final_ship.distance_moved_this_turn += result.total_distance
                final_ship.turns_used_this_turn += result.turns_used
                left_deg = sum(c.value for c in commands if c.action == "turn_left")
                right_deg = sum(c.value for c in commands if c.action == "turn_right")
                final_ship.net_rotation_this_turn += (left_deg - right_deg)
                self.ctx.gs.update_ship(final_ship)

                # Lock the ship only when its movement budget is exhausted
                base_speed = final_ship.effective_speed
                max_budget = (base_speed + aaf_bonus
                              if order == "all_ahead_full"
                              else (base_speed // 2
                                    if order == "burn_retros"
                                    else base_speed))
                remaining = max_budget - final_ship.distance_moved_this_turn
                if remaining <= 0.1:
                    self.ctx.tc.mark_ship_moved(ship.id)
                    self.ctx.log(
                        f"{ship.name}: drag-moved {result.total_distance:.1f}cm "
                        f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                        f"hdg {result.final_heading:.0f}°")
                else:
                    self.ctx.log(
                        f"{ship.name}: drag-moved {result.total_distance:.1f}cm "
                        f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                        f"hdg {result.final_heading:.0f}° — {remaining:.1f}cm remaining")
            self.ctx.board.redraw()

        self.ctx.board.can_drag_ship_fn = can_drag
        self.ctx.board.commit_drag_fn = commit_drag

        # M key: execute min-move for selected ship (staged, no dialog)
        self.ctx.root.bind("m", lambda e: self._quick_min_move_selected())
        self.ctx.root.bind("M", lambda e: self._quick_min_move_selected())

        # Spacebar: min-move ALL unmoved ships for active player
        self.ctx.root.bind("<space>", lambda e: self._min_move_all_ships())

        # Backspace: undo all movement this turn
        self.ctx.root.bind("<BackSpace>", lambda e: self._undo_all_movement())

        # Ordnance launch drag callbacks
        def can_ord_drag(ship):
            if self.ctx.gs.current_phase != "ordnance":
                return False
            if ship.player != self.ctx.gs.active_player:
                return False
            if ship.is_destroyed or ship.is_disengaged:
                return False
            return ship.ordnance_loaded_torps or ship.ordnance_loaded_craft

        def commit_ord_drag(ship, heading):
            self.ctx.ordnance._launch_ordnance_dialog(
                preselected_ship=ship, preselected_heading=heading)

        self.ctx.board.can_ord_drag_fn = can_ord_drag
        self.ctx.board.commit_ord_drag_fn = commit_ord_drag

        # Board-level scroll wheel: add pending turn to selected ship
        def _on_board_scroll(event):
            if self.ctx.gs.current_phase != "movement":
                return
            ship_id = self.ctx.board.selected_ship_id
            if not ship_id:
                return
            ship = self.ctx.gs.get_ship_by_id(ship_id)
            if not ship or ship.player != self.ctx.gs.active_player:
                return
            unmoved_ids = {s.id for s in self.ctx.tc.get_unmoved_ships()}
            if ship_id not in unmoved_ids:
                return
            if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
                delta = 5.0
            elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
                delta = -5.0
            else:
                return
            current = self._pending_turn.get(ship_id, 0.0)
            new_val = max(-float(ship.turn_angle),
                          min(float(ship.turn_angle), current + delta))
            self._pending_turn[ship_id] = new_val
            self.ctx.board.redraw()
            self._redraw_pending_turn_ghost()

        self.ctx.board.canvas.bind("<MouseWheel>", _on_board_scroll)
        self.ctx.board.canvas.bind("<Button-4>", _on_board_scroll)
        self.ctx.board.canvas.bind("<Button-5>", _on_board_scroll)
        self._board_scroll_fn = _on_board_scroll

    def _quick_min_move_selected(self):
        """
        M key: execute the selected ship's minimum move immediately (no dialog),
        including any pending scroll-wheel turn, and update staged movement tracking.
        The ship is NOT marked fully moved — the player can continue giving orders.

        If there is no remaining movement budget after the min-move (e.g. AAF),
        the ship is marked fully moved automatically.
        """
        from .movement import (MoveCommand, validate_movement, execute_movement,
                               resolve_aaf_speed)

        if self.ctx.gs.current_phase != "movement":
            return

        ship_id = self.ctx.board.selected_ship_id
        if not ship_id:
            self.ctx.board.status_var.set("M: no ship selected — click a ship first")
            return

        ship = self.ctx.gs.get_ship_by_id(ship_id)
        if not ship:
            return
        if ship.player != self.ctx.gs.active_player:
            self.ctx.board.status_var.set(f"M: {ship.name} belongs to the other player")
            return
        unmoved_ids = {s.id for s in self.ctx.tc.get_unmoved_ships()}
        if ship.id not in unmoved_ids:
            self.ctx.board.status_var.set(f"M: {ship.name} has already moved this turn")
            return
        if ship.is_grappled:
            self.ctx.board.status_var.set(f"M: {ship.name} is locked in boarding combat")
            return

        order = ship.special_order
        base = ship.effective_speed
        aaf_bonus = 0

        if order == "all_ahead_full":
            # Offer ramming declaration before the speed roll
            if self.ctx.gs.rule_ramming and ship.ramming_target_id is None:
                enemies = [s for s in self.ctx.gs.get_ships()
                           if s.player != ship.player
                           and not s.is_destroyed and not s.is_disengaged
                           and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
                if enemies and messagebox.askyesno(
                        "Declare Ramming Target",
                        f"{ship.name} is on All Ahead Full.\n"
                        f"Declare a ramming target before the speed roll?"):
                    ram_target = self.ctx.pick_ship(enemies, "Select Ramming Target")
                    if ram_target:
                        from .combat import ram_ld_dice
                        n_dice = ram_ld_dice(ship.ship_type, ram_target.ship_type)
                        rolls = self.ctx.dice.roll_d6(n_dice, "ram command check")
                        total = sum(rolls)
                        if total <= ship.leadership:
                            ship.ramming_target_id = ram_target.id
                            self.ctx.gs.update_ship(ship)
                            self.ctx.log(
                                f"{ship.name} declares ram on {ram_target.name}! "
                                f"Ld check {n_dice}D6={total} ≤ {ship.leadership} PASSED")
                        else:
                            self.ctx.log(
                                f"{ship.name} ram attempt failed — "
                                f"{n_dice}D6={total} > {ship.leadership} Ld")
            aaf_bonus = resolve_aaf_speed(ship, self.ctx.dice)
            self.ctx.log(f"{ship.name} AAF speed bonus: +{aaf_bonus}cm")
            move_dist = float(base + aaf_bonus)
        elif order == "burn_retros":
            move_dist = float(base // 2)
        else:
            move_dist = float(max(1, base // 2))

        # Remaining budget after any prior staged movement
        already_moved = ship.distance_moved_this_turn
        remaining_budget = max(0.0, (base + aaf_bonus if order == "all_ahead_full"
                                     else (base // 2 if order == "burn_retros"
                                           else base)) - already_moved)
        if remaining_budget < 0.5:
            self.ctx.board.status_var.set(
                f"M: {ship.name} has no remaining movement budget")
            return
        move_dist = min(move_dist, remaining_budget)

        # Build commands: forward then any pending scroll-wheel turn
        commands = [MoveCommand("forward", move_dist)]
        pending_deg = self._pending_turn.pop(ship_id, 0.0)
        if abs(pending_deg) > 0.1 and ship.turns_used_this_turn < 1:
            action = "turn_left" if pending_deg > 0 else "turn_right"
            commands.append(MoveCommand(action, abs(pending_deg)))

        result = validate_movement(
            ship, commands, order, aaf_bonus,
            self.ctx.gs.get_blast_markers(),
            self.ctx.gs.table_width, self.ctx.gs.table_height,
            turns_already_used=ship.turns_used_this_turn)

        if not result.valid:
            # Try without the turn if the combined command fails
            if len(commands) > 1:
                commands = [MoveCommand("forward", move_dist)]
                result = validate_movement(
                    ship, commands, order, aaf_bonus,
                    self.ctx.gs.get_blast_markers(),
                    self.ctx.gs.table_width, self.ctx.gs.table_height,
                    turns_already_used=ship.turns_used_this_turn)
            if not result.valid:
                self.ctx.board.status_var.set(
                    f"M: {ship.name} invalid — {result.errors[0]}")
                return

        start_x, start_y = ship.x, ship.y
        execute_movement(ship, result, self.ctx.gs)

        # Resolve ramming if a target was declared
        if ship.ramming_target_id:
            from .geometry import line_passes_near
            from .combat import resolve_ram
            ram_target = self.ctx.gs.get_ship_by_id(ship.ramming_target_id)
            ship = self.ctx.gs.get_ship_by_id(ship_id)
            if ram_target and ship:
                threshold = ship.base_radius + ram_target.base_radius
                if line_passes_near(start_x, start_y, ship.x, ship.y,
                                    ram_target.x, ram_target.y, threshold):
                    self.ctx.log(f"  {ship.name} rams {ram_target.name}!")
                    resolve_ram(ship, ram_target, self.ctx.dice, self.ctx.gs)
                    self.ctx.check_destruction(ram_target)
                    self.ctx.check_destruction(ship)
                    self.ctx.board.redraw()
                else:
                    self.ctx.log(f"  {ship.name} missed the ram — {ram_target.name} not contacted")
            ship = self.ctx.gs.get_ship_by_id(ship_id) or ship
            ship.ramming_target_id = None
            self.ctx.gs.update_ship(ship)

        # Offer boarding declaration if rule is on and ship is in base contact with enemy
        if self.ctx.gs.rule_boarding:
            ship = self.ctx.gs.get_ship_by_id(ship_id)
            if ship and not ship.has_boarded and not ship.is_grappled:
                from .boarding import ships_in_base_contact
                enemies = [s for s in self.ctx.gs.get_ships()
                           if s.player != ship.player
                           and not s.is_destroyed and not s.is_disengaged
                           and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
                contacted = [e for e in enemies if ships_in_base_contact(ship, e)]
                if contacted:
                    target_names = ", ".join(e.name for e in contacted)
                    if messagebox.askyesno(
                            "Declare Boarding Action",
                            f"{ship.name} is in base contact with {target_names}.\n"
                            f"Declare a boarding action?\n"
                            f"(Ship cannot fire weapons or launch ordnance this turn)"):
                        board_target = (contacted[0] if len(contacted) == 1
                                        else self.ctx.pick_ship(contacted,
                                                                 "Select boarding target"))
                        if board_target:
                            ship.boarding_target_id = board_target.id
                            ship.has_boarded = True
                            self.ctx.gs.update_ship(ship)
                            self.ctx.log(
                                f"{ship.name} declares boarding action against "
                                f"{board_target.name}!")

        # Update staged tracking fields on the now-moved ship
        ship = self.ctx.gs.get_ship_by_id(ship_id)
        if ship:
            ship.distance_moved_this_turn += result.total_distance
            ship.turns_used_this_turn += result.turns_used
            left_deg = sum(c.value for c in commands if c.action == "turn_left")
            right_deg = sum(c.value for c in commands if c.action == "turn_right")
            ship.net_rotation_this_turn += (left_deg - right_deg)
            self.ctx.gs.update_ship(ship)

            # If no budget remains, mark fully moved
            max_budget = (base + aaf_bonus if order == "all_ahead_full"
                          else (base // 2 if order == "burn_retros" else base))
            if ship.distance_moved_this_turn >= max_budget - 0.1:
                self.ctx.tc.mark_ship_moved(ship_id)
                self.ctx.log(
                    f"{ship.name}: M-move complete {ship.distance_moved_this_turn:.0f}cm"
                    + (f" ↶{left_deg:.0f}°" if left_deg > 0.1 else "")
                    + (f" ↷{right_deg:.0f}°" if right_deg > 0.1 else ""))
            else:
                self.ctx.log(
                    f"{ship.name}: min-move {result.total_distance:.0f}cm"
                    + (f" ↶{left_deg:.0f}°" if left_deg > 0.1 else "")
                    + (f" ↷{right_deg:.0f}°" if right_deg > 0.1 else "")
                    + f" — {max_budget - ship.distance_moved_this_turn:.0f}cm remaining")
            self.ctx.board.status_var.set(
                f"M: {ship.name} moved {result.total_distance:.0f}cm")

        self._redraw_pending_turn_ghost()
        self.ctx.board.canvas.focus_set()
        self.ctx.board.redraw()

    # --- Game Flow ---

    def _min_move_all_ships(self):
        """Spacebar: execute minimum move for every unmoved ship of the active player."""
        from .movement import MoveCommand, validate_movement, execute_movement, resolve_aaf_speed

        if self.ctx.gs.current_phase != "movement":
            return
        unmoved = [s for s in self.ctx.tc.get_unmoved_ships()
                   if s.player == self.ctx.gs.active_player]
        if not unmoved:
            return

        moved_count = 0
        for ship in unmoved:
            order = ship.special_order
            base = ship.effective_speed
            aaf_bonus = 0
            if order == "all_ahead_full":
                aaf_bonus = resolve_aaf_speed(ship, self.ctx.dice)
                move_dist = float(base + aaf_bonus)
            elif order == "burn_retros":
                move_dist = float(base // 2)
            else:
                move_dist = float(max(1, base // 2))

            commands = [MoveCommand("forward", move_dist)]
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.ctx.gs.get_blast_markers(),
                self.ctx.gs.table_width, self.ctx.gs.table_height)
            if not result.valid:
                self.ctx.log(
                    f"  {ship.name}: min-move skipped — {result.errors[0]}")
                continue

            execute_movement(ship, result, self.ctx.gs)
            self.ctx.tc.mark_ship_moved(ship.id)
            # Update staged fields so dialog is consistent if opened later
            updated = self.ctx.gs.get_ship_by_id(ship.id)
            if updated:
                updated.distance_moved_this_turn += result.total_distance
                self.ctx.gs.update_ship(updated)
            moved_count += 1

        self.ctx.log(f"Spacebar: min-moved {moved_count} ships")
        self.ctx.board.canvas.focus_set()
        self.ctx.board.redraw()

    def _undo_all_movement(self):
        """Backspace: undo all ship movement this turn, restoring phase-start positions."""
        if self.ctx.gs.current_phase != "movement":
            return
        if self.ctx.tc.undo_to_phase_start():
            self._pending_turn.clear()
            self.ctx.log("Backspace: all movement undone")
            self.ctx.board.status_var.set("All movement undone")
            self.ctx.board.canvas.focus_set()
            self.ctx.board.redraw()

    def _redraw_pending_turn_ghost(self):
        """Draw a ghost on the board canvas showing pending scroll-wheel turn result."""
        ship_id = self.ctx.board.selected_ship_id
        if not ship_id:
            return
        pending = self._pending_turn.get(ship_id, 0.0)
        ship = self.ctx.gs.get_ship_by_id(ship_id)
        if not ship or abs(pending) < 0.1:
            return

        from .movement import get_effective_speed
        order = ship.special_order
        _, max_spd = get_effective_speed(ship, order)
        remaining_budget = max(0.0, max_spd - ship.distance_moved_this_turn)
        if order == "all_ahead_full":
            move_dist = remaining_budget
        elif order == "burn_retros":
            move_dist = min(float(max_spd), remaining_budget)
        else:
            move_dist = min(float(max(1, ship.effective_speed // 2)), remaining_budget)

        # Compute end position: forward then turn
        import math as _math
        hdg_rad = _math.radians(ship.heading)
        mid_x = ship.x + move_dist * _math.cos(hdg_rad)
        mid_y = ship.y + move_dist * _math.sin(hdg_rad)
        final_heading = (ship.heading + pending) % 360
        final_hdg_rad = _math.radians(final_heading)
        arrow_len = self.ctx.board.cm_to_pixels(8)

        sx0, sy0 = self.ctx.board.cm_to_screen(ship.x, ship.y)
        sx1, sy1 = self.ctx.board.cm_to_screen(mid_x, mid_y)
        ax = sx1 + arrow_len * _math.cos(final_hdg_rad)
        ay = sy1 - arrow_len * _math.sin(final_hdg_rad)

        self.ctx.board.canvas.create_line(
            sx0, sy0, sx1, sy1, fill="#FFAA00", width=2, dash=(5, 3))
        self.ctx.board.canvas.create_line(
            sx1, sy1, ax, ay, fill="#FFAA00", width=2, arrow=tk.LAST)

        dir_str = f"↶{pending:.0f}°" if pending > 0 else f"↷{abs(pending):.0f}°"
        self.ctx.board.status_var.set(
            f"{ship.name}: pending {dir_str} after {move_dist:.0f}cm | "
            f"M to execute | Esc to clear")

    def _process_movement_phase_start(self):
        """Process things that happen at the start of each movement phase."""
        from .end_phase import resolve_hulk_drift
        hulk_logs = resolve_hulk_drift(self.ctx.gs, self.ctx.dice)
        if hulk_logs:
            self.ctx.log_lines(hulk_logs)
            self.ctx.board.redraw()

        # Reset per-turn ordnance flags
        for i, o_dict in enumerate(self.ctx.gs.ordnance):
            if o_dict.get("resilient_used"):
                self.ctx.gs.ordnance[i] = {**o_dict, "resilient_used": False}

        # Reset staged movement tracking on all ships
        for s_dict in self.ctx.gs.ships:
            if (s_dict.get("distance_moved_this_turn", 0) != 0
                    or s_dict.get("turns_used_this_turn", 0) != 0
                    or s_dict.get("net_rotation_this_turn", 0) != 0):
                for i, sd in enumerate(self.ctx.gs.ships):
                    if sd["id"] == s_dict["id"]:
                        self.ctx.gs.ships[i]["distance_moved_this_turn"] = 0.0
                        self.ctx.gs.ships[i]["turns_used_this_turn"] = 0
                        self.ctx.gs.ships[i]["net_rotation_this_turn"] = 0.0
                        break

        # Squadron coherency check at movement phase start
        from .squadron import check_squadron_coherency
        violations = check_squadron_coherency(self.ctx.gs, self.ctx.gs.active_player)
        if violations:
            for v in violations:
                self.ctx.log(f"  COHERENCY: {v}")
            messagebox.showwarning(
                "Squadron Coherency",
                "Ships out of squadron coherency (>15 cm from all squadron-mates):\n\n"
                + "\n".join(f"• {v}" for v in violations),
            )

        # Clear any pending scroll-wheel turns
        self._pending_turn.clear()

    # _move_ship_dialog and _move_squadron_dialog live in MovementDialogMixin
    # (src/movement_dialog.py)


    def _undo_movement(self):
        """Undo a ship's movement."""
        moved_ids = self.ctx.tc.ships_moved
        if not moved_ids:
            messagebox.showinfo("Nothing to undo", "No ships have moved yet")
            return

        # Pick which to undo
        moved_ships = [Ship.from_dict(s) for s in self.ctx.gs.ships
                       if s["id"] in moved_ids]
        ship = self.ctx.pick_ship(moved_ships, "Select ship to undo movement")
        if not ship:
            return

        if self.ctx.tc.undo_ship_movement(ship.id):
            self.ctx.log(f"Undid movement for {ship.name}")
            self.ctx.board.redraw()

    # --- Shooting ---
