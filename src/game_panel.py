"""BFG:XR Game Controls Panel — thin coordinator using composition."""
import os
import tkinter as tk
from tkinter import messagebox, ttk

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

        self.combine_ord_btn = tk.Button(
            self.btn_frame, text="Combine Ordnance Launch",
            command=self.ordnance._combine_ordnance_dialog,
            bg="#664422", fg="white", font=("Consolas", 9), width=25)

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

        # Save / Load / Export row — always visible
        sl_frame = tk.Frame(self.parent, bg="#1a1a2e")
        sl_frame.pack(pady=2, padx=5, fill=tk.X)
        tk.Button(sl_frame, text="Save Game", command=self._save_game,
                  bg="#2a3d2a", fg="#aaccaa", font=("Consolas", 8),
                  width=10).pack(side=tk.LEFT, padx=1)
        tk.Button(sl_frame, text="Load Game", command=self._load_game,
                  bg="#2a2a3d", fg="#aaaacc", font=("Consolas", 8),
                  width=10).pack(side=tk.LEFT, padx=1)
        tk.Button(sl_frame, text="Export .bfg", command=self._export_match,
                  bg="#28283a", fg="#9999bb", font=("Consolas", 8),
                  width=10).pack(side=tk.LEFT, padx=1)
        tk.Button(sl_frame, text="Export Map", command=self._export_map,
                  bg="#283038", fg="#99aabb", font=("Consolas", 8),
                  width=10).pack(side=tk.LEFT, padx=1)
        # LAN multiplayer row
        mp_frame = tk.Frame(self.parent, bg="#1a1a2e")
        mp_frame.pack(pady=1, padx=5, fill=tk.X)
        tk.Button(mp_frame, text="Host LAN Game", command=self._show_host_dialog,
                  bg="#2a3344", fg="#99aacc", font=("Consolas", 8),
                  width=14).pack(side=tk.LEFT, padx=1)
        tk.Button(mp_frame, text="Join LAN Game", command=self._show_join_dialog,
                  bg="#2a3344", fg="#99aacc", font=("Consolas", 8),
                  width=14).pack(side=tk.LEFT, padx=1)

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
                  self.launch_btn, self.combine_ord_btn, self.end_phase_btn,
                  self.undo_btn, self.start_btn, self.disengage_btn,
                  self.move_missile_btn, self.vp_btn):
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
            self.combine_ord_btn.pack(pady=2)
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
        dialog.geometry("520x780")
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

        camp_frame = tk.LabelFrame(dialog, text="Campaign / Scenario", font=("Consolas", 9, "bold"),
                                   padx=8, pady=4)
        camp_frame.pack(fill=tk.X, padx=15, pady=4)

        # ── Scenario mode ────────────────────────────────────────────────────
        locked = gs.turn_number > 1
        mode_row = tk.Frame(camp_frame)
        mode_row.pack(fill=tk.X, pady=2)
        tk.Label(mode_row, text="Scenario:", font=("Consolas", 8), width=14,
                 anchor=tk.W).pack(side=tk.LEFT)
        scen_modes = ["standard", "kill_admiral", "destroy_ship",
                      "protect_ship", "capture_artefact"]
        scen_var = tk.StringVar(value=gs.scenario_mode)
        scen_cb = ttk.Combobox(mode_row, textvariable=scen_var, values=scen_modes,
                                state="disabled" if locked else "readonly", width=22,
                                font=("Consolas", 8))
        scen_cb.pack(side=tk.LEFT)
        if locked:
            tk.Label(mode_row, text="(locked after turn 1)",
                     font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT, padx=4)

        # ── Objective ship ───────────────────────────────────────────────────
        obj_row = tk.Frame(camp_frame)
        obj_row.pack(fill=tk.X, pady=2)
        tk.Label(obj_row, text="Objective ship:", font=("Consolas", 8), width=14,
                 anchor=tk.W).pack(side=tk.LEFT)
        all_ships = gs.get_ships()
        ship_names = [f"P{s.player} {s.name}" for s in all_ships]
        ship_ids   = [s.id for s in all_ships]
        cur_idx = ship_ids.index(gs.objective_ship_id) if gs.objective_ship_id in ship_ids else 0
        obj_var = tk.StringVar(value=ship_names[cur_idx] if ship_names else "")
        obj_cb  = ttk.Combobox(obj_row, textvariable=obj_var, values=ship_names,
                                state="disabled" if locked else "readonly", width=24,
                                font=("Consolas", 8))
        obj_cb.pack(side=tk.LEFT)
        tk.Label(obj_row, text="(destroy/protect/admiral)",
                 font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT, padx=4)

        # ── Artefact submode ─────────────────────────────────────────────────
        art_row = tk.Frame(camp_frame)
        art_row.pack(fill=tk.X, pady=2)
        tk.Label(art_row, text="Artefact mode:", font=("Consolas", 8), width=14,
                 anchor=tk.W).pack(side=tk.LEFT)
        art_var = tk.StringVar(value=gs.artefact_submode)
        for lbl, val in [("Race", "race"), ("Carrier escape", "carrier_escape")]:
            tk.Radiobutton(art_row, text=lbl, variable=art_var, value=val,
                           font=("Consolas", 8),
                           state=tk.DISABLED if locked else tk.NORMAL).pack(side=tk.LEFT)

        # ── Artefact position (X, Y) ─────────────────────────────────────────
        artpos_row = tk.Frame(camp_frame)
        artpos_row.pack(fill=tk.X, pady=2)
        tk.Label(artpos_row, text="Artefact pos:", font=("Consolas", 8), width=14,
                 anchor=tk.W).pack(side=tk.LEFT)
        cur_ax = str(int(gs.artefact_token_pos[0])) if gs.artefact_token_pos else str(int(gs.table_width // 2))
        cur_ay = str(int(gs.artefact_token_pos[1])) if gs.artefact_token_pos else str(int(gs.table_height // 2))
        art_x_var = tk.StringVar(value=cur_ax)
        art_y_var = tk.StringVar(value=cur_ay)
        tk.Label(artpos_row, text="X:", font=("Consolas", 8)).pack(side=tk.LEFT)
        tk.Entry(artpos_row, textvariable=art_x_var, width=5,
                 font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Label(artpos_row, text="Y:", font=("Consolas", 8)).pack(side=tk.LEFT, padx=(4, 0))
        tk.Entry(artpos_row, textvariable=art_y_var, width=5,
                 font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Label(artpos_row, text="cm (when uncarried)",
                 font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT, padx=4)

        # ── Turn limit ───────────────────────────────────────────────────────
        tl_row = tk.Frame(camp_frame)
        tl_row.pack(fill=tk.X, pady=2)
        tk.Label(tl_row, text="Turn limit:", font=("Consolas", 8), width=14,
                 anchor=tk.W).pack(side=tk.LEFT)
        tl_var = tk.StringVar(value="" if gs.turn_limit is None else str(gs.turn_limit))
        tk.Entry(tl_row, textvariable=tl_var, width=5,
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        tk.Label(tl_row, text="(blank = unlimited)",
                 font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT, padx=4)

        # ── FTL available from turn ──────────────────────────────────────────
        ftl_row = tk.Frame(camp_frame)
        ftl_row.pack(fill=tk.X, pady=2)
        tk.Label(ftl_row, text="FTL from turn:", font=("Consolas", 8), width=14,
                 anchor=tk.W).pack(side=tk.LEFT)
        ftl_var = tk.StringVar(value="" if gs.ftl_available_turn is None
                               else str(gs.ftl_available_turn))
        tk.Entry(ftl_row, textvariable=ftl_var, width=5,
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        tk.Label(ftl_row, text="(blank = always available)",
                 font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT, padx=4)

        # ── Export ───────────────────────────────────────────────────────────
        tk.Button(camp_frame, text="Export Fleet with Damage…",
                  command=lambda: (dialog.destroy(), self._export_fleet_dialog()),
                  bg="#2a2a44", fg="#aaaacc",
                  font=("Consolas", 8)).pack(anchor=tk.W, pady=4)

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
            # Scenario settings (only if not locked)
            if not locked:
                gs.scenario_mode = scen_var.get()
                obj_sel = obj_var.get()
                if obj_sel and obj_sel in ship_names:
                    gs.objective_ship_id = ship_ids[ship_names.index(obj_sel)]
                gs.artefact_submode = art_var.get()
            # Artefact position always editable (carrier may drop it)
            try:
                ax = float(art_x_var.get())
                ay = float(art_y_var.get())
                if 0 <= ax <= gs.table_width and 0 <= ay <= gs.table_height:
                    gs.artefact_token_pos = (ax, ay)
            except ValueError:
                pass
            # Turn limit / FTL always adjustable
            tl = tl_var.get().strip()
            gs.turn_limit = int(tl) if tl.isdigit() else None
            ftl = ftl_var.get().strip()
            gs.ftl_available_turn = int(ftl) if ftl.isdigit() else None
            self.ctx.board.redraw()
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

    # ── Save / Load / Export ─────────────────────────────────────────────────

    def _save_game(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Choose save folder")
        if d:
            self.ctx.gs.save(d)
            self.ctx.log(f"[Save] Game saved to {d}")

    def _load_game(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Select save folder to load")
        if d:
            try:
                self.ctx.gs.load(d)
                self.ctx.board.redraw()
                self._update_phase_display()
                self.ctx.log(f"[Load] Game loaded from {d}")
            except Exception as exc:
                from tkinter import messagebox as _mb
                _mb.showerror("Load Error", str(exc))

    def _export_match(self):
        from tkinter import filedialog
        fp = filedialog.asksaveasfilename(
            title="Export match archive",
            defaultextension=".bfg",
            filetypes=[("BFG match archive", "*.bfg"), ("All files", "*.*")])
        if fp:
            self.ctx.tc.export_match(fp)
            self.ctx.log(f"[Export] Match exported to {fp}")

    def _export_map(self):
        from tkinter import filedialog
        gs = self.ctx.gs
        phenomena = getattr(gs, "phenomena", [])
        width = getattr(gs, "table_width", 180)
        height = getattr(gs, "table_height", 120)
        sunward = getattr(gs, "sunward_edge", "bottom")
        fp = filedialog.asksaveasfilename(
            title="Export map JSON",
            defaultextension=".json",
            filetypes=[("Map JSON", "*.json"), ("All files", "*.*")])
        if fp:
            from .map_maker import save_map
            save_map(phenomena, width, height, sunward, fp)
            self.ctx.log(f"[Export] Map exported to {fp}")

    # ── LAN multiplayer ───────────────────────────────────────────────────────

    def _network_sync_phase(self):
        """After each phase: active player sends state; passive player receives."""
        net = self.ctx.network
        if net is None:
            return
        gs = self.ctx.gs
        local = self.ctx.local_player
        try:
            # The player who just finished their turn sends state
            if local == gs.active_player:
                net.send_state(gs)
            else:
                # Receive updated state from the active player
                new_gs = net.recv_state()
                # Preserve our reference but overwrite all mutable fields
                for attr in ("ships", "ordnance", "blast_markers", "phenomena",
                             "log", "turn_number", "current_phase", "active_player",
                             "phase_step"):
                    setattr(gs, attr, getattr(new_gs, attr))
        except ConnectionError as e:
            messagebox.showerror("Multiplayer Error",
                                 f"Network error: {e}\nGame will continue locally.")
            self.ctx.network = None

    def _show_host_dialog(self):
        """Show the 'host a game' dialog and wait for a client to connect."""
        from .network import GameServer, DEFAULT_PORT
        net = GameServer()
        ip = net.start()
        dialog = tk.Toplevel(self.root)
        dialog.title("Hosting Game")
        dialog.geometry("360x180")
        dialog.transient(self.root)
        tk.Label(dialog, text="Waiting for opponent to connect…",
                 font=("Consolas", 10, "bold")).pack(pady=12)
        tk.Label(dialog, text=f"Your IP:  {ip}",
                 font=("Consolas", 11)).pack()
        tk.Label(dialog, text=f"Port:  {DEFAULT_PORT}",
                 font=("Consolas", 11)).pack()
        tk.Label(dialog, text="Share these with your opponent.",
                 font=("Consolas", 8), fg="#888888").pack(pady=6)
        cancel_var = [False]

        def on_cancel():
            cancel_var[0] = True
            net.close()
            dialog.destroy()

        tk.Button(dialog, text="Cancel", command=on_cancel,
                  font=("Consolas", 9)).pack(pady=6)

        def poll():
            if cancel_var[0]:
                return
            if net.connected:
                dialog.destroy()
                self.ctx.network = net
                self.ctx.local_player = 1
                # Send initial state to client
                net.send_state(self.ctx.gs)
                self.ctx.log("[Net] Opponent connected. You are Player 1.")
            else:
                self.root.after(500, poll)

        poll()

    def _show_join_dialog(self):
        """Show the 'join a game' dialog and connect to a host."""
        from .network import GameClient, DEFAULT_PORT
        dialog = tk.Toplevel(self.root)
        dialog.title("Join Game")
        dialog.geometry("320x160")
        dialog.transient(self.root)
        tk.Label(dialog, text="Join LAN Game",
                 font=("Consolas", 10, "bold")).pack(pady=8)
        row = tk.Frame(dialog)
        row.pack()
        tk.Label(row, text="Host IP:", font=("Consolas", 9)).pack(side=tk.LEFT)
        ip_var = tk.StringVar()
        tk.Entry(row, textvariable=ip_var, width=18,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)

        def on_connect():
            host_ip = ip_var.get().strip()
            if not host_ip:
                return
            try:
                client = GameClient(host_ip, DEFAULT_PORT)
                client.connect()
                # Receive initial game state from host
                new_gs = client.recv_state()
                self.ctx.gs = new_gs
                self.ctx.tc.gs = new_gs
                self.ctx.network = client
                self.ctx.local_player = 2
                dialog.destroy()
                self.ctx.board.redraw()
                self.ctx.log(f"[Net] Connected to {host_ip}. You are Player 2.")
            except Exception as e:
                messagebox.showerror("Connection Failed", str(e))

        tk.Button(dialog, text="Connect", command=on_connect,
                  font=("Consolas", 9), bg="#2a4422", fg="#aaccaa").pack(pady=8)

    def _export_fleet_dialog(self):
        from tkinter import filedialog
        from .fleet_loader import export_fleet_with_damage
        gs = self.ctx.gs
        player = gs.active_player
        fp = filedialog.asksaveasfilename(
            title=f"Export Player {player} fleet with damage",
            defaultextension=".json",
            filetypes=[("Fleet JSON", "*.json"), ("All files", "*.*")])
        if fp:
            ships = [Ship.from_dict(s) for s in gs.ships]
            export_fleet_with_damage(ships, player, fp)
            self.ctx.log(f"[Export] Player {player} fleet exported to {fp}")

    # ── Campaign ─────────────────────────────────────────────────────────────

    def _campaign_post_battle_dialog(self, vp_p1: int, vp_p2: int):
        """After a battle, let the player choose (or create) a campaign save."""
        from tkinter import filedialog
        from .campaign import (CampaignState, load_campaign, post_battle_update)
        gs = self.ctx.gs
        campaign_dir = filedialog.askdirectory(
            title="Select campaign folder (existing or new)")
        if not campaign_dir:
            return
        campaign_file = os.path.join(campaign_dir, "campaign.json")
        if os.path.exists(campaign_file):
            cs = load_campaign(campaign_dir)
        else:
            cs = CampaignState(
                campaign_name=os.path.basename(campaign_dir),
                player1_name=gs.player1_name,
                player2_name=gs.player2_name,
                player1_faction=gs.player1_faction,
                player2_faction=gs.player2_faction,
                points_limit=gs.points_limit,
            )
        cs = post_battle_update(cs, gs, vp_p1, vp_p2, campaign_dir)
        self.ctx.log(
            f"[Campaign] Battle {cs.battles_played} saved. "
            f"VP: {gs.player1_name} {cs.player1_total_vp} — "
            f"{gs.player2_name} {cs.player2_total_vp}")
        # Offer repair dialog for each player
        for player, fleet_path, budget in [
            (1, cs.player1_fleet_file, cs.repair_budget_p1),
            (2, cs.player2_fleet_file, cs.repair_budget_p2),
        ]:
            if fleet_path and os.path.exists(fleet_path) and budget > 0:
                self._campaign_repair_dialog(
                    gs.player1_name if player == 1 else gs.player2_name,
                    fleet_path, budget, campaign_dir, cs)

    def _campaign_repair_dialog(self, player_name: str, fleet_path: str,
                                 budget: int, campaign_dir: str, cs):
        """Let a player spend their repair budget on crits and hull points."""
        from .campaign import apply_repairs, save_campaign
        import json as _json
        with open(fleet_path) as f:
            fleet_data = _json.load(f)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"{player_name} — Repair ({budget} pts available)")
        dialog.geometry("500x480")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"{player_name} Repair Bay",
                 font=("Consolas", 11, "bold")).pack(pady=6)
        tk.Label(dialog, text=f"Budget: {budget} pts  |  Crit repair: 25 pts  |  Hull +1HP: 10 pts",
                 font=("Consolas", 8), fg="#888888").pack()

        orders_var: list = []
        budget_var = tk.IntVar(value=budget)
        budget_lbl = tk.Label(dialog, text=f"Remaining: {budget} pts",
                              font=("Consolas", 9, "bold"))
        budget_lbl.pack()

        canvas = tk.Canvas(dialog, bg="#1a1a2e")
        scroll = tk.Scrollbar(dialog, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True, padx=8)
        inner = tk.Frame(canvas, bg="#1a1a2e")
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        def refresh_budget():
            budget_lbl.config(text=f"Remaining: {budget_var.get()} pts")

        for ship in fleet_data.get("ships", []):
            sid = ship["id"]
            name = ship.get("name", sid)
            hits = ship.get("hits_remaining", 0)
            hits_max = ship.get("hits_max", 8)
            crits = ship.get("critical_damage", [])
            frame = tk.LabelFrame(inner, text=f"{name}  HP {hits}/{hits_max}",
                                  font=("Consolas", 8), padx=4, pady=2, bg="#1a1a2e",
                                  fg="#aaaacc")
            frame.pack(fill=tk.X, padx=4, pady=2)
            # Hull repair button
            if hits < hits_max // 2:
                def _hull(s=sid, f=frame):
                    cost = 10
                    if budget_var.get() >= cost:
                        orders_var.append({"ship_id": s, "action": "hull"})
                        budget_var.set(budget_var.get() - cost)
                        refresh_budget()
                tk.Button(frame, text=f"+1 HP (10 pts)", command=_hull,
                          font=("Consolas", 7), bg="#2a3a2a", fg="#aaccaa").pack(anchor=tk.W)
            # Crit repair buttons
            for idx, crit in enumerate(crits):
                crit_name = crit.get("crit_type", "unknown") if isinstance(crit, dict) else str(crit)
                def _crit(s=sid, i=idx):
                    cost = 25
                    if budget_var.get() >= cost:
                        orders_var.append({"ship_id": s, "action": "crit", "crit_index": i})
                        budget_var.set(budget_var.get() - cost)
                        refresh_budget()
                tk.Button(frame, text=f"Repair: {crit_name} (25 pts)", command=_crit,
                          font=("Consolas", 7), bg="#3a2a2a", fg="#ccaaaa").pack(anchor=tk.W)

        def on_apply():
            remaining = apply_repairs(fleet_path, orders_var, budget)
            if player_name == cs.player1_name:
                cs.repair_budget_p1 = remaining
            else:
                cs.repair_budget_p2 = remaining
            save_campaign(cs, campaign_dir)
            self.ctx.log(f"[Campaign] {player_name}: repairs applied, {remaining} pts unused.")
            dialog.destroy()

        tk.Button(dialog, text="Apply Repairs", command=on_apply,
                  bg="#2a4422", fg="#aaccaa",
                  font=("Consolas", 9)).pack(pady=6)

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
        # If Player 1 (or both players) is AI, start automation immediately
        is_ai_turn = (gs.ai_spectator or
                      (gs.ai_player is not None and gs.active_player == gs.ai_player))
        if is_ai_turn:
            self.root.after(500, self._run_ai_phase)

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
        for ship in gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            fire_logs = resolve_fire_damage(ship, self.ctx.dice, gs)
            self.ctx.log_lines(fire_logs)
            if ship.hits_remaining <= 0:
                self.ctx.check_destruction(ship)

        # 2. Damage control with player choice
        for ship in gs.get_ships():
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
            for s in gs.player_ships(gs.active_player):
                if s.is_destroyed or s.is_disengaged:
                    continue
                unfired = []
                for i, w in enumerate(s.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay"):
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

        # LAN multiplayer: sync state to peer after each phase
        self._network_sync_phase()

        # Check for game-over conditions at the start of each new turn
        if gs.current_phase == "movement" and gs.turn_number > 1:
            if self._check_game_over():
                self._update_phase_display()
                self.ctx.board.redraw()
                return

        if gs.current_phase == "movement":
            self.movement._process_movement_phase_start()
            self._check_artefact_pickup()
            self.ctx.log(
                "Keys: M=min-move selected  Space=min-move all  "
                "BackSpace=undo all  Scroll=pending turn  Esc=cancel")
            self.ctx.board.canvas.focus_set()

        if gs.current_phase == "ordnance":
            for i, o_dict in enumerate(gs.ordnance):
                if o_dict.get("moved_this_phase"):
                    gs.ordnance[i] = {**o_dict, "moved_this_phase": False}

        # Check scenario conditions after shooting and ordnance resolve too
        if phase in ("shooting", "ordnance", "end"):
            self._check_scenario_end()

        self._update_phase_display()
        self.ctx.log(f"--- {gs.current_phase.upper()} PHASE ---")
        self.ctx.board.redraw()

        # AI automation: trigger if active player is AI-controlled
        is_ai_turn = (gs.ai_spectator or
                      (gs.ai_player is not None and gs.active_player == gs.ai_player))
        if is_ai_turn and gs.current_phase != "setup":
            self.root.after(400, self._run_ai_phase)

    # ── AI phase automation ───────────────────────────────────────────────────

    def _run_ai_phase(self):
        import threading
        from .ai_player import AIPlayer
        gs = self.ctx.gs
        tc = self.ctx.tc
        phase = gs.current_phase

        # In spectator mode both players are AI; use active_player as the controller
        ai_player_num = gs.active_player if gs.ai_spectator else gs.ai_player

        old_mode = gs.dice_mode
        gs.dice_mode = "auto"

        if gs.ai_difficulty == "expert":
            from .lookahead_ai import LookaheadAI
            ai = LookaheadAI(ai_player_num, tc, gs, self.ctx.dice, gs.ai_difficulty)
        else:
            ai = AIPlayer(ai_player_num, tc, gs, self.ctx.dice, gs.ai_difficulty)

        # Expert movement is slow (minimax depth-5); run off-thread so UI stays live
        if gs.ai_difficulty == "expert" and phase == "movement":
            self.phase_label.config(text="AI Thinking…")

            def _do_movement():
                ai.run_movement_phase()
                self.root.after(0, _on_done)

            def _on_done():
                gs.dice_mode = old_mode
                self.ctx.board.redraw()
                self.ctx.log("[AI] movement phase complete")
                self.root.after(300, self._end_phase)

            threading.Thread(target=_do_movement, daemon=True).start()
            return

        try:
            if phase == "movement":
                ai.run_movement_phase()
            elif phase == "shooting":
                ai.run_shooting_phase()
            elif phase == "ordnance":
                ai.run_ordnance_phase()
            elif phase == "end":
                self._resolve_end_phase_auto(ai)
        finally:
            gs.dice_mode = old_mode

        self.ctx.board.redraw()
        self.ctx.log(f"[AI] {phase} phase complete")
        self.root.after(300, self._end_phase)

    def _resolve_end_phase_auto(self, ai):
        """End phase for the AI player — same logic as interactive but auto-repairs."""
        from .end_phase import (resolve_fire_damage, get_repair_info,
                                apply_repair_choices, remove_blast_markers,
                                remove_brace_orders)
        from .ai_player import AIPlayer
        gs = self.ctx.gs

        self.ctx.log("=== END PHASE (AI) ===")

        self.end_phase._resolve_boarding_actions()
        self.end_phase._resolve_teleport_attacks()

        for ship in gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            fire_logs = resolve_fire_damage(ship, self.ctx.dice, gs)
            self.ctx.log_lines(fire_logs)
            if ship.hits_remaining <= 0:
                self.ctx.check_destruction(ship)

        for ship in gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            info = get_repair_info(ship, self.ctx.dice, gs)
            if info["sixes"] > 0 and info["repairable"]:
                repairs_available = min(info["sixes"], len(info["repairable"]))
                if ship.player == gs.ai_player:
                    choices = AIPlayer.auto_repair_choices(
                        info["repairable"], repairs_available)
                else:
                    choices = self.end_phase._repair_choice_dialog(
                        ship, info["repairable"], repairs_available)
                if choices:
                    repair_logs = apply_repair_choices(ship, choices, gs)
                    self.ctx.log_lines(repair_logs)

        bm_logs = remove_blast_markers(gs, self.ctx.dice)
        self.ctx.log_lines(bm_logs)
        brace_logs = remove_brace_orders(gs)
        self.ctx.log_lines(brace_logs)
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
        if result.get("blocked"):
            messagebox.showwarning("FTL Not Charged",
                f"{ship.name} cannot disengage yet.\n"
                + "\n".join(result["modifiers"]))
            return
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

    # ── Game-end detection ────────────────────────────────────────────────────

    def _ships_alive(self, player: int) -> bool:
        return any(
            s for s in self.ctx.gs.get_ships()
            if s.player == player and not s.is_destroyed and not s.is_disengaged
        )

    def _vp_winner(self):
        from .victory_points import calculate_victory_points
        vp = calculate_victory_points(self.ctx.gs)
        if vp["player1"] > vp["player2"]:
            return 1
        if vp["player2"] > vp["player1"]:
            return 2
        return None

    def _show_game_over_dialog(self, winner, reason: str = "", detail: str = ""):
        from .victory_points import calculate_victory_points, format_vp_summary
        gs = self.ctx.gs
        vp = calculate_victory_points(gs)
        vp_text = format_vp_summary(vp, gs)

        p1_name = gs.player1_name
        p2_name = gs.player2_name

        if winner == 1:
            title = f"Victory — {p1_name}!"
            headline = f"{p1_name} wins!"
        elif winner == 2:
            title = f"Victory — {p2_name}!"
            headline = f"{p2_name} wins!"
        else:
            title = "Draw!"
            headline = "The battle ends in a draw."

        reason_text = {
            "turn_limit": f"Turn limit ({gs.turn_limit}) reached.",
            "no_ships": "One side has no ships remaining.",
            "admiral_killed": f"Admiral killed ({detail}).",
            "objective_destroyed": f"Objective ship destroyed ({detail}).",
            "artefact_escaped": "Artefact carrier escaped the field!",
            "artefact_lost": "Artefact carrier destroyed — artefact lost!",
        }.get(reason, "")

        # Build the game-over dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("420x340")
        dialog.transient(self.root)
        dialog.focus_set()
        tk.Label(dialog, text=headline,
                 font=("Consolas", 13, "bold")).pack(pady=10)
        if reason_text:
            tk.Label(dialog, text=reason_text,
                     font=("Consolas", 9), fg="#888888").pack()
        tk.Label(dialog, text=vp_text, font=("Consolas", 9),
                 justify=tk.LEFT).pack(padx=15, pady=6)
        tk.Button(dialog, text="Save to Campaign…",
                  command=lambda: (dialog.destroy(),
                                   self._campaign_post_battle_dialog(
                                       vp.get("p1_total", 0), vp.get("p2_total", 0))),
                  bg="#2a3344", fg="#aabbcc",
                  font=("Consolas", 9)).pack(pady=4)
        tk.Button(dialog, text="Close", command=dialog.destroy,
                  font=("Consolas", 9)).pack(pady=2)

    def _check_game_over(self) -> bool:
        gs = self.ctx.gs

        # Turn limit
        if gs.turn_limit and gs.turn_number > gs.turn_limit:
            winner = self._vp_winner()
            self._show_game_over_dialog(winner, reason="turn_limit")
            return True

        # All ships gone
        p1_alive = self._ships_alive(1)
        p2_alive = self._ships_alive(2)
        if not p1_alive:
            self._show_game_over_dialog(2, reason="no_ships")
            return True
        if not p2_alive:
            self._show_game_over_dialog(1, reason="no_ships")
            return True

        return self._check_scenario_end()

    def _check_scenario_end(self) -> bool:
        gs = self.ctx.gs

        if gs.scenario_mode == "kill_admiral":
            for ship in gs.get_ships():
                if ship.is_flagship and ship.is_destroyed:
                    self._show_game_over_dialog(
                        winner=3 - ship.player,
                        reason="admiral_killed",
                        detail=ship.name)
                    return True

        elif gs.scenario_mode in ("destroy_ship", "protect_ship"):
            if gs.objective_ship_id:
                target = gs.get_ship_by_id(gs.objective_ship_id)
                if target and target.is_destroyed:
                    self._show_game_over_dialog(
                        winner=gs.scenario_attacker,
                        reason="objective_destroyed",
                        detail=target.name)
                    return True

        elif gs.scenario_mode == "capture_artefact":
            carrier_id = gs.artefact_carrier_id
            if carrier_id:
                carrier = gs.get_ship_by_id(carrier_id)
                if carrier:
                    if carrier.is_disengaged and gs.artefact_owner == gs.scenario_attacker:
                        self._show_game_over_dialog(
                            winner=gs.scenario_attacker,
                            reason="artefact_escaped")
                        return True
                    if carrier.is_destroyed:
                        self._show_game_over_dialog(
                            winner=3 - gs.scenario_attacker,
                            reason="artefact_lost")
                        return True

        return False

    def _check_artefact_pickup(self):
        """After movement: check if any ship moved onto the uncarried artefact token."""
        gs = self.ctx.gs
        if gs.scenario_mode != "capture_artefact":
            return
        if gs.artefact_token_pos is None or gs.artefact_carrier_id is not None:
            return

        import math
        tx, ty = gs.artefact_token_pos
        for ship in gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.player == gs.scenario_attacker:
                dist = math.sqrt((ship.x - tx) ** 2 + (ship.y - ty) ** 2)
                if dist <= 5.0:
                    gs.artefact_carrier_id = ship.id
                    gs.artefact_owner = ship.player
                    gs.artefact_token_pos = None
                    gs.add_log(f"[ARTEFACT] {ship.name} picks up the artefact!")
                    self.ctx.board.redraw()
                    messagebox.showinfo("Artefact Seized",
                        f"{ship.name} has picked up the artefact!\n"
                        f"Escape the board edge or warp out to win.")
                    return
