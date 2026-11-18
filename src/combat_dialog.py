"""BFG:XR — CombatDialogMixin: _fire_dialog."""
from .tk_compat import tk, messagebox

from .models import Ship, SpecialOrder
from .chapter_tactics import weapon_range, shadow_engines_hidden
from .combat import check_los_clear, squadron_group, squadron_fire_preview


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

# Fire order within one ship's volley: batteries, then lances, then the nova
# cannon (the target is asked about bracing before each kind, s.7)
_FIRE_ORDER = {"battery": 0, "lance": 1, "nova_cannon": 2, "armageddon_gun": 3,
               "star_pulse": 4}


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
            elif wtype == "armageddon_gun":
                from .combat import armageddon_ready
                why = armageddon_ready(attacker)
                desc = ("Armageddon Gun: 90cm straight ahead (any target)"
                        + (f" [cannot fire: {why}]" if why else ""))
                avail_str = 1
            elif wtype == "star_pulse":
                desc = "Star Pulse Generator: every non-Necron ship within 20cm (any target)"
                avail_str = 1
            else:
                desc = weapon["name"]

            tk.Label(row, text=f"{weapon['name']}: {desc}",
                     font=("Consolas", 8), anchor=tk.W).pack(
                         side=tk.LEFT, fill=tk.X, expand=True)

            # "all" fires the whole pool; a number splits it (s.13 Splitting Fire)
            str_var = tk.StringVar(value="all" if pool_later else str(avail_str))
            if wtype not in ("nova_cannon", "armageddon_gun", "star_pulse") and (
                    avail_str > 1 or pool_later):
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
                los = check_los_clear(attacker, e, phenomena, self.blast_markers,
                                      self.ctx.gs.ships)
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

        # s.13 Mixing Different Gunnery Weapons (owner ruling): fire them
        # simultaneously (no shifts from each other's blast markers, all
        # committed even if the first kills the target) or in sequence
        from .combat import gunnery_kind
        kinds = {gunnery_kind(w) for _i, w, *_r in self.weapon_assignments
                 if w.get("weapon_type") == "battery"}
        self._together_var = tk.BooleanVar(value=False)
        if len(kinds) > 1:
            tk.Checkbutton(dialog, variable=self._together_var,
                           text="Fire different gunnery weapons together (s.13: no column "
                                "shifts from each other's blast markers; all are committed)",
                           font=("Consolas", 8), wraplength=520,
                           justify=tk.LEFT).pack(anchor=tk.W, padx=10)

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

    def _fire_all(self):
        """Fire the selected weapons at their targets: one recorded action
        (actions.fire_volley; the volley itself is fire_volley.FireVolley)."""
        from .actions import fire_volley
        orders = []
        for w_idx, weapon, enabled, target_var, str_var, _avail in self.weapon_assignments:
            if not enabled.get():
                continue
            target = self._resolve_target(weapon, target_var.get())
            try:
                strength = int(str_var.get())
            except (ValueError, TypeError):
                strength = None
            orders.append([w_idx, target.id if target else None, strength])
        together = bool(self._together_var.get()) if hasattr(self, "_together_var") else False
        context = {"closest": self.closest_visible.id if self.closest_visible else None,
                   "lock_on": bool(self.lock_on), "asteroid": bool(self.in_asteroid_field),
                   "enemies": [e.id for e in self.enemies]}
        fire_volley(self.panel, self.attacker.id, orders, together, log=self._log,
                    context=context)
        self.dialog.destroy()
        self.ctx.board.redraw()


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

        ships_with_weapons = [s for s in ships_with_weapons if self.ctx.tc._aa_ok(s)]
        if not ships_with_weapons:
            messagebox.showinfo("No Ships", "All ships have fired all weapons")
            return

        attacker = self.ctx.pick_ship(ships_with_weapons, "Select ship to fire")
        if not attacker:
            return

        enemy_player = 2 if attacker.player == 1 else 1
        # Enemy hulks may be fired on too (s.34); never your own side's
        enemies = [Ship.from_dict(s) for s in self.ctx.gs.ships
                   if s["player"] == enemy_player
                   and (not Ship.from_dict(s).is_destroyed
                        or s.get("status") in ("drifting_hulk", "burning_hulk"))
                   and s.get("status") != "destroyed"
                   and not s.get("is_disengaged", False)]
        if not enemies:
            messagebox.showinfo("No Targets", "No enemy ships in play")
            return

        enemies.sort(key=lambda e: attacker.distance_to(e))
        phenomena = self.ctx.gs.get_phenomena()
        blast_markers = self.ctx.gs.get_blast_markers()

        closest_visible = next(
            (e for e in enemies
             if e.status == "active"          # a closest hulk may be ignored (s.34)
             and check_los_clear(attacker, e, phenomena, blast_markers,
                                 self.ctx.gs.ships)["clear"]),
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
