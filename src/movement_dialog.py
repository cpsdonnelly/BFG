"""BFG:XR — MovementDialogMixin: _move_ship_dialog and _move_squadron_dialog."""
import tkinter as tk
from tkinter import messagebox
import math

from .models import SpecialOrder
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE, get_max_turns)


class MovementDialogMixin:

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
            self._resolve_post_move_terrain(
                ship.id, order == SpecialOrder.ALL_AHEAD_FULL.value)

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
                self._resolve_post_move_terrain(
                    s.id, s.special_order == SpecialOrder.ALL_AHEAD_FULL.value)

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
