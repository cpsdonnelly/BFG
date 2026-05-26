"""BFG:XR Game Controls Panel — thin coordinator using composition."""
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from .models import Ship, SpecialOrder
from .turn_controller import TurnController
from .game_context import GameContext
from .movement_panel import MovementPanel
from .combat_panel import CombatPanel
from .ordnance_panel import OrdnancePanel
from .end_phase_panel import EndPhasePanel


class GamePanel:
    """
    Controls panel for running the game turn-by-turn.
    Attaches to an existing Tk frame (the side panel of BoardView).
    Delegates all phase logic to composed panel objects sharing a GameContext.
    """

    def __init__(self, parent_frame: tk.Frame, turn_controller: TurnController,
                 board_view, root: tk.Tk):
        self.parent = parent_frame
        self.root = root

        # Build log widget first — GameContext needs a reference to it
        self._build_log_widget()

        # Compose shared context and panels
        tc = turn_controller
        gs = turn_controller.gs
        dice = turn_controller.dice
        dice.root = root

        self.ctx = GameContext(tc=tc, gs=gs, dice=dice,
                               board=board_view, root=root,
                               log_widget=self.log_text)

        self.movement  = MovementPanel(self.ctx)
        self.combat    = CombatPanel(self.ctx)
        self.ordnance  = OrdnancePanel(self.ctx)
        self.end_phase = EndPhasePanel(self.ctx)

        # Wire cross-panel references into context
        self.ctx.movement = self.movement
        self.ctx.ordnance = self.ordnance

        # Build the rest of the UI and wire drag callbacks
        self._build_ui()
        self.movement.wire_drag_callbacks()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_log_widget(self):
        """Build the log text widget (needed before GameContext is created)."""
        self.log_text = tk.Text(
            self.parent, bg="#0a0a1a", fg="#88CC88",
            font=("Consolas", 8), wrap=tk.WORD, height=12,
            state=tk.DISABLED, borderwidth=1, relief=tk.SUNKEN)
        # Packed later in _build_ui; stored here so GameContext can use it

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

        self.start_btn = tk.Button(
            self.btn_frame, text="Start Game", command=self._start_game,
            bg="#336633", fg="white", font=("Consolas", 10, "bold"), width=25)
        self.start_btn.pack(pady=3)

        self.move_btn = tk.Button(
            self.btn_frame, text="Move Ship",
            command=self.movement._move_ship_dialog,
            bg="#333366", fg="white", font=("Consolas", 9), width=25)

        self.move_squad_btn = tk.Button(
            self.btn_frame, text="Move Squadron",
            command=self.movement._move_squadron_dialog,
            bg="#334466", fg="white", font=("Consolas", 9), width=25)

        self.order_btn = tk.Button(
            self.btn_frame, text="Issue Special Order",
            command=self.movement._special_order_dialog,
            bg="#333366", fg="white", font=("Consolas", 9), width=25)

        self.fire_btn = tk.Button(
            self.btn_frame, text="Fire Weapons",
            command=self.combat._fire_dialog,
            bg="#663333", fg="white", font=("Consolas", 9), width=25)

        self.combine_fire_btn = tk.Button(
            self.btn_frame, text="Combine Squadron Fire",
            command=self.combat._combine_squadron_fire_dialog,
            bg="#663344", fg="white", font=("Consolas", 9), width=25)

        self.target_squad_btn = tk.Button(
            self.btn_frame, text="Fire at Enemy Squadron",
            command=self.combat._squadron_target_dialog,
            bg="#663355", fg="white", font=("Consolas", 9), width=25)

        self.fire_ord_btn = tk.Button(
            self.btn_frame, text="Fire at Ordnance",
            command=self.combat._fire_at_ordnance_dialog,
            bg="#553344", fg="white", font=("Consolas", 9), width=25)

        self.launch_btn = tk.Button(
            self.btn_frame, text="Launch Ordnance",
            command=self.ordnance._launch_ordnance_dialog,
            bg="#663333", fg="white", font=("Consolas", 9), width=25)

        self.end_phase_btn = tk.Button(
            self.btn_frame, text="End Phase >>",
            command=self._end_phase,
            bg="#666633", fg="white", font=("Consolas", 9, "bold"), width=25)

        self.undo_btn = tk.Button(
            self.btn_frame, text="Undo Ship Movement",
            command=self.movement._undo_movement,
            bg="#553333", fg="white", font=("Consolas", 9), width=25)

        self.disengage_btn = tk.Button(
            self.btn_frame, text="Attempt Disengage",
            command=self._disengage_dialog,
            bg="#555533", fg="white", font=("Consolas", 9), width=25)

        self.move_missile_btn = tk.Button(
            self.btn_frame, text="Move Tau Missiles",
            command=self.ordnance._move_tau_missiles_dialog,
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
        self.log_text.pack(padx=5, pady=3, fill=tk.BOTH, expand=True)

    def _update_phase_display(self):
        """Update the phase/turn indicators and show the correct buttons."""
        gs = self.ctx.gs
        self.turn_label.config(text=f"Turn {gs.turn_number}")
        self.phase_label.config(text=f"Phase: {gs.current_phase.upper()}")
        pname = gs.player1_name if gs.active_player == 1 else gs.player2_name
        self.player_label.config(text=f"Active: {pname}")

        for w in (self.move_btn, self.move_squad_btn, self.order_btn, self.fire_btn,
                  self.combine_fire_btn, self.target_squad_btn, self.fire_ord_btn,
                  self.launch_btn, self.end_phase_btn, self.undo_btn, self.start_btn,
                  self.disengage_btn, self.move_missile_btn, self.vp_btn):
            w.pack_forget()

        phase = gs.current_phase
        if phase == "movement":
            self.order_btn.pack(pady=2)
            self.move_btn.pack(pady=2)
            self.move_squad_btn.pack(pady=2)
            self.disengage_btn.pack(pady=2)
            self.undo_btn.pack(pady=2)
            self.end_phase_btn.pack(pady=5)
            self.vp_btn.pack(pady=2)
        elif phase == "shooting":
            self.fire_btn.pack(pady=2)
            self.combine_fire_btn.pack(pady=2)
            self.target_squad_btn.pack(pady=2)
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

    # ── Settings dialog ───────────────────────────────────────────────────────

    def _settings_dialog(self):
        """In-game settings dialog — changes take effect immediately."""
        gs = self.ctx.gs
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

        dice_frame = tk.LabelFrame(dialog, text="Dice Mode", font=("Consolas", 9, "bold"),
                                   padx=8, pady=4)
        dice_frame.pack(fill=tk.X, padx=15, pady=6)
        dice_var = tk.StringVar(value=gs.dice_mode)
        for label, val in [("Mixed (popup with manual/auto choice)", "mixed"),
                            ("Auto (computer RNG, no prompts)", "auto"),
                            ("Manual (always prompt for each die)", "manual")]:
            tk.Radiobutton(dice_frame, text=label, variable=dice_var, value=val,
                           font=("Consolas", 8)).pack(anchor=tk.W)
        tk.Label(dice_frame,
                 text="Mixed: each roll shows a popup — enter dice manually or click Auto-Roll.\n"
                      "      Both per-die entry and number-of-successes shortcut are always available.",
                 font=("Consolas", 7), fg="#888888", justify=tk.LEFT).pack(anchor=tk.W)

        move_frame = tk.LabelFrame(dialog, text="Movement", font=("Consolas", 9, "bold"),
                                   padx=8, pady=4)
        move_frame.pack(fill=tk.X, padx=15, pady=4)
        pass_var = tk.BooleanVar(value=gs.allow_movement_pass)
        tk.Checkbutton(move_frame,
                       text="Allow movement pass (skip moving ships without penalty)",
                       variable=pass_var, font=("Consolas", 8)).pack(anchor=tk.W)

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
            var = tk.BooleanVar(value=getattr(gs, attr))
            rule_vars[attr] = var
            tk.Checkbutton(rules_frame, text=label, variable=var,
                           font=("Consolas", 8), justify=tk.LEFT).pack(anchor=tk.W)

        adv_frame = tk.LabelFrame(dialog, text="Advanced", font=("Consolas", 9, "bold"),
                                  padx=8, pady=4)
        adv_frame.pack(fill=tk.X, padx=15, pady=4)
        margin_row = tk.Frame(adv_frame)
        margin_row.pack(fill=tk.X)
        tk.Label(margin_row, text="Contact margin (cm):", font=("Consolas", 8)).pack(side=tk.LEFT)
        margin_var = tk.StringVar(value=str(gs.contact_margin_cm))
        tk.Entry(margin_row, textvariable=margin_var, width=6,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
        tk.Label(margin_row, text="(wiggle room for contact distance checks)",
                 font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)

        def on_apply():
            gs.dice_mode = dice_var.get()
            self.ctx.dice.mode = dice_var.get()
            gs.allow_movement_pass = pass_var.get()
            for attr, var in rule_vars.items():
                setattr(gs, attr, var.get())
            try:
                gs.contact_margin_cm = float(margin_var.get())
            except ValueError:
                pass
            dialog.destroy()
            self.ctx.log("[Settings] Updated game settings.")

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

    # ── Game flow ─────────────────────────────────────────────────────────────

    def _start_game(self):
        """Launch the deployment phase, then begin Turn 1 Movement."""
        self.start_btn.config(state=tk.DISABLED)
        from .deployment_panel import DeploymentPanel
        DeploymentPanel(
            parent_frame=self.parent,
            board_view=self.ctx.board,
            gs=self.ctx.gs,
            root=self.root,
            on_complete=self._begin_turn1,
            mode="sequential",
        )

    def _begin_turn1(self):
        """Called by DeploymentPanel when all ships are placed."""
        tc = self.ctx.tc
        gs = self.ctx.gs
        tc.start_game()
        tc.begin_phase("movement")
        self.movement._process_movement_phase_start()
        self._update_phase_display()
        self.ctx.log("=== GAME START ===")
        self.ctx.log(f"Turn 1 - {gs.player1_name}")
        self.ctx.log("Movement Phase")
        self.ctx.log(
            "Keys: M=min-move selected  Space=min-move all  "
            "BackSpace=undo all movement  Scroll=pending turn  Esc=cancel")
        self.ctx.board.canvas.focus_set()
        self.ctx.board.redraw()

    def _resolve_end_phase_interactive(self):
        """Run end phase with interactive repair choices."""
        from .end_phase import (resolve_fire_damage, get_repair_info,
                                 apply_repair_choices, remove_blast_markers,
                                 remove_brace_orders)
        gs = self.ctx.gs

        self.ctx.log("=== END PHASE ===")

        # 0a. Boarding actions (before teleport, before damage control)
        self.end_phase._resolve_boarding_actions()

        # 0b. Teleport attacks
        self.end_phase._resolve_teleport_attacks()

        # 1. Fire damage
        for s_dict in gs.ships:
            ship = Ship.from_dict(s_dict)
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            fire_logs = resolve_fire_damage(ship, self.ctx.dice, gs)
            self.ctx.log_lines(fire_logs)
            if ship.hits_remaining <= 0:
                self.ctx.check_destruction(ship)

        # 2. Damage control with player choice
        for s_dict in list(gs.ships):
            ship = Ship.from_dict(s_dict)
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue

            info = get_repair_info(ship, self.ctx.dice, gs)
            if info["sixes"] > 0 and info["repairable"]:
                repairs_available = min(info["sixes"], len(info["repairable"]))
                touch_msg = (f" (halved, {info['touching_blast']} blast markers)"
                             if info.get("touching_blast", 0) > 0 else "")
                self.ctx.log(
                    f"{ship.name}: {info['num_dice']} dice{touch_msg}, "
                    f"{info['sixes']} repair(s) available!")
                choices = self.end_phase._repair_choice_dialog(
                    ship, info["repairable"], repairs_available)
                if choices:
                    repair_logs = apply_repair_choices(ship, choices, gs)
                    self.ctx.log_lines(repair_logs)
                else:
                    self.ctx.log(f"  {ship.name}: no repairs applied")
            elif info["num_dice"] > 0:
                self.ctx.log(f"{ship.name}: {info['num_dice']} dice, no 6s rolled")

        # 3. Remove blast markers
        bm_logs = remove_blast_markers(gs, self.ctx.dice)
        self.ctx.log_lines(bm_logs)

        # 4. Remove expired brace orders
        brace_logs = remove_brace_orders(gs)
        self.ctx.log_lines(brace_logs)

        self.ctx.board.redraw()

    def _end_phase(self):
        gs = self.ctx.gs
        tc = self.ctx.tc
        phase = gs.current_phase

        if phase == "movement":
            unmoved = tc.get_unmoved_ships()
            unmoved_obligated = [
                s for s in unmoved
                if not s.is_destroyed
                and s.special_order != SpecialOrder.BURN_RETROS.value
            ]
            if unmoved_obligated:
                names = "\n  ".join(s.name for s in unmoved_obligated[:8])
                if not gs.allow_movement_pass:
                    messagebox.showerror(
                        "Ships Must Move",
                        f"These ships have not moved:\n  {names}\n\n"
                        f"All ships must move before ending the movement phase.\n"
                        f"Use Burn Retros to remain stationary.")
                    return
                else:
                    override = messagebox.askyesno(
                        "Ships Haven't Moved",
                        f"These ships haven't moved:\n  {names}\n\n"
                        f"All ships should move before ending movement.\n"
                        f"Use Burn Retros to remain stationary.\n\n"
                        f"OVERRIDE and end phase anyway?",
                        icon="warning")
                    if not override:
                        return

        if phase == "ordnance":
            self.ordnance._resolve_ordnance_movement()

        if phase == "shooting":
            unfired_warnings = []
            for s_dict in gs.ships:
                if s_dict["player"] != gs.active_player:
                    continue
                s = Ship.from_dict(s_dict)
                if s.is_destroyed or s.is_disengaged:
                    continue
                unfired = []
                for i, w in enumerate(s.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay", "gravitic_launcher"):
                        continue
                    if self.combat._weapon_disabled_by_crit(s, w):
                        continue
                    if i not in s.weapons_fired_indices:
                        unfired.append(w["name"])
                if unfired:
                    unfired_warnings.append(f"{s.name}: {', '.join(unfired)}")
            if unfired_warnings:
                msg = "\n".join(unfired_warnings[:6])
                messagebox.showwarning("Unfired Weapons",
                    f"These weapons haven't fired:\n{msg}\n\nEnd shooting phase anyway?")

        if phase == "end":
            self._resolve_end_phase_interactive()

        tc.end_phase()
        tc.advance_phase()

        if gs.current_phase == "movement":
            self.movement._process_movement_phase_start()
            self.ctx.log(
                "Keys: M=min-move selected  Space=min-move all  "
                "BackSpace=undo all  Scroll=pending turn  Esc=cancel")
            self.ctx.board.canvas.focus_set()

        if gs.current_phase == "ordnance":
            for i, o_dict in enumerate(gs.ordnance):
                if o_dict.get("moved_this_phase"):
                    gs.ordnance[i] = {**o_dict, "moved_this_phase": False}

        self._update_phase_display()
        self.ctx.log(f"--- {gs.current_phase.upper()} PHASE ---")
        self.ctx.board.redraw()

    # ── Disengagement ─────────────────────────────────────────────────────────

    def _disengage_dialog(self):
        """Dialog to attempt voluntary disengagement."""
        from .disengage import attempt_disengage, get_disengage_ld_modifiers
        gs = self.ctx.gs

        candidates = [Ship.from_dict(s) for s in gs.ships
                      if s["player"] == gs.active_player
                      and s.get("status", "active") == "active"
                      and not Ship.from_dict(s).is_destroyed
                      and not s.get("is_disengaged", False)]
        if not candidates:
            messagebox.showinfo("No Ships", "No ships available to disengage")
            return

        ship = self.ctx.pick_ship(candidates, "Select ship to disengage")
        if not ship:
            return

        ld_info = get_disengage_ld_modifiers(ship, gs)
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

        result = attempt_disengage(ship, self.ctx.dice, gs)
        if result["success"]:
            self.ctx.log(
                f"{ship.name} DISENGAGED (rolled {result['roll']} "
                f"vs Ld {result['needed']})")
            messagebox.showinfo("Disengaged",
                f"{ship.name} has disengaged from battle!\n"
                f"Rolled {result['roll']} vs Ld {result['needed']}")
        else:
            rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
            used_reroll = False
            rr_result = {}
            if rerolls > 0:
                use_rr = messagebox.askyesno(
                    "Disengage Failed - Re-roll?",
                    f"{ship.name} disengage FAILED\n"
                    f"Rolled {result['roll']} vs Ld {result['needed']}\n\n"
                    f"Fleet commander has {rerolls} re-roll(s).\n"
                    f"Use a re-roll?")
                if use_rr:
                    from .disengage import attempt_disengage as _rr_disengage
                    ship.disengage_failed_this_turn = False
                    ship.has_fired = False
                    gs.update_ship(ship)
                    self.ctx.tc.use_fleet_reroll(ship.player)
                    rr_result = _rr_disengage(ship, self.ctx.dice, gs)
                    used_reroll = True
                    if rr_result["success"]:
                        self.ctx.log(
                            f"{ship.name} RE-ROLL DISENGAGED "
                            f"(rolled {rr_result['roll']} vs Ld {rr_result['needed']})")
                        messagebox.showinfo("Re-roll: Disengaged!",
                            f"{ship.name} disengaged on re-roll!\n"
                            f"Rolled {rr_result['roll']} vs Ld {rr_result['needed']}")
                    else:
                        self.ctx.log(
                            f"{ship.name} RE-ROLL disengage FAILED "
                            f"(rolled {rr_result['roll']} vs Ld {rr_result['needed']})")

            if not used_reroll or (used_reroll and not rr_result.get("success")):
                self.ctx.log(f"{ship.name} disengage FAILED. No firing this turn!")
                if not used_reroll:
                    messagebox.showwarning("Disengage Failed",
                        f"{ship.name} failed to disengage.\n"
                        f"Rolled {result['roll']} vs Ld {result['needed']}\n\n"
                        f"No firing or orders this turn.")

        self.ctx.board.redraw()

    # ── Victory Points ────────────────────────────────────────────────────────

    def _show_victory_points(self):
        from .victory_points import calculate_victory_points, format_vp_summary
        vp = calculate_victory_points(self.ctx.gs)
        summary = format_vp_summary(vp, self.ctx.gs)
        messagebox.showinfo("Victory Points", summary)
