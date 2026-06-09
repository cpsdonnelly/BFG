"""BFG:XR — CombatPanel: shooting phase UI, weapon targeting, damage resolution."""
import tkinter as tk
from tkinter import messagebox
import math

from .models import Ship, SpecialOrder, OrdnanceMarker
from .combat import (check_weapon_in_arc, resolve_batteries,
                     resolve_lances, resolve_nova_cannon, apply_damage,
                     check_los_clear, resolve_batteries_vs_squadron,
                     eligible_orientations)
from .game_context import GameContext


class CombatPanel:
    """Handles all shooting phase UI: fire dialog, ordnance targeting."""

    def __init__(self, ctx: GameContext):
        self.ctx = ctx

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

    def _fire_at_ordnance_dialog(self):
        """Fire weapons at ordnance. 6+ to hit, one hit removes entire wave/salvo.
        Batteries use Ordnance column on gunnery table. Lances roll strength dice.
        Ordnance-only target priority (other ordnance = nearest, not ships)."""
        enemy_player = 2 if self.ctx.gs.active_player == 1 else 1
        enemy_ordnance = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance
                          if o["owner_player"] == enemy_player]
        if not enemy_ordnance:
            messagebox.showinfo("No Targets", "No enemy ordnance on the board")
            return

        # Get ships with unfired direct-fire weapons (batteries OR lances)
        active_ships = [Ship.from_dict(s) for s in self.ctx.gs.ships
                        if s["player"] == self.ctx.gs.active_player
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

        attacker = self.ctx.pick_ship(ships_with_weapons,
                                           "Select ship to fire at ordnance")
        if not attacker:
            return

        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Fire at Ordnance - {attacker.name}")
        dialog.geometry("500x500")
        dialog.transient(self.ctx.root)

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
                check = do_command_check(attacker, "target_priority", self.ctx.dice)
                if not check["passed"]:
                    self.ctx.log(
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
                                self.ctx.gs.get_phenomena(),
                                self.ctx.gs.get_blast_markers())
                shifts += los.get("column_shifts", 0)
                # Targeting matrix
                if "targeting_matrix" in attacker.special_rules:
                    shifts -= 1

                dice_count = lookup_gunnery_dice(avail, COL_ABEAM_ESCORT, shifts)
                self.ctx.log(
                    f"  {weapon['name']} FP{avail} vs ordnance: "
                    f"{dice_count} dice (col Ordnance, {shifts:+d} shifts)")
            elif wtype == "lance":
                # Lances roll their strength in dice
                dice_count = avail
                self.ctx.log(
                    f"  {weapon['name']} Str{avail} vs ordnance: "
                    f"{dice_count} dice")
            else:
                dice_count = 0

            if dice_count <= 0:
                self.ctx.log(f"  No dice to roll")
                dialog.destroy()
                return

            # Roll: 6+ to hit ordnance
            rolls = self.ctx.dice.roll_d6(dice_count,
                f"{weapon['name']} vs {target_ord.ordnance_type} (6+ to hit)")
            hits = sum(1 for r in rolls if r >= 6)

            # Track weapon as used
            wr[idx_key] = 0
            attacker.weapons_remaining = wr
            if w_idx not in attacker.weapons_fired_indices:
                attacker.weapons_fired_indices.append(w_idx)
            self.ctx.gs.update_ship(attacker)

            if hits > 0:
                # ONE HIT KILLS ENTIRE WAVE/SALVO
                self.ctx.gs.ordnance = [
                    o for o in self.ctx.gs.ordnance
                    if o["id"] != target_ord.id]
                self.ctx.log(
                    f"  HIT! {target_ord.ordnance_type} Str{target_ord.strength} "
                    f"destroyed! (rolled {hits} hit(s) on 6+)")
            else:
                self.ctx.log(
                    f"  MISS! No 6s rolled ({dice_count} dice)")

            dialog.destroy()
            self.ctx.board.redraw()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Fire at Ordnance", command=_fire,
                  bg="#663333", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=5)

    def _apply_hits_to_target(self, attacker: Ship, target: Ship,
                              total_hits: int, log_fn) -> None:
        """Brace prompt, apply_damage, crits, and destruction check for one volley."""
        brace = False
        already_braced = (target.special_order ==
                          SpecialOrder.BRACE_FOR_IMPACT.value)
        if already_braced:
            brace = True
            log_fn(f"     (already braced)")
        elif self.ctx.gs.ai_player == target.player:
            from .ai_player import ai_should_brace
            from .movement import attempt_brace
            if ai_should_brace(self.ctx.gs, target, total_hits, attacker):
                check = attempt_brace(target, self.ctx.gs, self.ctx.dice)
                if check["passed"]:
                    brace = True
                    log_fn(f"     [AI] Brace PASSED (rolled {check['roll']} "
                           f"vs Ld {check['needed']})")
                else:
                    failed_list = list(target.brace_failed_vs or [])
                    failed_list.append(attacker.id)
                    target.brace_failed_vs = failed_list
                    self.ctx.gs.update_ship(target)
                    log_fn(f"     [AI] Brace FAILED (rolled {check['roll']} "
                           f"vs Ld {check['needed']})")
        elif attacker.id not in (target.brace_failed_vs or []):
            want_brace = messagebox.askyesno(
                "Brace For Impact?",
                f"{target.name} taking {total_hits} hits from {attacker.name}.\n"
                f"Attempt Brace For Impact? (Ld test, then 4+ save per hull hit)\n"
                f"If failed: cannot brace against {attacker.name} again.")
            if want_brace:
                from .movement import attempt_brace
                check = attempt_brace(target, self.ctx.gs, self.ctx.dice)
                if check["passed"]:
                    brace = True
                    log_fn(f"     Brace PASSED (rolled {check['roll']} "
                           f"vs Ld {check['needed']})")
                else:
                    failed_list = list(target.brace_failed_vs or [])
                    failed_list.append(attacker.id)
                    target.brace_failed_vs = failed_list
                    self.ctx.gs.update_ship(target)
                    log_fn(f"     Brace FAILED (rolled {check['roll']} "
                           f"vs Ld {check['needed']})")
        else:
            log_fn(f"     (already failed brace vs {attacker.name})")

        dmg = apply_damage(target, total_hits, self.ctx.dice, self.ctx.gs,
                           target_braced=brace)
        log_fn(f"     Shields: {dmg['shield_hits']}, "
               f"Hull: {dmg['hull_hits']}, "
               f"Saves: {dmg['brace_saves']}")
        if dmg.get("crits"):
            for crit in dmg["crits"]:
                log_fn(f"     CRITICAL: {crit}")
        if dmg["crippled"]:
            log_fn(f"     {target.name} is CRIPPLED!")
        if dmg["destroyed"]:
            log_fn(f"     {target.name} DESTROYED!")
            self.ctx.check_destruction(target)

    def _combine_squadron_fire_dialog(self):
        """Pool battery fire from multiple squadron ships into one gunnery roll."""
        from .squadron import get_squadrons
        from .combat import (resolve_combined_batteries, check_weapon_in_arc,
                             check_weapon_in_range, effective_battery_firepower)

        player = self.ctx.gs.active_player

        # Gather candidates: ships in a squadron with unfired batteries
        def _has_unfired_batteries(ship):
            wr = ship.weapons_remaining or {}
            for i, w in enumerate(ship.weapons):
                if w.get("weapon_type") != "battery":
                    continue
                if self._weapon_disabled_by_crit(ship, w):
                    continue
                if wr.get(str(i), w["strength"]) > 0:
                    return True
            return False

        all_squads = get_squadrons(self.ctx.gs, player)
        candidates = [
            s for s in (Ship.from_dict(d) for d in self.ctx.gs.ships)
            if s.player == player
            and not s.is_destroyed
            and not s.is_disengaged
            and not s.disengage_failed_this_turn
            and not s.has_boarded
            and not s.is_grappled
            and s.squadron_id in all_squads
            and _has_unfired_batteries(s)
        ]
        if not candidates:
            messagebox.showinfo(
                "No Squadron",
                "No ships in a squadron have unfired battery weapons.")
            return

        primary = self.ctx.pick_ship(candidates,
                                     "Select squadron ship to coordinate fire")
        if not primary:
            return

        # Squadron members that have unfired batteries
        all_members = all_squads.get(primary.squadron_id, [])
        squad_with_batteries = [s for s in all_members if _has_unfired_batteries(s)]
        if len(squad_with_batteries) < 2:
            messagebox.showinfo(
                "Not Enough Ships",
                "Need at least 2 squadron members with unfired battery weapons.")
            return

        # Pick a single target
        enemy_player = 2 if player == 1 else 1
        enemies = [Ship.from_dict(s) for s in self.ctx.gs.ships
                   if s["player"] == enemy_player
                   and not Ship.from_dict(s).is_destroyed
                   and not s.get("is_disengaged")]
        if not enemies:
            messagebox.showinfo("No Targets", "No valid enemy targets.")
            return
        target = self.ctx.pick_ship(enemies, "Select target for combined fire")
        if not target:
            return

        blast_markers = self.ctx.gs.get_blast_markers()
        phenomena = self.ctx.gs.get_phenomena()
        in_asteroid_field = "in_asteroid_field" in (primary.special_rules or [])
        lock_on = primary.special_order == SpecialOrder.LOCK_ON.value

        # Build the weapon-contribution list: batteries in arc + range + LoS
        weapon_rows = []
        for member in squad_with_batteries:
            wr = member.weapons_remaining or {}
            for i, w in enumerate(member.weapons):
                if w.get("weapon_type") != "battery":
                    continue
                if self._weapon_disabled_by_crit(member, w):
                    continue
                avail = wr.get(str(i), w["strength"])
                if avail <= 0:
                    continue
                if not check_weapon_in_arc(member, w, target.x, target.y):
                    continue
                if not check_weapon_in_range(member, w, target):
                    continue
                eff_fp = effective_battery_firepower(member,
                                                     dict(w, strength=avail))
                weapon_rows.append((member, i, w, avail, eff_fp))

        if not weapon_rows:
            messagebox.showinfo(
                "No Eligible Weapons",
                "No squadron battery weapons are in arc, range, and LoS of "
                f"{target.name}.")
            return

        # Dialog: checkbox per weapon, pooled FP display
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Combine Squadron Fire → {target.name}")
        dialog.geometry("480x420")
        dialog.transient(self.ctx.root)

        tk.Label(dialog, text="Combine Squadron Battery Fire",
                 font=("Consolas", 11, "bold")).pack(pady=4)
        tk.Label(dialog, text=f"Target: {target.name}",
                 font=("Consolas", 9)).pack()

        chk_frame = tk.LabelFrame(dialog, text="Contributing weapons",
                                  font=("Consolas", 9))
        chk_frame.pack(fill=tk.X, padx=10, pady=4)

        chk_vars: list = []
        for member, w_idx, weapon, avail, eff_fp in weapon_rows:
            var = tk.BooleanVar(value=True)
            text = (f"{member.name} — {weapon['name']} "
                    f"(avail {avail}, eff FP {eff_fp})")
            tk.Checkbutton(chk_frame, text=text, variable=var,
                           font=("Consolas", 8)).pack(anchor=tk.W, padx=4)
            chk_vars.append(var)

        pooled_var = tk.StringVar()
        pooled_lbl = tk.Label(dialog, textvariable=pooled_var,
                              font=("Consolas", 10, "bold"), fg="#FFAA00")
        pooled_lbl.pack(pady=2)

        def _update_pooled(*_):
            total = sum(
                row[4] for row, var in zip(weapon_rows, chk_vars) if var.get()
            )
            pooled_var.set(f"Pooled effective firepower: {total}")

        for var in chk_vars:
            var.trace_add("write", _update_pooled)
        _update_pooled()

        log_lines: list = []

        def _log(msg):
            log_lines.append(msg)
            self.ctx.log(msg)

        def _confirm():
            selected = [(row[0], dict(row[2], strength=row[3]))
                        for row, var in zip(weapon_rows, chk_vars) if var.get()]
            if not selected:
                messagebox.showwarning("Nothing Selected",
                                       "Select at least one weapon.")
                return

            sr = resolve_combined_batteries(
                primary, selected, target,
                self.ctx.dice, blast_markers, lock_on,
                phenomena, self.ctx.gs.ships,
                no_column_shifts=in_asteroid_field)
            _log(f"  {sr.description}")

            if sr.hits > 0:
                fresh_target = self.ctx.gs.get_ship_by_id(target.id)
                if fresh_target and not fresh_target.is_destroyed:
                    _log(f"  >> {fresh_target.name}: {sr.hits} hits")
                    self._apply_hits_to_target(primary, fresh_target, sr.hits, _log)

            # Mark each contributing weapon as fired
            used_by_ship: dict = {}
            for row_idx, (member, w_idx, _w, avail, _) in enumerate(weapon_rows):
                if not chk_vars[row_idx].get():
                    continue
                used_by_ship.setdefault(member.id, []).append((w_idx, avail))

            for ship_id, fired_list in used_by_ship.items():
                fresh = self.ctx.gs.get_ship_by_id(ship_id)
                if not fresh:
                    continue
                wr = dict(fresh.weapons_remaining or {})
                wfi = list(fresh.weapons_fired_indices or [])
                for w_idx, fire_str in fired_list:
                    wr[str(w_idx)] = 0
                    if w_idx not in wfi:
                        wfi.append(w_idx)
                fresh.weapons_remaining = wr
                fresh.weapons_fired_indices = wfi
                # Check if all direct-fire weapons are spent
                all_done = True
                for i, w in enumerate(fresh.weapons):
                    if w.get("weapon_type") in ("torpedo", "launch_bay"):
                        continue
                    if self._weapon_disabled_by_crit(fresh, w):
                        continue
                    if wr.get(str(i), w["strength"]) > 0:
                        all_done = False
                        break
                fresh.has_fired = all_done
                self.ctx.gs.update_ship(fresh)

            self.ctx.log(
                f"Squadron combined fire: {len(selected)} weapons vs "
                f"{target.name} — {sr.hits} hits")
            dialog.destroy()
            self.ctx.board.redraw()

        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=6)
        tk.Button(btn_row, text="Fire!", command=_confirm,
                  bg="#663333", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

    def _squadron_target_dialog(self):
        """Fire a single ship's battery at an enemy squadron (hit-allocation mode)."""
        from .squadron import get_squadrons

        player = self.ctx.gs.active_player
        enemy_player = 2 if player == 1 else 1

        # Candidates: ships with unfired batteries, not boarded/grappled
        def _has_unfired_batteries(ship):
            wr = ship.weapons_remaining or {}
            for i, w in enumerate(ship.weapons):
                if w.get("weapon_type") != "battery":
                    continue
                if self._weapon_disabled_by_crit(ship, w):
                    continue
                if wr.get(str(i), w.get("strength", 0)) > 0:
                    return True
            return False

        candidates = [
            Ship.from_dict(s) for s in self.ctx.gs.ships
            if s["player"] == player
            and not Ship.from_dict(s).is_destroyed
            and not s.get("is_disengaged", False)
            and not s.get("disengage_failed_this_turn", False)
            and not s.get("has_boarded", False)
            and not s.get("is_grappled", False)
            and _has_unfired_batteries(Ship.from_dict(s))
        ]
        if not candidates:
            messagebox.showinfo("No Ships", "No ships have unfired battery weapons.")
            return

        attacker = self.ctx.pick_ship(candidates, "Select ship to fire at squadron")
        if not attacker:
            return

        # Find enemy squadrons (2+ members)
        all_enemy_squads = get_squadrons(self.ctx.gs, enemy_player)
        enemy_squads = {sid: members for sid, members in all_enemy_squads.items()
                        if len(members) >= 2}
        if not enemy_squads:
            messagebox.showinfo("No Squadrons",
                "No enemy squadrons (2+ ships) on the board.\n"
                "Use 'Fire Weapons' to target individual ships.")
            return

        # Pick squadron via dialog
        squad_ids = list(enemy_squads.keys())
        squad_labels = []
        for sid in squad_ids:
            members = enemy_squads[sid]
            names = ", ".join(m.name for m in members)
            squad_labels.append(f"{sid}: [{names}]")

        sel_dlg = tk.Toplevel(self.ctx.root)
        sel_dlg.title("Select Enemy Squadron")
        sel_dlg.geometry("420x250")
        sel_dlg.transient(self.ctx.root)
        tk.Label(sel_dlg, text="Select enemy squadron to target:",
                 font=("Consolas", 10, "bold")).pack(pady=6)
        squad_var = tk.StringVar(value=squad_ids[0])
        for sid, lbl in zip(squad_ids, squad_labels):
            tk.Radiobutton(sel_dlg, text=lbl, variable=squad_var,
                           value=sid, font=("Consolas", 8),
                           wraplength=380, justify=tk.LEFT).pack(anchor=tk.W, padx=10)
        chosen_squad_id = tk.StringVar()

        def _pick_squad():
            chosen_squad_id.set(squad_var.get())
            sel_dlg.destroy()

        tk.Button(sel_dlg, text="Select", command=_pick_squad,
                  bg="#663333", fg="white", font=("Consolas", 10)).pack(pady=8)
        sel_dlg.wait_window()
        if not chosen_squad_id.get():
            return

        squad_members = enemy_squads[chosen_squad_id.get()]

        # Compute orientation each member presents to attacker
        orient_groups = {"closing": [], "moving_away": [], "abeam": []}
        for m in squad_members:
            o = attacker.get_target_orientation(m)
            orient_groups[o].append(m)

        blast_markers = self.ctx.gs.get_blast_markers()
        phenomena = self.ctx.gs.get_phenomena()
        lock_on = attacker.special_order == SpecialOrder.LOCK_ON.value

        from .terrain_effects import check_ship_terrain_contact
        attacker_contacts = check_ship_terrain_contact(attacker, phenomena)
        in_asteroid_field = any(c["type"] == "asteroid_field" for c in attacker_contacts)

        # Available batteries on attacker
        avail_weapons = []
        for i, w in enumerate(attacker.weapons):
            if w.get("weapon_type") != "battery":
                continue
            if self._weapon_disabled_by_crit(attacker, w):
                continue
            wr = attacker.weapons_remaining or {}
            avail = wr.get(str(i), w.get("strength", 0))
            if in_asteroid_field:
                avail = max(1, (avail + 1) // 2)
            if avail <= 0:
                continue
            avail_weapons.append((i, w, avail))

        if not avail_weapons:
            messagebox.showinfo("No Weapons",
                f"{attacker.name} has no available battery weapons.")
            return

        # Main targeting dialog
        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Fire at Squadron — {attacker.name}")
        dialog.geometry("540x540")
        dialog.transient(self.ctx.root)

        tk.Label(dialog, text=f"{attacker.name} → Squadron {chosen_squad_id.get()}",
                 font=("Consolas", 11, "bold")).pack(pady=4)
        tk.Label(dialog,
                 text="Pick orientation: determines which ships are eligible targets.\n"
                      "Choosing 'abeam' allows hits on ALL members (closing / moving away / abeam).",
                 font=("Consolas", 8), fg="#AAAAAA", wraplength=500).pack()

        # Orientation selection
        orient_frame = tk.LabelFrame(dialog, text="Target Orientation",
                                     font=("Consolas", 9))
        orient_frame.pack(fill=tk.X, padx=10, pady=4)
        orient_var = tk.StringVar(value="closing")
        for o in ("closing", "moving_away", "abeam"):
            ships_in_o = orient_groups.get(o, [])
            label = (f"{o.replace('_', ' ').title()}: "
                     f"{', '.join(s.name for s in ships_in_o) or '(none)'}")
            tk.Radiobutton(orient_frame, text=label, variable=orient_var,
                           value=o, font=("Consolas", 8)).pack(anchor=tk.W, padx=6)

        # Weapon selection
        weapon_frame = tk.LabelFrame(dialog, text="Battery Weapon",
                                     font=("Consolas", 9))
        weapon_frame.pack(fill=tk.X, padx=10, pady=4)
        weapon_idx_var = tk.StringVar(value=str(avail_weapons[0][0]))
        for i, w, avail in avail_weapons:
            arcs = "/".join(w.get("arcs", []))
            ast_note = " [ASTEROID: half FP, 10cm]" if in_asteroid_field else ""
            lbl = (f"{w['name']} FP{avail} {w['range_cm']}cm [{arcs}]{ast_note}")
            tk.Radiobutton(weapon_frame, text=lbl, variable=weapon_idx_var,
                           value=str(i), font=("Consolas", 8)).pack(anchor=tk.W, padx=6)

        # Log
        log_text = tk.Text(dialog, height=8, font=("Consolas", 8),
                           bg="#0a0a1a", fg="#88CC88", state=tk.DISABLED)
        log_text.pack(fill=tk.X, padx=10, pady=4)

        def _log(msg):
            log_text.config(state=tk.NORMAL)
            log_text.insert(tk.END, msg + "\n")
            log_text.see(tk.END)
            log_text.config(state=tk.DISABLED)

        def _fire():
            chosen_orient = orient_var.get()
            w_idx = int(weapon_idx_var.get())
            weapon = attacker.weapons[w_idx]
            wr = attacker.weapons_remaining or {}
            full_avail = wr.get(str(w_idx), weapon.get("strength", 0))
            avail = max(1, (full_avail + 1) // 2) if in_asteroid_field else full_avail

            # Filter eligible members: orientation ≤ chosen AND in arc AND in range AND LoS
            elig_orientations = eligible_orientations(chosen_orient)
            eligible = []
            for m in squad_members:
                m_orient = attacker.get_target_orientation(m)
                if m_orient not in elig_orientations:
                    continue
                if not check_weapon_in_arc(attacker, weapon, m.x, m.y):
                    continue
                eff_range = min(weapon.get("range_cm", 999),
                                10 if in_asteroid_field else 9999)
                if attacker.distance_to(m) > eff_range:
                    continue
                los = check_los_clear(attacker, m, phenomena, blast_markers)
                if not los["clear"]:
                    _log(f"  {m.name}: no LoS ({los['blocked_by']}) — skipped")
                    continue
                eligible.append(m)

            if not eligible:
                _log("  No eligible targets after filtering — check arc/range/LoS.")
                return

            # Sort nearest-first
            eligible.sort(key=lambda s: attacker.distance_to(s))

            # Determine target_type from first eligible member
            target_type = eligible[0].ship_type

            fire_weapon = dict(weapon, strength=avail)
            sr = resolve_batteries_vs_squadron(
                attacker, fire_weapon, target_type, chosen_orient, eligible,
                self.ctx.dice, blast_markers, lock_on, phenomena,
                self.ctx.gs.ships, no_column_shifts=in_asteroid_field)
            _log(f"  {sr.description}")

            # Apply hits ship by ship
            for m in eligible:
                h = sr.hits_by_ship.get(m.id, 0)
                if h <= 0:
                    continue
                fresh = self.ctx.gs.get_ship_by_id(m.id)
                if fresh and not fresh.is_destroyed:
                    _log(f"  >> {fresh.name}: {h} hits")
                    self._apply_hits_to_target(attacker, fresh, h, _log)

            # Mark weapon fired
            fresh_att = self.ctx.gs.get_ship_by_id(attacker.id)
            if fresh_att:
                wr2 = dict(fresh_att.weapons_remaining or {})
                wfi = list(fresh_att.weapons_fired_indices or [])
                wr2[str(w_idx)] = 0
                if w_idx not in wfi:
                    wfi.append(w_idx)
                fresh_att.weapons_remaining = wr2
                fresh_att.weapons_fired_indices = wfi
                # Check if all direct-fire weapons spent
                all_done = True
                for i2, w2 in enumerate(fresh_att.weapons):
                    if w2.get("weapon_type") in ("torpedo", "launch_bay"):
                        continue
                    if self._weapon_disabled_by_crit(fresh_att, w2):
                        continue
                    if wr2.get(str(i2), w2.get("strength", 0)) > 0:
                        all_done = False
                        break
                fresh_att.has_fired = all_done
                self.ctx.gs.update_ship(fresh_att)

            self.ctx.log(
                f"{attacker.name} fires at squadron {chosen_squad_id.get()}: "
                f"{sr.hits} total hits")
            dialog.destroy()
            self.ctx.board.redraw()

        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=6)
        tk.Button(btn_row, text="Fire at Squadron!", command=_fire,
                  bg="#663333", fg="white",
                  font=("Consolas", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

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
