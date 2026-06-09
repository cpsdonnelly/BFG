"""BFG:XR — CombatDialogMixin: _fire_dialog."""
import tkinter as tk
from tkinter import messagebox

from .models import Ship, SpecialOrder
from .combat import (check_weapon_in_arc, resolve_batteries, resolve_lances,
                     resolve_nova_cannon, apply_damage, check_los_clear,
                     resolve_batteries_vs_squadron, eligible_orientations)


class CombatDialogMixin:

    def _fire_dialog(self):
        """Dialog to fire a ship's weapons - pick weapons, pick targets, split fire."""
        # Get ships that have unfired weapons (check per-weapon, not just has_fired)
        active_ships = [Ship.from_dict(s) for s in self.ctx.gs.ships
                        if s["player"] == self.ctx.gs.active_player
                        and not Ship.from_dict(s).is_destroyed
                        and not s.get("is_disengaged", False)
                        and not s.get("disengage_failed_this_turn", False)
                        and not s.get("has_boarded", False)
                        and not s.get("is_grappled", False)]

        ships_with_weapons = []
        for s in active_ships:
            ship = Ship.from_dict(s) if isinstance(s, dict) else s
            wr = ship.weapons_remaining or {}
            has_unfired = False
            for i, w in enumerate(ship.weapons):
                wtype = w.get("weapon_type", "")
                if wtype in ("torpedo", "launch_bay"):
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

        attacker = self.ctx.pick_ship(ships_with_weapons, "Select ship to fire")
        if not attacker:
            return

        # Get enemies (only living, not disengaged)
        enemy_player = 2 if attacker.player == 1 else 1
        enemies = [Ship.from_dict(s) for s in self.ctx.gs.ships
                   if s["player"] == enemy_player
                   and not Ship.from_dict(s).is_destroyed
                   and not s.get("is_disengaged", False)]
        if not enemies:
            messagebox.showinfo("No Targets", "No enemy ships in play")
            return

        # Sort enemies by distance, but only consider visible ones for "closest"
        enemies.sort(key=lambda e: attacker.distance_to(e))
        phenomena = self.ctx.gs.get_phenomena()
        blast_markers = self.ctx.gs.get_blast_markers()

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
            if wtype in ("torpedo", "launch_bay"):
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
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Fire Weapons - {attacker.name}")
        dialog.geometry("550x600")
        dialog.transient(self.ctx.root)
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
            phenomena = self.ctx.gs.get_phenomena()
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
                                            self.ctx.gs.get_phenomena(), blast_markers)
                    if cv_in_arc and cv_in_range and cv_los["clear"]:
                        needs_priority_check = True

                if needs_priority_check:
                    from .movement import do_command_check
                    check = do_command_check(attacker, "target_priority",
                                             self.ctx.dice)
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
                phenomena = self.ctx.gs.get_phenomena()

                # Create weapon dict with the specific strength to fire
                fire_weapon = dict(weapon)
                fire_weapon["strength"] = fire_str

                if wtype == "battery":
                    sr = resolve_batteries(attacker, target, fire_weapon,
                                          self.ctx.dice, blast_markers, lock_on,
                                          phenomena, self.ctx.gs.ships,
                                          no_column_shifts=in_asteroid_field)
                    _log(f"  {sr.description}")
                    if sr.hits > 0:
                        all_damage.setdefault(target.id, []).append(
                            (sr.hits, "battery", target))

                elif wtype == "lance":
                    sr = resolve_lances(attacker, target, fire_weapon,
                                       self.ctx.dice, lock_on)
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
                                               self.ctx.dice, self.ctx.gs)
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
                            self.ctx.board.draw_nova_template(tx, ty,
                                                          hit=bool(nc.get("ship_hits")))

                            # Apply hits
                            if nc.get("ship_hits"):
                                for sid, hd in nc["ship_hits"].items():
                                    hit_ship = self.ctx.gs.get_ship_by_id(sid)
                                    if hit_ship:
                                        _log(f"  Nova Cannon hits {hit_ship.name}: "
                                             f"{hd['hits']} hits (ignores armor)")
                                        apply_damage(hit_ship, hd["hits"],
                                                   self.ctx.dice, self.ctx.gs,
                                                   ignores_shields=True)
                                        self.ctx.check_destruction(hit_ship)
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
                                self.ctx.gs.add_blast_marker(bm)
                                _log(f"  Blast marker placed at ({bx:.0f}, {by:.0f})")

                # Only track as fired if the weapon actually resolved
                if weapon_actually_fired:
                    fired_weapon_indices.append((w_idx, fire_str, avail_str))

            # Now apply damage per target
            for target_id, hit_list in all_damage.items():
                total = sum(h for h, _, _ in hit_list)
                target = self.ctx.gs.get_ship_by_id(target_id)
                if not target or target.is_destroyed:
                    continue
                _log(f"  >> {target.name}: {total} total hits")
                self._apply_hits_to_target(attacker, target, total, _log)

            # Record which weapons were fired and track remaining strength
            attacker_fresh = self.ctx.gs.get_ship_by_id(attacker.id)
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
                    if wtype in ("torpedo", "launch_bay"):
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
                self.ctx.gs.update_ship(attacker_fresh)

            self.ctx.log(
                f"{attacker.name} fired {len(fired_weapon_indices)} weapon(s)")

            # Warn if unfired weapons remain
            if attacker_fresh and not attacker_fresh.has_fired:
                remaining_weapons = []
                wr2 = attacker_fresh.weapons_remaining or {}
                for i, w in enumerate(attacker_fresh.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay"):
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
                    self.ctx.log(
                        f"  WARNING: {attacker.name} still has unfired: "
                        + ", ".join(remaining_weapons))

            dialog.destroy()
            self.ctx.board.redraw()

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
