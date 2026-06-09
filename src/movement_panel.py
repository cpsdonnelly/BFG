"""BFG:XR — MovementPanel: ship movement UI and drag-drop callbacks."""
import tkinter as tk
from tkinter import messagebox
import math
from typing import Optional, List

from .models import Ship, SpecialOrder
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE)
from .game_context import GameContext


def _pick_coherency_group(
    root: tk.Tk, groups: List[List["Ship"]]
) -> Optional[List["Ship"]]:
    """Dialog for the player to choose which coherent sub-group issues the order.

    Returns the selected group, or None if cancelled.
    """
    result: List = [None]

    dlg = tk.Toplevel(root)
    dlg.title("Select Coherent Group")
    dlg.geometry("380x260")
    dlg.transient(root)
    dlg.grab_set()

    tk.Label(
        dlg,
        text="Squadron coherency is broken.\nChoose which group issues the order:",
        font=("Consolas", 9), justify=tk.LEFT,
    ).pack(pady=(10, 4), padx=12, anchor=tk.W)

    var = tk.IntVar(value=0)
    for i, grp in enumerate(groups):
        names = ", ".join(s.name for s in grp)
        label = f"Group {i+1} ({len(grp)} ships): {names}"
        if i == 0:
            label += "  [default]"
        tk.Radiobutton(
            dlg, text=label, variable=var, value=i,
            font=("Consolas", 8), wraplength=340,
            justify=tk.LEFT, anchor=tk.W,
        ).pack(anchor=tk.W, padx=16, pady=2)

    def _ok():
        result[0] = groups[var.get()]
        dlg.destroy()

    def _cancel():
        dlg.destroy()

    btn = tk.Frame(dlg)
    btn.pack(pady=8)
    tk.Button(btn, text="OK",     command=_ok,     width=10).pack(side=tk.LEFT, padx=6)
    tk.Button(btn, text="Cancel", command=_cancel, width=10).pack(side=tk.LEFT, padx=6)
    dlg.bind("<Return>", lambda e: _ok())
    dlg.bind("<Escape>", lambda e: _cancel())
    root.wait_window(dlg)
    return result[0]


class MovementPanel:
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
            # Terrain navigation tests (same logic as dialog confirm)
            updated = self.ctx.gs.get_ship_by_id(ship.id)
            if updated and not updated.is_disengaged:
                from .terrain_effects import (resolve_asteroid_navigation,
                                               resolve_warp_rift_navigation,
                                               resolve_gas_dust_contact)
                if "in_asteroid_field" in (updated.special_rules or []):
                    on_aaf = order == "all_ahead_full"
                    nav = resolve_asteroid_navigation(updated, self.ctx.dice, self.ctx.gs, on_aaf)
                    if not nav["passed"]:
                        self.ctx.log(
                            f"  {updated.name}: asteroid damage {nav['damage']} HP!")
                        self.ctx.check_destruction(updated)
                    updated = self.ctx.gs.get_ship_by_id(ship.id)
                    if updated:
                        updated.special_rules = [r for r in updated.special_rules
                                                 if r != "in_asteroid_field"]
                        self.ctx.gs.update_ship(updated)
                if updated and "in_warp_rift" in (updated.special_rules or []):
                    nav = resolve_warp_rift_navigation(updated, self.ctx.dice, self.ctx.gs)
                    updated = self.ctx.gs.get_ship_by_id(ship.id)
                    if updated:
                        updated.special_rules = [r for r in updated.special_rules
                                                 if r != "in_warp_rift"]
                        self.ctx.gs.update_ship(updated)
                if updated and "in_dust_cloud" in (updated.special_rules or []):
                    resolve_gas_dust_contact(updated, self.ctx.dice, self.ctx.gs)
                    updated = self.ctx.gs.get_ship_by_id(ship.id)
                    if updated:
                        updated.special_rules = [r for r in updated.special_rules
                                                 if r != "in_dust_cloud"]
                        self.ctx.gs.update_ship(updated)

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

    def _special_order_dialog(self):
        """Dialog to issue a special order to a ship."""
        # Include ships that haven't yet been fully committed (M-key staged moves
        # don't mark a ship as moved, so those ships still appear here).
        unmoved = self.ctx.tc.get_unmoved_ships()
        if not unmoved:
            messagebox.showinfo(
                "No Ships Available",
                "All active ships have already moved.\n"
                "Special orders must be issued before a ship moves.")
            return

        if self.ctx.tc.command_check_failed:
            messagebox.showinfo("Command Failed",
                "A command check already failed this turn.\n"
                "No more special orders can be issued (except Brace).")
            return

        # Pick ship
        ship = self.ctx.pick_ship(unmoved, "Select ship for special order")
        if not ship:
            return

        # Detect squadron membership for optional squadron-order mechanic
        from .squadron import get_squadrons
        unmoved_ids = {s.id for s in unmoved}
        sq_members: list = []  # other active unmoved members in same squadron
        if ship.squadron_id:
            all_squads = get_squadrons(self.ctx.gs, ship.player)
            sq_all = all_squads.get(ship.squadron_id, [])
            sq_members = [s for s in sq_all
                          if s.id != ship.id and s.id in unmoved_ids]

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

        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Special Order - {ship.name}")
        dialog.geometry("320x360" if sq_members else "300x300")
        dialog.transient(self.ctx.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=f"Order for {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=5)
        tk.Label(dialog, text=f"Leadership: {ship.leadership}",
                 font=("Consolas", 9)).pack()

        selected = tk.StringVar(value=orders[0][1])  # default to first option

        for name, value in orders:
            tk.Radiobutton(dialog, text=name, variable=selected, value=value,
                          font=("Consolas", 9)).pack(anchor=tk.W, padx=20)

        # Squadron order option
        sq_order_var = tk.BooleanVar(value=False)
        if sq_members:
            from .squadron import get_coherency_components
            all_sq_members = [ship] + sq_members
            groups, isolated_sq = get_coherency_components(all_sq_members)

            if not groups:
                coh_text = "⚠ All ships isolated — squadron order not possible"
            elif len(groups) == 1:
                leader = max(groups[0], key=lambda s: s.leadership)
                coh_text = (f"Leader: {leader.name}  •  Ld {leader.leadership}\n"
                            f"Members: {', '.join(s.name for s in all_sq_members)}")
            else:
                sizes = " | ".join(f"{len(g)} ships" for g in groups)
                coh_text = (f"⚠ Broken coherency — {len(groups)} groups ({sizes})\n"
                            f"You will choose which group issues the order.")
            if isolated_sq:
                coh_text += f"\n  Isolated (excluded): {', '.join(s.name for s in isolated_sq)}"

            sq_frame = tk.LabelFrame(dialog, text="Squadron Order",
                                     font=("Consolas", 8, "bold"), padx=6, pady=4)
            sq_frame.pack(fill=tk.X, padx=10, pady=4)
            tk.Checkbutton(
                sq_frame,
                text="Apply to whole squadron (roll once for all)",
                variable=sq_order_var,
                font=("Consolas", 8),
            ).pack(anchor=tk.W)
            tk.Label(
                sq_frame,
                text=coh_text,
                font=("Consolas", 7), fg="#AAAAAA", justify=tk.LEFT,
            ).pack(anchor=tk.W)

        def _handle_failed_individual(result, order_str):
            """Show failure UI and offer re-roll for an individual order."""
            rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
            if rerolls > 0:
                use_reroll = messagebox.askyesno(
                    "Order Failed - Re-roll Available",
                    f"{ship.name}: {order_str} FAILED\n"
                    f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}\n\n"
                    f"Fleet commander has {rerolls} re-roll(s) remaining.\n"
                    f"Use a re-roll? (Cannot be undone)")
                if use_reroll:
                    reroll_result = self.ctx.tc.attempt_reroll_command_check(
                        ship, order_str)
                    rr_info = (f" (RE-ROLL: rolled {reroll_result.get('roll', '?')} "
                               f"vs Ld {reroll_result.get('needed', '?')})")
                    if reroll_result["success"]:
                        self.ctx.log(
                            f"{ship.name}: {order_str} RE-ROLL PASSED{rr_info}")
                        messagebox.showinfo("Re-roll Passed!",
                            f"{ship.name}: {order_str} RE-ROLL PASSED\n"
                            f"Rolled {reroll_result.get('roll')} vs "
                            f"Leadership {reroll_result.get('needed')}")
                    else:
                        msg = reroll_result.get("error",
                                                f"{order_str} RE-ROLL FAILED")
                        self.ctx.log(f"{ship.name}: {msg}")
                        messagebox.showwarning("Re-roll Failed",
                            f"{ship.name}: {order_str} RE-ROLL ALSO FAILED\n"
                            f"Rolled {reroll_result.get('roll')} vs "
                            f"Leadership {reroll_result.get('needed')}\n"
                            f"No more special orders this turn!")
                else:
                    msg = result.get("error", f"{order_str} FAILED")
                    self.ctx.log(f"{ship.name}: {msg}")
            else:
                msg = result.get("error", f"{order_str} FAILED")
                self.ctx.log(f"{ship.name}: {msg}")
                messagebox.showwarning("Order Failed",
                    f"{ship.name}: {order_str} FAILED\n"
                    f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}\n"
                    f"No fleet re-rolls available.\n"
                    f"No more special orders this turn!")

        def confirm():
            order = selected.get()
            if not order:
                return
            dialog.destroy()

            if sq_order_var.get() and sq_members:
                # --- Squadron order path ---
                from .squadron import get_coherency_components
                all_sq = [ship] + sq_members
                groups, isolated_sq = get_coherency_components(all_sq)

                for s in isolated_sq:
                    self.ctx.log(
                        f"  {s.name}: isolated from squadron — cannot join order")

                if not groups:
                    messagebox.showinfo("No Coherency",
                        "No ships are in coherency — cannot issue a squadron order.")
                    return

                if len(groups) == 1:
                    all_sq = groups[0]
                else:
                    chosen = _pick_coherency_group(self.ctx.root, groups)
                    if chosen is None:
                        return   # player cancelled
                    all_sq = chosen

                result = self.ctx.tc.issue_squadron_order(all_sq, order)
                roll_info = (f" (rolled {result.get('roll', '?')} "
                             f"vs Ld {result.get('needed', '?')} "
                             f"via {result.get('leader', '?')})")
                if result["success"]:
                    affected = result.get("ships_affected", [])
                    self.ctx.log(
                        f"Squadron {order} PASSED{roll_info}")
                    messagebox.showinfo("Squadron Order Passed",
                        f"Squadron {order} PASSED{roll_info}\n"
                        f"Applied to: {', '.join(affected)}")
                else:
                    err = result.get("error", f"Squadron {order} FAILED")
                    self.ctx.log(err)
                    # Offer re-roll on squadron fail (rolls against the leader)
                    leader_ship = max([ship] + sq_members,
                                      key=lambda s: s.leadership)
                    rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
                    if rerolls > 0:
                        use_rr = messagebox.askyesno(
                            "Squadron Order Failed - Re-roll Available",
                            f"{err}\n\n"
                            f"Fleet commander has {rerolls} re-roll(s) remaining.\n"
                            f"Use a re-roll? (Cannot be undone)")
                        if use_rr:
                            rr = self.ctx.tc.attempt_reroll_command_check(
                                leader_ship, order)
                            if rr["success"]:
                                # Apply order to all non-braced members
                                from .models import SpecialOrder as _SO
                                affected2 = []
                                for m in [ship] + sq_members:
                                    fresh = self.ctx.gs.get_ship_by_id(m.id)
                                    if (fresh and fresh.special_order
                                            != _SO.BRACE_FOR_IMPACT.value):
                                        fresh.special_order = order
                                        self.ctx.gs.update_ship(fresh)
                                        affected2.append(fresh.name)
                                        self.ctx.gs.add_log(
                                            f"  {fresh.name}: {order} "
                                            f"(squadron re-roll)")
                                self.ctx.log(
                                    f"Squadron {order} RE-ROLL PASSED "
                                    f"(rolled {rr.get('roll')} vs "
                                    f"Ld {rr.get('needed')})")
                                messagebox.showinfo("Re-roll Passed!",
                                    f"Squadron {order} RE-ROLL PASSED\n"
                                    f"Applied to: {', '.join(affected2)}")
                            else:
                                rr_err = rr.get("error",
                                                f"Squadron {order} RE-ROLL FAILED")
                                self.ctx.log(rr_err)
                                messagebox.showwarning("Re-roll Failed",
                                    f"Squadron {order} RE-ROLL ALSO FAILED\n"
                                    f"Rolled {rr.get('roll')} vs "
                                    f"Ld {rr.get('needed')}\n"
                                    f"No more special orders this turn!")
                    else:
                        messagebox.showwarning("Squadron Order Failed", err)
            else:
                # --- Individual order path (original behaviour) ---
                result = self.ctx.tc.issue_special_order(ship, order)
                roll_info = (f" (rolled {result.get('roll', '?')} "
                             f"vs Ld {result.get('needed', '?')})")
                if result["success"]:
                    self.ctx.log(f"{ship.name}: {order} PASSED{roll_info}")
                    messagebox.showinfo("Order Passed",
                        f"{ship.name}: {order} PASSED\n"
                        f"Rolled {result.get('roll')} vs "
                        f"Leadership {result.get('needed')}")
                else:
                    _handle_failed_individual(result, order)
            self.ctx.board.redraw()

        # Show re-roll count
        rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
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
        unmoved = self.ctx.tc.get_unmoved_ships()
        if not unmoved:
            messagebox.showinfo("No Ships", "All ships have moved")
            return

        if preselected_ship and preselected_ship.id in {s.id for s in unmoved}:
            ship = preselected_ship
        else:
            ship = self.ctx.pick_ship(unmoved, "Select ship to move")
        if not ship:
            return

        # Movement command dialog
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Move {ship.name}")
        dialog.geometry("500x580")
        dialog.transient(self.ctx.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=f"Move: {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        # Ship stats
        order = ship.special_order
        min_turn_dist = MIN_TURN_DISTANCE.get(ship.ship_type, 10)
        aaf_bonus = 0
        if order == SpecialOrder.ALL_AHEAD_FULL.value:
            aaf_bonus = resolve_aaf_speed(ship, self.ctx.dice)
            self.ctx.log(
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
            self.ctx.board.redraw()

        def _validate():
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.ctx.gs.get_blast_markers(),
                self.ctx.gs.table_width, self.ctx.gs.table_height,
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
            self.ctx.board.redraw()
            if result.path:
                for i in range(len(result.path) - 1):
                    sx0, sy0 = self.ctx.board.cm_to_screen(*result.path[i])
                    sx1, sy1 = self.ctx.board.cm_to_screen(*result.path[i+1])
                    color = "#44FF44" if result.valid else "#FF4444"
                    self.ctx.board.canvas.create_line(
                        sx0, sy0, sx1, sy1,
                        fill=color, width=2, dash=(4, 4))
                if result.valid:
                    gx, gy = self.ctx.board.cm_to_screen(
                        result.final_x, result.final_y)
                    r = self.ctx.board.cm_to_pixels(1.2)
                    self.ctx.board.canvas.create_oval(
                        gx-r, gy-r, gx+r, gy+r,
                        outline="#44FF44", width=2, dash=(3, 3))
                    # Ghost heading arrow
                    head_rad = math.radians(result.final_heading)
                    ax = gx + r * 2 * math.cos(head_rad)
                    ay = gy - r * 2 * math.sin(head_rad)
                    self.ctx.board.canvas.create_line(
                        gx, gy, ax, ay, fill="#44FF44", width=2, arrow=tk.LAST)

        def _on_dialog_close():
            self.ctx.board.canvas.unbind("<MouseWheel>")
            self.ctx.board.canvas.unbind("<Button-4>")
            self.ctx.board.canvas.unbind("<Button-5>")
            if self._board_scroll_fn:
                self.ctx.board.canvas.bind("<MouseWheel>", self._board_scroll_fn)
                self.ctx.board.canvas.bind("<Button-4>", self._board_scroll_fn)
                self.ctx.board.canvas.bind("<Button-5>", self._board_scroll_fn)
            dialog.destroy()

        def _confirm():
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.ctx.gs.get_blast_markers(),
                self.ctx.gs.table_width, self.ctx.gs.table_height,
                turns_already_used=_turns_already)
            if not result.valid:
                messagebox.showerror("Invalid Movement",
                                     "\n".join(result.errors))
                return
            execute_movement(ship, result, self.ctx.gs)

            # Check for terrain navigation tests
            updated_ship = self.ctx.gs.get_ship_by_id(ship.id)
            if updated_ship and not updated_ship.is_disengaged:
                from .terrain_effects import (resolve_asteroid_navigation,
                                               resolve_warp_rift_navigation,
                                               resolve_gas_dust_contact)
                if "in_asteroid_field" in (updated_ship.special_rules or []):
                    on_aaf = order == SpecialOrder.ALL_AHEAD_FULL.value
                    nav = resolve_asteroid_navigation(
                        updated_ship, self.ctx.dice, self.ctx.gs, on_aaf)
                    if not nav["passed"]:
                        self.ctx.log(
                            f"  {updated_ship.name}: asteroid damage {nav['damage']} HP!")
                        self.ctx.check_destruction(updated_ship)
                    # Remove flag
                    updated_ship = self.ctx.gs.get_ship_by_id(ship.id)
                    if updated_ship:
                        sr = [r for r in updated_ship.special_rules
                              if r != "in_asteroid_field"]
                        updated_ship.special_rules = sr
                        self.ctx.gs.update_ship(updated_ship)

                if "in_warp_rift" in (updated_ship.special_rules or []):
                    nav = resolve_warp_rift_navigation(
                        updated_ship, self.ctx.dice, self.ctx.gs)
                    if not nav["passed"]:
                        self.ctx.log(f"  {updated_ship.name}: LOST IN THE WARP!")
                    else:
                        pos = nav.get("new_position", (0, 0))
                        self.ctx.log(
                            f"  {updated_ship.name}: emerged at ({pos[0]:.0f}, {pos[1]:.0f})")
                    updated_ship = self.ctx.gs.get_ship_by_id(ship.id)
                    if updated_ship:
                        sr = [r for r in updated_ship.special_rules
                              if r != "in_warp_rift"]
                        updated_ship.special_rules = sr
                        self.ctx.gs.update_ship(updated_ship)

                if "in_dust_cloud" in (updated_ship.special_rules or []):
                    resolve_gas_dust_contact(updated_ship, self.ctx.dice, self.ctx.gs)
                    updated_ship = self.ctx.gs.get_ship_by_id(ship.id)
                    if updated_ship:
                        sr = [r for r in updated_ship.special_rules
                              if r != "in_dust_cloud"]
                        updated_ship.special_rules = sr
                        self.ctx.gs.update_ship(updated_ship)

            # Update staged movement tracking fields before marking fully moved
            final_ship = self.ctx.gs.get_ship_by_id(ship.id)
            if final_ship:
                final_ship.distance_moved_this_turn = (
                    already_moved + result.total_distance)
                final_ship.turns_used_this_turn = (
                    _turns_already + result.turns_used)
                dialog_net = (
                    sum(c.value for c in commands if c.action == "turn_left")
                    - sum(c.value for c in commands if c.action == "turn_right"))
                final_ship.net_rotation_this_turn = _net_rot_already + dialog_net
                self.ctx.gs.update_ship(final_ship)
            self.ctx.tc.mark_ship_moved(ship.id)
            self.ctx.tc.record_action(
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
            self.ctx.log(
                f"{ship.name}: moved {result.total_distance:.1f}cm")

            # Offer boarding declaration if rule is on and ship ended in base contact
            if self.ctx.gs.rule_boarding:
                moved_ship = self.ctx.gs.get_ship_by_id(ship.id)
                if moved_ship and not moved_ship.has_boarded and not moved_ship.is_grappled:
                    from .boarding import ships_in_base_contact
                    enemies = [s for s in self.ctx.gs.get_ships()
                               if s.player != moved_ship.player
                               and not s.is_destroyed and not s.is_disengaged
                               and s.status not in (
                                   "drifting_hulk", "burning_hulk", "destroyed")]
                    contacted = [e for e in enemies
                                 if ships_in_base_contact(moved_ship, e)]
                    if contacted:
                        target_names = ", ".join(e.name for e in contacted)
                        if messagebox.askyesno(
                                "Declare Boarding Action",
                                f"{moved_ship.name} is in base contact with "
                                f"{target_names}.\n"
                                f"Declare a boarding action?\n"
                                f"(Ship cannot fire weapons or launch ordnance "
                                f"this turn)"):
                            board_target = (
                                contacted[0] if len(contacted) == 1
                                else self.ctx.pick_ship(contacted,
                                                        "Select boarding target"))
                            if board_target:
                                moved_ship.boarding_target_id = board_target.id
                                moved_ship.has_boarded = True
                                self.ctx.gs.update_ship(moved_ship)
                                self.ctx.log(
                                    f"{moved_ship.name} declares boarding action "
                                    f"against {board_target.name}!")

            _on_dialog_close()
            self.ctx.board.redraw()

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

        self.ctx.board.canvas.bind("<MouseWheel>", _on_scroll)
        self.ctx.board.canvas.bind("<Button-4>", _on_scroll)
        self.ctx.board.canvas.bind("<Button-5>", _on_scroll)

        # Pre-populate commands if provided (after all helpers are defined)
        if initial_commands:
            for c in initial_commands:
                commands.append(c)
                cmd_listbox.insert(tk.END, str(c))
            _validate()

        dialog.protocol("WM_DELETE_WINDOW", _on_dialog_close)

    def _move_squadron_dialog(self):
        """Move all ships in a squadron with the same movement commands."""
        from .squadron import get_squadrons
        from .movement import (validate_movement, execute_movement,
                               resolve_aaf_speed, MIN_TURN_DISTANCE)
        from .terrain_effects import (resolve_asteroid_navigation,
                                      resolve_warp_rift_navigation,
                                      resolve_gas_dust_contact)

        if self.ctx.gs.current_phase != "movement":
            return

        player = self.ctx.gs.active_player
        unmoved_ids = {s.id for s in self.ctx.tc.get_unmoved_ships()}

        # Squadrons that have at least one unmoved ship
        all_squads = get_squadrons(self.ctx.gs, player)
        active_squads = {
            sid: members for sid, members in all_squads.items()
            if any(s.id in unmoved_ids for s in members)
        }
        if not active_squads:
            messagebox.showinfo("No Squadrons",
                                "No squadrons with unmoved ships available.")
            return

        # Pick a squadron
        if len(active_squads) == 1:
            chosen_sid = next(iter(active_squads))
        else:
            pick_dialog = tk.Toplevel(self.ctx.root)
            pick_dialog.title("Select Squadron")
            pick_dialog.geometry("340x200")
            pick_dialog.transient(self.ctx.root)
            tk.Label(pick_dialog, text="Select Squadron to Move",
                     font=("Consolas", 10, "bold")).pack(pady=6)
            lb = tk.Listbox(pick_dialog, font=("Consolas", 9),
                            height=6, width=38)
            lb.pack(padx=10, fill=tk.X)
            sq_keys = list(active_squads.keys())
            for sid in sq_keys:
                names = ", ".join(s.name for s in active_squads[sid])
                lb.insert(tk.END, f"{sid}: {names}")
            lb.selection_set(0)
            chosen_sid_holder = [None]

            def _pick_confirm():
                sel = lb.curselection()
                if sel:
                    chosen_sid_holder[0] = sq_keys[sel[0]]
                pick_dialog.destroy()

            tk.Button(pick_dialog, text="Select", command=_pick_confirm,
                      bg="#336633", fg="white",
                      font=("Consolas", 9)).pack(pady=6)
            pick_dialog.wait_window()
            chosen_sid = chosen_sid_holder[0]
            if not chosen_sid:
                return

        members = active_squads[chosen_sid]

        # Pre-compute AAF bonuses for AAF ships at dialog-open time
        aaf_bonuses: dict = {}
        for s in members:
            if (s.special_order == SpecialOrder.ALL_AHEAD_FULL.value
                    and s.id in unmoved_ids):
                bonus = resolve_aaf_speed(s, self.ctx.dice)
                aaf_bonuses[s.id] = bonus
                self.ctx.log(f"{s.name} AAF speed bonus: +{bonus}cm")

        # Main dialog
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Move Squadron: {chosen_sid}")
        dialog.geometry("540x640")
        dialog.transient(self.ctx.root)

        tk.Label(dialog, text=f"Squadron Move: {chosen_sid}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        # ---- Checkboxes: include/exclude members ----
        chk_frame = tk.LabelFrame(dialog, text="Ships to move",
                                  font=("Consolas", 9))
        chk_frame.pack(fill=tk.X, padx=10, pady=3)
        chk_vars: dict = {}
        for s in members:
            unmoved = s.id in unmoved_ids
            var = tk.BooleanVar(value=unmoved)
            lbl_txt = (f"{s.name}  [{s.ship_class}]"
                       + ("" if unmoved else "  (already moved)"))
            cb = tk.Checkbutton(chk_frame, text=lbl_txt, variable=var,
                                font=("Consolas", 9),
                                state=tk.NORMAL if unmoved else tk.DISABLED)
            cb.pack(anchor=tk.W, padx=5)
            chk_vars[s.id] = var

        # ---- Aggregate stats label ----
        stats_var = tk.StringVar()
        stats_lbl = tk.Label(dialog, textvariable=stats_var,
                             font=("Consolas", 8), justify=tk.LEFT)
        stats_lbl.pack(padx=10, anchor=tk.W)

        remaining_var = tk.StringVar()
        remaining_lbl = tk.Label(dialog, textvariable=remaining_var,
                                 font=("Consolas", 10, "bold"), fg="#44CC44")
        remaining_lbl.pack()

        def _included_ships():
            return [s for s in members if chk_vars[s.id].get()]

        def _update_stats():
            ships_in = _included_ships()
            if not ships_in:
                stats_var.set("No ships selected.")
                remaining_var.set("")
                return
            speeds = []
            mins = []
            for s in ships_in:
                order = s.special_order
                base = s.effective_speed
                aaf = aaf_bonuses.get(s.id, 0)
                already = s.distance_moved_this_turn
                if order == SpecialOrder.ALL_AHEAD_FULL.value:
                    budget = max(0.0, base + aaf - already)
                    sp_min = budget  # must use all
                elif order == SpecialOrder.BURN_RETROS.value:
                    budget = max(0.0, base // 2 - already)
                    sp_min = 0.0
                else:
                    budget = max(0.0, base - already)
                    sp_min = max(0.0, max(1, base // 2) - already)
                speeds.append(budget)
                mins.append(sp_min)
            max_spd = min(speeds)
            min_spd = max(mins)
            ta = min(s.turn_angle for s in ships_in)
            mtd = max(MIN_TURN_DISTANCE.get(s.ship_type, 0) for s in ships_in)
            orders_str = ", ".join(
                f"{s.name}:{s.special_order}" for s in ships_in
                if s.special_order != "none"
            ) or "none"
            stats_var.set(
                f"Ships: {', '.join(s.name for s in ships_in)}\n"
                f"Speed range: {min_spd:.0f}–{max_spd:.0f}cm  "
                f"Turn: ≤{ta}°  Min-before-turn: {mtd}cm\n"
                f"Orders: {orders_str}"
            )
            remaining_var.set(f"Max budget: {max_spd:.0f}cm")
            remaining_lbl.config(fg="#44CC44")

        for var in chk_vars.values():
            var.trace_add("write", lambda *_: (_update_stats(), _validate()))

        _update_stats()

        # ---- Command list ----
        cmd_listbox = tk.Listbox(dialog, font=("Consolas", 9),
                                  height=5, width=55)
        cmd_listbox.pack(padx=10, pady=3, fill=tk.X)
        commands: list = []

        # Quick move buttons
        quick_frame = tk.Frame(dialog)
        quick_frame.pack(padx=10, pady=2, fill=tk.X)

        def _agg_max():
            ships_in = _included_ships()
            if not ships_in:
                return 0.0
            speeds = []
            for s in ships_in:
                order = s.special_order
                base = s.effective_speed
                aaf = aaf_bonuses.get(s.id, 0)
                already = s.distance_moved_this_turn
                if order == SpecialOrder.ALL_AHEAD_FULL.value:
                    speeds.append(max(0.0, base + aaf - already))
                elif order == SpecialOrder.BURN_RETROS.value:
                    speeds.append(max(0.0, base // 2 - already))
                else:
                    speeds.append(max(0.0, base - already))
            return min(speeds)

        def _agg_min():
            ships_in = _included_ships()
            if not ships_in:
                return 0.0
            mins = []
            for s in ships_in:
                order = s.special_order
                base = s.effective_speed
                already = s.distance_moved_this_turn
                if order == SpecialOrder.BURN_RETROS.value:
                    mins.append(0.0)
                else:
                    mins.append(max(0.0, max(1, base // 2) - already))
            return max(mins)

        def _quick_min():
            needed = max(0.0, _agg_min()
                         - sum(c.value for c in commands if c.action == "forward"))
            if needed > 0:
                _add_cmd("forward", needed)

        def _quick_full():
            used = sum(c.value for c in commands if c.action == "forward")
            rem = max(0.0, _agg_max() - used)
            if rem > 0:
                _add_cmd("forward", rem)

        tk.Button(quick_frame, text="Auto: Min Move",
                  command=_quick_min,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Auto: Full Speed",
                  command=_quick_full,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        # Add command buttons
        add_frame = tk.Frame(dialog)
        add_frame.pack(padx=10, pady=3)
        dist_var = tk.StringVar(value="10")
        angle_var = tk.StringVar(value="45")
        tk.Label(add_frame, text="Distance:").grid(row=0, column=0)
        tk.Entry(add_frame, textvariable=dist_var, width=6,
                 font=("Consolas", 10)).grid(row=0, column=1)
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

        # Quick turn buttons
        turn_frame = tk.Frame(dialog)
        turn_frame.pack(padx=10, pady=2, fill=tk.X)
        tk.Label(turn_frame, text="Quick turns:",
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        for deg in [5, 15, 30, 45]:
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

        # Validation label
        preview_var = tk.StringVar(value="Add movement commands above")
        preview_lbl = tk.Label(dialog, textvariable=preview_var,
                               font=("Consolas", 8), fg="#AAAAAA",
                               wraplength=500, justify=tk.LEFT)
        preview_lbl.pack(padx=10)

        confirm_btn_holder: list = []

        def _add_cmd(action, value):
            try:
                value = float(value)
            except ValueError:
                return
            if action in ("turn_left", "turn_right"):
                if value <= 0:
                    return
                ships_in = _included_ships()
                max_ta = min((s.turn_angle for s in ships_in), default=45)
                _SNAP = 15.0
                if value > max_ta:
                    if value - max_ta <= _SNAP:
                        value = float(max_ta)
                    else:
                        preview_var.set(
                            f"Cancelled: {value:.0f}° exceeds max turn of {max_ta:.0f}°")
                        return
            commands.append(MoveCommand(action, value))
            cmd_listbox.insert(tk.END, str(commands[-1]))
            _validate()

        def _remove_last():
            if commands:
                commands.pop()
                cmd_listbox.delete(tk.END)
                _validate()

        def _clear_all():
            commands.clear()
            cmd_listbox.delete(0, tk.END)
            _update_stats()
            preview_var.set("Add movement commands above")
            preview_lbl.config(fg="#AAAAAA")
            self.ctx.board.redraw()

        def _validate():
            ships_in = _included_ships()
            if not ships_in:
                preview_var.set("No ships selected.")
                preview_lbl.config(fg="#FF6644")
                if confirm_btn_holder:
                    confirm_btn_holder[0].config(state=tk.DISABLED)
                return
            all_valid = True
            errors_out: list = []
            first_result = None
            for s in ships_in:
                order = s.special_order
                aaf = aaf_bonuses.get(s.id, 0)
                res = validate_movement(
                    s, commands, order, aaf,
                    self.ctx.gs.get_blast_markers(),
                    self.ctx.gs.table_width, self.ctx.gs.table_height,
                    turns_already_used=s.turns_used_this_turn)
                if first_result is None:
                    first_result = res
                if not res.valid:
                    all_valid = False
                    errors_out.append(f"{s.name}: " + "; ".join(res.errors))
            if all_valid and first_result:
                preview_var.set(
                    f"VALID ({len(ships_in)} ships): "
                    f"{first_result.total_distance:.1f}cm, "
                    f"{first_result.turns_used} turns, "
                    f"end hdg {first_result.final_heading:.0f}°")
                preview_lbl.config(fg="#44FF44")
                if confirm_btn_holder:
                    confirm_btn_holder[0].config(state=tk.NORMAL)
            else:
                preview_var.set("ERRORS:\n" + "\n".join(errors_out))
                preview_lbl.config(fg="#FF4444")
                if confirm_btn_holder:
                    confirm_btn_holder[0].config(state=tk.DISABLED)

            # Draw ghost path for first included ship
            self.ctx.board.redraw()
            if first_result and first_result.path:
                for i in range(len(first_result.path) - 1):
                    sx0, sy0 = self.ctx.board.cm_to_screen(*first_result.path[i])
                    sx1, sy1 = self.ctx.board.cm_to_screen(*first_result.path[i+1])
                    color = "#44FF44" if all_valid else "#FF4444"
                    self.ctx.board.canvas.create_line(
                        sx0, sy0, sx1, sy1,
                        fill=color, width=2, dash=(4, 4))

        def _on_close():
            self.ctx.board.canvas.unbind("<MouseWheel>")
            self.ctx.board.canvas.unbind("<Button-4>")
            self.ctx.board.canvas.unbind("<Button-5>")
            if self._board_scroll_fn:
                self.ctx.board.canvas.bind("<MouseWheel>", self._board_scroll_fn)
                self.ctx.board.canvas.bind("<Button-4>", self._board_scroll_fn)
                self.ctx.board.canvas.bind("<Button-5>", self._board_scroll_fn)
            dialog.destroy()

        def _confirm():
            ships_in = _included_ships()
            if not ships_in:
                return
            # Final validation pass
            results: dict = {}
            for s in ships_in:
                order = s.special_order
                aaf = aaf_bonuses.get(s.id, 0)
                res = validate_movement(
                    s, commands, order, aaf,
                    self.ctx.gs.get_blast_markers(),
                    self.ctx.gs.table_width, self.ctx.gs.table_height,
                    turns_already_used=s.turns_used_this_turn)
                if not res.valid:
                    messagebox.showerror(
                        "Invalid Movement",
                        f"{s.name}:\n" + "\n".join(res.errors))
                    return
                results[s.id] = res

            for s in ships_in:
                res = results[s.id]
                execute_movement(s, res, self.ctx.gs)

                # Terrain navigation tests
                updated = self.ctx.gs.get_ship_by_id(s.id)
                if updated and not updated.is_disengaged:
                    if "in_asteroid_field" in (updated.special_rules or []):
                        on_aaf = s.special_order == SpecialOrder.ALL_AHEAD_FULL.value
                        nav = resolve_asteroid_navigation(
                            updated, self.ctx.dice, self.ctx.gs, on_aaf)
                        if not nav["passed"]:
                            self.ctx.log(
                                f"  {updated.name}: asteroid damage {nav['damage']} HP!")
                            self.ctx.check_destruction(updated)
                        updated = self.ctx.gs.get_ship_by_id(s.id)
                        if updated:
                            updated.special_rules = [
                                r for r in updated.special_rules
                                if r != "in_asteroid_field"]
                            self.ctx.gs.update_ship(updated)
                    if updated and "in_warp_rift" in (updated.special_rules or []):
                        nav = resolve_warp_rift_navigation(
                            updated, self.ctx.dice, self.ctx.gs)
                        if not nav["passed"]:
                            self.ctx.log(f"  {updated.name}: LOST IN THE WARP!")
                        updated = self.ctx.gs.get_ship_by_id(s.id)
                        if updated:
                            updated.special_rules = [
                                r for r in updated.special_rules
                                if r != "in_warp_rift"]
                            self.ctx.gs.update_ship(updated)
                    if updated and "in_dust_cloud" in (updated.special_rules or []):
                        resolve_gas_dust_contact(updated, self.ctx.dice, self.ctx.gs)
                        updated = self.ctx.gs.get_ship_by_id(s.id)
                        if updated:
                            updated.special_rules = [
                                r for r in updated.special_rules
                                if r != "in_dust_cloud"]
                            self.ctx.gs.update_ship(updated)

                # Update staged tracking
                final = self.ctx.gs.get_ship_by_id(s.id)
                if final:
                    final.distance_moved_this_turn += res.total_distance
                    final.turns_used_this_turn += res.turns_used
                    left_deg = sum(c.value for c in commands
                                   if c.action == "turn_left")
                    right_deg = sum(c.value for c in commands
                                    if c.action == "turn_right")
                    final.net_rotation_this_turn += (left_deg - right_deg)
                    self.ctx.gs.update_ship(final)

                self.ctx.tc.mark_ship_moved(s.id)
                self.ctx.log(
                    f"{s.name}: squadron-moved {res.total_distance:.1f}cm "
                    f"to ({res.final_x:.1f}, {res.final_y:.1f}) "
                    f"hdg {res.final_heading:.0f}°")

            _on_close()
            self.ctx.board.redraw()

        # Buttons
        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=5)
        confirm_btn = tk.Button(btn_row, text="Confirm Move", command=_confirm,
                                bg="#336633", fg="white",
                                font=("Consolas", 10), state=tk.DISABLED)
        confirm_btn.pack(side=tk.LEFT, padx=5)
        confirm_btn_holder.append(confirm_btn)
        tk.Button(btn_row, text="Cancel", command=_on_close,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        # Scroll-wheel turns on board canvas
        _scroll_deg_sq = 5

        def _on_scroll_sq(event):
            if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
                _add_cmd("turn_left", _scroll_deg_sq)
            elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
                _add_cmd("turn_right", _scroll_deg_sq)

        self.ctx.board.canvas.bind("<MouseWheel>", _on_scroll_sq)
        self.ctx.board.canvas.bind("<Button-4>", _on_scroll_sq)
        self.ctx.board.canvas.bind("<Button-5>", _on_scroll_sq)

        dialog.protocol("WM_DELETE_WINDOW", _on_close)

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
