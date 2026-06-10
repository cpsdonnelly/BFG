"""BFG:XR — MovementDialogMixin: ship and squadron movement dialogs."""
import tkinter as tk
from tkinter import messagebox
import math

from .models import SpecialOrder
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE, get_max_turns)


# ---------------------------------------------------------------------------
# Private dialog controllers
# ---------------------------------------------------------------------------

class _MoveShipDialog:
    """Controller for the individual-ship movement dialog."""

    def __init__(self, panel, ship, initial_commands=None):
        self.panel = panel
        self.ctx = panel.ctx
        self.ship = ship
        self.initial_commands = initial_commands or []
        self.commands = []

        # Pre-compute movement budget (AAF roll happens here, before UI opens)
        self.order = ship.special_order
        self.min_turn_dist = MIN_TURN_DISTANCE.get(ship.ship_type, 10)
        self.aaf_bonus = 0
        if self.order == SpecialOrder.ALL_AHEAD_FULL.value:
            self.aaf_bonus = resolve_aaf_speed(ship, self.ctx.dice)
            self.ctx.log(f"{ship.name} AAF speed bonus: +{self.aaf_bonus}cm")

        base = ship.effective_speed
        already = ship.distance_moved_this_turn
        if self.order == SpecialOrder.ALL_AHEAD_FULL.value:
            self.max_speed = max(0.0, base + self.aaf_bonus - already)
            self.min_speed = self.max_speed
            self.speed_text = (
                f"Speed: {self.max_speed:.0f}cm remaining "
                f"(AAF: {base}+{self.aaf_bonus}, moved {already:.0f}cm)")
        elif self.order == SpecialOrder.BURN_RETROS.value:
            self.max_speed = max(0.0, base // 2 - already)
            self.min_speed = 0
            self.speed_text = (
                f"Speed: 0-{self.max_speed:.0f}cm "
                f"(Burn Retros, moved {already:.0f}cm)")
        else:
            self.max_speed = max(0.0, base - already)
            raw_min = max(1, base // 2)
            self.min_speed = max(0.0, raw_min - already)
            self.speed_text = (
                f"Speed: {self.min_speed:.0f}-{self.max_speed:.0f}cm"
                + (f" (moved {already:.0f}cm)" if already > 0 else ""))

        self.already_moved = already
        self._max_turns = get_max_turns(self.order, ship)
        self._turns_already = ship.turns_used_this_turn
        self._net_rot_already = ship.net_rotation_this_turn
        self._net_init_str = (f"+{self._net_rot_already:.0f}°"
                              if self._net_rot_already >= 0
                              else f"{self._net_rot_already:.0f}°")
        self._scroll_deg = min(5, ship.turn_angle)

    def run(self):
        if self.max_speed < 0.5 and self.order != SpecialOrder.BURN_RETROS.value:
            messagebox.showinfo(
                "No Budget",
                f"{self.ship.name} has already moved {self.already_moved:.0f}cm "
                f"— no remaining movement budget.")
            return
        self._build_ui()
        if self.initial_commands:
            for c in self.initial_commands:
                self.commands.append(c)
                self.cmd_listbox.insert(tk.END, str(c))
            self._validate()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        ship = self.ship
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Move {ship.name}")
        dialog.geometry("500x580")
        dialog.transient(self.ctx.root)
        self.dialog = dialog

        tk.Label(dialog, text=f"Move: {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        # Crit warnings
        crit_warnings = []
        if any(c.get("crit_type") == "engine_room" for c in ship.critical_damage):
            crit_warnings.append("ENGINE ROOM DAMAGED: No turns!")
        thrusters = sum(1 for c in ship.critical_damage
                        if c.get("crit_type") == "thrusters_damaged")
        if thrusters:
            crit_warnings.append(f"THRUSTERS DAMAGED x{thrusters}: -10cm speed")

        info_text = (
            f"Order: {self.order} | {self.speed_text}\n"
            f"Turn: {ship.turn_angle}° max | "
            f"Min before turn: {self.min_turn_dist}cm\n"
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
        self.remaining_var = tk.StringVar(
            value=f"Remaining: {self.max_speed:.0f}cm / {self.max_speed:.0f}cm")
        self.remaining_label = tk.Label(
            meter_frame, textvariable=self.remaining_var,
            font=("Consolas", 10, "bold"), fg="#44CC44")
        self.remaining_label.pack()

        self.turn_stats_var = tk.StringVar(
            value=(f"Turns: {self._turns_already}/{self._max_turns} used | "
                   f"Net: {self._net_init_str} | "
                   f"Remaining angle: {ship.turn_angle}°"))
        self.turn_stats_label = tk.Label(
            meter_frame, textvariable=self.turn_stats_var,
            font=("Consolas", 9), fg="#AAAAFF")
        self.turn_stats_label.pack()

        # Command list
        self.cmd_listbox = tk.Listbox(dialog, font=("Consolas", 9),
                                      height=6, width=50)
        self.cmd_listbox.pack(padx=10, pady=3, fill=tk.X)

        # Quick-move buttons
        quick_frame = tk.Frame(dialog)
        quick_frame.pack(padx=10, pady=3, fill=tk.X)
        tk.Button(quick_frame, text=f"Auto: Min Move ({self.min_speed:.0f}cm)",
                  command=self._quick_min_move,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        if self.min_turn_dist > 0 and ship.ship_type != "escort":
            tk.Button(quick_frame, text=f"Auto: Pre-Turn ({self.min_turn_dist}cm)",
                      command=self._quick_min_before_turn,
                      font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Auto: Full Speed",
                  command=self._quick_full_speed,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Auto: Remaining",
                  command=self._quick_remaining,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        # Add-command controls
        add_frame = tk.Frame(dialog)
        add_frame.pack(padx=10, pady=3)
        self.dist_var = tk.StringVar(value="10")
        self.angle_var = tk.StringVar(value=str(ship.turn_angle))

        tk.Label(add_frame, text="Distance:").grid(row=0, column=0)
        tk.Entry(add_frame, textvariable=self.dist_var, width=6,
                 font=("Consolas", 10)).grid(row=0, column=1)
        tk.Button(add_frame, text="Forward",
                  command=lambda: self._add_cmd("forward", float(self.dist_var.get())),
                  font=("Consolas", 9)).grid(row=0, column=2, padx=3)

        tk.Label(add_frame, text="Angle:").grid(row=1, column=0)
        tk.Entry(add_frame, textvariable=self.angle_var, width=6,
                 font=("Consolas", 10)).grid(row=1, column=1)
        tk.Button(add_frame, text="Anticlockwise",
                  command=lambda: self._add_cmd("turn_left", float(self.angle_var.get())),
                  font=("Consolas", 9)).grid(row=1, column=2, padx=3)
        tk.Button(add_frame, text="Clockwise",
                  command=lambda: self._add_cmd("turn_right", float(self.angle_var.get())),
                  font=("Consolas", 9)).grid(row=1, column=3, padx=3)

        turn_frame = tk.Frame(dialog)
        turn_frame.pack(padx=10, pady=2, fill=tk.X)
        tk.Label(turn_frame, text="Quick turns:",
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        for deg in [5, 15, 30, 45]:
            if deg <= ship.turn_angle:
                tk.Button(turn_frame, text=f"↶{deg}°",
                          command=lambda d=deg: self._add_cmd("turn_left", d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
                tk.Button(turn_frame, text=f"↷{deg}°",
                          command=lambda d=deg: self._add_cmd("turn_right", d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)

        tk.Button(add_frame, text="Remove Last", command=self._remove_last,
                  font=("Consolas", 9)).grid(row=2, column=0, columnspan=2, pady=3)
        tk.Button(add_frame, text="Clear All", command=self._clear_all,
                  font=("Consolas", 9)).grid(row=2, column=2, columnspan=2, pady=3)

        self.preview_var = tk.StringVar(value="Add movement commands above")
        tk.Label(dialog, textvariable=self.preview_var,
                 font=("Consolas", 8), fg="#AAAAAA",
                 wraplength=460, justify=tk.LEFT).pack(padx=10)

        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=5)
        tk.Button(btn_row, text="Confirm Move", command=self._confirm,
                  bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Cancel", command=self._on_close,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        self.ctx.board.canvas.bind("<MouseWheel>", self._on_scroll)
        self.ctx.board.canvas.bind("<Button-4>", self._on_scroll)
        self.ctx.board.canvas.bind("<Button-5>", self._on_scroll)

    # --------------------------------------------------------- quick buttons -

    def _quick_min_move(self):
        current = sum(c.value for c in self.commands if c.action == "forward")
        needed = max(0, self.min_speed - current)
        if needed > 0:
            self._add_cmd("forward", needed)

    def _quick_min_before_turn(self):
        dist_since_turn = 0
        for c in reversed(self.commands):
            if c.action == "forward":
                dist_since_turn += c.value
            else:
                break
        needed = max(0, self.min_turn_dist - dist_since_turn)
        if needed > 0:
            self._add_cmd("forward", needed)

    def _quick_full_speed(self):
        current = sum(c.value for c in self.commands if c.action == "forward")
        remaining = max(0, self.max_speed - current)
        if remaining > 0:
            self._add_cmd("forward", remaining)

    def _quick_remaining(self):
        current = sum(c.value for c in self.commands if c.action == "forward")
        remaining = max(0, self.max_speed - current)
        if remaining > 0:
            self._add_cmd("forward", remaining)

    # --------------------------------------------------------- command list --

    def _add_cmd(self, action, value):
        try:
            value = float(value)
        except ValueError:
            return
        if action in ("turn_left", "turn_right"):
            if value <= 0:
                return
            max_turn = float(self.ship.turn_angle)
            if value > max_turn:
                _SNAP = 15.0
                if value - max_turn <= _SNAP:
                    value = max_turn
                    self.preview_var.set(f"Snapped to max turn ({max_turn:.0f}°)")
                else:
                    self.preview_var.set(
                        f"Cancelled: {value:.0f}° exceeds max turn of {max_turn:.0f}°")
                    return
        self.commands.append(MoveCommand(action, value))
        self.cmd_listbox.insert(tk.END, str(self.commands[-1]))
        self._validate()

    def _remove_last(self):
        if self.commands:
            self.commands.pop()
            self.cmd_listbox.delete(tk.END)
            self._validate()

    def _clear_all(self):
        self.commands.clear()
        self.cmd_listbox.delete(0, tk.END)
        self.remaining_var.set(
            f"Remaining: {self.max_speed:.0f}cm / {self.max_speed:.0f}cm")
        self.remaining_label.config(fg="#44CC44")
        self.turn_stats_var.set(
            f"Turns: {self._turns_already}/{self._max_turns} used | "
            f"Net: {self._net_init_str} | "
            f"Remaining angle: {self.ship.turn_angle}°")
        self.turn_stats_label.config(fg="#AAAAFF")
        self.preview_var.set("Add movement commands above")
        self.ctx.board.redraw()

    # ------------------------------------------------------- validation/exec -

    def _validate(self):
        result = validate_movement(
            self.ship, self.commands, self.order, self.aaf_bonus,
            self.ctx.gs.get_blast_markers(),
            self.ctx.gs.table_width, self.ctx.gs.table_height,
            turns_already_used=self._turns_already)

        used = result.total_distance
        remaining = max(0, self.max_speed - used)
        self.remaining_var.set(
            f"Remaining: {remaining:.1f}cm / {self.max_speed:.0f}cm "
            f"(used {used:.1f}cm)")
        self.remaining_label.config(fg="#CCAA00" if remaining < 0.5 else "#44CC44")

        left_deg = sum(c.value for c in self.commands if c.action == "turn_left")
        right_deg = sum(c.value for c in self.commands if c.action == "turn_right")
        net_total = self._net_rot_already + (left_deg - right_deg)
        turns_total = self._turns_already + result.turns_used
        angle_left = max(0.0, self.ship.turn_angle - max(left_deg, right_deg))
        net_str = f"+{net_total:.0f}°" if net_total > 0 else f"{net_total:.0f}°"
        self.turn_stats_var.set(
            f"Turns: {turns_total}/{self._max_turns} used | "
            f"Net: {net_str} | Remaining angle: {angle_left:.0f}°")
        self.turn_stats_label.config(
            fg="#FF6644" if turns_total > self._max_turns else "#AAAAFF")

        if result.valid:
            self.preview_var.set(
                f"VALID: {result.total_distance:.1f}cm, "
                f"{result.turns_used} turns, "
                f"end ({result.final_x:.1f}, {result.final_y:.1f}) "
                f"hdg {result.final_heading:.0f}°"
                + (" [DEFENSES]" if result.counts_as_defense else ""))
        else:
            self.preview_var.set("ERRORS: " + "; ".join(result.errors))

        self.ctx.board.redraw()
        if result.path:
            for i in range(len(result.path) - 1):
                sx0, sy0 = self.ctx.board.cm_to_screen(*result.path[i])
                sx1, sy1 = self.ctx.board.cm_to_screen(*result.path[i + 1])
                color = "#44FF44" if result.valid else "#FF4444"
                self.ctx.board.canvas.create_line(
                    sx0, sy0, sx1, sy1, fill=color, width=2, dash=(4, 4))
            if result.valid:
                gx, gy = self.ctx.board.cm_to_screen(
                    result.final_x, result.final_y)
                r = self.ctx.board.cm_to_pixels(1.2)
                self.ctx.board.canvas.create_oval(
                    gx - r, gy - r, gx + r, gy + r,
                    outline="#44FF44", width=2, dash=(3, 3))
                head_rad = math.radians(result.final_heading)
                ax = gx + r * 2 * math.cos(head_rad)
                ay = gy - r * 2 * math.sin(head_rad)
                self.ctx.board.canvas.create_line(
                    gx, gy, ax, ay, fill="#44FF44", width=2, arrow=tk.LAST)

    def _confirm(self):
        result = validate_movement(
            self.ship, self.commands, self.order, self.aaf_bonus,
            self.ctx.gs.get_blast_markers(),
            self.ctx.gs.table_width, self.ctx.gs.table_height,
            turns_already_used=self._turns_already)
        if not result.valid:
            messagebox.showerror("Invalid Movement", "\n".join(result.errors))
            return
        execute_movement(self.ship, result, self.ctx.gs)
        self.panel._resolve_post_move_terrain(
            self.ship.id, self.order == SpecialOrder.ALL_AHEAD_FULL.value)

        final_ship = self.ctx.gs.get_ship_by_id(self.ship.id)
        if final_ship:
            final_ship.distance_moved_this_turn = (
                self.already_moved + result.total_distance)
            final_ship.turns_used_this_turn = (
                self._turns_already + result.turns_used)
            dialog_net = (
                sum(c.value for c in self.commands if c.action == "turn_left")
                - sum(c.value for c in self.commands if c.action == "turn_right"))
            final_ship.net_rotation_this_turn = self._net_rot_already + dialog_net
            self.ctx.gs.update_ship(final_ship)
        self.ctx.tc.mark_ship_moved(self.ship.id)
        self.ctx.tc.record_action(
            "move_ship", self.ship.id,
            details={
                "commands": [{"action": c.action, "value": c.value}
                             for c in self.commands],
                "special_order": self.order,
            },
            result={
                "final_position": [result.final_x, result.final_y],
                "final_heading": result.final_heading,
                "distance_moved": result.total_distance,
            },
            description=(
                f"{self.ship.name} moved {result.total_distance:.1f}cm "
                f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                f"heading {result.final_heading:.0f}°"))
        self.ctx.log(f"{self.ship.name}: moved {result.total_distance:.1f}cm")

        self.panel._offer_boarding(self.ship.id)
        self._on_close()
        self.ctx.board.redraw()

    def _on_close(self):
        self.ctx.board.canvas.unbind("<MouseWheel>")
        self.ctx.board.canvas.unbind("<Button-4>")
        self.ctx.board.canvas.unbind("<Button-5>")
        if self.panel._board_scroll_fn:
            self.ctx.board.canvas.bind("<MouseWheel>", self.panel._board_scroll_fn)
            self.ctx.board.canvas.bind("<Button-4>", self.panel._board_scroll_fn)
            self.ctx.board.canvas.bind("<Button-5>", self.panel._board_scroll_fn)
        self.dialog.destroy()

    def _on_scroll(self, event):
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self._add_cmd("turn_left", self._scroll_deg)
        elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            self._add_cmd("turn_right", self._scroll_deg)


class _MoveSquadronDialog:
    """Controller for the squadron movement dialog."""

    def __init__(self, panel, chosen_sid, members, unmoved_ids, aaf_bonuses):
        self.panel = panel
        self.ctx = panel.ctx
        self.chosen_sid = chosen_sid
        self.members = members
        self.unmoved_ids = unmoved_ids
        self.aaf_bonuses = aaf_bonuses
        self.commands = []
        self.confirm_btn = None

    def run(self):
        self._build_ui()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Move Squadron: {self.chosen_sid}")
        dialog.geometry("540x640")
        dialog.transient(self.ctx.root)
        self.dialog = dialog

        tk.Label(dialog, text=f"Squadron Move: {self.chosen_sid}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        # Ship checkboxes
        chk_frame = tk.LabelFrame(dialog, text="Ships to move",
                                  font=("Consolas", 9))
        chk_frame.pack(fill=tk.X, padx=10, pady=3)
        self.chk_vars: dict = {}
        for s in self.members:
            unmoved = s.id in self.unmoved_ids
            var = tk.BooleanVar(value=unmoved)
            lbl_txt = (f"{s.name}  [{s.ship_class}]"
                       + ("" if unmoved else "  (already moved)"))
            cb = tk.Checkbutton(chk_frame, text=lbl_txt, variable=var,
                                font=("Consolas", 9),
                                state=tk.NORMAL if unmoved else tk.DISABLED)
            cb.pack(anchor=tk.W, padx=5)
            self.chk_vars[s.id] = var

        # Stats
        self.stats_var = tk.StringVar()
        self.stats_lbl = tk.Label(dialog, textvariable=self.stats_var,
                                  font=("Consolas", 8), justify=tk.LEFT)
        self.stats_lbl.pack(padx=10, anchor=tk.W)
        self.remaining_var = tk.StringVar()
        self.remaining_lbl = tk.Label(dialog, textvariable=self.remaining_var,
                                      font=("Consolas", 10, "bold"), fg="#44CC44")
        self.remaining_lbl.pack()

        for var in self.chk_vars.values():
            var.trace_add("write", lambda *_: (self._update_stats(), self._validate()))
        self._update_stats()

        # Command list
        self.cmd_listbox = tk.Listbox(dialog, font=("Consolas", 9),
                                      height=5, width=55)
        self.cmd_listbox.pack(padx=10, pady=3, fill=tk.X)

        # Quick move buttons
        quick_frame = tk.Frame(dialog)
        quick_frame.pack(padx=10, pady=2, fill=tk.X)
        tk.Button(quick_frame, text="Auto: Min Move",
                  command=self._quick_min,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Auto: Full Speed",
                  command=self._quick_full,
                  font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        # Add-command controls
        add_frame = tk.Frame(dialog)
        add_frame.pack(padx=10, pady=3)
        self.dist_var = tk.StringVar(value="10")
        self.angle_var = tk.StringVar(value="45")
        tk.Label(add_frame, text="Distance:").grid(row=0, column=0)
        tk.Entry(add_frame, textvariable=self.dist_var, width=6,
                 font=("Consolas", 10)).grid(row=0, column=1)
        tk.Button(add_frame, text="Forward",
                  command=lambda: self._add_cmd("forward", float(self.dist_var.get())),
                  font=("Consolas", 9)).grid(row=0, column=2, padx=3)
        tk.Label(add_frame, text="Angle:").grid(row=1, column=0)
        tk.Entry(add_frame, textvariable=self.angle_var, width=6,
                 font=("Consolas", 10)).grid(row=1, column=1)
        tk.Button(add_frame, text="Anticlockwise",
                  command=lambda: self._add_cmd("turn_left", float(self.angle_var.get())),
                  font=("Consolas", 9)).grid(row=1, column=2, padx=3)
        tk.Button(add_frame, text="Clockwise",
                  command=lambda: self._add_cmd("turn_right", float(self.angle_var.get())),
                  font=("Consolas", 9)).grid(row=1, column=3, padx=3)

        turn_frame = tk.Frame(dialog)
        turn_frame.pack(padx=10, pady=2, fill=tk.X)
        tk.Label(turn_frame, text="Quick turns:",
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        for deg in [5, 15, 30, 45]:
            tk.Button(turn_frame, text=f"↶{deg}°",
                      command=lambda d=deg: self._add_cmd("turn_left", d),
                      font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
            tk.Button(turn_frame, text=f"↷{deg}°",
                      command=lambda d=deg: self._add_cmd("turn_right", d),
                      font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)

        tk.Button(add_frame, text="Remove Last", command=self._remove_last,
                  font=("Consolas", 9)).grid(row=2, column=0, columnspan=2, pady=3)
        tk.Button(add_frame, text="Clear All", command=self._clear_all,
                  font=("Consolas", 9)).grid(row=2, column=2, columnspan=2, pady=3)

        self.preview_var = tk.StringVar(value="Add movement commands above")
        self.preview_lbl = tk.Label(dialog, textvariable=self.preview_var,
                                    font=("Consolas", 8), fg="#AAAAAA",
                                    wraplength=500, justify=tk.LEFT)
        self.preview_lbl.pack(padx=10)

        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=5)
        self.confirm_btn = tk.Button(
            btn_row, text="Confirm Move", command=self._confirm,
            bg="#336633", fg="white", font=("Consolas", 10), state=tk.DISABLED)
        self.confirm_btn.pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Cancel", command=self._on_close,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        self.ctx.board.canvas.bind("<MouseWheel>", self._on_scroll)
        self.ctx.board.canvas.bind("<Button-4>", self._on_scroll)
        self.ctx.board.canvas.bind("<Button-5>", self._on_scroll)

    # -------------------------------------------------- aggregate helpers ---

    def _included_ships(self):
        return [s for s in self.members if self.chk_vars[s.id].get()]

    def _agg_max(self):
        ships_in = self._included_ships()
        if not ships_in:
            return 0.0
        speeds = []
        for s in ships_in:
            order = s.special_order
            base = s.effective_speed
            aaf = self.aaf_bonuses.get(s.id, 0)
            already = s.distance_moved_this_turn
            if order == SpecialOrder.ALL_AHEAD_FULL.value:
                speeds.append(max(0.0, base + aaf - already))
            elif order == SpecialOrder.BURN_RETROS.value:
                speeds.append(max(0.0, base // 2 - already))
            else:
                speeds.append(max(0.0, base - already))
        return min(speeds)

    def _agg_min(self):
        ships_in = self._included_ships()
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

    def _update_stats(self):
        ships_in = self._included_ships()
        if not ships_in:
            self.stats_var.set("No ships selected.")
            self.remaining_var.set("")
            return
        speeds, mins = [], []
        for s in ships_in:
            order = s.special_order
            base = s.effective_speed
            aaf = self.aaf_bonuses.get(s.id, 0)
            already = s.distance_moved_this_turn
            if order == SpecialOrder.ALL_AHEAD_FULL.value:
                budget = max(0.0, base + aaf - already)
                sp_min = budget
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
        self.stats_var.set(
            f"Ships: {', '.join(s.name for s in ships_in)}\n"
            f"Speed range: {min_spd:.0f}–{max_spd:.0f}cm  "
            f"Turn: ≤{ta}°  Min-before-turn: {mtd}cm\n"
            f"Orders: {orders_str}")
        self.remaining_var.set(f"Max budget: {max_spd:.0f}cm")
        self.remaining_lbl.config(fg="#44CC44")

    # --------------------------------------------------------- quick buttons -

    def _quick_min(self):
        needed = max(0.0, self._agg_min()
                     - sum(c.value for c in self.commands if c.action == "forward"))
        if needed > 0:
            self._add_cmd("forward", needed)

    def _quick_full(self):
        used = sum(c.value for c in self.commands if c.action == "forward")
        rem = max(0.0, self._agg_max() - used)
        if rem > 0:
            self._add_cmd("forward", rem)

    # --------------------------------------------------------- command list --

    def _add_cmd(self, action, value):
        try:
            value = float(value)
        except ValueError:
            return
        if action in ("turn_left", "turn_right"):
            if value <= 0:
                return
            ships_in = self._included_ships()
            max_ta = min((s.turn_angle for s in ships_in), default=45)
            _SNAP = 15.0
            if value > max_ta:
                if value - max_ta <= _SNAP:
                    value = float(max_ta)
                else:
                    self.preview_var.set(
                        f"Cancelled: {value:.0f}° exceeds max turn of {max_ta:.0f}°")
                    return
        self.commands.append(MoveCommand(action, value))
        self.cmd_listbox.insert(tk.END, str(self.commands[-1]))
        self._validate()

    def _remove_last(self):
        if self.commands:
            self.commands.pop()
            self.cmd_listbox.delete(tk.END)
            self._validate()

    def _clear_all(self):
        self.commands.clear()
        self.cmd_listbox.delete(0, tk.END)
        self._update_stats()
        self.preview_var.set("Add movement commands above")
        self.preview_lbl.config(fg="#AAAAAA")
        self.ctx.board.redraw()

    # ------------------------------------------------------- validation/exec -

    def _validate(self):
        ships_in = self._included_ships()
        if not ships_in:
            self.preview_var.set("No ships selected.")
            self.preview_lbl.config(fg="#FF6644")
            if self.confirm_btn:
                self.confirm_btn.config(state=tk.DISABLED)
            return
        all_valid = True
        errors_out = []
        first_result = None
        for s in ships_in:
            order = s.special_order
            aaf = self.aaf_bonuses.get(s.id, 0)
            res = validate_movement(
                s, self.commands, order, aaf,
                self.ctx.gs.get_blast_markers(),
                self.ctx.gs.table_width, self.ctx.gs.table_height,
                turns_already_used=s.turns_used_this_turn)
            if first_result is None:
                first_result = res
            if not res.valid:
                all_valid = False
                errors_out.append(f"{s.name}: " + "; ".join(res.errors))
        if all_valid and first_result:
            self.preview_var.set(
                f"VALID ({len(ships_in)} ships): "
                f"{first_result.total_distance:.1f}cm, "
                f"{first_result.turns_used} turns, "
                f"end hdg {first_result.final_heading:.0f}°")
            self.preview_lbl.config(fg="#44FF44")
            if self.confirm_btn:
                self.confirm_btn.config(state=tk.NORMAL)
        else:
            self.preview_var.set("ERRORS:\n" + "\n".join(errors_out))
            self.preview_lbl.config(fg="#FF4444")
            if self.confirm_btn:
                self.confirm_btn.config(state=tk.DISABLED)

        self.ctx.board.redraw()
        if first_result and first_result.path:
            for i in range(len(first_result.path) - 1):
                sx0, sy0 = self.ctx.board.cm_to_screen(*first_result.path[i])
                sx1, sy1 = self.ctx.board.cm_to_screen(*first_result.path[i + 1])
                color = "#44FF44" if all_valid else "#FF4444"
                self.ctx.board.canvas.create_line(
                    sx0, sy0, sx1, sy1, fill=color, width=2, dash=(4, 4))

    def _confirm(self):
        ships_in = self._included_ships()
        if not ships_in:
            return
        results = {}
        for s in ships_in:
            order = s.special_order
            aaf = self.aaf_bonuses.get(s.id, 0)
            res = validate_movement(
                s, self.commands, order, aaf,
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
            self.panel._resolve_post_move_terrain(
                s.id, s.special_order == SpecialOrder.ALL_AHEAD_FULL.value)
            final = self.ctx.gs.get_ship_by_id(s.id)
            if final:
                final.distance_moved_this_turn += res.total_distance
                final.turns_used_this_turn += res.turns_used
                left_deg = sum(c.value for c in self.commands
                               if c.action == "turn_left")
                right_deg = sum(c.value for c in self.commands
                                if c.action == "turn_right")
                final.net_rotation_this_turn += (left_deg - right_deg)
                self.ctx.gs.update_ship(final)
            self.ctx.tc.mark_ship_moved(s.id)
            self.ctx.log(
                f"{s.name}: squadron-moved {res.total_distance:.1f}cm "
                f"to ({res.final_x:.1f}, {res.final_y:.1f}) "
                f"hdg {res.final_heading:.0f}°")

        self._on_close()
        self.ctx.board.redraw()

    def _on_close(self):
        self.ctx.board.canvas.unbind("<MouseWheel>")
        self.ctx.board.canvas.unbind("<Button-4>")
        self.ctx.board.canvas.unbind("<Button-5>")
        if self.panel._board_scroll_fn:
            self.ctx.board.canvas.bind("<MouseWheel>", self.panel._board_scroll_fn)
            self.ctx.board.canvas.bind("<Button-4>", self.panel._board_scroll_fn)
            self.ctx.board.canvas.bind("<Button-5>", self.panel._board_scroll_fn)
        self.dialog.destroy()

    def _on_scroll(self, event):
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self._add_cmd("turn_left", 5)
        elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            self._add_cmd("turn_right", 5)


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class MovementDialogMixin:

    def _offer_boarding(self, ship_id: str):
        """Offer boarding declaration if the moved ship is in base contact with enemies."""
        if not self.ctx.gs.rule_boarding:
            return
        ship = self.ctx.gs.get_ship_by_id(ship_id)
        if not ship or ship.has_boarded or ship.is_grappled:
            return
        from .boarding import ships_in_base_contact
        enemies = [s for s in self.ctx.gs.get_ships()
                   if s.player != ship.player
                   and not s.is_destroyed and not s.is_disengaged
                   and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
        contacted = [e for e in enemies if ships_in_base_contact(ship, e)]
        if not contacted:
            return
        target_names = ", ".join(e.name for e in contacted)
        if not messagebox.askyesno(
                "Declare Boarding Action",
                f"{ship.name} is in base contact with {target_names}.\n"
                f"Declare a boarding action?\n"
                f"(Ship cannot fire weapons or launch ordnance this turn)"):
            return
        board_target = (contacted[0] if len(contacted) == 1
                        else self.ctx.pick_ship(contacted, "Select boarding target"))
        if board_target:
            ship.boarding_target_id = board_target.id
            ship.has_boarded = True
            self.ctx.gs.update_ship(ship)
            self.ctx.log(
                f"{ship.name} declares boarding action against {board_target.name}!")

    def _move_ship_dialog(self, preselected_ship=None, initial_commands=None):
        """Open the individual-ship movement dialog."""
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
        _MoveShipDialog(self, ship, initial_commands).run()

    def _move_squadron_dialog(self):
        """Open the squadron movement dialog."""
        from .squadron import get_squadrons

        if self.ctx.gs.current_phase != "movement":
            return

        player = self.ctx.gs.active_player
        unmoved_ids = {s.id for s in self.ctx.tc.get_unmoved_ships()}

        all_squads = get_squadrons(self.ctx.gs, player)
        active_squads = {
            sid: members for sid, members in all_squads.items()
            if any(s.id in unmoved_ids for s in members)
        }
        if not active_squads:
            messagebox.showinfo("No Squadrons",
                                "No squadrons with unmoved ships available.")
            return

        # Pick a squadron (inline sub-dialog if more than one)
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

        # Pre-compute AAF bonuses
        aaf_bonuses: dict = {}
        for s in members:
            if (s.special_order == SpecialOrder.ALL_AHEAD_FULL.value
                    and s.id in unmoved_ids):
                bonus = resolve_aaf_speed(s, self.ctx.dice)
                aaf_bonuses[s.id] = bonus
                self.ctx.log(f"{s.name} AAF speed bonus: +{bonus}cm")

        _MoveSquadronDialog(self, chosen_sid, members, unmoved_ids, aaf_bonuses).run()
