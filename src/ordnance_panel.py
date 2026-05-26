"""BFG:XR — OrdnancePanel: ordnance launch, movement, and contact resolution."""
import tkinter as tk
from tkinter import messagebox, simpledialog
import math
from typing import Optional, Callable, List

from .models import Ship, SpecialOrder, OrdnanceMarker, OrdnanceType
from .game_context import GameContext


class OrdnancePanel:
    """Handles ordnance phase UI: launch dialogs, movement, mine/torp/bomber contact."""

    def __init__(self, ctx: GameContext):
        self.ctx = ctx

    def _move_tau_missiles_dialog(self):
        """Player-controlled Tau missile movement. Reuses ship movement concepts:
        choose speed (20-40cm), optional 45° turn at start, quick buttons."""
        tau_missiles = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance
                        if o["ordnance_type"] == OrdnanceType.TORPEDO_GUIDED.value
                        and o["owner_player"] == self.ctx.gs.active_player
                        and not o.get("moved_this_phase", False)]
        if not tau_missiles:
            messagebox.showinfo("No Missiles",
                "No unmoved Tau missile salvos this phase")
            return

        # Pick which salvo to move
        if len(tau_missiles) == 1:
            missile = tau_missiles[0]
        else:
            dialog = tk.Toplevel(self.ctx.root)
            dialog.title("Select Missile Salvo")
            dialog.geometry("350x300")
            dialog.transient(self.ctx.root)
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
            self.ctx.root.wait_window(dialog)
            missile = selected[0]
            if not missile:
                return

        # Movement dialog (similar to ship movement)
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Move Tau Missiles (Str {missile.strength})")
        dialog.geometry("480x450")
        dialog.transient(self.ctx.root)

        tk.Label(dialog, text=f"Tau Missile Salvo Str {missile.strength}",
                 font=("Consolas", 11, "bold")).pack(pady=3)

        can_turn = missile.launched_turn < self.ctx.gs.turn_number  # can't turn on launch turn
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
            self.ctx.board.redraw()
            sx0, sy0 = self.ctx.board.cm_to_screen(missile.x, missile.y)
            sx1, sy1 = self.ctx.board.cm_to_screen(end_x, end_y)
            self.ctx.board.canvas.create_line(sx0, sy0, sx1, sy1,
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
            for j, o_dict in enumerate(self.ctx.gs.ordnance):
                if o_dict["id"] == missile.id:
                    updated = missile.to_dict()
                    updated["moved_this_phase"] = True
                    self.ctx.gs.ordnance[j] = updated
                    break

            turn_desc = f", turned {turn_applied[0]:+.0f}°" if turn_applied[0] != 0 else ""
            self.ctx.log(
                f"Tau missiles Str {missile.strength} moved {spd:.0f}cm"
                f"{turn_desc} to ({missile.x:.0f}, {missile.y:.0f})")
            dialog.destroy()
            self.ctx.board.redraw()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Confirm Move", command=_confirm,
                  bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=5)

    def _get_player_bay_capacity(self, player: int) -> int:
        """Total launch bay strength across all non-destroyed, non-disengaged ships for player."""
        total = 0
        for s_dict in self.ctx.gs.ships:
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
        return sum(1 for o in self.ctx.gs.ordnance
                   if o.get("owner_player") == player
                   and o.get("ordnance_type") in craft_types)

    def _update_cap_positions(self):
        """Sync CAP fighters to their parent ship's current position."""
        ship_pos = {s["id"]: (s["x"], s["y"]) for s in self.ctx.gs.ships}
        for i, o_dict in enumerate(self.ctx.gs.ordnance):
            cap_id = o_dict.get("cap_ship_id", "")
            if cap_id and cap_id in ship_pos:
                updated = dict(o_dict)
                updated["x"] = ship_pos[cap_id][0]
                updated["y"] = ship_pos[cap_id][1]
                self.ctx.gs.ordnance[i] = updated

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
        for o_dict in list(self.ctx.gs.ordnance):
            if marker.id in to_remove_set:
                break
            if o_dict.get("cap_ship_id", "") != ship.id:
                continue
            if o_dict.get("owner_player") != ship.player:
                continue
            cap_marker = OrdnanceMarker.from_dict(o_dict)
            if not is_fighter_type(cap_marker):
                continue

            self.ctx.log(
                f"  CAP fighter intercepts {marker.ordnance_type} "
                f"threatening {ship.name}!")
            result = resolve_fighter_intercept(
                cap_marker, marker, self.ctx.dice, self.ctx.gs)
            if result["fighter_removed"]:
                cap_to_remove.append(cap_marker.id)
            if result["target_removed"]:
                to_remove_set.add(marker.id)

        if cap_to_remove:
            self.ctx.gs.ordnance = [
                o for o in self.ctx.gs.ordnance
                if o["id"] not in cap_to_remove]

        return marker.id in to_remove_set

    def _resolve_ordnance_movement(self):
        """Move all ordnance markers in the ordnance phase.
        Order: degrade Tau missiles, move all, blast checks,
        ordnance-vs-ordnance interactions, then ship contacts."""
        from .ordnance import (move_ordnance, degrade_tau_missiles,
                                check_torpedo_contact, resolve_torpedo_attack,
                                resolve_bomber_attack, resolve_mine_contact,
                                check_ordnance_vs_blast,
                                check_ordnance_vs_phenomena,
                                resolve_ordnance_interactions,
                                resolve_bomber_interception)
        from .geometry import (circle_touches_square, circle_touches_torpedo,
                                ATTACK_CRAFT_HALF_SIDE_CM)

        self.ctx.log("--- Ordnance Movement ---")

        # Sync CAP fighters to their parent ships before movement
        self._update_cap_positions()

        # Degrade Tau missiles from previous turns
        degrade_tau_missiles(self.ctx.gs, self.ctx.dice, self.ctx.gs.turn_number)

        # Check for unmoved Tau missiles - auto-move at minimum speed straight
        for i, o_dict in enumerate(list(self.ctx.gs.ordnance)):
            if (o_dict.get("ordnance_type") == OrdnanceType.TORPEDO_GUIDED.value
                    and o_dict.get("owner_player") == self.ctx.gs.active_player
                    and not o_dict.get("moved_this_phase", False)):
                marker = OrdnanceMarker.from_dict(o_dict)
                rad = math.radians(marker.heading)
                marker.x += 20 * math.cos(rad)  # minimum speed
                marker.y += 20 * math.sin(rad)
                self.ctx.gs.ordnance[i] = marker.to_dict()
                self.ctx.log(
                    f"  Tau missiles Str {marker.strength} auto-moved 20cm (minimum)")

        ships = self.ctx.gs.get_ships()
        blast_markers = self.ctx.gs.get_blast_markers()
        phenomena = self.ctx.gs.get_phenomena()
        to_remove = set()

        # 1. Move all ordnance
        for i, o_dict in enumerate(list(self.ctx.gs.ordnance)):
            marker = OrdnanceMarker.from_dict(o_dict)
            move_ordnance(marker, self.ctx.gs)

            # CAP fighters are co-located with their ship; skip off-table check
            if marker.cap_ship_id:
                self.ctx.gs.ordnance[i] = marker.to_dict()
                continue

            # Off table check
            if (marker.x < -5 or marker.x > self.ctx.gs.table_width + 5 or
                    marker.y < -5 or marker.y > self.ctx.gs.table_height + 5):
                to_remove.add(marker.id)
                self.ctx.log(f"  {marker.ordnance_type} left the table")
                continue

            # Blast marker destruction (D6=6)
            if check_ordnance_vs_blast(marker, blast_markers, self.ctx.dice):
                to_remove.add(marker.id)
                self.ctx.log(f"  {marker.ordnance_type} destroyed by blast marker")
                continue

            # Terrain check: applies to all ordnance types.
            # Torpedoes/mines: asteroid/planet/warp rift = auto-destroyed; dust = D6=6.
            # Attack craft: asteroid = D6=6; warp rift/planet = auto-destroyed.
            destroyed, terrain_type = check_ordnance_vs_phenomena(
                marker, phenomena, self.ctx.dice)
            if destroyed:
                to_remove.add(marker.id)
                self.ctx.log(
                    f"  {marker.ordnance_type} destroyed by {terrain_type}")
                continue

            # Update position
            self.ctx.gs.ordnance[i] = marker.to_dict()

        # Remove off-table and blast-destroyed ordnance
        if to_remove:
            self.ctx.gs.ordnance = [
                o for o in self.ctx.gs.ordnance if o["id"] not in to_remove]

        # 2. Ordnance-vs-ordnance interactions (fighters intercept, torp collisions)
        interaction_logs = resolve_ordnance_interactions(self.ctx.gs, self.ctx.dice)
        for log in interaction_logs:
            self.ctx.log(log)

        # 3. Check ordnance contact with ships
        to_remove_after = set()

        # Phase 1: bomber wave interception — turrets (with massed bonus) fire once
        # per ship at every incoming bomber wave before individual attacks resolve.
        live_ordnance = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance]
        for s in ships:
            if s.is_destroyed or s.is_disengaged:
                continue
            # Collect enemy bomber markers currently contacting this ship
            wave = [
                m for m in live_ordnance
                if m.ordnance_type in (OrdnanceType.BOMBER.value,
                                       OrdnanceType.MANTA.value)
                and m.owner_player != s.player
                and m.id not in to_remove
                and circle_touches_square(s.x, s.y, s.base_radius,
                                          m.x, m.y, m.heading)
            ]
            if not wave:
                continue
            p1 = resolve_bomber_interception(
                len(wave), s, ships, self.ctx.dice, self.ctx.gs)
            for msg in p1["log"]:
                self.ctx.log(msg)
            for m in wave[:p1["killed"]]:
                self.ctx.log(
                    f"  Phase 1: {m.ordnance_type} [{m.id[:8]}] destroyed by interception")
                to_remove_after.add(m.id)

        # Per-marker ship contact resolution
        for o_dict in list(self.ctx.gs.ordnance):
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.id in to_remove_after:
                continue

            is_torp = "torpedo" in marker.ordnance_type
            is_bomber = marker.ordnance_type in (
                OrdnanceType.BOMBER.value, OrdnanceType.MANTA.value)
            is_assault_boat = marker.ordnance_type == OrdnanceType.ASSAULT_BOAT.value

            if is_torp:
                # Torpedoes attack ANY ship they contact (friend or foe), except
                # friendly ships that were in base contact with the launcher at
                # launch (captured in marker.launch_exempt_ships).
                for s in ships:
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue
                    if (s.id in (marker.launch_exempt_ships or [])
                            and marker.launched_turn == self.ctx.gs.turn_number):
                        continue
                    if not check_torpedo_contact(marker, s):
                        continue

                    # CAP fighters intercept before the torpedo hits
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  Torpedoes contact {s.name}"
                        + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                        + f"!")
                    result = resolve_torpedo_attack(
                        marker, s, self.ctx.dice, self.ctx.gs,
                        all_ships=ships)

                    # remaining_strength = initial − turret_kills − hits;
                    # torps destroyed by turrets and torps that struck the target
                    # are both spent — only misses pass through.
                    marker.strength = result["remaining_strength"]
                    if result["hits"] > 0:
                        self.ctx.check_destruction(s)
                    if marker.strength <= 0:
                        to_remove_after.add(marker.id)
                        break
                    # Update marker for next ship in path
                    for j, od in enumerate(self.ctx.gs.ordnance):
                        if od["id"] == marker.id:
                            self.ctx.gs.ordnance[j] = marker.to_dict()
                            break

            elif is_bomber:
                # Bombers attack enemy ships only
                for s in ships:
                    if s.player == marker.owner_player:
                        continue
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if not circle_touches_square(s.x, s.y, s.base_radius,
                                                 marker.x, marker.y,
                                                 marker.heading):
                        continue
                    # CAP fighters intercept before the bomber attacks
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  {marker.ordnance_type} attacks {s.name}!")

                    # Count friendly fighters whose square marker touches this ship.
                    # Mantas are bombers, not fighters — they do not suppress turrets.
                    suppressing_fighters = sum(
                        1 for od in self.ctx.gs.ordnance
                        if od.get("owner_player") == marker.owner_player
                        and od.get("ordnance_type") in (
                            OrdnanceType.FIGHTER.value,
                            OrdnanceType.BARRACUDA.value)
                        and circle_touches_square(s.x, s.y, s.base_radius,
                                                  od.get("x", 0), od.get("y", 0),
                                                  od.get("heading", 0)))

                    # Count all bombers from same player contacting this ship
                    # (needed for Remastered cap)
                    total_bombers_on_target = sum(
                        1 for od in self.ctx.gs.ordnance
                        if od.get("owner_player") == marker.owner_player
                        and od.get("ordnance_type") in (
                            OrdnanceType.BOMBER.value, OrdnanceType.MANTA.value)
                        and circle_touches_square(s.x, s.y, s.base_radius,
                                                  od.get("x", 0), od.get("y", 0),
                                                  od.get("heading", 0)))

                    if suppressing_fighters > 0:
                        if self.ctx.gs.rule_turret_suppression_remastered:
                            # Remastered: fighters add +1 to attack roll,
                            # capped at total attacking bombers
                            result = resolve_bomber_attack(
                                marker, s, self.ctx.dice, self.ctx.gs,
                                remastered_fighter_bonus=suppressing_fighters,
                                remastered_bomber_cap=total_bombers_on_target)
                        else:
                            # XR default: this bomber gets exactly 3 attacks
                            result = resolve_bomber_attack(
                                marker, s, self.ctx.dice, self.ctx.gs,
                                suppressed_by_fighter=True)
                    else:
                        result = resolve_bomber_attack(
                            marker, s, self.ctx.dice, self.ctx.gs)

                    if result["hits"] > 0:
                        self.ctx.check_destruction(s)
                    to_remove_after.add(marker.id)
                    break

            elif marker.ordnance_type == OrdnanceType.MINE_FIELD.value:
                # Mine fields detonate against any ship in contact (friend or foe).
                # Only friendly ships that were in base contact with the launcher
                # at launch are exempt (captured in marker.launch_exempt_ships).
                for s in ships:
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue
                    if (s.id in (marker.launch_exempt_ships or [])
                            and marker.launched_turn == self.ctx.gs.turn_number):
                        continue
                    if not circle_touches_square(s.x, s.y, s.base_radius,
                                                 marker.x, marker.y,
                                                 marker.heading):
                        continue

                    # CAP fighters intercept the mine before it detonates
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  Mine contacts {s.name}"
                        + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                        + "!")
                    result = resolve_mine_contact(
                        marker, s, self.ctx.dice, self.ctx.gs, ships)
                    if result["hits"] > 0:
                        self.ctx.check_destruction(s)
                    to_remove_after.add(marker.id)
                    break  # one ship triggers the field

            elif is_assault_boat:
                if not self.ctx.gs.rule_hit_and_run:
                    continue
                # Assault boats trigger hit-and-run raids against enemy ships
                from .hit_and_run import resolve_hit_and_run
                for s in ships:
                    if s.player == marker.owner_player:
                        continue
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue
                    if not circle_touches_square(s.x, s.y, s.base_radius,
                                                 marker.x, marker.y,
                                                 marker.heading):
                        continue

                    # CAP fighters intercept before the raid
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  Assault boats contact {s.name} — hit-and-run raid!")

                    def _brace_fn(target_ship, msg, _s=s):
                        from .movement import do_command_check
                        if target_ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                            self.ctx.log(
                                f"  {target_ship.name} already braced — "
                                f"will roll to repel each raid")
                            return True, True
                        want = messagebox.askyesno("Hit-and-Run Raid — Brace?", msg)
                        if not want:
                            return False, False
                        check = do_command_check(target_ship, "brace_for_impact",
                                                 self.ctx.dice)
                        passed = check["passed"]
                        self.ctx.log(
                            f"  {target_ship.name} brace check: "
                            f"{'PASSED' if passed else 'FAILED'} "
                            f"(rolled {check['roll']} vs Ld {check['needed']})")
                        if passed:
                            target_ship.previous_order = target_ship.special_order
                            target_ship.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
                            target_ship.brace_set_on_turn = self.ctx.gs.turn_number
                            self.ctx.gs.update_ship(target_ship)
                        return True, passed

                    result = resolve_hit_and_run(
                        marker, s, self.ctx.dice, self.ctx.gs, _brace_fn)

                    n_crits = len(result["crits_applied"])
                    n_repelled = result["repelled"]
                    n_failed = result["failures"]
                    self.ctx.log(
                        f"  Raid result: {n_crits} crit(s) applied, "
                        f"{n_repelled} repelled, {n_failed} failed")
                    self.ctx.check_destruction(s)
                    to_remove_after.add(marker.id)
                    break

        # Remove spent ordnance
        if to_remove_after:
            self.ctx.gs.ordnance = [
                o for o in self.ctx.gs.ordnance
                if o["id"] not in to_remove_after]

        self.ctx.log(
            f"  Ordnance phase complete: {len(self.ctx.gs.ordnance)} markers remain")
        self.ctx.board.redraw()

    def _launch_ordnance_dialog(self, preselected_ship=None, preselected_heading=None):
        """Dialog to launch torpedoes or attack craft with heading and composition control.

        preselected_ship: Ship — skip the ship picker and use this ship directly.
        preselected_heading: float — pre-populate all heading controls to this value.
        """
        all_active = [Ship.from_dict(s) for s in self.ctx.gs.ships
                      if s["player"] == self.ctx.gs.active_player
                      and not Ship.from_dict(s).is_destroyed
                      and not s.get("is_disengaged", False)]
        launchers = [s for s in all_active
                     if s.ordnance_loaded_torps or s.ordnance_loaded_craft]
        if not launchers:
            messagebox.showinfo("No Ordnance", "No ships with loaded ordnance")
            return

        launcher_ids = {s.id for s in launchers}
        if preselected_ship and preselected_ship.id in launcher_ids:
            ship = preselected_ship
        else:
            ship = self.ctx.pick_ship(launchers, "Select ship to launch from")
        if not ship:
            return

        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Launch Ordnance - {ship.name}")
        dialog.geometry("500x550")
        dialog.transient(self.ctx.root)

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
                _init_heading = preselected_heading if preselected_heading is not None \
                    else ship.heading
                heading_var = tk.StringVar(value=f"{_init_heading:.0f}")

                arc_label_frame = tk.Frame(torp_frame)
                arc_label_frame.pack(fill=tk.X, padx=10, pady=1)
                tk.Label(arc_label_frame,
                         text=f"Launch heading (forward arc: "
                              f"{ship.heading-45:.0f}° to {ship.heading+45:.0f}°):",
                         font=("Consolas", 8)).pack(side=tk.LEFT)

                head_frame = tk.Frame(torp_frame)
                head_frame.pack(fill=tk.X, padx=10, pady=1)

                def _nudge_torp_heading(delta, hv=heading_var):
                    try:
                        current = float(hv.get())
                    except ValueError:
                        current = ship.heading
                    diff = ((current + delta) - ship.heading + 180) % 360 - 180
                    diff = max(-45.0, min(45.0, diff))
                    hv.set(f"{(ship.heading + diff) % 360:.0f}")

                for deg in [45, 30, 15, 5]:
                    tk.Button(head_frame, text=f"↶{deg}°",
                              command=lambda d=deg: _nudge_torp_heading(d),
                              font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
                tk.Entry(head_frame, textvariable=heading_var, width=5,
                         font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
                for deg in [5, 15, 30, 45]:
                    tk.Button(head_frame, text=f"↷{deg}°",
                              command=lambda d=deg: _nudge_torp_heading(-d),
                              font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
                tk.Button(head_frame, text="Reset",
                          command=lambda hv=heading_var: hv.set(f"{ship.heading:.0f}"),
                          font=("Consolas", 7)).pack(side=tk.LEFT, padx=4)

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

                    from .ordnance import compute_torpedo_launch_exempt
                    exempt = compute_torpedo_launch_exempt(ship, self.ctx.gs)

                    # First (or only) salvo
                    marker = OrdnanceMarker(
                        id=f"torp_{ship.id}_{self.ctx.gs.turn_number}_{_rng.randint(0,9999)}",
                        ordnance_type=o_type,
                        owner_player=ship.player,
                        launched_by=ship.id,
                        x=ship.x, y=ship.y,
                        heading=heading,
                        strength=strength,
                        speed=w.get("torpedo_speed", 30),
                        launched_turn=self.ctx.gs.turn_number,
                        can_turn=is_g,
                        turn_angle=45 if is_g else 0,
                        launch_exempt_ships=list(exempt),
                    )
                    self.ctx.gs.add_ordnance(marker)

                    name = "guided missiles" if is_g else "torpedoes"
                    self.ctx.log(
                        f"{ship.name} launched {name} Str {strength} "
                        f"heading {heading:.0f}°")

                    # Second salvo if split
                    remainder = total - strength
                    if remainder > 0:
                        marker2 = OrdnanceMarker(
                            id=f"torp_{ship.id}_{self.ctx.gs.turn_number}_{_rng.randint(0,9999)}_b",
                            ordnance_type=o_type,
                            owner_player=ship.player,
                            launched_by=ship.id,
                            x=ship.x, y=ship.y,
                            heading=heading,  # same heading for now
                            strength=remainder,
                            speed=w.get("torpedo_speed", 30),
                            launched_turn=self.ctx.gs.turn_number,
                            can_turn=is_g,
                            turn_angle=45 if is_g else 0,
                            launch_exempt_ships=list(exempt),
                        )
                        self.ctx.gs.add_ordnance(marker2)
                        self.ctx.log(
                            f"  Split salvo: second volley Str {remainder} "
                            f"heading {heading:.0f}°")

                    ship_fresh = self.ctx.gs.get_ship_by_id(ship.id)
                    if ship_fresh:
                        ship_fresh.ordnance_loaded_torps = False
                        self.ctx.gs.update_ship(ship_fresh)

                    dialog.destroy()
                    self.ctx.board.redraw()

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
                    from .ordnance import compute_torpedo_launch_exempt
                    spd = w.get("mine_speed", 10)
                    exempt = compute_torpedo_launch_exempt(ship, self.ctx.gs)
                    for i in range(effective_str):
                        # Each mine launcher fires one independent mine marker
                        marker = OrdnanceMarker(
                            id=f"mine_{ship.id}_{self.ctx.gs.turn_number}_{i}_{_rng.randint(0,9999)}",
                            ordnance_type=OrdnanceType.MINE_FIELD.value,
                            owner_player=ship.player,
                            launched_by=ship.id,
                            x=ship.x + (i - effective_str / 2) * 1.5,
                            y=ship.y,
                            heading=ship.heading,
                            strength=1,
                            speed=spd,
                            launched_turn=self.ctx.gs.turn_number,
                            launch_exempt_ships=list(exempt),
                        )
                        self.ctx.gs.add_ordnance(marker)

                    ship_fresh = self.ctx.gs.get_ship_by_id(ship.id)
                    if ship_fresh:
                        ship_fresh.ordnance_loaded_craft = False
                        self.ctx.gs.update_ship(ship_fresh)

                    self.ctx.log(
                        f"{ship.name} launches {effective_str} mine(s)")
                    dialog.destroy()
                    self.ctx.board.redraw()

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
                "manta": "Manta (resilient bomber)",
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
            _craft_init_heading = preselected_heading if preselected_heading is not None \
                else ship.heading
            craft_heading_var = tk.StringVar(value=f"{_craft_init_heading:.0f}")

            craft_arc_frame = tk.Frame(bay_frame)
            craft_arc_frame.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(craft_arc_frame,
                     text=f"Launch heading (forward arc: "
                          f"{ship.heading-45:.0f}° to {ship.heading+45:.0f}°):",
                     font=("Consolas", 8)).pack(side=tk.LEFT)

            craft_head_frame = tk.Frame(bay_frame)
            craft_head_frame.pack(fill=tk.X, padx=10, pady=1)

            def _nudge_craft_heading(delta):
                try:
                    current = float(craft_heading_var.get())
                except ValueError:
                    current = ship.heading
                diff = ((current + delta) - ship.heading + 180) % 360 - 180
                diff = max(-45.0, min(45.0, diff))
                craft_heading_var.set(f"{(ship.heading + diff) % 360:.0f}")

            for deg in [45, 30, 15, 5]:
                tk.Button(craft_head_frame, text=f"↶{deg}°",
                          command=lambda d=deg: _nudge_craft_heading(d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
            tk.Entry(craft_head_frame, textvariable=craft_heading_var, width=5,
                     font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
            for deg in [5, 15, 30, 45]:
                tk.Button(craft_head_frame, text=f"↷{deg}°",
                          command=lambda d=deg: _nudge_craft_heading(-d),
                          font=("Consolas", 8), width=4).pack(side=tk.LEFT, padx=1)
            tk.Button(craft_head_frame, text="Reset",
                      command=lambda: craft_heading_var.set(f"{ship.heading:.0f}"),
                      font=("Consolas", 7)).pack(side=tk.LEFT, padx=4)

            # CAP assignment: fighters only; protect a friendly ship
            cap_frame = tk.Frame(bay_frame)
            cap_frame.pack(fill=tk.X, padx=10, pady=2)
            cap_var = tk.BooleanVar(value=False)
            tk.Checkbutton(cap_frame, text="Assign fighters to CAP",
                           variable=cap_var,
                           font=("Consolas", 8)).pack(side=tk.LEFT)

            own_ships_for_cap = [
                Ship.from_dict(s) for s in self.ctx.gs.ships
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

                    # CAP only applies to fighter-type craft; bombers (incl. Manta) cannot CAP
                    fighter_types = (OrdnanceType.FIGHTER.value,
                                     OrdnanceType.BARRACUDA.value)
                    if cap_var.get() and o_type not in fighter_types:
                        messagebox.showerror(
                            "Bombers Cannot CAP",
                            f"Bombers cannot be assigned to Combat Air Patrol.\n"
                            f"Only fighters may perform CAP.")
                        return
                    assign_cap = cap_var.get() and o_type in fighter_types
                    protect_id = cap_ship_id_map.get(
                        cap_protect_var.get(), ship.id) if assign_cap else ""
                    protect_pos = cap_ship_pos_map.get(
                        protect_id, (ship.x, ship.y)) if assign_cap else (ship.x, ship.y)

                    # CAP range check: fighter must be able to reach protected ship
                    if assign_cap and protect_id:
                        px_ship, py_ship = cap_ship_pos_map.get(protect_id, (ship.x, ship.y))
                        cap_range = spd  # fighter's movement speed is its max range
                        dist_to_protect = math.sqrt(
                            (ship.x - px_ship)**2 + (ship.y - py_ship)**2)
                        if dist_to_protect > cap_range:
                            messagebox.showerror(
                                "CAP Out of Range",
                                f"Protected ship is {dist_to_protect:.1f}cm away.\n"
                                f"Fighter speed is {cap_range:.0f}cm — cannot reach.")
                            return

                    for i in range(count):
                        if total_launched >= current_remaining:
                            break  # fleet cap reached mid-launch
                        px = protect_pos[0] + (i - count / 2) * 1.5
                        py = protect_pos[1]
                        marker = OrdnanceMarker(
                            id=f"craft_{ship.id}_{ct}_{self.ctx.gs.turn_number}_{_rng.randint(0,9999)}",
                            ordnance_type=o_type,
                            owner_player=ship.player,
                            launched_by=ship.id,
                            x=px if assign_cap else ship.x + (i - count / 2) * 1.5,
                            y=py if assign_cap else ship.y,
                            heading=heading,
                            strength=1,
                            speed=spd,
                            launched_turn=self.ctx.gs.turn_number,
                            resilient_save=resil,
                            cap_ship_id=protect_id,
                        )
                        self.ctx.gs.add_ordnance(marker)
                        total_launched += 1

                if total_launched == 0:
                    messagebox.showwarning("No Craft",
                        "Set at least one craft type to a non-zero count")
                    return

                if total_launched > total_bays:
                    messagebox.showwarning("Over Capacity",
                        f"Launched {total_launched} but only have {total_bays} bays. "
                        f"Excess will be placed anyway.")

                ship_fresh = self.ctx.gs.get_ship_by_id(ship.id)
                if ship_fresh:
                    ship_fresh.ordnance_loaded_craft = False
                    self.ctx.gs.update_ship(ship_fresh)

                if cap_var.get():
                    protect_name = cap_protect_var.get()
                    self.ctx.log(
                        f"{ship.name} launched {total_launched} attack craft "
                        f"on CAP for {protect_name}")
                else:
                    self.ctx.log(
                        f"{ship.name} launched {total_launched} attack craft "
                        f"heading {heading:.0f}°")
                dialog.destroy()
                self.ctx.board.redraw()

            tk.Button(bay_frame, text="Launch Attack Craft",
                      command=_launch_craft,
                      bg="#663333", fg="white",
                      font=("Consolas", 9)).pack(pady=3)

        # Cancel
        tk.Button(dialog, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(pady=5)

    # --- Disengagement ---
