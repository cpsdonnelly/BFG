"""BFG:XR — CombatPanel: shooting phase UI, weapon targeting, damage resolution."""
from .tk_compat import tk, messagebox, ttk
import math
from typing import Optional, Tuple

from .models import Ship, SpecialOrder, OrdnanceMarker
from .combat import check_weapon_in_arc, apply_damage, squadron_group
from .game_context import GameContext
from .combat_dialog import CombatDialogMixin


class CombatPanel(CombatDialogMixin):
    """Handles all shooting phase UI: fire dialog, ordnance targeting."""

    def __init__(self, ctx: GameContext):
        self.ctx = ctx

    # _fire_dialog lives in CombatDialogMixin (src/combat_dialog.py)

    def _fire_at_ordnance_dialog(self):
        """Fire weapons at ordnance. 6+ to hit, one hit removes entire wave/salvo.
        Batteries use Ordnance column on gunnery table. Lances roll strength dice.
        Ordnance-only target priority (other ordnance = nearest, not ships)."""
        enemy_player = 2 if self.ctx.gs.active_player == 1 else 1
        all_ord = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance
                   if o["owner_player"] == enemy_player]
        # A wave counts as a single marker for enemy shooting (s.25)
        from .waves import members as wave_members, wave_label
        enemy_ordnance = [o for o in all_ord
                          if not o.wave_id or wave_members(all_ord, o.wave_id)[0].id == o.id]
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
            label = (f"Wave: {wave_label(wave_members(all_ord, o.wave_id))} ({dist:.0f}cm)"
                     if o.wave_id else f"{o.ordnance_type} Str{o.strength} ({dist:.0f}cm)")
            target_listbox.insert(tk.END, label)
        if enemy_ordnance:
            target_listbox.selection_set(0)

        def _fire():
            sel = target_listbox.curselection()
            if not sel:
                return
            target_ord = enemy_ordnance[sel[0]]
            w_idx = int(weapon_var.get())
            from .actions import shoot_ordnance
            res = shoot_ordnance(self.ctx.gs, self.ctx.dice, attacker.id, w_idx,
                                 target_ord.id, enemy_ordnance[0].id, log=self.ctx.log)
            if res.get("error"):
                messagebox.showerror(res.get("title", "Can't fire"), res["error"])
                return
            dialog.destroy()
            self.ctx.board.redraw()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Fire at Ordnance", command=_fire,
                  bg="#663333", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=("Consolas", 9)).pack(side=tk.LEFT, padx=5)

    def _brace_before_attack(self, attacker_key: str, attacker_name: str, target: Ship,
                             expected: float, log_fn=None, group=None,
                             attacker: Ship = None) -> bool:
        """Brace for Impact is declared before any combat rolls for the attack
        (s.7). Asks the target's player (the AI decides for its own ships) and
        rolls the command check. group: the target's squadron, which tests once
        and braces together (s.8). A ship may only try once per attacker per
        turn. Returns True if the target is braced."""
        log_fn = log_fn or self.ctx.log
        target = self.ctx.gs.get_ship_by_id(target.id) or target
        if target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
            return True
        if attacker_key in (target.brace_failed_vs or []):
            return False
        if target.is_destroyed or target.status != "active":
            return False
        from .aa_turn import brace_is_reactive
        if not brace_is_reactive(self.ctx.gs):
            return False            # AA: Brace is a command-phase order
        from .scenarios import orders_forbidden
        if orders_forbidden(self.ctx.gs, target):
            return False            # e.g. Ambush: the defender is caught unawares
        if self.ctx.is_ai_controlled(target.player):
            from .ai_player import ai_should_brace
            want = ai_should_brace(self.ctx.gs, target, int(round(expected)), attacker)
        else:
            who = (f"{target.name}'s squadron" if group and len(group) > 1 else target.name)
            from .ai_player import ai_should_brace
            want = self.ctx.prompt.yes_no("Brace For Impact?",
                f"{who} is about to be attacked by {attacker_name} "
                f"(about {expected:.1f} hits expected).\n"
                f"Attempt Brace For Impact before the attack is rolled?\n"
                f"(Ld test, then 4+ save per hull hit; braced ships fire at half.)\n"
                f"If failed: cannot brace against {attacker_name} again this turn.",
                ai_should_brace(self.ctx.gs, target, int(round(expected)), attacker))
        if not want:
            return False
        from .actions import declare_brace
        check = declare_brace(self.ctx.gs, self.ctx.dice, target.id, attacker_key,
                              [m.id for m in (group or [target])])
        tag = "[AI] " if self.ctx.is_ai_controlled(target.player) else ""
        members = [m for m in (group or [target]) if m.id != target.id]
        if check["passed"]:
            log_fn(f"     {tag}{target.name} Brace PASSED (rolled {check['roll']} "
                   f"vs Ld {check['needed']})" + (" — whole squadron braced" if members else ""))
            return True
        log_fn(f"     {tag}{target.name} Brace FAILED (rolled {check['roll']} "
               f"vs Ld {check['needed']})")
        return False

    def _apply_hits_to_target(self, attacker: Ship, target: Ship,
                              total_hits: int, log_fn,
                              crit_on: int = 6,
                              braced: Optional[bool] = None,
                              bypass_hits: int = 0,
                              gunnery: bool = False) -> Tuple[int, bool]:
        """apply_damage, crits, and destruction check for one volley. braced:
        the target's Brace for Impact decision, taken before the attack was
        rolled (s.7); None falls back to asking now (older callers).
        Returns (hits left unused because the ship was destroyed, destroyed)."""
        brace = False
        already_braced = (target.special_order ==
                          SpecialOrder.BRACE_FOR_IMPACT.value)
        if braced is not None:
            brace = braced or already_braced
        elif already_braced:
            brace = True
            log_fn("     (already braced)")
        elif self.ctx.is_ai_controlled(target.player):
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
            want_brace = self.ctx.prompt.yes_no(
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
                           target_braced=brace, crit_on=crit_on,
                           attacker_key=attacker.id, origin=(attacker.x, attacker.y),
                           bypass_hits=bypass_hits, gunnery=gunnery)
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
        return dmg["unused_hits"], dmg["destroyed"]

    def _combine_squadron_fire_dialog(self):
        """Pool battery fire from multiple squadron ships into one gunnery roll."""
        from .squadron import get_squadrons
        from .combat import check_weapon_in_range, effective_battery_firepower

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
        # Firing at a squadron targets the whole squadron (s.8)
        t_group = squadron_group(target, self.ctx.gs.get_ships())

        # Build the weapon-contribution list: batteries in arc + range of the
        # target (or any ship of its squadron)
        weapon_rows = []
        for member in squad_with_batteries:
            wr = member.weapons_remaining or {}
            for i, w in enumerate(member.weapons):
                # Bombardment cannons hit on 4+, not the target's armour: they
                # can't share a gunnery roll with ordinary batteries
                if w.get("weapon_type") != "battery" or w.get("hits_on"):
                    continue
                if self._weapon_disabled_by_crit(member, w):
                    continue
                avail = wr.get(str(i), w["strength"])
                if avail <= 0:
                    continue
                if not any(check_weapon_in_arc(member, w, t.x, t.y)
                           and check_weapon_in_range(member, w, t.x, t.y) for t in t_group):
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

        # Squadron against squadron: each group of firing ships that sees a
        # different mix of target aspects chooses the aspect it fires at (s.8)
        from .combat import plan_squadron_volley
        aspect_vars = {}
        if len(t_group) > 1:
            from .combat import best_aspect_choice
            contribs = [(r[0], dict(r[2], strength=r[3])) for r in weapon_rows]
            views = plan_squadron_volley(
                contribs, t_group, blast_markers, phenomena, self.ctx.gs.get_ships(),
                no_column_shifts=in_asteroid_field)["views"]
            # Default: "Best for expected hits" (combat.best_aspect_choice)
            best_aspects = best_aspect_choice(contribs, t_group, blast_markers, phenomena,
                                              self.ctx.gs.get_ships(),
                                              no_column_shifts=in_asteroid_field)
            asp_frame = tk.LabelFrame(dialog, text="Aspect fired at (squadron target)",
                                      font=("Consolas", 9))
            for view, present in views.items():
                if len(present) < 2:
                    continue
                if not asp_frame.winfo_ismapped():
                    asp_frame.pack(fill=tk.X, padx=10, pady=2)
                who = ", ".join(sorted({r[0].name for r in weapon_rows
                                        if tuple(sorted((m.id, r[0].get_target_orientation(m))
                                                        for m in t_group)) == view}))
                row_f = tk.Frame(asp_frame)
                row_f.pack(fill=tk.X)
                tk.Label(row_f, text=f"{who}:", font=("Consolas", 8)).pack(side=tk.LEFT)
                best_a = best_aspects.get(view, present[-1])
                var = tk.StringVar(value=best_a)
                ttk.Combobox(row_f, textvariable=var, values=present, state="readonly",
                             width=12, font=("Consolas", 8)).pack(side=tk.LEFT, padx=4)
                tk.Label(row_f, text=f"(Auto: {best_a.replace('_', ' ')}; "
                                     f"harder aspects can't be hit)",
                         font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)
                aspect_vars[view] = var

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
            from .actions import fire_combined
            rows = [[row[0].id, row[1]] for row, var in zip(weapon_rows, chk_vars) if var.get()]
            aspects = [[[list(p) for p in view], var.get()] for view, var in aspect_vars.items()]
            res = fire_combined(self, primary.id, target.id, rows, aspects, log=_log)
            if res.get("error"):
                messagebox.showwarning("Nothing Selected", res["error"])
                return
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

        phenomena = self.ctx.gs.get_phenomena()

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
            from .actions import fire_at_squadron_ships
            res = fire_at_squadron_ships(self, attacker.id, [m.id for m in squad_members],
                                         chosen_squad_id.get(), orient_var.get(),
                                         int(weapon_idx_var.get()), log=_log)
            if res.get("error"):
                return
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
        from .combat import weapon_disabled_by_crit
        return weapon_disabled_by_crit(ship, weapon)
