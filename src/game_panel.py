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


class GamePanel:
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
                self.gs.table_width, self.gs.table_height)
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
            self.tc.mark_ship_moved(ship.id)
            self._append_log(
                f"{ship.name}: drag-moved {result.total_distance:.1f}cm "
                f"to ({result.final_x:.1f}, {result.final_y:.1f}) "
                f"hdg {result.final_heading:.0f}°")
            self.board.redraw()

        self.board.can_drag_ship_fn = can_drag
        self.board.commit_drag_fn = commit_drag

        # M key: auto minimum-move the selected ship without opening the dialog
        self.root.bind("m", lambda e: self._quick_min_move_selected())
        self.root.bind("M", lambda e: self._quick_min_move_selected())

    def _quick_min_move_selected(self):
        """
        M key: open the movement dialog for the selected ship, pre-populated
        with the minimum legal move straight forward. The player can then add
        more commands before confirming.

        - Normal/CtNH/LockOn/Reload: pre-fills half speed forward.
        - Burn Retros: pre-fills half of effective speed forward.
        - All Ahead Full: rolls 4D6, pre-fills exact required total.
        """
        from .movement import MoveCommand, resolve_aaf_speed

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

        self._move_ship_dialog(
            preselected_ship=ship,
            initial_commands=[MoveCommand("forward", move_dist)])

    # --- Game Flow ---

    def _start_game(self):
        self.tc.start_game()
        self.tc.begin_phase("movement")
        self._process_movement_phase_start()
        self._update_phase_display()
        self._append_log(f"=== GAME START ===")
        self._append_log(f"Turn 1 - {self.gs.player1_name}")
        self._append_log(f"Movement Phase")
        self.board.redraw()

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

    def _resolve_teleport_attacks(self):
        """Allow the active player to make teleport attacks during the end phase."""
        from .hit_and_run import check_teleport_eligibility, resolve_teleport_attack
        from .movement import do_command_check

        active = self.gs.active_player
        ships = self.gs.get_ships()
        attackers = [s for s in ships
                     if s.player == active
                     and not s.is_destroyed and not s.is_disengaged
                     and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
        enemies = [s for s in ships
                   if s.player != active
                   and not s.is_destroyed and not s.is_disengaged
                   and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]

        if not attackers or not enemies:
            return

        # Track which ships have already teleported this end phase
        teleported = set()

        # Offer each eligible attacker a teleport opportunity
        for attacker in attackers:
            eligible_targets = []
            for target in enemies:
                ok, reason = check_teleport_eligibility(attacker, target, self.gs)
                if ok:
                    eligible_targets.append(target)

            if not eligible_targets or attacker.id in teleported:
                continue

            target_names = ", ".join(
                f"{t.name} ({attacker.distance_to(t):.0f}cm)"
                for t in eligible_targets)
            want = messagebox.askyesno(
                "Teleport Attack",
                f"{attacker.name} can teleport against:\n{target_names}\n\n"
                f"Attempt a teleport attack?")
            if not want:
                continue

            # Pick target if multiple eligible
            if len(eligible_targets) == 1:
                target = eligible_targets[0]
            else:
                target = self._pick_ship_dialog(eligible_targets,
                                                "Select teleport target")
                if not target:
                    continue

            # Re-fetch both ships to get live state
            attacker = self.gs.get_ship_by_id(attacker.id)
            target = self.gs.get_ship_by_id(target.id)
            if not attacker or not target:
                continue

            def _brace_fn(target_ship, msg):
                if target_ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                    self._append_log(
                        f"  {target_ship.name} already braced — saves apply automatically")
                    return True, True
                want_b = messagebox.askyesno("Teleport Attack — Brace?", msg)
                if not want_b:
                    return False, False
                check = do_command_check(target_ship, "brace_for_impact",
                                         self.dice)
                self._append_log(
                    f"  {target_ship.name} brace: "
                    f"{'PASSED' if check['passed'] else 'FAILED'} "
                    f"(rolled {check['roll']} vs Ld {check['needed']})")
                if check["passed"]:
                    target_ship.previous_order = target_ship.special_order
                    target_ship.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
                    target_ship.brace_set_on_turn = self.gs.turn_number
                    self.gs.update_ship(target_ship)
                return True, check["passed"]

            result = resolve_teleport_attack(
                attacker, target, self.dice, self.gs, _brace_fn)
            teleported.add(attacker.id)

            n_crits = len(result["crits_applied"])
            n_repelled = result["repelled"]
            n_failed = result["failures"]
            self._append_log(
                f"  Teleport result: {n_crits} crit(s) applied, "
                f"{n_repelled} repelled, {n_failed} failed")
            self._check_destruction(target)
            self.board.redraw()

    def _repair_choice_dialog(self, ship: Ship, repairable: List[str],
                               max_repairs: int) -> List[str]:
        """Show dialog for player to choose which crits to repair."""
        if max_repairs >= len(repairable):
            # Can repair everything, no choice needed
            return list(repairable)

        if max_repairs == 1 and len(repairable) == 1:
            return list(repairable)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Repair Choice - {ship.name}")
        dialog.geometry("400x350")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"{ship.name}: Choose {max_repairs} crit(s) to repair",
                 font=("Consolas", 10, "bold")).pack(pady=5)

        chosen = []
        check_vars = {}
        for crit_desc in repairable:
            var = tk.BooleanVar(value=False)
            check_vars[crit_desc] = var
            tk.Checkbutton(dialog, text=crit_desc, variable=var,
                           font=("Consolas", 9)).pack(anchor=tk.W, padx=20)

        result = [None]

        def confirm():
            selected = [desc for desc, var in check_vars.items() if var.get()]
            if len(selected) > max_repairs:
                messagebox.showwarning("Too Many",
                    f"Select at most {max_repairs} crit(s) to repair.")
                return
            result[0] = selected
            dialog.destroy()

        def skip():
            result[0] = []
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Repair Selected", command=confirm,
                  bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Skip Repairs", command=skip,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)
        return result[0] if result[0] is not None else []

    def _end_phase(self):
        phase = self.gs.current_phase

        # Movement phase: BLOCK if ships haven't moved (with override option)
        if phase == "movement":
            unmoved = self.tc.get_unmoved_ships()
            unmoved = [s for s in unmoved if not s.is_destroyed]
            if unmoved:
                names = "\n  ".join(s.name for s in unmoved[:8])
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

        # Reset per-ordnance-phase missile movement flags
        if self.gs.current_phase == "ordnance":
            for i, o_dict in enumerate(self.gs.ordnance):
                if o_dict.get("moved_this_phase"):
                    self.gs.ordnance[i] = {**o_dict, "moved_this_phase": False}

        self._update_phase_display()
        self._append_log(f"--- {self.gs.current_phase.upper()} PHASE ---")
        self.board.redraw()

    # --- Movement ---

    def _special_order_dialog(self):
        """Dialog to issue a special order to a ship."""
        unmoved = self.tc.get_unmoved_ships()
        if not unmoved:
            messagebox.showinfo("No Ships", "All ships have moved")
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

        selected = tk.StringVar()

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
        if order == SpecialOrder.ALL_AHEAD_FULL.value:
            max_speed = base_speed + aaf_bonus
            min_speed = max_speed  # must move exact
            speed_text = f"Speed: {max_speed}cm (AAF: {base_speed}+{aaf_bonus}) MUST MOVE ALL"
        elif order == SpecialOrder.BURN_RETROS.value:
            max_speed = base_speed // 2
            min_speed = 0
            speed_text = f"Speed: 0-{max_speed}cm (Burn Retros)"
        else:
            max_speed = base_speed
            min_speed = max(1, base_speed // 2)
            speed_text = f"Speed: {min_speed}-{max_speed}cm"

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

        # Turn stats line
        from .movement import get_max_turns
        _max_turns = get_max_turns(order, ship)
        turn_stats_var = tk.StringVar(
            value=f"Turns: 0/{_max_turns} used | Net: 0° | Remaining angle: {ship.turn_angle}°")
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
                f"Turns: 0/{_max_turns} used | Net: 0° | Remaining angle: {ship.turn_angle}°")
            turn_stats_label.config(fg="#AAAAFF")
            preview_var.set("Add movement commands above")
            self.board.redraw()

        def _validate():
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.gs.get_blast_markers(),
                self.gs.table_width, self.gs.table_height)

            # Update remaining distance
            used = result.total_distance
            remaining = max(0, max_speed - used)
            remaining_var.set(f"Remaining: {remaining:.1f}cm / {max_speed:.0f}cm (used {used:.1f}cm)")
            if remaining < 0.5:
                remaining_label.config(fg="#CCAA00")
            else:
                remaining_label.config(fg="#44CC44")

            # Update turn stats: net heading change and counts
            left_deg = sum(c.value for c in commands if c.action == "turn_left")
            right_deg = sum(c.value for c in commands if c.action == "turn_right")
            net_deg = left_deg - right_deg  # positive = net anticlockwise
            turns_count = sum(1 for c in commands
                              if c.action in ("turn_left", "turn_right"))
            angle_remaining = max(0.0, ship.turn_angle - max(left_deg, right_deg))
            net_str = f"+{net_deg:.0f}°" if net_deg > 0 else f"{net_deg:.0f}°"
            turn_stats_var.set(
                f"Turns: {turns_count}/{_max_turns} used | "
                f"Net: {net_str} | "
                f"Remaining angle: {angle_remaining:.0f}°")
            turn_stats_label.config(
                fg="#FF6644" if turns_count > _max_turns else "#AAAAFF")

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
            dialog.destroy()

        def _confirm():
            result = validate_movement(
                ship, commands, order, aaf_bonus,
                self.gs.get_blast_markers(),
                self.gs.table_width, self.gs.table_height)
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

    def _fire_dialog(self):
        """Dialog to fire a ship's weapons - pick weapons, pick targets, split fire."""
        # Get ships that have unfired weapons (check per-weapon, not just has_fired)
        active_ships = [Ship.from_dict(s) for s in self.gs.ships
                        if s["player"] == self.gs.active_player
                        and not Ship.from_dict(s).is_destroyed
                        and not s.get("is_disengaged", False)
                        and not s.get("disengage_failed_this_turn", False)]

        ships_with_weapons = []
        for s in active_ships:
            ship = Ship.from_dict(s) if isinstance(s, dict) else s
            wr = ship.weapons_remaining or {}
            has_unfired = False
            for i, w in enumerate(ship.weapons):
                wtype = w.get("weapon_type", "")
                if wtype in ("torpedo", "launch_bay", "gravitic_launcher"):
                    continue
                if not self._weapon_disabled_by_crit(ship, w):
                    idx_key = str(i)
                    if idx_key in wr:
                        if wr[idx_key] > 0:
                            has_unfired = True
                            break
                    else:
                        has_unfired = True
                        break
            if has_unfired:
                ships_with_weapons.append(ship)

        if not ships_with_weapons:
            messagebox.showinfo("No Ships", "All ships have fired all weapons")
            return

        attacker = self._pick_ship_dialog(ships_with_weapons, "Select ship to fire")
        if not attacker:
            return

        # Get enemies (only living, not disengaged)
        enemy_player = 2 if attacker.player == 1 else 1
        enemies = [Ship.from_dict(s) for s in self.gs.ships
                   if s["player"] == enemy_player
                   and not Ship.from_dict(s).is_destroyed
                   and not s.get("is_disengaged", False)]
        if not enemies:
            messagebox.showinfo("No Targets", "No enemy ships in play")
            return

        # Sort enemies by distance, but only consider visible ones for "closest"
        enemies.sort(key=lambda e: attacker.distance_to(e))
        phenomena = self.gs.get_phenomena()
        blast_markers = self.gs.get_blast_markers()

        # Find closest VISIBLE enemy (for target priority)
        closest_visible = None
        for e in enemies:
            los = check_los_clear(attacker, e, phenomena, blast_markers)
            if los["clear"]:
                closest_visible = e
                break

        lock_on = attacker.special_order == SpecialOrder.LOCK_ON.value

        # Check asteroid field firing restrictions
        from .terrain_effects import check_ship_terrain_contact
        attacker_contacts = check_ship_terrain_contact(attacker, phenomena)
        in_asteroid_field = any(c["type"] == "asteroid_field" for c in attacker_contacts)
        if in_asteroid_field:
            if attacker.is_crippled:
                messagebox.showinfo("Cannot Fire",
                    f"{attacker.name} is crippled — cannot fire from an asteroid field.")
                return
            if attacker.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                messagebox.showinfo("Cannot Fire",
                    f"{attacker.name} is bracing — cannot fire from an asteroid field.")
                return

        # Build list of available weapons (not ordnance, not crit-disabled, has remaining strength)
        available_weapons = []
        for i, weapon in enumerate(attacker.weapons):
            wtype = weapon.get("weapon_type", "")
            if wtype in ("torpedo", "launch_bay", "gravitic_launcher"):
                continue
            if self._weapon_disabled_by_crit(attacker, weapon):
                continue
            # Check remaining strength
            idx_key = str(i)
            if idx_key in attacker.weapons_remaining:
                remaining = attacker.weapons_remaining[idx_key]
                if remaining <= 0:
                    continue  # fully spent
            available_weapons.append((i, weapon))

        if not available_weapons:
            messagebox.showinfo("No Weapons",
                f"{attacker.name} has no available direct fire weapons")
            return

        # Weapon selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Fire Weapons - {attacker.name}")
        dialog.geometry("550x600")
        dialog.transient(self.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=f"Fire: {attacker.name}",
                 font=("Consolas", 11, "bold")).pack(pady=3)
        tk.Label(dialog, text=f"Order: {attacker.special_order}"
                 + (" [LOCK ON - re-roll misses]" if lock_on else ""),
                 font=("Consolas", 8)).pack()

        # Weapon assignment frame
        assign_frame = tk.Frame(dialog)
        assign_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(assign_frame, text="Select weapons and assign targets:",
                 font=("Consolas", 9, "bold")).pack(anchor=tk.W)

        # For each weapon, create a row with checkbox, weapon info, target dropdown
        weapon_assignments = []
        target_options_per_weapon = {}  # w_idx -> list of option strings

        for w_idx, weapon in available_weapons:
            row = tk.Frame(assign_frame)
            row.pack(fill=tk.X, pady=2)

            enabled = tk.BooleanVar(value=True)
            tk.Checkbutton(row, variable=enabled).pack(side=tk.LEFT)

            wtype = weapon.get("weapon_type", "")
            arcs = "/".join(weapon.get("arcs", []))

            # Calculate available strength (may be reduced from prior split fire)
            full_str = weapon.get("strength", 0)
            idx_key = str(w_idx)
            if idx_key in attacker.weapons_remaining:
                avail_str = attacker.weapons_remaining[idx_key]
            else:
                avail_str = full_str

            # Asteroid field: half strength/firepower, max 10cm range, no column shifts
            ast_range_cap = 10 if in_asteroid_field and wtype != "nova_cannon" else None
            if in_asteroid_field and wtype in ("battery", "lance"):
                avail_str = max(1, (avail_str + 1) // 2)

            if wtype == "battery":
                ast_note = " [ASTEROID: half FP, 10cm, no shifts]" if in_asteroid_field else ""
                desc = f"Battery FP{avail_str}/{full_str} {weapon['range_cm']}cm [{arcs}]{ast_note}"
            elif wtype == "lance":
                ast_note = " [ASTEROID: half Str, 10cm]" if in_asteroid_field else ""
                desc = f"Lance Str{avail_str}/{full_str} {weapon['range_cm']}cm [{arcs}]{ast_note}"
            elif wtype == "nova_cannon":
                desc = f"Nova Cannon 30-150cm [front]"
                avail_str = 1  # nova cannon is binary
            else:
                desc = f"{weapon['name']}"

            tk.Label(row, text=f"{weapon['name']}: {desc}",
                     font=("Consolas", 8), anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Strength to fire entry (for split fire)
            str_var = tk.StringVar(value=str(avail_str))
            if wtype != "nova_cannon" and avail_str > 1:
                tk.Label(row, text="Fire:", font=("Consolas", 8)).pack(side=tk.LEFT)
                str_entry = tk.Entry(row, textvariable=str_var, width=3,
                                      font=("Consolas", 9))
                str_entry.pack(side=tk.LEFT, padx=2)

            # Target dropdown - show name + distance + arc + LoS
            target_options = []
            phenomena = self.gs.get_phenomena()
            for e in enemies:
                dist = attacker.distance_to(e)
                arc = attacker.get_target_arc(e.x, e.y)
                in_arc = arc.value in weapon.get("arcs", []) or not weapon.get("arcs")
                effective_range = min(weapon.get("range_cm", 999),
                                      ast_range_cap if ast_range_cap else 9999)
                in_range = dist <= effective_range
                los = check_los_clear(attacker, e, phenomena, blast_markers)
                status = ""
                if not los["clear"]:
                    status = f" [NO LOS: {los['blocked_by']}]"
                elif not in_arc:
                    status = " [NO ARC]"
                elif not in_range:
                    status = " [OUT OF RANGE]"
                target_options.append(f"{e.name} ({dist:.0f}cm {arc.value}){status}")

            target_options_per_weapon[w_idx] = list(target_options)
            target_var = tk.StringVar(value=target_options[0] if target_options else "")
            target_menu = tk.OptionMenu(row, target_var, *target_options)
            target_menu.config(font=("Consolas", 7), width=25)
            target_menu.pack(side=tk.RIGHT)

            weapon_assignments.append((w_idx, weapon, enabled, target_var, str_var, avail_str))

        # Log area
        log_frame = tk.Frame(dialog)
        log_frame.pack(fill=tk.X, padx=10, pady=3)
        fire_log = tk.Text(log_frame, height=10, font=("Consolas", 8),
                           bg="#0a0a1a", fg="#88CC88", state=tk.DISABLED)
        fire_log.pack(fill=tk.X)

        def _log(msg):
            fire_log.config(state=tk.NORMAL)
            fire_log.insert(tk.END, msg + "\n")
            fire_log.see(tk.END)
            fire_log.config(state=tk.DISABLED)

        def _fire_all():
            """Fire all selected weapons at their assigned targets."""
            all_damage = {}  # target_id -> list of (hits, weapon_type)
            fired_weapon_indices = []  # track which weapons we fire

            for w_idx, weapon, enabled, target_var, str_var, avail_str in weapon_assignments:
                if not enabled.get():
                    continue

                target_str = target_var.get()
                if not target_str:
                    _log(f"  {weapon['name']}: skipped (no target selected)")
                    continue
                if any(block in target_str for block in
                       ["[NO ARC]", "[OUT OF RANGE]", "[NO LOS"]):
                    _log(f"  {weapon['name']}: skipped (invalid target)")
                    continue

                # Parse strength to fire (for split volleys)
                try:
                    fire_str = int(str_var.get())
                    fire_str = max(1, min(fire_str, avail_str))
                except (ValueError, TypeError):
                    fire_str = avail_str

                # Find target ship by name match
                target_name = target_str.split(" (")[0]
                target = None
                for e in enemies:
                    if e.name == target_name:
                        target = e
                        break
                if not target:
                    continue

                # Target priority check: only needed if firing at a target
                # that is NOT the closest VALID target for THIS weapon
                # (valid = in arc, in range, in LoS)
                needs_priority_check = False
                if closest_visible and target.id != closest_visible.id:
                    # Check if closest_visible is actually valid for this weapon
                    cv_arc = attacker.get_target_arc(closest_visible.x, closest_visible.y)
                    cv_in_arc = cv_arc.value in weapon.get("arcs", []) or not weapon.get("arcs")
                    cv_in_range = attacker.distance_to(closest_visible) <= weapon.get("range_cm", 999)
                    cv_los = check_los_clear(attacker, closest_visible,
                                            self.gs.get_phenomena(), blast_markers)
                    if cv_in_arc and cv_in_range and cv_los["clear"]:
                        needs_priority_check = True

                if needs_priority_check:
                    from .movement import do_command_check
                    check = do_command_check(attacker, "target_priority",
                                             self.dice)
                    if not check["passed"]:
                        _log(f"  {weapon['name']}: Target priority FAILED "
                             f"(rolled {check['roll']} vs Ld {check['needed']}). "
                             f"Must fire at closest visible: {closest_visible.name}")
                        target = closest_visible
                    else:
                        _log(f"  {weapon['name']}: Target priority passed "
                             f"(rolled {check['roll']} vs Ld {check['needed']})")

                # Track this weapon as fired (with strength used)
                # BUT: nova cannon errors don't consume the weapon
                weapon_actually_fired = True

                wtype = weapon.get("weapon_type", "")
                phenomena = self.gs.get_phenomena()

                # Create weapon dict with the specific strength to fire
                fire_weapon = dict(weapon)
                fire_weapon["strength"] = fire_str

                if wtype == "battery":
                    sr = resolve_batteries(attacker, target, fire_weapon,
                                          self.dice, blast_markers, lock_on,
                                          phenomena, self.gs.ships,
                                          no_column_shifts=in_asteroid_field)
                    _log(f"  {sr.description}")
                    if sr.hits > 0:
                        all_damage.setdefault(target.id, []).append(
                            (sr.hits, "battery", target))

                elif wtype == "lance":
                    sr = resolve_lances(attacker, target, fire_weapon,
                                       self.dice, lock_on)
                    _log(f"  {sr.description}")
                    if sr.hits > 0:
                        all_damage.setdefault(target.id, []).append(
                            (sr.hits, "lance", target))

                elif wtype == "nova_cannon":
                    # Check range BEFORE attempting to fire
                    dist_to_target = attacker.distance_to(target)
                    if dist_to_target < 30 or dist_to_target > 150:
                        _log(f"  Nova Cannon: target at {dist_to_target:.0f}cm, "
                             f"range is 30-150cm. Cannot fire.")
                        weapon_actually_fired = False
                    else:
                        nc = resolve_nova_cannon(attacker, target.x, target.y,
                                               self.dice, self.gs)
                        if "error" in nc:
                            _log(f"  Nova Cannon: {nc['error']}")
                            weapon_actually_fired = False
                        else:
                            # Log scatter result
                            tx, ty = nc["template_x"], nc["template_y"]
                            if nc.get("scatter_distance", 0) > 0:
                                _log(f"  Nova Cannon: SCATTERED {nc['scatter_distance']:.0f}cm "
                                     f"to ({tx:.0f}, {ty:.0f})")
                            else:
                                _log(f"  Nova Cannon: HIT! Template at ({tx:.0f}, {ty:.0f})")

                            # Draw template on board
                            self.board.draw_nova_template(tx, ty,
                                                          hit=bool(nc.get("ship_hits")))

                            # Apply hits
                            if nc.get("ship_hits"):
                                for sid, hd in nc["ship_hits"].items():
                                    hit_ship = self.gs.get_ship_by_id(sid)
                                    if hit_ship:
                                        _log(f"  Nova Cannon hits {hit_ship.name}: "
                                             f"{hd['hits']} hits (ignores armor)")
                                        apply_damage(hit_ship, hd["hits"],
                                                   self.dice, self.gs,
                                                   ignores_shields=True)
                                        self._check_destruction(hit_ship)
                            else:
                                _log(f"  Nova Cannon: no ships hit")

                            # Place blast markers for misses
                            for bx, by in nc.get("blast_markers", []):
                                from .models import BlastMarker as BM
                                import random as _rng
                                bm = BM(
                                    id=f"nova_miss_{_rng.randint(0,9999)}",
                                    x=bx, y=by,
                                    source="nova_cannon_miss")
                                self.gs.add_blast_marker(bm)
                                _log(f"  Blast marker placed at ({bx:.0f}, {by:.0f})")

                # Only track as fired if the weapon actually resolved
                if weapon_actually_fired:
                    fired_weapon_indices.append((w_idx, fire_str, avail_str))

            # Now apply damage per target
            for target_id, hit_list in all_damage.items():
                total = sum(h for h, _, _ in hit_list)
                target = hit_list[0][2]  # get target ship from first entry
                target = self.gs.get_ship_by_id(target_id)  # re-fetch
                if not target or target.is_destroyed:
                    continue

                _log(f"  >> {target.name}: {total} total hits")

                # Brace option (per attacker, requires Ld test)
                brace = False
                already_braced = (target.special_order ==
                                  SpecialOrder.BRACE_FOR_IMPACT.value)

                if already_braced:
                    brace = True
                    _log(f"     (already braced)")
                elif attacker.id not in (target.brace_failed_vs or []):
                    want_brace = messagebox.askyesno(
                        "Brace For Impact?",
                        f"{target.name} taking {total} hits from {attacker.name}.\n"
                        f"Attempt Brace For Impact? (Ld test, then 4+ save per hull hit)\n"
                        f"If failed: cannot brace against {attacker.name} again.")
                    if want_brace:
                        # Command check for brace
                        from .movement import do_command_check
                        check = do_command_check(target, "brace_for_impact",
                                                 self.dice)
                        if check["passed"]:
                            brace = True
                            # Save previous order before replacing
                            if target.special_order != SpecialOrder.BRACE_FOR_IMPACT.value:
                                target.previous_order = target.special_order
                            target.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
                            target.brace_set_on_turn = self.gs.turn_number
                            self.gs.update_ship(target)
                            _log(f"     Brace PASSED (rolled {check['roll']} "
                                 f"vs Ld {check['needed']})")
                        else:
                            # Failed: can't brace against this attacker again
                            failed_list = target.brace_failed_vs or []
                            failed_list.append(attacker.id)
                            target.brace_failed_vs = failed_list
                            self.gs.update_ship(target)
                            _log(f"     Brace FAILED (rolled {check['roll']} "
                                 f"vs Ld {check['needed']})")
                else:
                    _log(f"     (already failed brace vs {attacker.name})")

                dmg = apply_damage(target, total, self.dice, self.gs,
                                  target_braced=brace)
                _log(f"     Shields: {dmg['shield_hits']}, "
                     f"Hull: {dmg['hull_hits']}, "
                     f"Saves: {dmg['brace_saves']}")
                if dmg.get("crits"):
                    for crit in dmg["crits"]:
                        _log(f"     CRITICAL: {crit}")
                if dmg["crippled"]:
                    _log(f"     {target.name} is CRIPPLED!")
                if dmg["destroyed"]:
                    _log(f"     {target.name} DESTROYED!")
                    self._check_destruction(target)

            # Record which weapons were fired and track remaining strength
            attacker_fresh = self.gs.get_ship_by_id(attacker.id)
            if attacker_fresh:
                wr = attacker_fresh.weapons_remaining or {}
                wfi = attacker_fresh.weapons_fired_indices or []

                for w_idx, fire_str, avail_str in fired_weapon_indices:
                    new_remaining = avail_str - fire_str
                    wr[str(w_idx)] = new_remaining
                    if new_remaining <= 0 and w_idx not in wfi:
                        wfi.append(w_idx)

                attacker_fresh.weapons_remaining = wr
                attacker_fresh.weapons_fired_indices = wfi

                # Check if ALL direct-fire weapons are fully spent
                all_done = True
                for i, w in enumerate(attacker_fresh.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay", "gravitic_launcher"):
                        continue
                    if self._weapon_disabled_by_crit(attacker_fresh, w):
                        continue
                    idx_key = str(i)
                    if idx_key in wr:
                        if wr[idx_key] > 0:
                            all_done = False
                            break
                    else:
                        all_done = False
                        break
                attacker_fresh.has_fired = all_done
                self.gs.update_ship(attacker_fresh)

            self._append_log(
                f"{attacker.name} fired {len(fired_weapon_indices)} weapon(s)")

            # Warn if unfired weapons remain
            if attacker_fresh and not attacker_fresh.has_fired:
                remaining_weapons = []
                wr2 = attacker_fresh.weapons_remaining or {}
                for i, w in enumerate(attacker_fresh.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay", "gravitic_launcher"):
                        continue
                    if self._weapon_disabled_by_crit(attacker_fresh, w):
                        continue
                    idx_key = str(i)
                    if idx_key in wr2:
                        rem = wr2[idx_key]
                        if rem > 0:
                            remaining_weapons.append(
                                f"{w['name']} ({rem} remaining)")
                    else:
                        remaining_weapons.append(w["name"])
                if remaining_weapons:
                    self._append_log(
                        f"  WARNING: {attacker.name} still has unfired: "
                        + ", ".join(remaining_weapons))

            dialog.destroy()
            self.board.redraw()

        def _auto_full_volley():
            """Set all weapons to fire at closest valid target."""
            for w_idx, weapon, enabled, target_var, str_var, avail_str in weapon_assignments:
                # Find closest valid target for this weapon
                best = None
                for opt in target_options_per_weapon.get(w_idx, []):
                    if not any(x in opt for x in ["[NO ARC]", "[OUT OF RANGE]", "[NO LOS"]):
                        best = opt
                        break
                if best:
                    enabled.set(True)
                    target_var.set(best)
                else:
                    enabled.set(False)
            _fire_all()

        # Buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Auto: Full Volley at Closest",
                  command=_auto_full_volley,
                  bg="#444466", fg="white",
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="Fire Selected Weapons", command=_fire_all,
                  bg="#663333", fg="white",
                  font=("Consolas", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

    def _move_tau_missiles_dialog(self):
        """Player-controlled Tau missile movement. Reuses ship movement concepts:
        choose speed (20-40cm), optional 45° turn at start, quick buttons."""
        tau_missiles = [OrdnanceMarker.from_dict(o) for o in self.gs.ordnance
                        if o["ordnance_type"] == OrdnanceType.TORPEDO_GUIDED.value
                        and o["owner_player"] == self.gs.active_player
                        and not o.get("moved_this_phase", False)]
        if not tau_missiles:
            messagebox.showinfo("No Missiles",
                "No unmoved Tau missile salvos this phase")
            return

        # Pick which salvo to move
        if len(tau_missiles) == 1:
            missile = tau_missiles[0]
        else:
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Missile Salvo")
            dialog.geometry("350x300")
            dialog.transient(self.root)
            listbox = tk.Listbox(dialog, font=("Consolas", 9), height=8)
            listbox.pack(fill=tk.X, padx=10, pady=10)
            for m in tau_missiles:
                listbox.insert(tk.END,
                    f"Str {m.strength} at ({m.x:.0f},{m.y:.0f}) hdg {m.heading:.0f}°")
            selected = [None]
            def _sel():
                s = listbox.curselection()
                if s:
                    selected[0] = tau_missiles[s[0]]
                dialog.destroy()
            tk.Button(dialog, text="Select", command=_sel,
                      font=("Consolas", 10)).pack(pady=5)
            self.root.wait_window(dialog)
            missile = selected[0]
            if not missile:
                return

        # Movement dialog (similar to ship movement)
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Move Tau Missiles (Str {missile.strength})")
        dialog.geometry("480x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Tau Missile Salvo Str {missile.strength}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        can_turn = missile.launched_turn < self.gs.turn_number  # can't turn on launch turn
        turn_note = "Can turn 45° at start" if can_turn else "Cannot turn (launched this turn)"

        info_text = (
            f"Speed: 20-40cm | {turn_note}\n"
            f"Pos: ({missile.x:.1f}, {missile.y:.1f}) | Heading: {missile.heading:.0f}°"
        )
        tk.Label(dialog, text=info_text, font=("Consolas", 8),
                 justify=tk.LEFT).pack(padx=10, anchor=tk.W)

        # Turn controls (only if allowed)
        turn_applied = [0.0]  # net turn applied

        if can_turn:
            turn_frame = tk.Frame(dialog)
            turn_frame.pack(padx=10, pady=3, fill=tk.X)
            tk.Label(turn_frame, text="Turn:", font=("Consolas", 9)).pack(side=tk.LEFT)
            turn_var = tk.StringVar(value="0")

            for deg in [5, 15, 30, 45]:
                tk.Button(turn_frame, text=f"↶{deg}°",
                          command=lambda d=deg: _apply_turn(d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
                tk.Button(turn_frame, text=f"↷{deg}°",
                          command=lambda d=deg: _apply_turn(-d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)

            turn_label = tk.Label(dialog, text="Net turn: 0°",
                                   font=("Consolas", 9, "bold"))
            turn_label.pack()

            def _apply_turn(deg):
                new_net = turn_applied[0] + deg
                if abs(new_net) > 45:
                    return  # can't exceed 45°
                turn_applied[0] = new_net
                turn_label.config(
                    text=f"Net turn: {new_net:+.0f}° "
                         f"({'anticlockwise' if new_net > 0 else 'clockwise' if new_net < 0 else 'none'})")
                # Update preview
                _update_preview()

            tk.Button(turn_frame, text="Reset",
                      command=lambda: (_apply_turn(-turn_applied[0]),),
                      font=("Consolas", 7)).pack(side=tk.LEFT, padx=3)

        # Speed control
        speed_frame = tk.Frame(dialog)
        speed_frame.pack(padx=10, pady=3, fill=tk.X)
        tk.Label(speed_frame, text="Move distance (20-40cm):",
                 font=("Consolas", 9)).pack(side=tk.LEFT)
        speed_var = tk.StringVar(value="30")
        tk.Entry(speed_frame, textvariable=speed_var, width=5,
                 font=("Consolas", 10)).pack(side=tk.LEFT, padx=3)

        # Quick speed buttons
        quick_frame = tk.Frame(dialog)
        quick_frame.pack(padx=10, pady=2, fill=tk.X)
        for spd in [20, 25, 30, 35, 40]:
            tk.Button(quick_frame, text=f"{spd}cm",
                      command=lambda s=spd: speed_var.set(str(s)),
                      font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        # Preview
        preview_var = tk.StringVar(value="Set turn and speed, then confirm")
        tk.Label(dialog, textvariable=preview_var,
                 font=("Consolas", 8), fg="#AAAAAA",
                 wraplength=440).pack(padx=10, pady=5)

        def _update_preview():
            try:
                spd = float(speed_var.get())
            except ValueError:
                spd = 30
            spd = max(20, min(40, spd))
            new_heading = (missile.heading + turn_applied[0]) % 360
            rad = math.radians(new_heading)
            end_x = missile.x + spd * math.cos(rad)
            end_y = missile.y + spd * math.sin(rad)
            preview_var.set(
                f"Heading {new_heading:.0f}° -> ({end_x:.0f}, {end_y:.0f}), {spd:.0f}cm")

            # Draw preview on board
            self.board.redraw()
            sx0, sy0 = self.board.cm_to_screen(missile.x, missile.y)
            sx1, sy1 = self.board.cm_to_screen(end_x, end_y)
            self.board.canvas.create_line(sx0, sy0, sx1, sy1,
                                          fill="#44FF44", width=2, dash=(4, 4))

        speed_var.trace_add("write", lambda *a: _update_preview())
        _update_preview()

        def _confirm():
            try:
                spd = float(speed_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid speed")
                return
            spd = max(20, min(40, spd))

            # Apply turn
            new_heading = (missile.heading + turn_applied[0]) % 360
            missile.heading = new_heading

            # Apply movement
            rad = math.radians(missile.heading)
            missile.x += spd * math.cos(rad)
            missile.y += spd * math.sin(rad)

            # Update in game state
            for j, o_dict in enumerate(self.gs.ordnance):
                if o_dict["id"] == missile.id:
                    updated = missile.to_dict()
                    updated["moved_this_phase"] = True
                    self.gs.ordnance[j] = updated
                    break

            turn_desc = f", turned {turn_applied[0]:+.0f}°" if turn_applied[0] != 0 else ""
            self._append_log(
                f"Tau missiles Str {missile.strength} moved {spd:.0f}cm"
                f"{turn_desc} to ({missile.x:.0f}, {missile.y:.0f})")
            dialog.destroy()
            self.board.redraw()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Confirm Move", command=_confirm,
                  bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=5)

    def _fire_at_ordnance_dialog(self):
        """Fire weapons at ordnance. 6+ to hit, one hit removes entire wave/salvo.
        Batteries use Ordnance column on gunnery table. Lances roll strength dice.
        Ordnance-only target priority (other ordnance = nearest, not ships)."""
        enemy_player = 2 if self.gs.active_player == 1 else 1
        enemy_ordnance = [OrdnanceMarker.from_dict(o) for o in self.gs.ordnance
                          if o["owner_player"] == enemy_player]
        if not enemy_ordnance:
            messagebox.showinfo("No Targets", "No enemy ordnance on the board")
            return

        # Get ships with unfired direct-fire weapons (batteries OR lances)
        active_ships = [Ship.from_dict(s) for s in self.gs.ships
                        if s["player"] == self.gs.active_player
                        and not Ship.from_dict(s).is_destroyed
                        and not s.get("is_disengaged", False)]
        ships_with_weapons = []
        for s in active_ships:
            wr = s.weapons_remaining or {}
            for i, w in enumerate(s.weapons):
                wtype = w.get("weapon_type", "")
                if wtype not in ("battery", "lance"):
                    continue
                if self._weapon_disabled_by_crit(s, w):
                    continue
                idx_key = str(i)
                if idx_key in wr and wr[idx_key] <= 0:
                    continue
                ships_with_weapons.append(s)
                break

        if not ships_with_weapons:
            messagebox.showinfo("No Ships",
                "No ships with available battery or lance weapons")
            return

        attacker = self._pick_ship_dialog(ships_with_weapons,
                                           "Select ship to fire at ordnance")
        if not attacker:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Fire at Ordnance - {attacker.name}")
        dialog.geometry("500x500")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Fire {attacker.name} at ordnance",
                 font=("Consolas", 11, "bold")).pack(pady=3)
        tk.Label(dialog, text="All weapons hit ordnance on 6+. One hit kills the entire wave.",
                 font=("Consolas", 8), fg="#AAAAAA").pack()

        # Sort ordnance by distance (for ordnance-only target priority)
        enemy_ordnance.sort(key=lambda o: math.sqrt(
            (o.x - attacker.x)**2 + (o.y - attacker.y)**2))

        # Weapon selection
        avail_weapons = []
        for i, w in enumerate(attacker.weapons):
            wtype = w.get("weapon_type", "")
            if wtype not in ("battery", "lance"):
                continue
            if self._weapon_disabled_by_crit(attacker, w):
                continue
            wr = attacker.weapons_remaining or {}
            idx_key = str(i)
            avail = wr.get(idx_key, w.get("strength", 0))
            if avail <= 0:
                continue
            avail_weapons.append((i, w, avail))

        # Weapon selector
        tk.Label(dialog, text="Select weapon:", font=("Consolas", 9, "bold")).pack(anchor=tk.W, padx=10)
        weapon_var = tk.StringVar()
        weapon_labels = []
        for i, w, avail in avail_weapons:
            wtype = w.get("weapon_type", "")
            label = f"{w['name']} ({wtype} Str {avail}, {w.get('range_cm', 0)}cm)"
            weapon_labels.append(label)
            tk.Radiobutton(dialog, text=label, variable=weapon_var,
                           value=str(i), font=("Consolas", 8)).pack(anchor=tk.W, padx=20)
        if avail_weapons:
            weapon_var.set(str(avail_weapons[0][0]))

        # Target selector
        tk.Label(dialog, text="Select target:", font=("Consolas", 9, "bold")).pack(anchor=tk.W, padx=10, pady=(5,0))
        target_listbox = tk.Listbox(dialog, font=("Consolas", 9), height=6)
        target_listbox.pack(fill=tk.X, padx=10, pady=3)
        for o in enemy_ordnance:
            dist = math.sqrt((o.x - attacker.x)**2 + (o.y - attacker.y)**2)
            label = f"{o.ordnance_type} Str{o.strength} ({dist:.0f}cm)"
            target_listbox.insert(tk.END, label)
        if enemy_ordnance:
            target_listbox.selection_set(0)

        def _fire():
            sel = target_listbox.curselection()
            if not sel:
                return
            target_ord = enemy_ordnance[sel[0]]
            w_idx = int(weapon_var.get())

            # Find the weapon
            weapon = attacker.weapons[w_idx]
            wtype = weapon.get("weapon_type", "")
            wr = attacker.weapons_remaining or {}
            idx_key = str(w_idx)
            avail = wr.get(idx_key, weapon.get("strength", 0))

            dist = math.sqrt((target_ord.x - attacker.x)**2 +
                             (target_ord.y - attacker.y)**2)

            # Range check
            if dist > weapon.get("range_cm", 999):
                messagebox.showerror("Out of Range",
                    f"Target at {dist:.0f}cm, weapon range {weapon['range_cm']}cm")
                return

            # Ordnance-only target priority: check if this is the closest ordnance
            # If not, no Ld test needed (ordnance priority only counts other ordnance)
            closest_ord = enemy_ordnance[0]  # already sorted by distance
            if target_ord.id != closest_ord.id:
                from .movement import do_command_check
                check = do_command_check(attacker, "target_priority", self.dice)
                if not check["passed"]:
                    self._append_log(
                        f"  Target priority FAILED (rolled {check['roll']} vs Ld {check['needed']}). "
                        f"Must fire at closest ordnance.")
                    target_ord = closest_ord

            # Determine dice count
            if wtype == "battery":
                # Use Ordnance column (col 5) on gunnery table
                # Column shifts for range, blast markers, special rules still apply
                from .tables import lookup_gunnery_dice, COL_ABEAM_ESCORT
                shifts = 0
                # Range shifts
                if dist < 15:
                    shifts -= 1  # close range = better
                elif dist > 30:
                    shifts += 1  # long range = worse
                # Blast markers in line of fire
                from .los import check_los
                los = check_los(attacker.x, attacker.y,
                                target_ord.x, target_ord.y,
                                self.gs.get_phenomena(),
                                self.gs.get_blast_markers())
                shifts += los.get("column_shifts", 0)
                # Targeting matrix
                if "targeting_matrix" in attacker.special_rules:
                    shifts -= 1

                dice_count = lookup_gunnery_dice(avail, COL_ABEAM_ESCORT, shifts)
                self._append_log(
                    f"  {weapon['name']} FP{avail} vs ordnance: "
                    f"{dice_count} dice (col Ordnance, {shifts:+d} shifts)")
            elif wtype == "lance":
                # Lances roll their strength in dice
                dice_count = avail
                self._append_log(
                    f"  {weapon['name']} Str{avail} vs ordnance: "
                    f"{dice_count} dice")
            else:
                dice_count = 0

            if dice_count <= 0:
                self._append_log(f"  No dice to roll")
                dialog.destroy()
                return

            # Roll: 6+ to hit ordnance
            rolls = self.dice.roll_d6(dice_count,
                f"{weapon['name']} vs {target_ord.ordnance_type} (6+ to hit)")
            hits = sum(1 for r in rolls if r >= 6)

            # Track weapon as used
            wr[idx_key] = 0
            attacker.weapons_remaining = wr
            if w_idx not in attacker.weapons_fired_indices:
                attacker.weapons_fired_indices.append(w_idx)
            self.gs.update_ship(attacker)

            if hits > 0:
                # ONE HIT KILLS ENTIRE WAVE/SALVO
                self.gs.ordnance = [
                    o for o in self.gs.ordnance
                    if o["id"] != target_ord.id]
                self._append_log(
                    f"  HIT! {target_ord.ordnance_type} Str{target_ord.strength} "
                    f"destroyed! (rolled {hits} hit(s) on 6+)")
            else:
                self._append_log(
                    f"  MISS! No 6s rolled ({dice_count} dice)")

            dialog.destroy()
            self.board.redraw()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Fire at Ordnance", command=_fire,
                  bg="#663333", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=5)

    def _get_player_bay_capacity(self, player: int) -> int:
        """Total launch bay strength across all non-destroyed, non-disengaged ships for player."""
        total = 0
        for s_dict in self.gs.ships:
            if s_dict["player"] != player:
                continue
            ship = Ship.from_dict(s_dict)
            if ship.is_destroyed or ship.is_disengaged:
                continue
            for w in ship.weapons:
                if w.get("weapon_type") == "launch_bay":
                    total += w.get("strength", 0)
        return total

    def _count_active_craft(self, player: int) -> int:
        """Count attack craft markers currently on the board for player.
        Mines are excluded — they behave like torpedoes, not attack craft."""
        craft_types = {
            OrdnanceType.FIGHTER.value,
            OrdnanceType.BOMBER.value,
            OrdnanceType.MANTA.value,
            OrdnanceType.BARRACUDA.value,
            OrdnanceType.ASSAULT_BOAT.value,
            OrdnanceType.TORPEDO_BOMBER.value,
        }
        return sum(1 for o in self.gs.ordnance
                   if o.get("owner_player") == player
                   and o.get("ordnance_type") in craft_types)

    def _update_cap_positions(self):
        """Sync CAP fighters to their parent ship's current position."""
        ship_pos = {s["id"]: (s["x"], s["y"]) for s in self.gs.ships}
        for i, o_dict in enumerate(self.gs.ordnance):
            cap_id = o_dict.get("cap_ship_id", "")
            if cap_id and cap_id in ship_pos:
                updated = dict(o_dict)
                updated["x"] = ship_pos[cap_id][0]
                updated["y"] = ship_pos[cap_id][1]
                self.gs.ordnance[i] = updated

    def _check_cap_intercept(self, marker: OrdnanceMarker, ship,
                              to_remove_set: set) -> bool:
        """
        Resolve CAP fighter intercepts for incoming ordnance targeting ship.
        Returns True if the marker was destroyed by CAP (skip the ship attack).
        Removes destroyed CAP fighters from gs.ordnance immediately.

        CAP fighters never intercept friendly ordnance — only enemy torpedoes
        and enemy mines.
        """
        from .ordnance import resolve_fighter_intercept, is_fighter_type

        # Friendly ordnance is never intercepted by friendly CAP
        if marker.owner_player == ship.player:
            return False

        cap_to_remove = []
        for o_dict in list(self.gs.ordnance):
            if marker.id in to_remove_set:
                break
            if o_dict.get("cap_ship_id", "") != ship.id:
                continue
            if o_dict.get("owner_player") != ship.player:
                continue
            cap_marker = OrdnanceMarker.from_dict(o_dict)
            if not is_fighter_type(cap_marker):
                continue

            self._append_log(
                f"  CAP fighter intercepts {marker.ordnance_type} "
                f"threatening {ship.name}!")
            result = resolve_fighter_intercept(
                cap_marker, marker, self.dice, self.gs)
            if result["fighter_removed"]:
                cap_to_remove.append(cap_marker.id)
            if result["target_removed"]:
                to_remove_set.add(marker.id)

        if cap_to_remove:
            self.gs.ordnance = [
                o for o in self.gs.ordnance
                if o["id"] not in cap_to_remove]

        return marker.id in to_remove_set

    def _check_destruction(self, ship: Ship):
        """Handle ship destruction - escorts become blast markers, capitals roll catastrophic."""
        ship = self.gs.get_ship_by_id(ship.id)
        if not ship or ship.hits_remaining > 0:
            return

        from .combat import resolve_catastrophic
        result = resolve_catastrophic(ship, self.dice, self.gs)
        self._append_log(f"  {ship.name}: {result}")
        self.board.redraw()

    def _resolve_ordnance_movement(self):
        """Move all ordnance markers in the ordnance phase.
        Order: degrade Tau missiles, move all, blast checks,
        ordnance-vs-ordnance interactions, then ship contacts."""
        from .ordnance import (move_ordnance, degrade_tau_missiles,
                                check_torpedo_contact, resolve_torpedo_attack,
                                resolve_bomber_attack, resolve_mine_contact,
                                check_ordnance_vs_blast,
                                check_ordnance_vs_phenomena,
                                resolve_ordnance_interactions)

        self._append_log("--- Ordnance Movement ---")

        # Sync CAP fighters to their parent ships before movement
        self._update_cap_positions()

        # Degrade Tau missiles from previous turns
        degrade_tau_missiles(self.gs, self.dice, self.gs.turn_number)

        # Check for unmoved Tau missiles - auto-move at minimum speed straight
        for i, o_dict in enumerate(list(self.gs.ordnance)):
            if (o_dict.get("ordnance_type") == OrdnanceType.TORPEDO_GUIDED.value
                    and o_dict.get("owner_player") == self.gs.active_player
                    and not o_dict.get("moved_this_phase", False)):
                marker = OrdnanceMarker.from_dict(o_dict)
                rad = math.radians(marker.heading)
                marker.x += 20 * math.cos(rad)  # minimum speed
                marker.y += 20 * math.sin(rad)
                self.gs.ordnance[i] = marker.to_dict()
                self._append_log(
                    f"  Tau missiles Str {marker.strength} auto-moved 20cm (minimum)")

        ships = self.gs.get_ships()
        blast_markers = self.gs.get_blast_markers()
        phenomena = self.gs.get_phenomena()
        to_remove = set()

        # 1. Move all ordnance
        for i, o_dict in enumerate(list(self.gs.ordnance)):
            marker = OrdnanceMarker.from_dict(o_dict)
            move_ordnance(marker, self.gs)

            # CAP fighters are co-located with their ship; skip off-table check
            if marker.cap_ship_id:
                self.gs.ordnance[i] = marker.to_dict()
                continue

            # Off table check
            if (marker.x < -5 or marker.x > self.gs.table_width + 5 or
                    marker.y < -5 or marker.y > self.gs.table_height + 5):
                to_remove.add(marker.id)
                self._append_log(f"  {marker.ordnance_type} left the table")
                continue

            # Blast marker destruction (D6=6)
            if check_ordnance_vs_blast(marker, blast_markers, self.dice):
                to_remove.add(marker.id)
                self._append_log(f"  {marker.ordnance_type} destroyed by blast marker")
                continue

            # Terrain check: applies to all ordnance types.
            # Torpedoes/mines: asteroid/planet/warp rift = auto-destroyed; dust = D6=6.
            # Attack craft: asteroid = D6=6; warp rift/planet = auto-destroyed.
            destroyed, terrain_type = check_ordnance_vs_phenomena(
                marker, phenomena, self.dice)
            if destroyed:
                to_remove.add(marker.id)
                self._append_log(
                    f"  {marker.ordnance_type} destroyed by {terrain_type}")
                continue

            # Update position
            self.gs.ordnance[i] = marker.to_dict()

        # Remove off-table and blast-destroyed ordnance
        if to_remove:
            self.gs.ordnance = [
                o for o in self.gs.ordnance if o["id"] not in to_remove]

        # 2. Ordnance-vs-ordnance interactions (fighters intercept, torp collisions)
        interaction_logs = resolve_ordnance_interactions(self.gs, self.dice)
        for log in interaction_logs:
            self._append_log(log)

        # 3. Check ordnance contact with ships
        # Torpedoes hit ALL ships (friendly fire!) unless launched through base contact
        to_remove_after = set()
        for o_dict in list(self.gs.ordnance):
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.id in to_remove_after:
                continue

            is_torp = "torpedo" in marker.ordnance_type
            is_bomber = marker.ordnance_type in (
                OrdnanceType.BOMBER.value, OrdnanceType.MANTA.value)
            is_assault_boat = marker.ordnance_type == OrdnanceType.ASSAULT_BOAT.value

            if is_torp:
                # Torpedoes attack ANY ship they contact (friend or foe)
                for s in ships:
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue
                    if not check_torpedo_contact(marker, s):
                        continue

                    # CAP fighters intercept before the torpedo hits
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self._append_log(
                        f"  Torpedoes contact {s.name}"
                        + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                        + f"!")
                    result = resolve_torpedo_attack(
                        marker, s, self.dice, self.gs,
                        all_ships=ships)

                    # Reduce salvo strength by hits inflicted, continue if strength remains
                    marker.strength -= result["hits"]
                    if result["hits"] > 0:
                        self._check_destruction(s)
                    if marker.strength <= 0:
                        to_remove_after.add(marker.id)
                        break
                    # Update marker for next ship in path
                    for j, od in enumerate(self.gs.ordnance):
                        if od["id"] == marker.id:
                            self.gs.ordnance[j] = marker.to_dict()
                            break

            elif is_bomber:
                # Bombers attack enemy ships only
                for s in ships:
                    if s.player == marker.owner_player:
                        continue
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    dist = math.sqrt(
                        (marker.x - s.x)**2 + (marker.y - s.y)**2)
                    if dist <= s.base_radius + 1.5:
                        # CAP fighters intercept before the bomber attacks
                        if self._check_cap_intercept(marker, s, to_remove_after):
                            break

                        self._append_log(
                            f"  {marker.ordnance_type} attacks {s.name}!")

                        # Count friendly fighters in contact with this target
                        # (same player as bomber, within base contact range)
                        contact_r = s.base_radius + 2.0
                        suppressing_fighters = sum(
                            1 for od in self.gs.ordnance
                            if od.get("owner_player") == marker.owner_player
                            and od.get("ordnance_type") in (
                                OrdnanceType.FIGHTER.value,
                                OrdnanceType.BARRACUDA.value,
                                OrdnanceType.MANTA.value)
                            and math.sqrt((od.get("x", 0) - s.x)**2
                                          + (od.get("y", 0) - s.y)**2) <= contact_r)

                        # Count all bombers from same player contacting this ship
                        # (needed for Remastered cap)
                        total_bombers_on_target = sum(
                            1 for od in self.gs.ordnance
                            if od.get("owner_player") == marker.owner_player
                            and od.get("ordnance_type") in (
                                OrdnanceType.BOMBER.value, OrdnanceType.MANTA.value)
                            and math.sqrt((od.get("x", 0) - s.x)**2
                                          + (od.get("y", 0) - s.y)**2)
                                <= s.base_radius + 1.5)

                        if suppressing_fighters > 0:
                            if self.gs.rule_turret_suppression_remastered:
                                # Remastered: fighters add +1 to attack roll,
                                # capped at total attacking bombers
                                result = resolve_bomber_attack(
                                    marker, s, self.dice, self.gs,
                                    remastered_fighter_bonus=suppressing_fighters,
                                    remastered_bomber_cap=total_bombers_on_target,
                                    all_ships=ships)
                            else:
                                # XR default: this bomber gets exactly 3 attacks
                                result = resolve_bomber_attack(
                                    marker, s, self.dice, self.gs,
                                    suppressed_by_fighter=True,
                                    all_ships=ships)
                        else:
                            result = resolve_bomber_attack(
                                marker, s, self.dice, self.gs,
                                all_ships=ships)

                        if result["hits"] > 0:
                            self._check_destruction(s)
                        to_remove_after.add(marker.id)
                        break

            elif marker.ordnance_type == OrdnanceType.MINE_FIELD.value:
                # Mine fields detonate against any ship in contact.
                # Friendly fire is safe on the turn the mine was laid,
                # but is a hazard from the following turn onward.
                for s in ships:
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue
                    if (s.player == marker.owner_player
                            and self.gs.turn_number == marker.launched_turn):
                        continue  # safe on launch turn
                    dist = math.sqrt(
                        (marker.x - s.x)**2 + (marker.y - s.y)**2)
                    if dist <= s.base_radius + 1.5:
                        self._append_log(
                            f"  Mine contacts {s.name}"
                            + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                            + "!")
                        result = resolve_mine_contact(
                            marker, s, self.dice, self.gs)
                        if result["hits"] > 0:
                            self._check_destruction(s)
                        to_remove_after.add(marker.id)
                        break  # one ship triggers the field

            elif is_assault_boat:
                # Assault boats trigger hit-and-run raids against enemy ships
                from .hit_and_run import resolve_hit_and_run
                for s in ships:
                    if s.player == marker.owner_player:
                        continue
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue
                    dist = math.sqrt(
                        (marker.x - s.x)**2 + (marker.y - s.y)**2)
                    if dist > s.base_radius + 1.5:
                        continue

                    # CAP fighters intercept before the raid
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self._append_log(
                        f"  Assault boats contact {s.name} — hit-and-run raid!")

                    def _brace_fn(target_ship, msg, _s=s):
                        from .movement import do_command_check
                        if target_ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                            self._append_log(
                                f"  {target_ship.name} already braced — "
                                f"will roll to repel each raid")
                            return True, True
                        want = messagebox.askyesno("Hit-and-Run Raid — Brace?", msg)
                        if not want:
                            return False, False
                        check = do_command_check(target_ship, "brace_for_impact",
                                                 self.dice)
                        passed = check["passed"]
                        self._append_log(
                            f"  {target_ship.name} brace check: "
                            f"{'PASSED' if passed else 'FAILED'} "
                            f"(rolled {check['roll']} vs Ld {check['needed']})")
                        if passed:
                            target_ship.previous_order = target_ship.special_order
                            target_ship.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
                            target_ship.brace_set_on_turn = self.gs.turn_number
                            self.gs.update_ship(target_ship)
                        return True, passed

                    result = resolve_hit_and_run(
                        marker, s, self.dice, self.gs, _brace_fn)

                    n_crits = len(result["crits_applied"])
                    n_repelled = result["repelled"]
                    n_failed = result["failures"]
                    self._append_log(
                        f"  Raid result: {n_crits} crit(s) applied, "
                        f"{n_repelled} repelled, {n_failed} failed")
                    self._check_destruction(s)
                    to_remove_after.add(marker.id)
                    break

        # Remove spent ordnance
        if to_remove_after:
            self.gs.ordnance = [
                o for o in self.gs.ordnance
                if o["id"] not in to_remove_after]

        self._append_log(
            f"  Ordnance phase complete: {len(self.gs.ordnance)} markers remain")
        self.board.redraw()

    def _launch_ordnance_dialog(self):
        """Dialog to launch torpedoes or attack craft with heading and composition control."""
        all_active = [Ship.from_dict(s) for s in self.gs.ships
                      if s["player"] == self.gs.active_player
                      and not Ship.from_dict(s).is_destroyed
                      and not s.get("is_disengaged", False)]
        launchers = [s for s in all_active
                     if s.ordnance_loaded_torps or s.ordnance_loaded_craft]
        if not launchers:
            messagebox.showinfo("No Ordnance", "No ships with loaded ordnance")
            return

        ship = self._pick_ship_dialog(launchers, "Select ship to launch from")
        if not ship:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Launch Ordnance - {ship.name}")
        dialog.geometry("500x550")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Launch from {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=3)
        tk.Label(dialog, text=f"Heading: {ship.heading:.0f}°",
                 font=("Consolas", 8)).pack()

        notebook_frame = tk.Frame(dialog)
        notebook_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Find launchable weapons
        torp_weapons = []
        mine_weapons = []
        bay_weapons = []
        for w in ship.weapons:
            wtype = w.get("weapon_type", "")
            if wtype in ("torpedo", "gravitic_launcher") and ship.ordnance_loaded_torps:
                torp_weapons.append(w)
            elif wtype == "mine_launcher" and ship.ordnance_loaded_craft:
                mine_weapons.append(w)
            elif wtype == "launch_bay" and ship.ordnance_loaded_craft:
                bay_weapons.append(w)

        # --- TORPEDO SECTION ---
        if torp_weapons:
            torp_frame = tk.LabelFrame(notebook_frame, text="Torpedoes / Missiles",
                                        font=("Consolas", 9, "bold"))
            torp_frame.pack(fill=tk.X, pady=3)

            for tw in torp_weapons:
                total_str = tw["strength"]
                # Halve for crippled, then halve again for braced (cumulative)
                halve_reasons = []
                if ship.is_crippled:
                    total_str = (total_str + 1) // 2
                    halve_reasons.append("crippled")
                if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                    total_str = (total_str + 1) // 2
                    halve_reasons.append("braced")

                is_guided = tw.get("torpedo_type") == "guided"
                label = "Guided Missiles" if is_guided else "Torpedoes"
                torp_speed = tw.get("torpedo_speed", 30)
                halve_note = f" [{', '.join(halve_reasons)}]" if halve_reasons else ""

                tk.Label(torp_frame,
                         text=f"{tw['name']}: Str {total_str}, Speed {torp_speed}cm"
                              + (" [GUIDED]" if is_guided else "") + halve_note,
                         font=("Consolas", 8)).pack(anchor=tk.W, padx=5)

                # Heading control (within forward arc: ship heading +/- 45°)
                head_frame = tk.Frame(torp_frame)
                head_frame.pack(fill=tk.X, padx=10, pady=2)
                tk.Label(head_frame, text="Launch heading:",
                         font=("Consolas", 8)).pack(side=tk.LEFT)
                heading_var = tk.StringVar(value=f"{ship.heading:.0f}")
                tk.Entry(head_frame, textvariable=heading_var, width=6,
                         font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
                tk.Label(head_frame,
                         text=f"(forward arc: {ship.heading-45:.0f}° to {ship.heading+45:.0f}°)",
                         font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)

                # Split volley (only Str 7+ can split, into exactly two)
                split_frame = tk.Frame(torp_frame)
                split_frame.pack(fill=tk.X, padx=10, pady=2)
                str_var = tk.StringVar(value=str(total_str))
                if total_str >= 7:
                    tk.Label(split_frame, text="Strength to launch:",
                             font=("Consolas", 8)).pack(side=tk.LEFT)
                    tk.Entry(split_frame, textvariable=str_var, width=4,
                             font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
                    tk.Label(split_frame,
                             text=f"(Str {total_str}: can split into two salvos, min 1 each)",
                             font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)
                else:
                    tk.Label(split_frame,
                             text=f"Full salvo: Str {total_str} (splitting requires Str 7+)",
                             font=("Consolas", 8), fg="#888888").pack(side=tk.LEFT)

                def _launch_torps(w=tw, hv=heading_var, sv=str_var,
                                   effective_str=total_str):
                    try:
                        heading = float(hv.get())
                        strength = int(sv.get())
                    except ValueError:
                        messagebox.showerror("Error", "Invalid heading or strength")
                        return

                    # Validate heading within forward arc (+/- 45°)
                    diff = (heading - ship.heading + 180) % 360 - 180
                    if abs(diff) > 45:
                        messagebox.showerror("Error",
                            f"Heading {heading:.0f}° is outside forward arc "
                            f"({ship.heading-45:.0f}° to {ship.heading+45:.0f}°)")
                        return

                    # Use the already-halved effective strength as the cap
                    total = effective_str
                    # Enforce split rules
                    if total < 7:
                        strength = total  # can't split below Str 7
                    else:
                        strength = max(1, min(strength, total))

                    is_g = w.get("torpedo_type") == "guided"
                    o_type = (OrdnanceType.TORPEDO_GUIDED.value if is_g
                              else OrdnanceType.TORPEDO_STANDARD.value)

                    import random as _rng

                    # First (or only) salvo
                    marker = OrdnanceMarker(
                        id=f"torp_{ship.id}_{self.gs.turn_number}_{_rng.randint(0,9999)}",
                        ordnance_type=o_type,
                        owner_player=ship.player,
                        launched_by=ship.id,
                        x=ship.x, y=ship.y,
                        heading=heading,
                        strength=strength,
                        speed=w.get("torpedo_speed", 30),
                        launched_turn=self.gs.turn_number,
                        can_turn=is_g,
                        turn_angle=45 if is_g else 0,
                    )
                    self.gs.add_ordnance(marker)

                    name = "guided missiles" if is_g else "torpedoes"
                    self._append_log(
                        f"{ship.name} launched {name} Str {strength} "
                        f"heading {heading:.0f}°")

                    # Second salvo if split
                    remainder = total - strength
                    if remainder > 0:
                        marker2 = OrdnanceMarker(
                            id=f"torp_{ship.id}_{self.gs.turn_number}_{_rng.randint(0,9999)}_b",
                            ordnance_type=o_type,
                            owner_player=ship.player,
                            launched_by=ship.id,
                            x=ship.x, y=ship.y,
                            heading=heading,  # same heading for now
                            strength=remainder,
                            speed=w.get("torpedo_speed", 30),
                            launched_turn=self.gs.turn_number,
                            can_turn=is_g,
                            turn_angle=45 if is_g else 0,
                        )
                        self.gs.add_ordnance(marker2)
                        self._append_log(
                            f"  Split salvo: second volley Str {remainder} "
                            f"heading {heading:.0f}°")

                    ship_fresh = self.gs.get_ship_by_id(ship.id)
                    if ship_fresh:
                        ship_fresh.ordnance_loaded_torps = False
                        self.gs.update_ship(ship_fresh)

                    dialog.destroy()
                    self.board.redraw()

                tk.Button(torp_frame, text=f"Launch {label}",
                          command=_launch_torps,
                          bg="#663333", fg="white",
                          font=("Consolas", 9)).pack(pady=3)

        # --- MINE LAUNCHER SECTION ---
        if mine_weapons:
            mine_frame = tk.LabelFrame(notebook_frame, text="Mine Launcher",
                                        font=("Consolas", 9, "bold"))
            mine_frame.pack(fill=tk.X, pady=3)

            for mw in mine_weapons:
                mine_str = mw["strength"]
                mine_halve_reasons = []
                if ship.is_crippled:
                    mine_str = (mine_str + 1) // 2
                    mine_halve_reasons.append("crippled")
                if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                    mine_str = (mine_str + 1) // 2
                    mine_halve_reasons.append("braced")

                halve_note = f" [{', '.join(mine_halve_reasons)}]" if mine_halve_reasons else ""
                tk.Label(mine_frame,
                         text=f"{mw['name']}: {mine_str} mine launcher(s)"
                              + " — 1 mine per launcher, 10cm/turn homing" + halve_note,
                         font=("Consolas", 8)).pack(anchor=tk.W, padx=5)
                tk.Label(mine_frame,
                         text="Each mine attacks with 8D6 vs armor (4D6 if turrets roll 4+). "
                              "Shields apply.",
                         font=("Consolas", 7), fg="#888888").pack(anchor=tk.W, padx=5)

                def _lay_mines(w=mw, effective_str=mine_str):
                    import random as _rng
                    spd = w.get("mine_speed", 10)
                    for i in range(effective_str):
                        # Each mine launcher fires one independent mine marker
                        marker = OrdnanceMarker(
                            id=f"mine_{ship.id}_{self.gs.turn_number}_{i}_{_rng.randint(0,9999)}",
                            ordnance_type=OrdnanceType.MINE_FIELD.value,
                            owner_player=ship.player,
                            launched_by=ship.id,
                            x=ship.x + (i - effective_str / 2) * 1.5,
                            y=ship.y,
                            heading=ship.heading,
                            strength=1,
                            speed=spd,
                            launched_turn=self.gs.turn_number,
                        )
                        self.gs.add_ordnance(marker)

                    ship_fresh = self.gs.get_ship_by_id(ship.id)
                    if ship_fresh:
                        ship_fresh.ordnance_loaded_craft = False
                        self.gs.update_ship(ship_fresh)

                    self._append_log(
                        f"{ship.name} launches {effective_str} mine(s)")
                    dialog.destroy()
                    self.board.redraw()

                tk.Button(mine_frame, text="Lay Mine Field",
                          command=_lay_mines,
                          bg="#664400", fg="white",
                          font=("Consolas", 9)).pack(pady=3)

        # --- ATTACK CRAFT SECTION ---
        if bay_weapons:
            # Fleet-wide cap check before building the UI
            fleet_bay_cap = self._get_player_bay_capacity(ship.player)
            active_craft = self._count_active_craft(ship.player)
            fleet_remaining = max(0, fleet_bay_cap - active_craft)

            bay_frame = tk.LabelFrame(notebook_frame, text="Attack Craft",
                                       font=("Consolas", 9, "bold"))
            bay_frame.pack(fill=tk.X, pady=3)

            # Fleet capacity status line
            cap_color = "#FF4444" if fleet_remaining == 0 else (
                "#FFAA00" if fleet_remaining < fleet_bay_cap // 2 else "#44AA44")
            tk.Label(bay_frame,
                     text=f"Fleet capacity: {fleet_bay_cap} bays total | "
                          f"{active_craft} active | {fleet_remaining} slots free",
                     font=("Consolas", 8), fg=cap_color).pack(anchor=tk.W, padx=5)

            if fleet_remaining == 0:
                tk.Label(bay_frame,
                         text="All fleet launch bay slots are occupied. "
                              "Attack craft must be destroyed or return before more can launch.",
                         font=("Consolas", 7), fg="#FF4444",
                         wraplength=460, justify=tk.LEFT).pack(anchor=tk.W, padx=5)

            # Combine all bays on this ship
            total_bays = sum(w["strength"] for w in bay_weapons)
            # Halve for crippled, then halve again for braced (cumulative)
            bay_halve_reasons = []
            if ship.is_crippled:
                total_bays = (total_bays + 1) // 2
                bay_halve_reasons.append("crippled")
            if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                total_bays = (total_bays + 1) // 2
                bay_halve_reasons.append("braced")
            # Cap by remaining fleet capacity
            total_bays = min(total_bays, fleet_remaining)

            available_types = set()
            for w in bay_weapons:
                for ct in w.get("craft_types", w.get("craft", [])):
                    available_types.add(ct)

            bay_cap_label = f"This ship can launch: {total_bays} squadrons"
            if bay_halve_reasons:
                bay_cap_label += f" [{', '.join(bay_halve_reasons)}]"
            if fleet_remaining < sum(w["strength"] for w in bay_weapons):
                bay_cap_label += f" (fleet cap limits to {total_bays})"
            tk.Label(bay_frame,
                     text=bay_cap_label,
                     font=("Consolas", 8)).pack(anchor=tk.W, padx=5)
            tk.Label(bay_frame,
                     text=f"Available types: {', '.join(sorted(available_types))}",
                     font=("Consolas", 8)).pack(anchor=tk.W, padx=5)

            # Composition picker: one row per craft type
            CRAFT_NAMES = {
                "fury_fighter": "Fury Interceptors (fighters)",
                "starhawk_bomber": "Starhawk Bombers",
                "manta": "Manta (fighter+bomber, resilient)",
                "barracuda": "Barracuda (fighters)",
            }
            composition_vars = {}
            comp_frame = tk.Frame(bay_frame)
            comp_frame.pack(fill=tk.X, padx=10, pady=3)

            for ct in sorted(available_types):
                row = tk.Frame(comp_frame)
                row.pack(fill=tk.X)
                name = CRAFT_NAMES.get(ct, ct)
                tk.Label(row, text=f"{name}:", font=("Consolas", 8),
                         width=30, anchor=tk.W).pack(side=tk.LEFT)
                var = tk.StringVar(value="0")
                composition_vars[ct] = var
                tk.Entry(row, textvariable=var, width=3,
                         font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)

            # Heading control for craft
            craft_head_frame = tk.Frame(bay_frame)
            craft_head_frame.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(craft_head_frame, text="Launch heading:",
                     font=("Consolas", 8)).pack(side=tk.LEFT)
            craft_heading_var = tk.StringVar(value=f"{ship.heading:.0f}")
            tk.Entry(craft_head_frame, textvariable=craft_heading_var, width=6,
                     font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)

            # CAP assignment: fighters only; protect a friendly ship
            cap_frame = tk.Frame(bay_frame)
            cap_frame.pack(fill=tk.X, padx=10, pady=2)
            cap_var = tk.BooleanVar(value=False)
            tk.Checkbutton(cap_frame, text="Assign fighters to CAP",
                           variable=cap_var,
                           font=("Consolas", 8)).pack(side=tk.LEFT)

            own_ships_for_cap = [
                Ship.from_dict(s) for s in self.gs.ships
                if s["player"] == ship.player
                and not Ship.from_dict(s).is_destroyed
                and not s.get("is_disengaged", False)]
            cap_ship_id_map = {s.name: s.id for s in own_ships_for_cap}
            cap_ship_pos_map = {s.id: (s.x, s.y) for s in own_ships_for_cap}
            cap_ship_names = [s.name for s in own_ships_for_cap]
            cap_protect_var = tk.StringVar(value=ship.name)
            if cap_ship_names:
                tk.Label(cap_frame, text="  Protect:",
                         font=("Consolas", 8)).pack(side=tk.LEFT)
                cap_menu = tk.OptionMenu(cap_frame, cap_protect_var,
                                         *cap_ship_names)
                cap_menu.config(font=("Consolas", 8), width=14)
                cap_menu.pack(side=tk.LEFT, padx=3)
            tk.Label(cap_frame,
                     text="(fighters only; bombers still free-roam)",
                     font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)

            # Quick buttons
            quick_craft = tk.Frame(bay_frame)
            quick_craft.pack(fill=tk.X, padx=10, pady=2)

            def _set_all_fighters():
                for ct, v in composition_vars.items():
                    v.set("0")
                fighter_key = next(
                    (k for k in composition_vars
                     if k in ("fury_fighter", "barracuda")), None)
                if fighter_key:
                    composition_vars[fighter_key].set(str(total_bays))

            def _set_all_bombers():
                for ct, v in composition_vars.items():
                    v.set("0")
                bomber_key = next(
                    (k for k in composition_vars
                     if k in ("starhawk_bomber", "manta")), None)
                if bomber_key:
                    composition_vars[bomber_key].set(str(total_bays))

            def _set_mixed():
                for ct, v in composition_vars.items():
                    v.set("0")
                types_list = sorted(available_types)
                if len(types_list) >= 2:
                    half = total_bays // 2
                    composition_vars[types_list[0]].set(str(half))
                    composition_vars[types_list[1]].set(str(total_bays - half))
                elif types_list:
                    composition_vars[types_list[0]].set(str(total_bays))

            tk.Button(quick_craft, text="All Fighters", command=_set_all_fighters,
                      font=("Consolas", 7)).pack(side=tk.LEFT, padx=2)
            tk.Button(quick_craft, text="All Bombers", command=_set_all_bombers,
                      font=("Consolas", 7)).pack(side=tk.LEFT, padx=2)
            tk.Button(quick_craft, text="Mixed", command=_set_mixed,
                      font=("Consolas", 7)).pack(side=tk.LEFT, padx=2)

            def _launch_craft():
                try:
                    heading = float(craft_heading_var.get())
                except ValueError:
                    messagebox.showerror("Error", "Invalid heading")
                    return

                # Re-check fleet cap at launch time (may have changed)
                current_remaining = max(
                    0, self._get_player_bay_capacity(ship.player)
                       - self._count_active_craft(ship.player))
                if current_remaining == 0:
                    messagebox.showwarning(
                        "Fleet At Capacity",
                        "All fleet launch bay slots are occupied.\n"
                        "Existing attack craft must be destroyed or complete "
                        "their mission before more can be launched.")
                    return

                total_launched = 0
                CRAFT_STATS = {
                    "manta": (OrdnanceType.MANTA.value, 20, 4),
                    "barracuda": (OrdnanceType.BARRACUDA.value, 25, 0),
                    "fury_fighter": (OrdnanceType.FIGHTER.value, 30, 0),
                    "starhawk_bomber": (OrdnanceType.BOMBER.value, 20, 0),
                }

                import random as _rng
                for ct, var in composition_vars.items():
                    try:
                        count = int(var.get())
                    except ValueError:
                        continue
                    if count <= 0:
                        continue

                    o_type, spd, resil = CRAFT_STATS.get(
                        ct, (OrdnanceType.FIGHTER.value, 30, 0))

                    # CAP only applies to fighter-type craft
                    fighter_types = (OrdnanceType.FIGHTER.value,
                                     OrdnanceType.BARRACUDA.value,
                                     OrdnanceType.MANTA.value)
                    assign_cap = cap_var.get() and o_type in fighter_types
                    protect_id = cap_ship_id_map.get(
                        cap_protect_var.get(), ship.id) if assign_cap else ""
                    protect_pos = cap_ship_pos_map.get(
                        protect_id, (ship.x, ship.y)) if assign_cap else (ship.x, ship.y)

                    for i in range(count):
                        if total_launched >= current_remaining:
                            break  # fleet cap reached mid-launch
                        px = protect_pos[0] + (i - count / 2) * 1.5
                        py = protect_pos[1]
                        marker = OrdnanceMarker(
                            id=f"craft_{ship.id}_{ct}_{self.gs.turn_number}_{_rng.randint(0,9999)}",
                            ordnance_type=o_type,
                            owner_player=ship.player,
                            launched_by=ship.id,
                            x=px if assign_cap else ship.x + (i - count / 2) * 1.5,
                            y=py if assign_cap else ship.y,
                            heading=heading,
                            strength=1,
                            speed=spd,
                            launched_turn=self.gs.turn_number,
                            resilient_save=resil,
                            cap_ship_id=protect_id,
                        )
                        self.gs.add_ordnance(marker)
                        total_launched += 1

                if total_launched == 0:
                    messagebox.showwarning("No Craft",
                        "Set at least one craft type to a non-zero count")
                    return

                if total_launched > total_bays:
                    messagebox.showwarning("Over Capacity",
                        f"Launched {total_launched} but only have {total_bays} bays. "
                        f"Excess will be placed anyway.")

                ship_fresh = self.gs.get_ship_by_id(ship.id)
                if ship_fresh:
                    ship_fresh.ordnance_loaded_craft = False
                    self.gs.update_ship(ship_fresh)

                if cap_var.get():
                    protect_name = cap_protect_var.get()
                    self._append_log(
                        f"{ship.name} launched {total_launched} attack craft "
                        f"on CAP for {protect_name}")
                else:
                    self._append_log(
                        f"{ship.name} launched {total_launched} attack craft "
                        f"heading {heading:.0f}°")
                dialog.destroy()
                self.board.redraw()

            tk.Button(bay_frame, text="Launch Attack Craft",
                      command=_launch_craft,
                      bg="#663333", fg="white",
                      font=("Consolas", 9)).pack(pady=3)

        # Cancel
        tk.Button(dialog, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(pady=5)

    # --- Disengagement ---

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

    def _weapon_disabled_by_crit(self, ship: Ship, weapon: dict) -> bool:
        """Check if a weapon is disabled by critical damage."""
        arcs = weapon.get("arcs", [])
        for crit in ship.critical_damage:
            ct = crit.get("crit_type", "")
            if ct == "dorsal_armament" and "dorsal" in weapon["name"].lower():
                return True
            if ct == "port_armament" and "port" in weapon["name"].lower():
                return True
            if ct == "starboard_armament" and "starboard" in weapon["name"].lower():
                return True
            if ct == "prow_armament" and "prow" in weapon["name"].lower():
                return True
            # Also check by arc matching
            if ct == "port_armament" and arcs == ["left"]:
                return True
            if ct == "starboard_armament" and arcs == ["right"]:
                return True
        return False
