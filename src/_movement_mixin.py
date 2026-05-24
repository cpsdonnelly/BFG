"""BFG:XR — extracted panel mixin (see game_panel.py for context)."""
import tkinter as tk
from tkinter import messagebox, simpledialog
import math
from typing import Optional, Callable, List

from .models import Ship, SpecialOrder, OrdnanceMarker, OrdnanceType
from .game_state import GameState
from .turn_controller import TurnController
from .dice import DiceRoller
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE)
from .combat import (check_weapon_in_arc, check_weapon_in_range,
                     resolve_batteries, resolve_lances, resolve_nova_cannon,
                     apply_damage, check_los_clear)
from .end_phase import resolve_end_phase
from .geometry import (circle_touches_square, circle_touches_torpedo,
                        ATTACK_CRAFT_HALF_SIDE_CM)


class _MovementMixin:
    """Mixin — methods injected into GamePanel."""

    def _wire_drag_callbacks(self):
        """Connect board_view drag-and-drop hooks to game panel movement logic."""
        from .movement import validate_movement, execute_movement

        def can_drag(ship):
            if self.gs.current_phase != "movement":
                return False
            if ship.player != self.gs.active_player:
                return False
            unmoved_ids = {s.id for s in self.tc.get_unmoved_ships()}
            return ship.id in unmoved_ids

        def commit_drag(ship, commands):
            from .movement import validate_movement, execute_movement, resolve_aaf_speed
            order = ship.special_order
            aaf_bonus = 0
            if order == "all_ahead_full":
                aaf_bonus = resolve_aaf_speed(ship, self.dice)
                self._append_log(f"{ship.name} AAF speed bonus: +{aaf_bonus}cm")
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.gs.get_blast_markers(),
                self.gs.table_width, self.gs.table_height,
                turns_already_used=ship.turns_used_this_turn)
            if not result.valid:
                return  # path became invalid between preview and release — discard
            execute_movement(ship, result, self.gs)
            # Terrain navigation tests (same logic as dialog confirm)
            updated = self.gs.get_ship_by_id(ship.id)
            if updated and not updated.is_disengaged:
                from .terrain_effects import (resolve_asteroid_navigation,
                                               resolve_warp_rift_navigation,
                                               resolve_gas_dust_contact)
                if "in_asteroid_field" in (updated.special_rules or []):
                    on_aaf = order == "all_ahead_full"
                    nav = resolve_asteroid_navigation(updated, self.dice, self.gs, on_aaf)
                    if not nav["passed"]:
                        self._append_log(
                            f"  {updated.name}: asteroid damage {nav['damage']} HP!")
                        self._check_destruction(updated)
                    updated = self.gs.get_ship_by_id(ship.id)
                    if updated:
                        updated.special_rules = [r for r in updated.special_rules
                                                 if r != "in_asteroid_field"]
                        self.gs.update_ship(updated)
                if updated and "in_warp_rift" in (updated.special_rules or []):
                    nav = resolve_warp_rift_navigation(updated, self.dice, self.gs)
                    updated = self.gs.get_ship_by_id(ship.id)
                    if updated:
                        updated.special_rules = [r for r in updated.special_rules
                                                 if r != "in_warp_rift"]
                        self.gs.update_ship(updated)
                if updated and "in_dust_cloud" in (updated.special_rules or []):
                    resolve_gas_dust_contact(updated, self.dice, self.gs)
                    updated = self.gs.get_ship_by_id(ship.id)
                    if updated:
                        updated.special_rules = [r for r in updated.special_rules
                                                 if r != "in_dust_cloud"]
                        self.gs.update_ship(updated)

            # Update staged tracking fields
            final_ship = self.gs.get_ship_by_id(ship.id)
            if final_ship:
                final_ship.distance_moved_this_turn += result.total_distance
                final_ship.turns_used_this_turn += result.turns_used
                left_deg = sum(c.value for c in commands if c.action == "turn_left")
                right_deg = sum(c.value for c in commands if c.action == "turn_right")
                final_ship.net_rotation_this_turn += (left_deg - right_deg)
                self.gs.update_ship(final_ship)

                # Lock the ship only when its movement budget is exhausted
                base_speed = final_ship.effective_speed
                max_budget = (base_speed + aaf_bonus
                              if order == "all_ahead_full"
                              else (base_speed // 2
                                    if order == "burn_retros"
                                    else base_speed))
                remaining = max_budget - final_ship.distance_moved_this_turn
                if remaining <= 0.1:
                    self.tc.mark_ship_moved(ship.id)
                    self._append_log(
                        f"{ship.name}: drag-moved {result.total_distance:.1f}cm "
                        f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                        f"hdg {result.final_heading:.0f}°")
                else:
                    self._append_log(
                        f"{ship.name}: drag-moved {result.total_distance:.1f}cm "
                        f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                        f"hdg {result.final_heading:.0f}° — {remaining:.1f}cm remaining")
            self.board.redraw()

        self.board.can_drag_ship_fn = can_drag
        self.board.commit_drag_fn = commit_drag

        # M key: execute min-move for selected ship (staged, no dialog)
        self.root.bind("m", lambda e: self._quick_min_move_selected())
        self.root.bind("M", lambda e: self._quick_min_move_selected())

        # Spacebar: min-move ALL unmoved ships for active player
        self.root.bind("<space>", lambda e: self._min_move_all_ships())

        # Backspace: undo all movement this turn
        self.root.bind("<BackSpace>", lambda e: self._undo_all_movement())

        # Ordnance launch drag callbacks
        def can_ord_drag(ship):
            if self.gs.current_phase != "ordnance":
                return False
            if ship.player != self.gs.active_player:
                return False
            if ship.is_destroyed or ship.is_disengaged:
                return False
            return ship.ordnance_loaded_torps or ship.ordnance_loaded_craft

        def commit_ord_drag(ship, heading):
            self._launch_ordnance_dialog(
                preselected_ship=ship, preselected_heading=heading)

        self.board.can_ord_drag_fn = can_ord_drag
        self.board.commit_ord_drag_fn = commit_ord_drag

        # Board-level scroll wheel: add pending turn to selected ship
        def _on_board_scroll(event):
            if self.gs.current_phase != "movement":
                return
            ship_id = self.board.selected_ship_id
            if not ship_id:
                return
            ship = self.gs.get_ship_by_id(ship_id)
            if not ship or ship.player != self.gs.active_player:
                return
            unmoved_ids = {s.id for s in self.tc.get_unmoved_ships()}
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
            self.board.redraw()
            self._redraw_pending_turn_ghost()

        self.board.canvas.bind("<MouseWheel>", _on_board_scroll)
        self.board.canvas.bind("<Button-4>", _on_board_scroll)
        self.board.canvas.bind("<Button-5>", _on_board_scroll)
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

        if self.gs.current_phase != "movement":
            return

        ship_id = self.board.selected_ship_id
        if not ship_id:
            self.board.status_var.set("M: no ship selected — click a ship first")
            return

        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return
        if ship.player != self.gs.active_player:
            self.board.status_var.set(f"M: {ship.name} belongs to the other player")
            return
        unmoved_ids = {s.id for s in self.tc.get_unmoved_ships()}
        if ship.id not in unmoved_ids:
            self.board.status_var.set(f"M: {ship.name} has already moved this turn")
            return

        order = ship.special_order
        base = ship.effective_speed
        aaf_bonus = 0

        if order == "all_ahead_full":
            aaf_bonus = resolve_aaf_speed(ship, self.dice)
            self._append_log(f"{ship.name} AAF speed bonus: +{aaf_bonus}cm")
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
            self.board.status_var.set(
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
            self.gs.get_blast_markers(),
            self.gs.table_width, self.gs.table_height,
            turns_already_used=ship.turns_used_this_turn)

        if not result.valid:
            # Try without the turn if the combined command fails
            if len(commands) > 1:
                commands = [MoveCommand("forward", move_dist)]
                result = validate_movement(
                    ship, commands, order, aaf_bonus,
                    self.gs.get_blast_markers(),
                    self.gs.table_width, self.gs.table_height,
                    turns_already_used=ship.turns_used_this_turn)
            if not result.valid:
                self.board.status_var.set(
                    f"M: {ship.name} invalid — {result.errors[0]}")
                return

        execute_movement(ship, result, self.gs)

        # Update staged tracking fields on the now-moved ship
        ship = self.gs.get_ship_by_id(ship_id)
        if ship:
            ship.distance_moved_this_turn += result.total_distance
            ship.turns_used_this_turn += result.turns_used
            left_deg = sum(c.value for c in commands if c.action == "turn_left")
            right_deg = sum(c.value for c in commands if c.action == "turn_right")
            ship.net_rotation_this_turn += (left_deg - right_deg)
            self.gs.update_ship(ship)

            # If no budget remains, mark fully moved
            max_budget = (base + aaf_bonus if order == "all_ahead_full"
                          else (base // 2 if order == "burn_retros" else base))
            if ship.distance_moved_this_turn >= max_budget - 0.1:
                self.tc.mark_ship_moved(ship_id)
                self._append_log(
                    f"{ship.name}: M-move complete {ship.distance_moved_this_turn:.0f}cm"
                    + (f" ↶{left_deg:.0f}°" if left_deg > 0.1 else "")
                    + (f" ↷{right_deg:.0f}°" if right_deg > 0.1 else ""))
            else:
                self._append_log(
                    f"{ship.name}: min-move {result.total_distance:.0f}cm"
                    + (f" ↶{left_deg:.0f}°" if left_deg > 0.1 else "")
                    + (f" ↷{right_deg:.0f}°" if right_deg > 0.1 else "")
                    + f" — {max_budget - ship.distance_moved_this_turn:.0f}cm remaining")
            self.board.status_var.set(
                f"M: {ship.name} moved {result.total_distance:.0f}cm")

        self._redraw_pending_turn_ghost()
        self.board.canvas.focus_set()
        self.board.redraw()

    # --- Game Flow ---

    def _min_move_all_ships(self):
        """Spacebar: execute minimum move for every unmoved ship of the active player."""
        from .movement import MoveCommand, validate_movement, execute_movement, resolve_aaf_speed

        if self.gs.current_phase != "movement":
            return
        unmoved = [s for s in self.tc.get_unmoved_ships()
                   if s.player == self.gs.active_player]
        if not unmoved:
            return

        moved_count = 0
        for ship in unmoved:
            order = ship.special_order
            base = ship.effective_speed
            aaf_bonus = 0
            if order == "all_ahead_full":
                aaf_bonus = resolve_aaf_speed(ship, self.dice)
                move_dist = float(base + aaf_bonus)
            elif order == "burn_retros":
                move_dist = float(base // 2)
            else:
                move_dist = float(max(1, base // 2))

            commands = [MoveCommand("forward", move_dist)]
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.gs.get_blast_markers(),
                self.gs.table_width, self.gs.table_height)
            if not result.valid:
                self._append_log(
                    f"  {ship.name}: min-move skipped — {result.errors[0]}")
                continue

            execute_movement(ship, result, self.gs)
            self.tc.mark_ship_moved(ship.id)
            # Update staged fields so dialog is consistent if opened later
            updated = self.gs.get_ship_by_id(ship.id)
            if updated:
                updated.distance_moved_this_turn += result.total_distance
                self.gs.update_ship(updated)
            moved_count += 1

        self._append_log(f"Spacebar: min-moved {moved_count} ships")
        self.board.canvas.focus_set()
        self.board.redraw()

    def _undo_all_movement(self):
        """Backspace: undo all ship movement this turn, restoring phase-start positions."""
        if self.gs.current_phase != "movement":
            return
        if self.tc.undo_to_phase_start():
            self._pending_turn.clear()
            self._append_log("Backspace: all movement undone")
            self.board.status_var.set("All movement undone")
            self.board.canvas.focus_set()
            self.board.redraw()

    def _redraw_pending_turn_ghost(self):
        """Draw a ghost on the board canvas showing pending scroll-wheel turn result."""
        ship_id = self.board.selected_ship_id
        if not ship_id:
            return
        pending = self._pending_turn.get(ship_id, 0.0)
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship or abs(pending) < 0.1:
            return

        from .movement import get_effective_speed, SpecialOrder
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
        arrow_len = self.board.cm_to_pixels(8)

        sx0, sy0 = self.board.cm_to_screen(ship.x, ship.y)
        sx1, sy1 = self.board.cm_to_screen(mid_x, mid_y)
        ax = sx1 + arrow_len * _math.cos(final_hdg_rad)
        ay = sy1 - arrow_len * _math.sin(final_hdg_rad)

        self.board.canvas.create_line(
            sx0, sy0, sx1, sy1, fill="#FFAA00", width=2, dash=(5, 3))
        self.board.canvas.create_line(
            sx1, sy1, ax, ay, fill="#FFAA00", width=2, arrow=tk.LAST)

        dir_str = f"↶{pending:.0f}°" if pending > 0 else f"↷{abs(pending):.0f}°"
        self.board.status_var.set(
            f"{ship.name}: pending {dir_str} after {move_dist:.0f}cm | "
            f"M to execute | Esc to clear")

    def _process_movement_phase_start(self):
        """Process things that happen at the start of each movement phase."""
        from .end_phase import resolve_hulk_drift
        hulk_logs = resolve_hulk_drift(self.gs, self.dice)
        if hulk_logs:
            self._log_lines(hulk_logs)
            self.board.redraw()

        # Reset per-turn ordnance flags
        for i, o_dict in enumerate(self.gs.ordnance):
            if o_dict.get("resilient_used"):
                self.gs.ordnance[i] = {**o_dict, "resilient_used": False}

        # Reset staged movement tracking on all ships
        for s_dict in self.gs.ships:
            if (s_dict.get("distance_moved_this_turn", 0) != 0
                    or s_dict.get("turns_used_this_turn", 0) != 0
                    or s_dict.get("net_rotation_this_turn", 0) != 0):
                for i, sd in enumerate(self.gs.ships):
                    if sd["id"] == s_dict["id"]:
                        self.gs.ships[i]["distance_moved_this_turn"] = 0.0
                        self.gs.ships[i]["turns_used_this_turn"] = 0
                        self.gs.ships[i]["net_rotation_this_turn"] = 0.0
                        break

        # Clear any pending scroll-wheel turns
        self._pending_turn.clear()

    def _special_order_dialog(self):
        """Dialog to issue a special order to a ship."""
        # Include ships that haven't yet been fully committed (M-key staged moves
        # don't mark a ship as moved, so those ships still appear here).
        unmoved = self.tc.get_unmoved_ships()
        if not unmoved:
            messagebox.showinfo(
                "No Ships Available",
                "All active ships have already moved.\n"
                "Special orders must be issued before a ship moves.")
            return

        if self.tc.command_check_failed:
            messagebox.showinfo("Command Failed",
                "A command check already failed this turn.\n"
                "No more special orders can be issued (except Brace).")
            return

        # Pick ship
        ship = self._pick_ship_dialog(unmoved, "Select ship for special order")
        if not ship:
            return

        # Pick order
        orders = [
            ("All Ahead Full", SpecialOrder.ALL_AHEAD_FULL.value),
            ("Burn Retros", SpecialOrder.BURN_RETROS.value),
            ("Come to New Heading", SpecialOrder.COME_TO_NEW_HEADING.value),
            ("Lock On", SpecialOrder.LOCK_ON.value),
            ("Reload Ordnance", SpecialOrder.RELOAD_ORDNANCE.value),
        ]

        # Filter out CtNH for ponderous ships
        if "ponderous" in ship.special_rules:
            orders = [(n, v) for n, v in orders
                      if v != SpecialOrder.COME_TO_NEW_HEADING.value]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Special Order - {ship.name}")
        dialog.geometry("300x300")
        dialog.transient(self.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=f"Order for {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=5)
        tk.Label(dialog, text=f"Leadership: {ship.leadership}",
                 font=("Consolas", 9)).pack()

        selected = tk.StringVar(value=orders[0][1])  # default to first option

        for name, value in orders:
            tk.Radiobutton(dialog, text=name, variable=selected, value=value,
                          font=("Consolas", 9)).pack(anchor=tk.W, padx=20)

        def confirm():
            order = selected.get()
            if not order:
                return
            dialog.destroy()
            result = self.tc.issue_special_order(ship, order)
            roll_info = f" (rolled {result.get('roll', '?')} vs Ld {result.get('needed', '?')})"
            if result["success"]:
                self._append_log(
                    f"{ship.name}: {order} PASSED{roll_info}")
                messagebox.showinfo("Order Passed",
                    f"{ship.name}: {order} PASSED\n"
                    f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}")
            else:
                # Check if fleet commander re-roll is available
                rerolls = self.tc.get_fleet_rerolls(ship.player)
                if rerolls > 0:
                    use_reroll = messagebox.askyesno(
                        "Order Failed - Re-roll Available",
                        f"{ship.name}: {order} FAILED\n"
                        f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}\n\n"
                        f"Fleet commander has {rerolls} re-roll(s) remaining.\n"
                        f"Use a re-roll? (Cannot be undone)")
                    if use_reroll:
                        reroll_result = self.tc.attempt_reroll_command_check(
                            ship, order)
                        rr_info = (f" (RE-ROLL: rolled {reroll_result.get('roll', '?')} "
                                   f"vs Ld {reroll_result.get('needed', '?')})")
                        if reroll_result["success"]:
                            self._append_log(
                                f"{ship.name}: {order} RE-ROLL PASSED{rr_info}")
                            messagebox.showinfo("Re-roll Passed!",
                                f"{ship.name}: {order} RE-ROLL PASSED\n"
                                f"Rolled {reroll_result.get('roll')} vs "
                                f"Leadership {reroll_result.get('needed')}")
                        else:
                            msg = reroll_result.get("error", f"{order} RE-ROLL FAILED")
                            self._append_log(f"{ship.name}: {msg}")
                            messagebox.showwarning("Re-roll Failed",
                                f"{ship.name}: {order} RE-ROLL ALSO FAILED\n"
                                f"Rolled {reroll_result.get('roll')} vs "
                                f"Leadership {reroll_result.get('needed')}\n"
                                f"No more special orders this turn!")
                    else:
                        msg = result.get("error", f"{order} FAILED")
                        self._append_log(f"{ship.name}: {msg}")
                else:
                    msg = result.get("error", f"{order} FAILED")
                    self._append_log(f"{ship.name}: {msg}")
                    messagebox.showwarning("Order Failed",
                        f"{ship.name}: {order} FAILED\n"
                        f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}\n"
                        f"No fleet re-rolls available.\n"
                        f"No more special orders this turn!")
            self.board.redraw()

        # Show re-roll count
        rerolls = self.tc.get_fleet_rerolls(ship.player)
        reroll_text = f"Fleet re-rolls available: {rerolls}" if rerolls > 0 else ""
        if reroll_text:
            tk.Label(dialog, text=reroll_text, font=("Consolas", 8),
                     fg="#FFAA00").pack(pady=2)

        tk.Button(dialog, text="Issue Order", command=confirm,
                  bg="#336633", fg="white", font=("Consolas", 10)).pack(pady=10)

    def _move_ship_dialog(self, preselected_ship=None, initial_commands=None):
        """Dialog to move a ship with exact instructions.

        preselected_ship: Ship — if given, skip the pick dialog and use this ship.
        initial_commands: list of MoveCommand — pre-populate the command list.
        """
        unmoved = self.tc.get_unmoved_ships()
        if not unmoved:
            messagebox.showinfo("No Ships", "All ships have moved")
            return

        if preselected_ship and preselected_ship.id in {s.id for s in unmoved}:
            ship = preselected_ship
        else:
            ship = self._pick_ship_dialog(unmoved, "Select ship to move")
        if not ship:
            return

        # Movement command dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Move {ship.name}")
        dialog.geometry("500x580")
        dialog.transient(self.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=f"Move: {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        # Ship stats
        order = ship.special_order
        min_turn_dist = MIN_TURN_DISTANCE.get(ship.ship_type, 10)
        aaf_bonus = 0
        if order == SpecialOrder.ALL_AHEAD_FULL.value:
            aaf_bonus = resolve_aaf_speed(ship, self.dice)
            self._append_log(
                f"{ship.name} AAF speed bonus: +{aaf_bonus}cm")

        base_speed = ship.effective_speed
        already_moved = ship.distance_moved_this_turn
        if order == SpecialOrder.ALL_AHEAD_FULL.value:
            full_budget = base_speed + aaf_bonus
            max_speed = max(0.0, full_budget - already_moved)
            min_speed = max_speed  # must move exact remaining
            speed_text = (f"Speed: {max_speed:.0f}cm remaining "
                          f"(AAF: {base_speed}+{aaf_bonus}, moved {already_moved:.0f}cm)")
        elif order == SpecialOrder.BURN_RETROS.value:
            max_speed = max(0.0, base_speed // 2 - already_moved)
            min_speed = 0
            speed_text = f"Speed: 0-{max_speed:.0f}cm (Burn Retros, moved {already_moved:.0f}cm)"
        else:
            max_speed = max(0.0, base_speed - already_moved)
            raw_min = max(1, base_speed // 2)
            min_speed = max(0.0, raw_min - already_moved)
            speed_text = (f"Speed: {min_speed:.0f}-{max_speed:.0f}cm"
                          + (f" (moved {already_moved:.0f}cm)" if already_moved > 0 else ""))

        # Bail out early if no movement budget remains
        if max_speed < 0.5 and order != SpecialOrder.BURN_RETROS.value:
            messagebox.showinfo(
                "No Budget",
                f"{ship.name} has already moved {already_moved:.0f}cm — "
                f"no remaining movement budget.")
            return

        # Crit warnings
        crit_warnings = []
        has_engine_crit = any(c.get("crit_type") == "engine_room" for c in ship.critical_damage)
        has_thrusters_crit = any(c.get("crit_type") == "thrusters_damaged" for c in ship.critical_damage)
        if has_engine_crit:
            crit_warnings.append("ENGINE ROOM DAMAGED: No turns!")
        if has_thrusters_crit:
            thrusters_count = sum(1 for c in ship.critical_damage if c.get("crit_type") == "thrusters_damaged")
            crit_warnings.append(f"THRUSTERS DAMAGED x{thrusters_count}: -10cm speed")

        info_text = (
            f"Order: {order} | {speed_text}\n"
            f"Turn: {ship.turn_angle}° max | "
            f"Min before turn: {min_turn_dist}cm\n"
            f"Pos: ({ship.x:.1f}, {ship.y:.1f}) | Heading: {ship.heading:.0f}°"
        )
        if crit_warnings:
            info_text += "\n" + " | ".join(crit_warnings)

        info_label = tk.Label(dialog, text=info_text, font=("Consolas", 8),
                 justify=tk.LEFT)
        info_label.pack(padx=10, anchor=tk.W)
        if crit_warnings:
            info_label.config(fg="#FF6644")

        # Remaining distance meter
        meter_frame = tk.Frame(dialog)
        meter_frame.pack(fill=tk.X, padx=10, pady=3)
        remaining_var = tk.StringVar(value=f"Remaining: {max_speed:.0f}cm / {max_speed:.0f}cm")
        remaining_label = tk.Label(meter_frame, textvariable=remaining_var,
                                    font=("Consolas", 10, "bold"), fg="#44CC44")
        remaining_label.pack()

        # Turn stats line — account for turns/rotation already used via M key
        from .movement import get_max_turns
        _max_turns = get_max_turns(order, ship)
        _turns_already = ship.turns_used_this_turn
        _net_rot_already = ship.net_rotation_this_turn
        _net_init_str = (f"+{_net_rot_already:.0f}°" if _net_rot_already >= 0
                         else f"{_net_rot_already:.0f}°")
        turn_stats_var = tk.StringVar(
            value=(f"Turns: {_turns_already}/{_max_turns} used | "
                   f"Net: {_net_init_str} | Remaining angle: {ship.turn_angle}°"))
        turn_stats_label = tk.Label(meter_frame, textvariable=turn_stats_var,
                                     font=("Consolas", 9), fg="#AAAAFF")
        turn_stats_label.pack()

        # Command list
        cmd_listbox = tk.Listbox(dialog, font=("Consolas", 9),
                                  height=6, width=50)
        cmd_listbox.pack(padx=10, pady=3, fill=tk.X)

        commands = []

        # Quick-move buttons
        quick_frame = tk.Frame(dialog)
        quick_frame.pack(padx=10, pady=3, fill=tk.X)

        def _quick_min_move():
            """Auto move minimum half-speed forward."""
            current_dist = sum(c.value for c in commands if c.action == "forward")
            needed = max(0, min_speed - current_dist)
            if needed > 0:
                _add_cmd("forward", needed)

        def _quick_min_before_turn():
            """Auto move minimum distance to enable a turn."""
            # Calculate distance since last turn
            dist_since_turn = 0
            for c in reversed(commands):
                if c.action == "forward":
                    dist_since_turn += c.value
                else:
                    break
            needed = max(0, min_turn_dist - dist_since_turn)
            if needed > 0:
                _add_cmd("forward", needed)

        def _quick_full_speed():
            """Auto move full remaining distance forward."""
            current_dist = sum(c.value for c in commands if c.action == "forward")
            remaining = max(0, max_speed - current_dist)
            if remaining > 0:
                _add_cmd("forward", remaining)

        tk.Button(quick_frame, text=f"Auto: Min Move ({min_speed}cm)",
                  command=_quick_min_move,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        if min_turn_dist > 0 and ship.ship_type != "escort":
            tk.Button(quick_frame, text=f"Auto: Pre-Turn ({min_turn_dist}cm)",
                      command=_quick_min_before_turn,
                      font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        tk.Button(quick_frame, text="Auto: Full Speed",
                  command=_quick_full_speed,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        def _quick_remaining():
            """Use up all remaining movement forward."""
            current_dist = sum(c.value for c in commands if c.action == "forward")
            remaining = max(0, max_speed - current_dist)
            if remaining > 0:
                _add_cmd("forward", remaining)

        tk.Button(quick_frame, text="Auto: Remaining",
                  command=_quick_remaining,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        # Add command buttons
        add_frame = tk.Frame(dialog)
        add_frame.pack(padx=10, pady=3)

        dist_var = tk.StringVar(value="10")
        angle_var = tk.StringVar(value=str(ship.turn_angle))

        tk.Label(add_frame, text="Distance:").grid(row=0, column=0)
        dist_entry = tk.Entry(add_frame, textvariable=dist_var, width=6,
                               font=("Consolas", 10))
        dist_entry.grid(row=0, column=1)
        tk.Button(add_frame, text="Forward",
                  command=lambda: _add_cmd("forward", float(dist_var.get())),
                  font=("Consolas", 9)).grid(row=0, column=2, padx=3)

        tk.Label(add_frame, text="Angle:").grid(row=1, column=0)
        tk.Entry(add_frame, textvariable=angle_var, width=6,
                 font=("Consolas", 10)).grid(row=1, column=1)
        tk.Button(add_frame, text="Anticlockwise",
                  command=lambda: _add_cmd("turn_left", float(angle_var.get())),
                  font=("Consolas", 9)).grid(row=1, column=2, padx=3)
        tk.Button(add_frame, text="Clockwise",
                  command=lambda: _add_cmd("turn_right", float(angle_var.get())),
                  font=("Consolas", 9)).grid(row=1, column=3, padx=3)

        # Common turn angle buttons
        turn_frame = tk.Frame(dialog)
        turn_frame.pack(padx=10, pady=2, fill=tk.X)
        tk.Label(turn_frame, text="Quick turns:",
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        for deg in [5, 15, 30, 45]:
            if deg <= ship.turn_angle:
                tk.Button(turn_frame, text=f"↶{deg}°",
                          command=lambda d=deg: _add_cmd("turn_left", d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
                tk.Button(turn_frame, text=f"↷{deg}°",
                          command=lambda d=deg: _add_cmd("turn_right", d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)

        tk.Button(add_frame, text="Remove Last",
                  command=lambda: _remove_last(),
                  font=("Consolas", 9)).grid(row=2, column=0, columnspan=2, pady=3)
        tk.Button(add_frame, text="Clear All",
                  command=lambda: _clear_all(),
                  font=("Consolas", 9)).grid(row=2, column=2, columnspan=2, pady=3)

        # Preview/validation label
        preview_var = tk.StringVar(value="Add movement commands above")
        tk.Label(dialog, textvariable=preview_var,
                 font=("Consolas", 8), fg="#AAAAAA",
                 wraplength=460, justify=tk.LEFT).pack(padx=10)

        def _add_cmd(action, value):
            try:
                value = float(value)
            except ValueError:
                return
            if action in ("turn_left", "turn_right"):
                if value <= 0:
                    return
                max_turn = float(ship.turn_angle)
                if value > max_turn:
                    _SNAP_TOLERANCE = 15.0
                    if value - max_turn <= _SNAP_TOLERANCE:
                        value = max_turn
                        preview_var.set(f"Snapped to max turn ({max_turn:.0f}°)")
                    else:
                        preview_var.set(
                            f"Cancelled: {value:.0f}° exceeds max turn of {max_turn:.0f}°")
                        return
            cmd = MoveCommand(action, value)
            commands.append(cmd)
            cmd_listbox.insert(tk.END, str(cmd))
            _validate()

        def _remove_last():
            if commands:
                commands.pop()
                cmd_listbox.delete(tk.END)
                _validate()

        def _clear_all():
            commands.clear()
            cmd_listbox.delete(0, tk.END)
            remaining_var.set(f"Remaining: {max_speed:.0f}cm / {max_speed:.0f}cm")
            remaining_label.config(fg="#44CC44")
            turn_stats_var.set(
                f"Turns: {_turns_already}/{_max_turns} used | "
                f"Net: {_net_init_str} | Remaining angle: {ship.turn_angle}°")
            turn_stats_label.config(fg="#AAAAFF")
            preview_var.set("Add movement commands above")
            self.board.redraw()

        def _validate():
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.gs.get_blast_markers(),
                self.gs.table_width, self.gs.table_height,
                turns_already_used=_turns_already)

            # Update remaining distance
            used = result.total_distance
            remaining = max(0, max_speed - used)
            remaining_var.set(f"Remaining: {remaining:.1f}cm / {max_speed:.0f}cm (used {used:.1f}cm)")
            if remaining < 0.5:
                remaining_label.config(fg="#CCAA00")
            else:
                remaining_label.config(fg="#44CC44")

            # Update turn stats: net heading change and counts (cumulative with staged)
            left_deg = sum(c.value for c in commands if c.action == "turn_left")
            right_deg = sum(c.value for c in commands if c.action == "turn_right")
            net_deg_dialog = left_deg - right_deg
            net_deg_total = _net_rot_already + net_deg_dialog
            turns_count_dialog = result.turns_used
            turns_total = _turns_already + turns_count_dialog
            angle_remaining = max(0.0, ship.turn_angle - max(left_deg, right_deg))
            net_str = f"+{net_deg_total:.0f}°" if net_deg_total > 0 else f"{net_deg_total:.0f}°"
            turn_stats_var.set(
                f"Turns: {turns_total}/{_max_turns} used | "
                f"Net: {net_str} | "
                f"Remaining angle: {angle_remaining:.0f}°")
            turn_stats_label.config(
                fg="#FF6644" if turns_total > _max_turns else "#AAAAFF")

            if result.valid:
                preview_var.set(
                    f"VALID: {result.total_distance:.1f}cm, "
                    f"{result.turns_used} turns, "
                    f"end ({result.final_x:.1f}, {result.final_y:.1f}) "
                    f"hdg {result.final_heading:.0f}°"
                    + (" [DEFENSES]" if result.counts_as_defense else ""))
            else:
                preview_var.set("ERRORS: " + "; ".join(result.errors))

            # Draw preview path on board
            self.board.redraw()
            if result.path:
                for i in range(len(result.path) - 1):
                    sx0, sy0 = self.board.cm_to_screen(*result.path[i])
                    sx1, sy1 = self.board.cm_to_screen(*result.path[i+1])
                    color = "#44FF44" if result.valid else "#FF4444"
                    self.board.canvas.create_line(
                        sx0, sy0, sx1, sy1,
                        fill=color, width=2, dash=(4, 4))
                if result.valid:
                    gx, gy = self.board.cm_to_screen(
                        result.final_x, result.final_y)
                    r = self.board.cm_to_pixels(1.2)
                    self.board.canvas.create_oval(
                        gx-r, gy-r, gx+r, gy+r,
                        outline="#44FF44", width=2, dash=(3, 3))
                    # Ghost heading arrow
                    head_rad = math.radians(result.final_heading)
                    ax = gx + r * 2 * math.cos(head_rad)
                    ay = gy - r * 2 * math.sin(head_rad)
                    self.board.canvas.create_line(
                        gx, gy, ax, ay, fill="#44FF44", width=2, arrow=tk.LAST)

        def _on_dialog_close():
            self.board.canvas.unbind("<MouseWheel>")
            self.board.canvas.unbind("<Button-4>")
            self.board.canvas.unbind("<Button-5>")
            if self._board_scroll_fn:
                self.board.canvas.bind("<MouseWheel>", self._board_scroll_fn)
                self.board.canvas.bind("<Button-4>", self._board_scroll_fn)
                self.board.canvas.bind("<Button-5>", self._board_scroll_fn)
            dialog.destroy()

        def _confirm():
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.gs.get_blast_markers(),
                self.gs.table_width, self.gs.table_height,
                turns_already_used=_turns_already)
            if not result.valid:
                messagebox.showerror("Invalid Movement",
                                     "\n".join(result.errors))
                return
            execute_movement(ship, result, self.gs)

            # Check for terrain navigation tests
            updated_ship = self.gs.get_ship_by_id(ship.id)
            if updated_ship and not updated_ship.is_disengaged:
                from .terrain_effects import (resolve_asteroid_navigation,
                                               resolve_warp_rift_navigation,
                                               resolve_gas_dust_contact)
                if "in_asteroid_field" in (updated_ship.special_rules or []):
                    on_aaf = order == SpecialOrder.ALL_AHEAD_FULL.value
                    nav = resolve_asteroid_navigation(
                        updated_ship, self.dice, self.gs, on_aaf)
                    if not nav["passed"]:
                        self._append_log(
                            f"  {updated_ship.name}: asteroid damage {nav['damage']} HP!")
                        self._check_destruction(updated_ship)
                    # Remove flag
                    updated_ship = self.gs.get_ship_by_id(ship.id)
                    if updated_ship:
                        sr = [r for r in updated_ship.special_rules
                              if r != "in_asteroid_field"]
                        updated_ship.special_rules = sr
                        self.gs.update_ship(updated_ship)

                if "in_warp_rift" in (updated_ship.special_rules or []):
                    nav = resolve_warp_rift_navigation(
                        updated_ship, self.dice, self.gs)
                    if not nav["passed"]:
                        self._append_log(f"  {updated_ship.name}: LOST IN THE WARP!")
                    else:
                        pos = nav.get("new_position", (0, 0))
                        self._append_log(
                            f"  {updated_ship.name}: emerged at ({pos[0]:.0f}, {pos[1]:.0f})")
                    updated_ship = self.gs.get_ship_by_id(ship.id)
                    if updated_ship:
                        sr = [r for r in updated_ship.special_rules
                              if r != "in_warp_rift"]
                        updated_ship.special_rules = sr
                        self.gs.update_ship(updated_ship)

                if "in_dust_cloud" in (updated_ship.special_rules or []):
                    resolve_gas_dust_contact(updated_ship, self.dice, self.gs)
                    updated_ship = self.gs.get_ship_by_id(ship.id)
                    if updated_ship:
                        sr = [r for r in updated_ship.special_rules
                              if r != "in_dust_cloud"]
                        updated_ship.special_rules = sr
                        self.gs.update_ship(updated_ship)

            # Update staged movement tracking fields before marking fully moved
            final_ship = self.gs.get_ship_by_id(ship.id)
            if final_ship:
                final_ship.distance_moved_this_turn = (
                    already_moved + result.total_distance)
                final_ship.turns_used_this_turn = (
                    _turns_already + result.turns_used)
                dialog_net = (
                    sum(c.value for c in commands if c.action == "turn_left")
                    - sum(c.value for c in commands if c.action == "turn_right"))
                final_ship.net_rotation_this_turn = _net_rot_already + dialog_net
                self.gs.update_ship(final_ship)
            self.tc.mark_ship_moved(ship.id)
            self.tc.record_action(
                "move_ship", ship.id,
                details={
                    "commands": [{"action": c.action, "value": c.value}
                                 for c in commands],
                    "special_order": order,
                },
                result={
                    "final_position": [result.final_x, result.final_y],
                    "final_heading": result.final_heading,
                    "distance_moved": result.total_distance,
                },
                description=(
                    f"{ship.name} moved {result.total_distance:.1f}cm "
                    f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                    f"heading {result.final_heading:.0f}°"))
            self._append_log(
                f"{ship.name}: moved {result.total_distance:.1f}cm")
            _on_dialog_close()
            self.board.redraw()

        # Confirm / Cancel
        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=5)
        tk.Button(btn_row, text="Confirm Move", command=_confirm,
                  bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Cancel",
                  command=lambda: _on_dialog_close(),
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        # Scroll wheel turning: scroll on the board canvas to add turn commands
        # Each tick = 5° turn (or the ship's max angle if smaller)
        _scroll_deg = min(5, ship.turn_angle)

        def _on_scroll(event):
            # Windows/macOS: event.delta (+/-120 per tick)
            # Linux: Button-4 = scroll up, Button-5 = scroll down
            if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
                _add_cmd("turn_left", _scroll_deg)
            elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
                _add_cmd("turn_right", _scroll_deg)

        self.board.canvas.bind("<MouseWheel>", _on_scroll)
        self.board.canvas.bind("<Button-4>", _on_scroll)
        self.board.canvas.bind("<Button-5>", _on_scroll)

        # Pre-populate commands if provided (after all helpers are defined)
        if initial_commands:
            for c in initial_commands:
                commands.append(c)
                cmd_listbox.insert(tk.END, str(c))
            _validate()

        dialog.protocol("WM_DELETE_WINDOW", _on_dialog_close)

    def _undo_movement(self):
        """Undo a ship's movement."""
        moved_ids = self.tc.ships_moved
        if not moved_ids:
            messagebox.showinfo("Nothing to undo", "No ships have moved yet")
            return

        # Pick which to undo
        moved_ships = [Ship.from_dict(s) for s in self.gs.ships
                       if s["id"] in moved_ids]
        ship = self._pick_ship_dialog(moved_ships, "Select ship to undo movement")
        if not ship:
            return

        if self.tc.undo_ship_movement(ship.id):
            self._append_log(f"Undid movement for {ship.name}")
            self.board.redraw()

    # --- Shooting ---

