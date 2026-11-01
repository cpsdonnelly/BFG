"""BFG:XR — CombatDialogMixin: _fire_dialog."""
import tkinter as tk
from tkinter import messagebox

from .models import Ship, SpecialOrder
from .chapter_tactics import weapon_range, shadow_engines_hidden
from .combat import (weapon_fire_pool, shot_weapon, resolve_siege_cannons,
                     resolve_batteries, resolve_lances, resolve_nova_cannon,
                     apply_damage, check_los_clear, squadron_group,
                     squadron_fire_preview, fire_at_squadron)


class _Tooltip:
    """Small hover tooltip whose text is computed when it is shown."""

    def __init__(self, widget, text_fn):
        self.widget, self.text_fn, self.tip = widget, text_fn, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None):
        text = self.text_fn()
        if not text or self.tip:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=text, justify=tk.LEFT, bg="#FFFFE0", fg="#000000",
                 relief=tk.SOLID, borderwidth=1, font=("Consolas", 8),
                 padx=4, pady=2).pack()

    def _hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


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
        self._pool_modes = {}   # Heavy Gunz range mode fixed by this volley

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

            heavy = weapon.get("strength_close") is not None
            rolled = weapon.get("strength_dice")
            unfired = idx_key not in attacker.weapons_remaining
            # Pool decided when fired: random values rolled, Heavy Gunz by range
            pool_later = bool(heavy or rolled) and unfired
            if pool_later and rolled:
                fp_text = f"{rolled} (rolled when fired)"
            elif pool_later:
                fp_text = f"{full_str} ({weapon['strength_close']} within 15cm)"
            else:
                fp_text = f"{avail_str}/{full_str}"
            if wtype == "battery":
                ast_note = (" [ASTEROID: half FP, 10cm, no shifts]"
                            if self.in_asteroid_field else "")
                desc = (f"Battery FP{fp_text} "
                        f"{weapon['range_cm']}cm [{arcs}]{ast_note}")
            elif wtype == "lance":
                ast_note = " [ASTEROID: half Str, 10cm]" if self.in_asteroid_field else ""
                desc = (f"Lance Str{fp_text} "
                        f"{weapon['range_cm']}cm [{arcs}]{ast_note}")
            elif wtype == "nova_cannon":
                desc = "Nova Cannon 30-150cm [front]"
                avail_str = 1
            else:
                desc = weapon["name"]

            tk.Label(row, text=f"{weapon['name']}: {desc}",
                     font=("Consolas", 8), anchor=tk.W).pack(
                         side=tk.LEFT, fill=tk.X, expand=True)

            # "all" fires the whole pool; a number splits it (s.13 Splitting Fire)
            str_var = tk.StringVar(value="all" if pool_later else str(avail_str))
            if wtype != "nova_cannon" and (avail_str > 1 or pool_later):
                tk.Label(row, text="Fire:", font=("Consolas", 8)).pack(side=tk.LEFT)
                tk.Entry(row, textvariable=str_var, width=3,
                         font=("Consolas", 9)).pack(side=tk.LEFT, padx=2)

            target_options = []
            for e in self.enemies:
                dist = attacker.distance_to(e)
                arc = attacker.get_target_arc(e.x, e.y)
                in_arc = arc.value in weapon.get("arcs", []) or not weapon.get("arcs")
                eff_range = min(weapon_range(attacker, weapon) or 999,
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
                elif wtype in ("battery", "lance") and shadow_engines_hidden(
                        attacker, e, self.enemies):
                    status = " [HIDDEN: Shadow Engines]"
                target_options.append(
                    f"{e.name} ({dist:.0f}cm {arc.value})"
                    f"{'' if status else self._squadron_note(weapon, e, ast_range_cap)}"
                    f"{status}")

            self.target_options_per_weapon[w_idx] = list(target_options)
            target_var = tk.StringVar(value=target_options[0] if target_options else "")
            target_menu = tk.OptionMenu(row, target_var, *target_options)
            target_menu.config(font=("Consolas", 7), width=25)
            target_menu.pack(side=tk.RIGHT)
            _Tooltip(target_menu,
                     lambda w=weapon, v=target_var, c=ast_range_cap:
                     self._squadron_tooltip(w, v.get(), c))

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

    # ------------------------------------------------------ squadron info --

    def _squadron_preview(self, weapon, target, range_cap):
        """(group, aspect, preview) if target is in a squadron, else None."""
        if weapon.get("weapon_type") not in ("battery", "lance"):
            return None
        group = squadron_group(target, self.ctx.gs.get_ships())
        if len(group) < 2:
            return None
        aspect = (self.attacker.get_target_orientation(target)
                  if weapon.get("weapon_type") == "battery" else None)
        preview = squadron_fire_preview(self.attacker, weapon, group, aspect,
                                        self.ctx.gs.get_phenomena(),
                                        self.blast_markers, range_cap)
        return group, aspect, preview

    def _squadron_note(self, weapon, target, range_cap):
        info = self._squadron_preview(weapon, target, range_cap)
        if not info:
            return ""
        group, aspect, preview = info
        reach = f"hits can go to {len(preview['eligible'])}/{len(group)} squadron members"
        return f" [{aspect.replace('_', ' ')}: {reach}]" if aspect else f" [{reach}]"

    def _squadron_tooltip(self, weapon, target_str, range_cap):
        target = self._resolve_target(weapon, target_str)
        info = target and self._squadron_preview(weapon, target, range_cap)
        if not info:
            return ""
        group, aspect, preview = info
        if aspect:
            lines = [f"{target.name} is in a squadron: you fire at its "
                     f"{aspect.replace('_', ' ')} aspect.",
                     "Easier aspects roll more dice; harder ones let hits reach more ships."]
        else:
            lines = [f"{target.name} is in a squadron. Lances ignore target aspect."]
        lines.append("Hits go nearest first, each ship until destroyed:")
        for i, m in enumerate(preview["eligible"], 1):
            m_aspect = self.attacker.get_target_orientation(m).replace("_", " ")
            lines.append(f"  {i}. {m.name} ({m_aspect}, "
                         f"{self.attacker.distance_to(m):.0f}cm)")
        for m, reason in preview["ineligible"]:
            lines.append(f"  x  {m.name}: can't be hit ({reason})")
        return "\n".join(lines)

    def _resolve_target(self, weapon, target_str):
        """Return (target_ship, fire_str, avail_str) from widget state, or None."""
        if not target_str:
            return None
        if any(b in target_str for b in ["[NO ARC]", "[OUT OF RANGE]", "[NO LOS",
                                         "[HIDDEN"]):
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
                       <= (weapon_range(self.attacker, weapon) or 999))
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
        siege_done = self._fire_siege_cannons(all_damage, fired_weapon_indices)

        for w_idx, weapon, enabled, target_var, str_var, avail_str in self.weapon_assignments:
            if not enabled.get() or w_idx in siege_done:
                continue
            target = self._resolve_target(weapon, target_var.get())
            if target is None:
                self._log(f"  {weapon['name']}: skipped (no valid target)")
                continue

            target = self._check_target_priority(weapon, target)

            weapon_actually_fired = True
            wtype = weapon.get("weapon_type", "")
            phenomena = self.ctx.gs.get_phenomena()
            if wtype in ("battery", "lance"):
                pool, mode, err = weapon_fire_pool(
                    self.attacker, weapon, w_idx,
                    self.attacker.distance_to(target), self.ctx.dice)
                if err:
                    self._log(f"  {err}")
                    continue
                if (weapon.get("strength_dice") or weapon.get("strength_close")
                        is not None) and str(w_idx) not in self.attacker.weapons_remaining:
                    if weapon.get("strength_dice"):
                        self._log(f"  {weapon['name']}: rolled {weapon['strength_dice']} "
                                  f"= {pool}")
                    if self.in_asteroid_field:
                        pool = max(1, (pool + 1) // 2)
                    avail_str = pool
                if mode:
                    self._pool_modes[w_idx] = mode
            try:
                fire_str = max(1, min(int(str_var.get()), avail_str))
            except (ValueError, TypeError):
                fire_str = avail_str
            fire_weapon = shot_weapon(weapon, fire_str)

            # A ship in a squadron can't be picked out: picking it fires at
            # the squadron at that ship's aspect, hits nearest first (s.8)
            group = squadron_group(target, self.ctx.gs.get_ships())
            if len(group) > 1 and wtype in ("battery", "lance"):
                def _apply_to(member, n):
                    fresh = self.ctx.gs.get_ship_by_id(member.id)
                    if not fresh or fresh.is_destroyed:
                        return n, True
                    self._log(f"  >> {fresh.name}: {n} hits")
                    return self.panel._apply_hits_to_target(
                        self.attacker, fresh, n, self._log,
                        crit_on=weapon.get("crit_on", 6))

                sr, _ = fire_at_squadron(
                    self.attacker, fire_weapon, target, group, self.ctx.dice,
                    _apply_to, self.lock_on, self.blast_markers, phenomena,
                    self.ctx.gs.ships, no_column_shifts=self.in_asteroid_field,
                    range_cap=10 if self.in_asteroid_field else None)
                self._log(f"  {sr.description} — squadron takes {sr.hits} hit(s)")
                fired_weapon_indices.append((w_idx, fire_str, avail_str))
                continue

            if wtype == "battery":
                sr = resolve_batteries(
                    self.attacker, target, fire_weapon,
                    self.ctx.dice, self.blast_markers, self.lock_on,
                    phenomena, self.ctx.gs.ships,
                    no_column_shifts=self.in_asteroid_field)
                self._log(f"  {sr.description}")
                if sr.hits > 0:
                    all_damage.setdefault(target.id, []).append(
                        (sr.hits, "battery", target, weapon.get("crit_on", 6)))

            elif wtype == "lance":
                sr = resolve_lances(self.attacker, target, fire_weapon,
                                    self.ctx.dice, self.lock_on)
                self._log(f"  {sr.description}")
                if sr.hits > 0:
                    all_damage.setdefault(target.id, []).append(
                        (sr.hits, "lance", target, weapon.get("crit_on", 6)))

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
                                                 self.ctx.dice, self.ctx.gs)
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
            # Hits that crit on 4+ (bombardment cannons) are applied separately
            for crit_on in sorted({c for _, _, _, c in hit_list}, reverse=True):
                total = sum(h for h, _, _, c in hit_list if c == crit_on)
                target = self.ctx.gs.get_ship_by_id(target_id)
                if not target or target.is_destroyed:
                    continue
                self._log(f"  >> {target.name}: {total} total hits"
                          + (f" (crits on {crit_on}+)" if crit_on != 6 else ""))
                self.panel._apply_hits_to_target(self.attacker, target, total, self._log,
                                                 crit_on=crit_on)

        self._record_fired(fired_weapon_indices)
        self.dialog.destroy()
        self.ctx.board.redraw()

    def _fire_siege_cannons(self, all_damage, fired_weapon_indices) -> set:
        """Siege Cannons Chapter tactic: macrobatteries and bombardment cannons
        assigned to the same target (not a squadron) fire together as one
        gunnery roll. Returns the weapon indices fired this way."""
        from .chapter_tactics import siege_ship
        done = set()
        if not siege_ship(self.attacker):
            return done
        groups = {}
        for w_idx, weapon, enabled, target_var, _sv, _av in self.weapon_assignments:
            if not enabled.get() or weapon.get("weapon_type") != "battery":
                continue
            target = self._resolve_target(weapon, target_var.get())
            if target is None or len(squadron_group(target, self.ctx.gs.get_ships())) > 1:
                continue
            groups.setdefault(target.id, (target, []))[1].append((w_idx, weapon))
        for target, ws in groups.values():
            macro = [(i, w) for i, w in ws if not w.get("hits_on")]
            bcs = [(i, w) for i, w in ws if w.get("hits_on")]
            if not macro or not bcs:
                continue
            target = self._check_target_priority(macro[0][1], target)
            shots = {}
            for i, w in macro + bcs:
                pool, mode, err = weapon_fire_pool(self.attacker, w, i,
                                                   self.attacker.distance_to(target),
                                                   self.ctx.dice)
                if err:
                    self._log(f"  {err}")
                    continue
                if self.in_asteroid_field:
                    pool = max(1, (pool + 1) // 2)
                shots[i] = shot_weapon(w, pool)
                fired_weapon_indices.append((i, pool, pool))
                done.add(i)
            m_res, b_res = resolve_siege_cannons(
                self.attacker, target,
                [shots[i] for i, _ in macro if i in shots],
                [shots[i] for i, _ in bcs if i in shots],
                self.ctx.dice, self.blast_markers, self.lock_on,
                self.ctx.gs.get_phenomena(), self.ctx.gs.ships,
                no_column_shifts=self.in_asteroid_field)
            self._log(f"  {m_res.description}")
            self._log(f"  {b_res.description}")
            for res, crit_on, wtype in ((m_res, 6, "battery"), (b_res, 4, "battery")):
                if res.hits:
                    all_damage.setdefault(target.id, []).append(
                        (res.hits, wtype, target, crit_on))
        return done

    def _record_fired(self, fired_weapon_indices):
        """Update attacker's weapons_remaining / weapons_fired_indices / has_fired."""
        attacker_fresh = self.ctx.gs.get_ship_by_id(self.attacker.id)
        if not attacker_fresh:
            return
        wr = attacker_fresh.weapons_remaining or {}
        wfi = attacker_fresh.weapons_fired_indices or []

        modes = dict(attacker_fresh.weapon_pool_mode or {})
        for w_idx, fire_str, avail_str in fired_weapon_indices:
            new_remaining = avail_str - fire_str
            wr[str(w_idx)] = new_remaining
            if w_idx in self._pool_modes:
                modes[str(w_idx)] = self._pool_modes[w_idx]
            if new_remaining <= 0 and w_idx not in wfi:
                wfi.append(w_idx)
        attacker_fresh.weapon_pool_mode = modes

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
