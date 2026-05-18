"""BFG:XR Game Controls Panel - Turn flow, movement input, shooting controls"""
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


from ._movement_mixin  import _MovementMixin
from ._combat_mixin    import _CombatMixin
from ._ordnance_mixin  import _OrdnanceMixin
from ._end_phase_mixin import _EndPhaseMixin


class GamePanel(_MovementMixin, _CombatMixin, _OrdnanceMixin, _EndPhaseMixin):
    """
    Controls panel for running the game turn-by-turn.
    Attaches to an existing Tk frame (the side panel of BoardView).
    """

    def __init__(self, parent_frame: tk.Frame, turn_controller: TurnController,
                 board_view, root: tk.Tk):
        self.parent = parent_frame
        self.tc = turn_controller
        self.gs = turn_controller.gs
        self.dice = turn_controller.dice
        self.board = board_view
        self.root = root

        # Make dice use our root for dialogs
        self.dice.root = root

        # Transient UI state — not persisted
        self._pending_turn: dict = {}     # ship_id → pending net turn degrees (+ = left)
        self._board_scroll_fn = None      # stored board scroll handler for dialog handoff

        self._build_ui()
        self._wire_drag_callbacks()

    def _build_ui(self):
        """Build the game controls UI."""
        # Phase indicator
        self.phase_frame = tk.Frame(self.parent, bg="#1a1a2e")
        self.phase_frame.pack(fill=tk.X, padx=5, pady=3)

        self.turn_label = tk.Label(
            self.phase_frame, text="Turn 1", bg="#1a1a2e", fg="#FFAA00",
            font=("Consolas", 11, "bold"))
        self.turn_label.pack()

        self.phase_label = tk.Label(
            self.phase_frame, text="Setup", bg="#1a1a2e", fg="#88AACC",
            font=("Consolas", 10))
        self.phase_label.pack()

        self.player_label = tk.Label(
            self.phase_frame, text="", bg="#1a1a2e", fg="#CCCCCC",
            font=("Consolas", 9))
        self.player_label.pack()

        # Separator
        tk.Frame(self.parent, bg="#333355", height=2).pack(fill=tk.X, padx=5, pady=3)

        # Action buttons frame
        self.btn_frame = tk.Frame(self.parent, bg="#1a1a2e")
        self.btn_frame.pack(fill=tk.X, padx=5, pady=3)

        # Start game button (shown initially)
        self.start_btn = tk.Button(
            self.btn_frame, text="Start Game", command=self._start_game,
            bg="#336633", fg="white", font=("Consolas", 10, "bold"),
            width=25)
        self.start_btn.pack(pady=3)

        # Phase action buttons (hidden until game starts)
        self.move_btn = tk.Button(
            self.btn_frame, text="Move Ship", command=self._move_ship_dialog,
            bg="#333366", fg="white", font=("Consolas", 9), width=25)

        self.order_btn = tk.Button(
            self.btn_frame, text="Issue Special Order",
            command=self._special_order_dialog,
            bg="#333366", fg="white", font=("Consolas", 9), width=25)

        self.fire_btn = tk.Button(
            self.btn_frame, text="Fire Weapons", command=self._fire_dialog,
            bg="#663333", fg="white", font=("Consolas", 9), width=25)

        self.fire_ord_btn = tk.Button(
            self.btn_frame, text="Fire at Ordnance",
            command=self._fire_at_ordnance_dialog,
            bg="#553344", fg="white", font=("Consolas", 9), width=25)

        self.launch_btn = tk.Button(
            self.btn_frame, text="Launch Ordnance",
            command=self._launch_ordnance_dialog,
            bg="#663333", fg="white", font=("Consolas", 9), width=25)

        self.end_phase_btn = tk.Button(
            self.btn_frame, text="End Phase >>",
            command=self._end_phase,
            bg="#666633", fg="white", font=("Consolas", 9, "bold"), width=25)

        self.undo_btn = tk.Button(
            self.btn_frame, text="Undo Ship Movement",
            command=self._undo_movement,
            bg="#553333", fg="white", font=("Consolas", 9), width=25)

        self.disengage_btn = tk.Button(
            self.btn_frame, text="Attempt Disengage",
            command=self._disengage_dialog,
            bg="#555533", fg="white", font=("Consolas", 9), width=25)

        self.move_missile_btn = tk.Button(
            self.btn_frame, text="Move Tau Missiles",
            command=self._move_tau_missiles_dialog,
            bg="#445544", fg="white", font=("Consolas", 9), width=25)

        self.vp_btn = tk.Button(
            self.btn_frame, text="Victory Points Summary",
            command=self._show_victory_points,
            bg="#334455", fg="white", font=("Consolas", 9), width=25)

        # Settings button — always visible
        self.settings_btn = tk.Button(
            self.parent, text="Settings", command=self._settings_dialog,
            bg="#2a2a44", fg="#aaaacc", font=("Consolas", 8), width=25)
        self.settings_btn.pack(pady=2, padx=5)

        # Log display
        tk.Frame(self.parent, bg="#333355", height=2).pack(fill=tk.X, padx=5, pady=3)
        tk.Label(self.parent, text="Game Log", bg="#1a1a2e", fg="#888888",
                 font=("Consolas", 9)).pack(padx=5)

        self.log_text = tk.Text(
            self.parent, bg="#0a0a1a", fg="#88CC88",
            font=("Consolas", 8), wrap=tk.WORD, height=12,
            state=tk.DISABLED, borderwidth=1, relief=tk.SUNKEN)
        self.log_text.pack(padx=5, pady=3, fill=tk.BOTH, expand=True)

    def _update_phase_display(self):
        """Update the phase/turn indicators."""
        self.turn_label.config(text=f"Turn {self.gs.turn_number}")
        self.phase_label.config(text=f"Phase: {self.gs.current_phase.upper()}")
        pname = self.gs.player1_name if self.gs.active_player == 1 else self.gs.player2_name
        self.player_label.config(text=f"Active: {pname}")

        # Show/hide buttons based on phase
        # First hide all
        for w in (self.move_btn, self.order_btn, self.fire_btn,
                  self.fire_ord_btn, self.launch_btn, self.end_phase_btn,
                  self.undo_btn, self.start_btn, self.disengage_btn,
                  self.move_missile_btn, self.vp_btn):
            w.pack_forget()

        phase = self.gs.current_phase
        if phase == "movement":
            self.order_btn.pack(pady=2)
            self.move_btn.pack(pady=2)
            self.disengage_btn.pack(pady=2)
            self.undo_btn.pack(pady=2)
            self.end_phase_btn.pack(pady=5)
            self.vp_btn.pack(pady=2)
        elif phase == "shooting":
            self.fire_btn.pack(pady=2)
            self.fire_ord_btn.pack(pady=2)
            self.end_phase_btn.pack(pady=5)
            self.vp_btn.pack(pady=2)
        elif phase == "ordnance":
            self.launch_btn.pack(pady=2)
            self.move_missile_btn.pack(pady=2)
            self.end_phase_btn.pack(pady=5)
            self.vp_btn.pack(pady=2)
        elif phase == "end":
            self.end_phase_btn.pack(pady=5)
            self.vp_btn.pack(pady=2)

    def _append_log(self, text: str):
        """Add text to the game log display."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _log_lines(self, lines):
        for line in lines:
            self._append_log(line)

    def _settings_dialog(self):
        """In-game settings dialog — changes take effect immediately."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Game Settings")
        dialog.geometry("480x520")
        dialog.transient(self.root)
        dialog.focus_set()
        dialog.lift()

        tk.Label(dialog, text="Game Settings",
                 font=("Consolas", 12, "bold")).pack(pady=8)
        tk.Label(dialog, text="Changes apply immediately — no need to restart.",
                 font=("Consolas", 8), fg="#888888").pack()

        # Dice mode
        dice_frame = tk.LabelFrame(dialog, text="Dice Mode", font=("Consolas", 9, "bold"),
                                   padx=8, pady=4)
        dice_frame.pack(fill=tk.X, padx=15, pady=6)
        dice_var = tk.StringVar(value=self.gs.dice_mode)
        for label, val in [("Mixed (popup with manual/auto choice)", "mixed"),
                            ("Auto (computer RNG, no prompts)", "auto"),
                            ("Manual (always prompt for each die)", "manual")]:
            tk.Radiobutton(dice_frame, text=label, variable=dice_var, value=val,
                           font=("Consolas", 8)).pack(anchor=tk.W)
        tk.Label(dice_frame,
                 text="Mixed: each roll shows a popup — enter dice manually or click Auto-Roll.\n"
                      "      Both per-die entry and number-of-successes shortcut are always available.",
                 font=("Consolas", 7), fg="#888888", justify=tk.LEFT).pack(anchor=tk.W)

        # Movement enforcement
        move_frame = tk.LabelFrame(dialog, text="Movement", font=("Consolas", 9, "bold"),
                                   padx=8, pady=4)
        move_frame.pack(fill=tk.X, padx=15, pady=4)
        pass_var = tk.BooleanVar(value=self.gs.allow_movement_pass)
        tk.Checkbutton(move_frame,
                       text="Allow movement pass (skip moving ships without penalty)",
                       variable=pass_var, font=("Consolas", 8)).pack(anchor=tk.W)

        # Optional rules
        rules_frame = tk.LabelFrame(dialog, text="Optional Rules", font=("Consolas", 9, "bold"),
                                    padx=8, pady=4)
        rules_frame.pack(fill=tk.X, padx=15, pady=4)

        rule_defs = [
            ("rule_fighting_sunward",          "Fighting Sunward (double range shifts)"),
            ("rule_solar_flares",              "Solar Flares"),
            ("rule_radiation_bursts",          "Radiation Bursts"),
            ("rule_boarding",                  "Boarding Actions"),
            ("rule_ramming",                   "Ramming"),
            ("rule_teleport",                  "Teleport Attacks (not Tau)"),
            ("rule_hit_and_run",               "Hit and Run Raids"),
            ("rule_turret_suppression_remastered",
             "Turret Suppression: Remastered mode\n"
             "  (default XR: fighters suppress to 3 fixed attacks)"),
        ]
        rule_vars = {}
        for attr, label in rule_defs:
            var = tk.BooleanVar(value=getattr(self.gs, attr))
            rule_vars[attr] = var
            tk.Checkbutton(rules_frame, text=label, variable=var,
                           font=("Consolas", 8), justify=tk.LEFT).pack(anchor=tk.W)

        # Contact margin (advanced)
        adv_frame = tk.LabelFrame(dialog, text="Advanced", font=("Consolas", 9, "bold"),
                                  padx=8, pady=4)
        adv_frame.pack(fill=tk.X, padx=15, pady=4)
        margin_row = tk.Frame(adv_frame)
        margin_row.pack(fill=tk.X)
        tk.Label(margin_row, text="Contact margin (cm):", font=("Consolas", 8)).pack(side=tk.LEFT)
        margin_var = tk.StringVar(value=str(self.gs.contact_margin_cm))
        tk.Entry(margin_row, textvariable=margin_var, width=6,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
        tk.Label(margin_row, text="(wiggle room for contact distance checks)",
                 font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)

        def on_apply():
            self.gs.dice_mode = dice_var.get()
            self.dice.mode = dice_var.get()

            self.gs.allow_movement_pass = pass_var.get()

            for attr, var in rule_vars.items():
                setattr(self.gs, attr, var.get())

            try:
                self.gs.contact_margin_cm = float(margin_var.get())
            except ValueError:
                pass

            dialog.destroy()
            self._append_log("[Settings] Updated game settings.")

        def on_cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Apply", command=on_apply,
                  bg="#336633", fg="white", font=("Consolas", 10, "bold"),
                  width=12).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="Cancel", command=on_cancel,
                  font=("Consolas", 10), width=12).pack(side=tk.LEFT, padx=8)

        dialog.bind("<Escape>", lambda e: on_cancel())
        self.root.wait_window(dialog)

    def _start_game(self):
        self.tc.start_game()
        self.tc.begin_phase("movement")
        self._process_movement_phase_start()
        self._update_phase_display()
        self._append_log(f"=== GAME START ===")
        self._append_log(f"Turn 1 - {self.gs.player1_name}")
        self._append_log(f"Movement Phase")
        self._append_log(
            "Keys: M=min-move selected  Space=min-move all  "
            "BackSpace=undo all movement  Scroll=pending turn  Esc=cancel")
        self.board.canvas.focus_set()
        self.board.redraw()

    def _resolve_end_phase_interactive(self):
        """Run end phase with interactive repair choices."""
        from .end_phase import (resolve_fire_damage, get_repair_info,
                                 apply_repair_choices, remove_blast_markers,
                                 remove_brace_orders)

        self._append_log("=== END PHASE ===")

        # 0. Teleport attacks (must resolve before damage control or blast removal)
        self._resolve_teleport_attacks()

        # 1. Fire damage
        for s_dict in self.gs.ships:
            ship = Ship.from_dict(s_dict)
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            fire_logs = resolve_fire_damage(ship, self.dice, self.gs)
            self._log_lines(fire_logs)
            if ship.hits_remaining <= 0:
                self._check_destruction(ship)

        # 2. Damage control with player choice
        for s_dict in list(self.gs.ships):
            ship = Ship.from_dict(s_dict)
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue

            info = get_repair_info(ship, self.dice, self.gs)
            if info["sixes"] > 0 and info["repairable"]:
                repairs_available = min(info["sixes"], len(info["repairable"]))

                touch_msg = (f" (halved, {info['touching_blast']} blast markers)"
                            if info.get("touching_blast", 0) > 0 else "")
                self._append_log(
                    f"{ship.name}: {info['num_dice']} dice{touch_msg}, "
                    f"{info['sixes']} repair(s) available!")

                # Show repair choice dialog
                choices = self._repair_choice_dialog(
                    ship, info["repairable"], repairs_available)
                if choices:
                    repair_logs = apply_repair_choices(ship, choices, self.gs)
                    self._log_lines(repair_logs)
                else:
                    self._append_log(f"  {ship.name}: no repairs applied")
            elif info["num_dice"] > 0:
                self._append_log(
                    f"{ship.name}: {info['num_dice']} dice, no 6s rolled")

        # 3. Remove blast markers
        bm_logs = remove_blast_markers(self.gs, self.dice)
        self._log_lines(bm_logs)

        # 4. Remove expired brace orders
        brace_logs = remove_brace_orders(self.gs)
        self._log_lines(brace_logs)

        self.board.redraw()

    def _end_phase(self):
        phase = self.gs.current_phase

        # Movement phase: enforce minimum move obligation
        if phase == "movement":
            unmoved = self.tc.get_unmoved_ships()
            # Burn Retros ships are exempt (their minimum speed is 0)
            unmoved_obligated = [
                s for s in unmoved
                if not s.is_destroyed
                and s.special_order != SpecialOrder.BURN_RETROS.value
            ]
            if unmoved_obligated:
                names = "\n  ".join(s.name for s in unmoved_obligated[:8])
                if not self.gs.allow_movement_pass:
                    # Strict mode: hard block, no override
                    messagebox.showerror(
                        "Ships Must Move",
                        f"These ships have not moved:\n  {names}\n\n"
                        f"All ships must move before ending the movement phase.\n"
                        f"Use Burn Retros to remain stationary.")
                    return
                else:
                    # Permissive mode: warn but allow override
                    override = messagebox.askyesno(
                        "Ships Haven't Moved",
                        f"These ships haven't moved:\n  {names}\n\n"
                        f"All ships should move before ending movement.\n"
                        f"Use Burn Retros to remain stationary.\n\n"
                        f"OVERRIDE and end phase anyway?",
                        icon="warning")
                    if not override:
                        return

        # Run ordnance phase movement if we're ending ordnance phase
        if phase == "ordnance":
            self._resolve_ordnance_movement()

        # Shooting phase: warn about unfired weapons
        if phase == "shooting":
            unfired_warnings = []
            for s_dict in self.gs.ships:
                if s_dict["player"] != self.gs.active_player:
                    continue
                s = Ship.from_dict(s_dict)
                if s.is_destroyed or s.is_disengaged:
                    continue
                unfired = []
                for i, w in enumerate(s.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay", "gravitic_launcher"):
                        continue
                    if self._weapon_disabled_by_crit(s, w):
                        continue
                    if i not in s.weapons_fired_indices:
                        unfired.append(w["name"])
                if unfired:
                    unfired_warnings.append(f"{s.name}: {', '.join(unfired)}")
            if unfired_warnings:
                msg = "\n".join(unfired_warnings[:6])
                messagebox.showwarning("Unfired Weapons",
                    f"These weapons haven't fired:\n{msg}\n\n"
                    f"End shooting phase anyway?")

        # Run end phase logic if this is the end phase
        if phase == "end":
            self._resolve_end_phase_interactive()

        # Save and advance
        self.tc.end_phase()
        self.tc.advance_phase()

        # Process start-of-movement-phase events
        if self.gs.current_phase == "movement":
            self._process_movement_phase_start()
            self._append_log(
                "Keys: M=min-move selected  Space=min-move all  "
                "BackSpace=undo all  Scroll=pending turn  Esc=cancel")
            self.board.canvas.focus_set()

        # Reset per-ordnance-phase missile movement flags
        if self.gs.current_phase == "ordnance":
            for i, o_dict in enumerate(self.gs.ordnance):
                if o_dict.get("moved_this_phase"):
                    self.gs.ordnance[i] = {**o_dict, "moved_this_phase": False}

        self._update_phase_display()
        self._append_log(f"--- {self.gs.current_phase.upper()} PHASE ---")
        self.board.redraw()

    # --- Movement ---

    def _check_destruction(self, ship: Ship):
        """Handle ship destruction - escorts become blast markers, capitals roll catastrophic."""
        ship = self.gs.get_ship_by_id(ship.id)
        if not ship or ship.hits_remaining > 0:
            return

        from .combat import resolve_catastrophic
        result = resolve_catastrophic(ship, self.dice, self.gs)
        self._append_log(f"  {ship.name}: {result}")
        self.board.redraw()

    def _disengage_dialog(self):
        """Dialog to attempt voluntary disengagement."""
        from .disengage import attempt_disengage, get_disengage_ld_modifiers

        # Get active player ships that haven't moved yet and are still active
        candidates = [Ship.from_dict(s) for s in self.gs.ships
                      if s["player"] == self.gs.active_player
                      and s.get("status", "active") == "active"
                      and not Ship.from_dict(s).is_destroyed
                      and not s.get("is_disengaged", False)]
        if not candidates:
            messagebox.showinfo("No Ships", "No ships available to disengage")
            return

        ship = self._pick_ship_dialog(candidates, "Select ship to disengage")
        if not ship:
            return

        # Show modifiers before rolling
        ld_info = get_disengage_ld_modifiers(ship, self.gs)
        mod_text = "\n".join(ld_info["modifiers"]) if ld_info["modifiers"] else "No modifiers"
        confirm = messagebox.askyesno(
            "Disengage Attempt",
            f"{ship.name} attempts to disengage.\n\n"
            f"Base Ld: {ld_info['base_ld']}\n"
            f"{mod_text}\n"
            f"Effective Ld: {ld_info['effective_ld']}\n"
            f"Need: 2D6 <= {ld_info['effective_ld']}\n\n"
            f"If FAILED: no firing or orders this turn.\n"
            f"Proceed?")
        if not confirm:
            return

        result = attempt_disengage(ship, self.dice, self.gs)
        if result["success"]:
            self._append_log(
                f"{ship.name} DISENGAGED (rolled {result['roll']} "
                f"vs Ld {result['needed']})")
            messagebox.showinfo("Disengaged",
                f"{ship.name} has disengaged from battle!\n"
                f"Rolled {result['roll']} vs Ld {result['needed']}")
        else:
            # Offer fleet re-roll
            rerolls = self.tc.get_fleet_rerolls(ship.player)
            used_reroll = False
            if rerolls > 0:
                use_rr = messagebox.askyesno(
                    "Disengage Failed - Re-roll?",
                    f"{ship.name} disengage FAILED\n"
                    f"Rolled {result['roll']} vs Ld {result['needed']}\n\n"
                    f"Fleet commander has {rerolls} re-roll(s).\n"
                    f"Use a re-roll?")
                if use_rr:
                    from .disengage import attempt_disengage as _rr_disengage
                    # Undo the failed state
                    ship.disengage_failed_this_turn = False
                    ship.has_fired = False
                    self.gs.update_ship(ship)
                    self.tc.use_fleet_reroll(ship.player)
                    rr_result = _rr_disengage(ship, self.dice, self.gs)
                    used_reroll = True
                    if rr_result["success"]:
                        self._append_log(
                            f"{ship.name} RE-ROLL DISENGAGED "
                            f"(rolled {rr_result['roll']} vs Ld {rr_result['needed']})")
                        messagebox.showinfo("Re-roll: Disengaged!",
                            f"{ship.name} disengaged on re-roll!\n"
                            f"Rolled {rr_result['roll']} vs Ld {rr_result['needed']}")
                    else:
                        self._append_log(
                            f"{ship.name} RE-ROLL disengage FAILED "
                            f"(rolled {rr_result['roll']} vs Ld {rr_result['needed']})")

            if not used_reroll or (used_reroll and not rr_result.get("success")):
                self._append_log(
                    f"{ship.name} disengage FAILED. No firing this turn!")
                if not used_reroll:
                    messagebox.showwarning("Disengage Failed",
                        f"{ship.name} failed to disengage.\n"
                        f"Rolled {result['roll']} vs Ld {result['needed']}\n\n"
                        f"No firing or orders this turn.")

        self.board.redraw()

    # --- Victory Points ---

    def _show_victory_points(self):
        """Show current victory points summary."""
        from .victory_points import calculate_victory_points, format_vp_summary
        vp = calculate_victory_points(self.gs)
        summary = format_vp_summary(vp, self.gs)
        messagebox.showinfo("Victory Points", summary)

    # --- Helpers ---

    def _pick_ship_dialog(self, ships: list, title: str) -> Optional[Ship]:
        """Show a dialog to pick a ship from a list."""
        if len(ships) == 1:
            return ships[0]

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("350x400")
        dialog.transient(self.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=title,
                 font=("Consolas", 10, "bold")).pack(pady=5)

        selected = [None]  # mutable container for closure
        listbox = tk.Listbox(dialog, font=("Consolas", 9), height=15)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for s in ships:
            status = ""
            if s.is_crippled:
                status = " [CRIPPLED]"
            order = f" ({s.special_order})" if s.special_order != "none" else ""
            listbox.insert(tk.END,
                          f"{s.name} ({s.ship_class}){status}{order}")

        def on_select():
            sel = listbox.curselection()
            if sel:
                selected[0] = ships[sel[0]]
            dialog.destroy()

        def on_double(event):
            on_select()

        listbox.bind("<Double-Button-1>", on_double)
        tk.Button(dialog, text="Select", command=on_select,
                  font=("Consolas", 10)).pack(pady=5)

        self.root.wait_window(dialog)
        return selected[0]

