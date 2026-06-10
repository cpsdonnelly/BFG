"""BFG:XR — CombatDialogMixin: _fire_dialog."""
import tkinter as tk
from tkinter import messagebox

from .models import Ship, SpecialOrder
from .combat import (resolve_batteries, resolve_lances, resolve_nova_cannon,
                     apply_damage, check_los_clear)


# ---------------------------------------------------------------------------
# Private dialog controller
# ---------------------------------------------------------------------------

class _FireDialog:
    """Controller for the fire-weapons dialog."""

    def __init__(self, panel, attacker, enemies, closest_visible,
                 lock_on, in_asteroid_field, blast_markers, available_weapons):
        self.panel = panel
        self.ctx = panel.ctx
        self.attacker = attacker
        self.enemies = enemies
        self.closest_visible = closest_visible
        self.lock_on = lock_on
        self.in_asteroid_field = in_asteroid_field
        self.blast_markers = blast_markers
        self.available_weapons = available_weapons
        self.weapon_assignments = []
        self.target_options_per_weapon = {}

    def run(self):
        self._build_ui()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        attacker = self.attacker
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Fire Weapons - {attacker.name}")
        dialog.geometry("550x600")
        dialog.transient(self.ctx.root)
        self.dialog = dialog

        tk.Label(dialog, text=f"Fire: {attacker.name}",
                 font=("Consolas", 11, "bold")).pack(pady=3)
        tk.Label(dialog,
                 text=(f"Order: {attacker.special_order}"
                       + (" [LOCK ON - re-roll misses]" if self.lock_on else "")),
                 font=("Consolas", 8)).pack()

        assign_frame = tk.Frame(dialog)
        assign_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(assign_frame, text="Select weapons and assign targets:",
                 font=("Consolas", 9, "bold")).pack(anchor=tk.W)

        phenomena = self.ctx.gs.get_phenomena()
        for w_idx, weapon in self.available_weapons:
            row = tk.Frame(assign_frame)
            row.pack(fill=tk.X, pady=2)

            enabled = tk.BooleanVar(value=True)
            tk.Checkbutton(row, variable=enabled).pack(side=tk.LEFT)

            wtype = weapon.get("weapon_type", "")
            arcs = "/".join(weapon.get("arcs", []))
            full_str = weapon.get("strength", 0)
            idx_key = str(w_idx)
            if idx_key in attacker.weapons_remaining:
                avail_str = attacker.weapons_remaining[idx_key]
            else:
                avail_str = full_str

            ast_range_cap = (10 if self.in_asteroid_field
                             and wtype != "nova_cannon" else None)
            if self.in_asteroid_field and wtype in ("battery", "lance"):
                avail_str = max(1, (avail_str + 1) // 2)

            if wtype == "battery":
                ast_note = (" [ASTEROID: half FP, 10cm, no shifts]"
                            if self.in_asteroid_field else "")
                desc = (f"Battery FP{avail_str}/{full_str} "
                        f"{weapon['range_cm']}cm [{arcs}]{ast_note}")
            elif wtype == "lance":
                ast_note = " [ASTEROID: half Str, 10cm]" if self.in_asteroid_field else ""
                desc = (f"Lance Str{avail_str}/{full_str} "
                        f"{weapon['range_cm']}cm [{arcs}]{ast_note}")
            elif wtype == "nova_cannon":
                desc = "Nova Cannon 30-150cm [front]"
                avail_str = 1
            else:
                desc = weapon["name"]

            tk.Label(row, text=f"{weapon['name']}: {desc}",
                     font=("Consolas", 8), anchor=tk.W).pack(
                         side=tk.LEFT, fill=tk.X, expand=True)

            str_var = tk.StringVar(value=str(avail_str))
            if wtype != "nova_cannon" and avail_str > 1:
                tk.Label(row, text="Fire:", font=("Consolas", 8)).pack(side=tk.LEFT)
                tk.Entry(row, textvariable=str_var, width=3,
                         font=("Consolas", 9)).pack(side=tk.LEFT, padx=2)

            target_options = []
            for e in self.enemies:
                dist = attacker.distance_to(e)
                arc = attacker.get_target_arc(e.x, e.y)
                in_arc = arc.value in weapon.get("arcs", []) or not weapon.get("arcs")
                eff_range = min(weapon.get("range_cm", 999),
                                ast_range_cap if ast_range_cap else 9999)
                in_range = dist <= eff_range
                los = check_los_clear(attacker, e, phenomena, self.blast_markers)
                status = ""
                if not los["clear"]:
                    status = f" [NO LOS: {los['blocked_by']}]"
                elif not in_arc:
                    status = " [NO ARC]"
                elif not in_range:
                    status = " [OUT OF RANGE]"
                target_options.append(
                    f"{e.name} ({dist:.0f}cm {arc.value}){status}")

            self.target_options_per_weapon[w_idx] = list(target_options)
            target_var = tk.StringVar(value=target_options[0] if target_options else "")
            target_menu = tk.OptionMenu(row, target_var, *target_options)
            target_menu.config(font=("Consolas", 7), width=25)
            target_menu.pack(side=tk.RIGHT)

            self.weapon_assignments.append(
                (w_idx, weapon, enabled, target_var, str_var, avail_str))

        # Log area
        log_frame = tk.Frame(dialog)
        log_frame.pack(fill=tk.X, padx=10, pady=3)
        self.fire_log = tk.Text(log_frame, height=10, font=("Consolas", 8),
                                bg="#0a0a1a", fg="#88CC88", state=tk.DISABLED)
        self.fire_log.pack(fill=tk.X)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Auto: Full Volley at Closest",
                  command=self._auto_full_volley,
                  bg="#444466", fg="white",
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="Fire Selected Weapons",
                  command=self._fire_all,
                  bg="#663333", fg="white",
                  font=("Consolas", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

    # ----------------------------------------------------------------- log --

    def _log(self, msg):
        self.fire_log.config(state=tk.NORMAL)
        self.fire_log.insert(tk.END, msg + "\n")
        self.fire_log.see(tk.END)
        self.fire_log.config(state=tk.DISABLED)

    # ----------------------------------------------------------- fire logic --

    def _resolve_target(self, weapon, target_str):
        """Return (target_ship, fire_str, avail_str) from widget state, or None."""
        if not target_str:
            return None
        if any(b in target_str for b in ["[NO ARC]", "[OUT OF RANGE]", "[NO LOS"]):
            return None
        target_name = target_str.split(" (")[0]
        return next((e for e in self.enemies if e.name == target_name), None)

    def _check_target_priority(self, weapon, target):
        """Enforce target priority; returns the ship that must actually be fired at."""
        cv = self.closest_visible
        if not cv or target.id == cv.id:
            return target
        cv_arc = self.attacker.get_target_arc(cv.x, cv.y)
        cv_in_arc = cv_arc.value in weapon.get("arcs", []) or not weapon.get("arcs")
        cv_in_range = (self.attacker.distance_to(cv)
                       <= weapon.get("range_cm", 999))
        cv_los = check_los_clear(self.attacker, cv,
                                 self.ctx.gs.get_phenomena(), self.blast_markers)
        if not (cv_in_arc and cv_in_range and cv_los["clear"]):
            return target  # closest visible isn't valid for this weapon
        from .movement import do_command_check
        check = do_command_check(self.attacker, "target_priority", self.ctx.dice)
        if not check["passed"]:
            self._log(
                f"  {weapon['name']}: Target priority FAILED "
                f"(rolled {check['roll']} vs Ld {check['needed']}). "
                f"Must fire at closest visible: {cv.name}")
            return cv
        self._log(
            f"  {weapon['name']}: Target priority passed "
            f"(rolled {check['roll']} vs Ld {check['needed']})")
        return target

    def _fire_all(self):
        """Fire all selected weapons at their assigned targets."""
        all_damage = {}
        fired_weapon_indices = []

        for w_idx, weapon, enabled, target_var, str_var, avail_str in self.weapon_assignments:
            if not enabled.get():
                continue
            target = self._resolve_target(weapon, target_var.get())
            if target is None:
                self._log(f"  {weapon['name']}: skipped (no valid target)")
                continue

            try:
                fire_str = max(1, min(int(str_var.get()), avail_str))
            except (ValueError, TypeError):
                fire_str = avail_str

            target = self._check_target_priority(weapon, target)

            weapon_actually_fired = True
            wtype = weapon.get("weapon_type", "")
            phenomena = self.ctx.gs.get_phenomena()
            fire_weapon = {**weapon, "strength": fire_str}

            if wtype == "battery":
                sr = resolve_batteries(
                    self.attacker, target, fire_weapon,
                    self.ctx.dice, self.blast_markers, self.lock_on,
                    phenomena, self.ctx.gs.ships,
                    no_column_shifts=self.in_asteroid_field)
                self._log(f"  {sr.description}")
                if sr.hits > 0:
                    all_damage.setdefault(target.id, []).append(
                        (sr.hits, "battery", target))

            elif wtype == "lance":
                sr = resolve_lances(self.attacker, target, fire_weapon,
                                    self.ctx.dice, self.lock_on)
                self._log(f"  {sr.description}")
                if sr.hits > 0:
                    all_damage.setdefault(target.id, []).append(
                        (sr.hits, "lance", target))

            elif wtype == "nova_cannon":
                dist_to = self.attacker.distance_to(target)
                if dist_to < 30 or dist_to > 150:
                    self._log(
                        f"  Nova Cannon: target at {dist_to:.0f}cm, "
                        f"range is 30-150cm. Cannot fire.")
                    weapon_actually_fired = False
                else:
                    nc = resolve_nova_cannon(
                        self.attacker, target.x, target.y,
                        self.ctx.dice, self.ctx.gs)
                    if "error" in nc:
                        self._log(f"  Nova Cannon: {nc['error']}")
                        weapon_actually_fired = False
                    else:
                        tx, ty = nc["template_x"], nc["template_y"]
                        if nc.get("scatter_distance", 0) > 0:
                            self._log(
                                f"  Nova Cannon: SCATTERED "
                                f"{nc['scatter_distance']:.0f}cm "
                                f"to ({tx:.0f}, {ty:.0f})")
                        else:
                            self._log(
                                f"  Nova Cannon: HIT! "
                                f"Template at ({tx:.0f}, {ty:.0f})")
                        self.ctx.board.draw_nova_template(
                            tx, ty, hit=bool(nc.get("ship_hits")))
                        if nc.get("ship_hits"):
                            for sid, hd in nc["ship_hits"].items():
                                hit_ship = self.ctx.gs.get_ship_by_id(sid)
                                if hit_ship:
                                    self._log(
                                        f"  Nova Cannon hits {hit_ship.name}: "
                                        f"{hd['hits']} hits (ignores armor)")
                                    apply_damage(hit_ship, hd["hits"],
                                                 self.ctx.dice, self.ctx.gs,
                                                 ignores_shields=True)
                                    self.ctx.check_destruction(hit_ship)
                        else:
                            self._log("  Nova Cannon: no ships hit")
                        for bx, by in nc.get("blast_markers", []):
                            from .models import BlastMarker as BM
                            import random as _rng
                            bm = BM(id=f"nova_miss_{_rng.randint(0,9999)}",
                                    x=bx, y=by, source="nova_cannon_miss")
                            self.ctx.gs.add_blast_marker(bm)
                            self._log(
                                f"  Blast marker placed at ({bx:.0f}, {by:.0f})")

            if weapon_actually_fired:
                fired_weapon_indices.append((w_idx, fire_str, avail_str))

        # Apply accumulated damage
        for target_id, hit_list in all_damage.items():
            total = sum(h for h, _, _ in hit_list)
            target = self.ctx.gs.get_ship_by_id(target_id)
            if not target or target.is_destroyed:
                continue
            self._log(f"  >> {target.name}: {total} total hits")
            self.panel._apply_hits_to_target(self.attacker, target, total, self._log)

        self._record_fired(fired_weapon_indices)
        self.dialog.destroy()
        self.ctx.board.redraw()

    def _record_fired(self, fired_weapon_indices):
        """Update attacker's weapons_remaining / weapons_fired_indices / has_fired."""
        attacker_fresh = self.ctx.gs.get_ship_by_id(self.attacker.id)
        if not attacker_fresh:
            return
        wr = attacker_fresh.weapons_remaining or {}
        wfi = attacker_fresh.weapons_fired_indices or []

        for w_idx, fire_str, avail_str in fired_weapon_indices:
            new_remaining = avail_str - fire_str
            wr[str(w_idx)] = new_remaining
            if new_remaining <= 0 and w_idx not in wfi:
                wfi.append(w_idx)

        attacker_fresh.weapons_remaining = wr
        attacker_fresh.weapons_fired_indices = wfi

        all_done = True
        for i, w in enumerate(attacker_fresh.weapons):
            wtype = w.get("weapon_type", "")
            if wtype in ("torpedo", "launch_bay"):
                continue
            if self.panel._weapon_disabled_by_crit(attacker_fresh, w):
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
        self.ctx.gs.update_ship(attacker_fresh)

        self.ctx.log(
            f"{self.attacker.name} fired {len(fired_weapon_indices)} weapon(s)")
        if not attacker_fresh.has_fired:
            self._log_remaining_weapons(attacker_fresh, wr)

    def _log_remaining_weapons(self, attacker_fresh, wr):
        remaining_weapons = []
        for i, w in enumerate(attacker_fresh.weapons):
            wtype = w.get("weapon_type", "")
            if wtype in ("torpedo", "launch_bay"):
                continue
            if self.panel._weapon_disabled_by_crit(attacker_fresh, w):
                continue
            idx_key = str(i)
            if idx_key in wr:
                rem = wr[idx_key]
                if rem > 0:
                    remaining_weapons.append(f"{w['name']} ({rem} remaining)")
            else:
                remaining_weapons.append(w["name"])
        if remaining_weapons:
            self.ctx.log(
                f"  WARNING: {attacker_fresh.name} still has unfired: "
                + ", ".join(remaining_weapons))

    def _auto_full_volley(self):
        """Select closest valid target for every weapon, then fire."""
        for w_idx, weapon, enabled, target_var, str_var, avail_str in self.weapon_assignments:
            best = None
            for opt in self.target_options_per_weapon.get(w_idx, []):
                if not any(x in opt for x in
                           ["[NO ARC]", "[OUT OF RANGE]", "[NO LOS"]):
                    best = opt
                    break
            if best:
                enabled.set(True)
                target_var.set(best)
            else:
                enabled.set(False)
        self._fire_all()


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class CombatDialogMixin:

    def _fire_dialog(self):
        """Open the fire-weapons dialog for the active player."""
        # Build list of active ships with unfired weapons
        active_ships = [Ship.from_dict(s) for s in self.ctx.gs.ships
                        if s["player"] == self.ctx.gs.active_player
                        and not Ship.from_dict(s).is_destroyed
                        and not s.get("is_disengaged", False)
                        and not s.get("disengage_failed_this_turn", False)
                        and not s.get("has_boarded", False)
                        and not s.get("is_grappled", False)]

        ships_with_weapons = []
        for s in active_ships:
            wr = s.weapons_remaining or {}
            has_unfired = any(
                not self._weapon_disabled_by_crit(s, w)
                and (str(i) not in wr or wr[str(i)] > 0)
                for i, w in enumerate(s.weapons)
                if w.get("weapon_type", "") not in ("torpedo", "launch_bay"))
            if has_unfired:
                ships_with_weapons.append(s)

        if not ships_with_weapons:
            messagebox.showinfo("No Ships", "All ships have fired all weapons")
            return

        attacker = self.ctx.pick_ship(ships_with_weapons, "Select ship to fire")
        if not attacker:
            return

        enemy_player = 2 if attacker.player == 1 else 1
        enemies = [Ship.from_dict(s) for s in self.ctx.gs.ships
                   if s["player"] == enemy_player
                   and not Ship.from_dict(s).is_destroyed
                   and not s.get("is_disengaged", False)]
        if not enemies:
            messagebox.showinfo("No Targets", "No enemy ships in play")
            return

        enemies.sort(key=lambda e: attacker.distance_to(e))
        phenomena = self.ctx.gs.get_phenomena()
        blast_markers = self.ctx.gs.get_blast_markers()

        closest_visible = next(
            (e for e in enemies
             if check_los_clear(attacker, e, phenomena, blast_markers)["clear"]),
            None)

        lock_on = attacker.special_order == SpecialOrder.LOCK_ON.value

        from .terrain_effects import check_ship_terrain_contact
        attacker_contacts = check_ship_terrain_contact(attacker, phenomena)
        in_asteroid_field = any(
            c["type"] == "asteroid_field" for c in attacker_contacts)
        if in_asteroid_field:
            if attacker.is_crippled:
                messagebox.showinfo(
                    "Cannot Fire",
                    f"{attacker.name} is crippled — cannot fire from an asteroid field.")
                return
            if attacker.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                messagebox.showinfo(
                    "Cannot Fire",
                    f"{attacker.name} is bracing — cannot fire from an asteroid field.")
                return

        available_weapons = []
        for i, weapon in enumerate(attacker.weapons):
            wtype = weapon.get("weapon_type", "")
            if wtype in ("torpedo", "launch_bay"):
                continue
            if self._weapon_disabled_by_crit(attacker, weapon):
                continue
            idx_key = str(i)
            if idx_key in attacker.weapons_remaining:
                if attacker.weapons_remaining[idx_key] <= 0:
                    continue
            available_weapons.append((i, weapon))

        if not available_weapons:
            messagebox.showinfo(
                "No Weapons",
                f"{attacker.name} has no available direct fire weapons")
            return

        _FireDialog(
            self, attacker, enemies, closest_visible,
            lock_on, in_asteroid_field, blast_markers, available_weapons
        ).run()
