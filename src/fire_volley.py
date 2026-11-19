"""A ship's volley in the shooting phase, as the Fire dialog orders it (To do
18: the rules out of the window; To do 17: a human's volley is one recorded
action, actions.fire_volley, so it replays).

The player's orders: each weapon fired, its target (None when the chosen
option has no valid target) and the firepower to use (None: all that is
left). The volley then runs as the dialog always did: target priority, Brace
before each kind of weapon, batteries as one roll per target and gunnery
type (s.13, optionally simultaneous), lances, the nova cannon, star pulse and
Armageddon Gun, hits applied per kind, the weapons used recorded."""
from .models import SpecialOrder
from .chapter_tactics import weapon_range
from .combat import (weapon_fire_pool, shot_weapon, resolve_siege_cannons, expected_hits,
                     resolve_batteries, resolve_lances, resolve_nova_cannon,
                     apply_damage, check_los_clear, squadron_group, fire_at_squadron)

# Fire order within one ship's volley: batteries, then lances, then the nova
# cannon (the target is asked about bracing before each kind, s.7)
_FIRE_ORDER = {"battery": 0, "lance": 1, "nova_cannon": 2, "armageddon_gun": 3,
               "star_pulse": 4}


class _Val:
    """A fixed value read like a Tk variable."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


def volley_setup(gs, attacker):
    """What the volley depends on, as the Fire dialog works it out when it
    opens: the enemies that may be fired on (hulks included, s.34), the
    closest visible one (target priority), Lock On, whether the ship is in
    an asteroid field, the blast markers."""
    from .models import Ship
    enemy_player = 2 if attacker.player == 1 else 1
    enemies = [Ship.from_dict(s) for s in gs.ships
               if s["player"] == enemy_player
               and (not Ship.from_dict(s).is_destroyed
                    or s.get("status") in ("drifting_hulk", "burning_hulk"))
               and s.get("status") != "destroyed"
               and not s.get("is_disengaged", False)]
    enemies.sort(key=lambda e: attacker.distance_to(e))
    phenomena = gs.get_phenomena()
    blast_markers = gs.get_blast_markers()
    closest_visible = next(
        (e for e in enemies
         if e.status == "active"          # a closest hulk may be ignored (s.34)
         and check_los_clear(attacker, e, phenomena, blast_markers, gs.ships)["clear"]),
        None)
    lock_on = attacker.special_order == SpecialOrder.LOCK_ON.value
    from .terrain_effects import check_ship_terrain_contact
    in_asteroid_field = any(c["type"] == "asteroid_field"
                            for c in check_ship_terrain_contact(attacker, phenomena))
    return enemies, closest_visible, lock_on, in_asteroid_field, blast_markers


class FireVolley:
    """One ship's ordered volley (no window). panel: the shooting panel
    (CombatPanel: Brace, applying hits); log: where the volley's lines go."""

    def __init__(self, panel, ship_id: str, orders, together: bool = False, log=None,
                 context=None):
        """context: what the dialog was opened with, {"closest": id or None,
        "lock_on", "asteroid"}; None works it out from the game state
        (volley_setup)."""
        self.panel = panel
        self.ctx = panel.ctx
        gs = self.ctx.gs
        self.attacker = gs.get_ship_by_id(ship_id)
        (self.enemies, self.closest_visible, self.lock_on, self.in_asteroid_field,
         self.blast_markers) = volley_setup(gs, self.attacker)
        if context is not None:
            cid = context.get("closest")
            self.closest_visible = gs.get_ship_by_id(cid) if cid else None
            self.lock_on = bool(context.get("lock_on"))
            self.in_asteroid_field = bool(context.get("asteroid"))
            self.enemies = [gs.get_ship_by_id(i) for i in context.get("enemies", [])
                            if gs.get_ship_by_id(i) is not None] or self.enemies
        self._together_var = _Val(bool(together))
        self._pool_modes = {}   # Heavy Gunz range mode fixed by this volley
        self._sink = log
        wr = self.attacker.weapons_remaining or {}
        self.weapon_assignments = []
        for w_idx, target_id, strength in orders:
            weapon = self.attacker.weapons[w_idx]
            avail = wr.get(str(w_idx), weapon.get("strength", 0))
            self.weapon_assignments.append(
                (w_idx, weapon, _Val(True), _Val(target_id),
                 _Val(strength), avail))   # None: all that is left

    def _log(self, msg):
        (self._sink or self.ctx.log)(msg)

    def _resolve_target(self, weapon, target_id):
        return next((e for e in self.enemies if e.id == target_id), None) if target_id else None

    def run(self):
        self._fire_all()

    def _check_target_priority(self, weapon, target):
        """Enforce target priority; returns the ship that must actually be fired at."""
        cv = self.closest_visible
        from .subplots import punitive_target
        pt = punitive_target(self.ctx.gs, self.attacker,
                             [s for s in self.ctx.gs.get_ships() if not s.is_destroyed
                              and not s.is_disengaged
                              and self.attacker.distance_to(s)
                              <= (weapon_range(self.attacker, weapon) or 999)
                              and (self.attacker.get_target_arc(s.x, s.y).value
                                   in weapon.get("arcs", []) or not weapon.get("arcs"))])
        if pt is not None:
            cv = pt              # Punitive Strike: must target it unless the test passes
        if not cv or target.id == cv.id:
            return target
        from .planet_scenarios import priority_free
        if priority_free(self.ctx.gs, self.attacker, target):
            return target    # Exterminatus!: an Exterminator counts as the closest
        # A hulk that is the closest enemy may be fired on without a test (s.34)
        if (target.status in ("drifting_hulk", "burning_hulk")
                and self.attacker.distance_to(target) < self.attacker.distance_to(cv)):
            return target
        cv_arc = self.attacker.get_target_arc(cv.x, cv.y)
        cv_in_arc = cv_arc.value in weapon.get("arcs", []) or not weapon.get("arcs")
        cv_in_range = (self.attacker.distance_to(cv)
                       <= (weapon_range(self.attacker, weapon) or 999))
        cv_los = check_los_clear(self.attacker, cv,
                                 self.ctx.gs.get_phenomena(), self.blast_markers, self.ctx.gs.ships)
        if not (cv_in_arc and cv_in_range and cv_los["clear"]):
            return target  # closest visible isn't valid for this weapon
        # One target priority test per ship per turn (s.7): the result stands
        att = self.ctx.gs.get_ship_by_id(self.attacker.id) or self.attacker
        if att.target_priority_turn == self.ctx.gs.turn_number:
            if att.target_priority_passed:
                return target
            self._log(f"  {weapon['name']}: target priority already failed this turn — "
                      f"must fire at closest visible: {cv.name}")
            return cv
        from .movement import do_command_check
        check = do_command_check(self.attacker, "target_priority", self.ctx.dice, gs=self.ctx.gs)
        from .movement import fleet_reroll_offered
        if not check["passed"] and fleet_reroll_offered(
                self.ctx.gs, self.attacker, "target priority", check["roll"], check["needed"]):
            check = do_command_check(self.attacker, "target_priority", self.ctx.dice, gs=self.ctx.gs)
        att.target_priority_turn = self.ctx.gs.turn_number
        att.target_priority_passed = check["passed"]
        self.ctx.gs.update_ship(att)
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
        # 1. Settle each weapon's target (target priority decides who is shot)
        self._volley_targets = {}
        for w_idx, weapon, enabled, target_var, _sv, _av in self.weapon_assignments:
            if not enabled.get():
                continue
            target = self._resolve_target(weapon, target_var.get())
            if target is not None:
                self._volley_targets[w_idx] = self._check_target_priority(weapon, target)
        # 2. Targets decide on Brace for Impact before any combat rolls (s.7),
        # separately against each kind of weapon (they may brace against the
        # lances after not bracing against the batteries, but try only once per
        # attacker per turn). Batteries fire first: their shield hits place
        # blast markers that lances ignore.
        self._braced = {}
        self._brace_targets(("battery",))
        # 3. Roll
        siege_done = self._fire_siege_cannons(all_damage, fired_weapon_indices)

        asked_kinds = {"battery"}
        self._fire_battery_groups(all_damage, fired_weapon_indices, siege_done)
        for w_idx, weapon, enabled, target_var, str_var, avail_str in sorted(
                self.weapon_assignments, key=lambda a: _FIRE_ORDER.get(
                    a[1].get("weapon_type", ""), 9)):
            if not enabled.get() or w_idx in siege_done:
                continue
            if weapon.get("weapon_type") == "battery":
                continue                    # fired as groups above (s.13)
            target = self._volley_targets.get(w_idx)
            if target is None:
                self._log(f"  {weapon['name']}: skipped (no valid target)")
                continue

            weapon_actually_fired = True
            wtype = weapon.get("weapon_type", "")
            if wtype in _FIRE_ORDER and wtype not in asked_kinds:
                asked_kinds.add(wtype)
                self._apply_volley_damage(all_damage, final=False)
                self._brace_targets((wtype,))
            phenomena = self.ctx.gs.get_phenomena()
            if wtype in ("battery", "lance"):
                pool, mode, err = weapon_fire_pool(
                    self.attacker, weapon, w_idx,
                    self.attacker.distance_to(target), self.ctx.dice, self.ctx.gs)
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
                        crit_on=weapon.get("crit_on", 6),
                        braced=self._braced.get(fresh.id, False),
                        gunnery=wtype == "battery")

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
                if weapon.get("kustom_kannon"):
                    from .combat import spend_kustom_kannon
                    spend_kustom_kannon(self.attacker, weapon, self.ctx.gs)
                if sr.hits > 0:
                    all_damage.setdefault(target.id, []).append(
                        (sr.hits, "battery", target, weapon.get("crit_on", 6),
                         self._braced.get(target.id, False)))

            elif wtype == "lance":
                sr = resolve_lances(self.attacker, target, fire_weapon,
                                    self.ctx.dice, self.lock_on)
                self._log(f"  {sr.description}")
                if sr.hits > 0:
                    all_damage.setdefault(target.id, []).append(
                        (sr.hits, "lance", target, weapon.get("crit_on", 6),
                         self._braced.get(target.id, False), sr.bypass_hits))

            elif wtype == "star_pulse":
                from .combat import resolve_star_pulse
                res = resolve_star_pulse(self.attacker, self.ctx.gs, self.ctx.dice)
                if "error" in res:
                    self._log(f"  Star pulse: {res['error']}")
                    weapon_actually_fired = False
                else:
                    for sid in res["hits"]:
                        hs = self.ctx.gs.get_ship_by_id(sid)
                        if hs is not None:
                            self._log(f"  Star pulse hits {hs.name}")
                            self.ctx.check_destruction(hs)

            elif wtype == "armageddon_gun":
                from .combat import resolve_armageddon_gun
                res = resolve_armageddon_gun(self.attacker, self.ctx.gs, self.ctx.dice)
                if "error" in res:
                    self._log(f"  Armageddon Gun: {res['error']}")
                    weapon_actually_fired = False
                else:
                    for sid, n in res["hits"].items():
                        hs = self.ctx.gs.get_ship_by_id(sid)
                        if hs is not None:
                            self._log(f"  Armageddon Gun hits {hs.name}: {n} hit(s)")
                            self.ctx.check_destruction(hs)
                    if res["blocked"]:
                        self._log("  Armageddon Gun blocked: blast markers at the obstacle")

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
                                                 target_braced=hit_ship.special_order
                                                 == SpecialOrder.BRACE_FOR_IMPACT.value,
                                                 attacker_key=self.attacker.id,
                                                 origin=(tx, ty))
                                    self.ctx.check_destruction(hit_ship)
                        else:
                            self._log("  Nova Cannon: no ships hit")
                        for bx, by in nc.get("blast_markers", []):
                            from .models import BlastMarker as BM
                            bm = BM(id=f"nova_miss_{self.ctx.gs.next_serial()}",
                                    x=bx, y=by, source="nova_cannon_miss")
                            self.ctx.gs.add_blast_marker(bm)
                            self._log(
                                f"  Blast marker placed at ({bx:.0f}, {by:.0f})")

            if weapon_actually_fired:
                fired_weapon_indices.append((w_idx, fire_str, avail_str))

        self._apply_volley_damage(all_damage)
        self._record_fired(fired_weapon_indices)

    def _battery_pool(self, w_idx, weapon, target, str_var, avail_str):
        """This shot's firepower for one battery: a random value rolled now
        (after the target chose to brace), Heavy Gunz by range, the player's
        chosen strength within what is available. None if it can't fire."""
        pool, mode, err = weapon_fire_pool(
            self.attacker, weapon, w_idx, self.attacker.distance_to(target),
            self.ctx.dice, self.ctx.gs)
        if err:
            self._log(f"  {err}")
            return None
        if (weapon.get("strength_dice") or weapon.get("strength_close")
                is not None) and str(w_idx) not in self.attacker.weapons_remaining:
            if weapon.get("strength_dice"):
                self._log(f"  {weapon['name']}: rolled {weapon['strength_dice']} = {pool}")
            if self.in_asteroid_field:
                pool = max(1, (pool + 1) // 2)
            avail_str = pool
        if mode:
            self._pool_modes[w_idx] = mode
        try:
            fire_str = max(1, min(int(str_var.get()), avail_str))
        except (ValueError, TypeError):
            fire_str = avail_str
        return fire_str, avail_str

    def _fire_battery_groups(self, all_damage, fired_weapon_indices, siege_done):
        """Owner ruling (s.11 / s.13): every macrobattery of one gunnery type
        the ship fires at one target makes ONE roll on their total firepower
        (combat.resolve_battery_group). Groups fire in turn and each sees the
        blast markers in play (markers come into effect at once), so a group's
        hits are applied before the next rolls; with "Fire different gunnery
        weapons together" every group uses the markers from before the volley
        (s.13 Mixing Different Gunnery Weapons)."""
        from .combat import gunnery_kind, resolve_battery_group
        gs = self.ctx.gs
        together = bool(self._together_var.get()) if hasattr(self, "_together_var") else False
        start_markers = gs.get_blast_markers()
        groups = {}
        for w_idx, weapon, enabled, _tv, str_var, avail_str in self.weapon_assignments:
            if (not enabled.get() or w_idx in siege_done
                    or weapon.get("weapon_type") != "battery"):
                continue
            target = self._volley_targets.get(w_idx)
            if target is None:
                self._log(f"  {weapon['name']}: skipped (no valid target)")
                continue
            groups.setdefault((target.id, gunnery_kind(weapon)), []).append(
                (w_idx, weapon, str_var, avail_str))
        phenomena = gs.get_phenomena()
        for (tid, _kind), entries in groups.items():
            target = gs.get_ship_by_id(tid)
            if target is None or (target.is_destroyed and not target.is_hulk):
                self._log(f"  {', '.join(e[1]['name'] for e in entries)}: target already "
                          f"destroyed")
                continue
            shots, fired = [], []
            for w_idx, weapon, str_var, avail_str in entries:
                got = self._battery_pool(w_idx, weapon, target, str_var, avail_str)
                if got is None:
                    continue
                fire_str, avail = got
                shots.append(shot_weapon(weapon, fire_str))
                fired.append((w_idx, fire_str, avail))
            if not shots:
                continue
            crit_on = entries[0][1].get("crit_on", 6)

            def _apply_to(member, n, _c=crit_on):
                fresh = gs.get_ship_by_id(member.id)
                if not fresh or fresh.is_destroyed:
                    return n, True
                self._log(f"  >> {fresh.name}: {n} hits")
                return self.panel._apply_hits_to_target(
                    self.attacker, fresh, n, self._log, crit_on=_c,
                    braced=self._braced.get(fresh.id, False), gunnery=True)
            markers = start_markers if together else gs.get_blast_markers()
            sr, applied = resolve_battery_group(
                self.attacker, target, shots, self.ctx.dice, markers, self.lock_on,
                phenomena, gs.ships, no_column_shifts=self.in_asteroid_field,
                group=squadron_group(target, gs.get_ships()), apply_hits=_apply_to,
                range_cap=10 if self.in_asteroid_field else None)
            for _w_idx, weapon, *_r in entries:
                if weapon.get("kustom_kannon"):
                    from .combat import spend_kustom_kannon
                    spend_kustom_kannon(self.attacker, weapon, gs)
            fired_weapon_indices.extend(fired)
            if applied is not None:
                self._log(f"  {sr.description} — squadron takes {sr.hits} hit(s)")
                continue
            self._log(f"  {sr.description}")
            if sr.hits > 0:
                all_damage.setdefault(target.id, []).append(
                    (sr.hits, "battery", target, crit_on, self._braced.get(target.id, False)))
            if not together:
                self._apply_volley_damage(all_damage, final=False)   # its markers now count

    def _apply_volley_damage(self, all_damage, final=True):
        """Apply the hits rolled so far, then clear them (each kind of weapon's
        hits are applied before the target decides on bracing against the next,
        so hits rolled before it braced get no save, s.7). Hulks don't brace:
        until `final` their hits wait, so a hulk takes the whole volley at once."""
        for target_id, hit_list in list(all_damage.items()):
            # Hits that crit on 4+ (bombardment cannons) are applied separately;
            # a hulk takes the whole volley at once (one re-roll per attacking
            # ship, s.34)
            tgt0 = self.ctx.gs.get_ship_by_id(target_id)
            if tgt0 is not None and tgt0.status in ("drifting_hulk", "burning_hulk"):
                if not final:
                    continue
                hit_list = [(sum(e[0] for e in hit_list), "battery", tgt0, 6,
                             self._braced.get(target_id, False))]
            # Hits rolled before the target braced get no save (s.7): each
            # batch keeps the brace state it was rolled under (unbraced first)
            batches = sorted({(e[3], e[4]) for e in hit_list},
                             key=lambda cb: (cb[1], -cb[0]))
            for crit_on, was_braced in batches:
                total = sum(e[0] for e in hit_list if (e[3], e[4]) == (crit_on, was_braced))
                bypass = sum(e[5] for e in hit_list
                             if len(e) > 5 and (e[3], e[4]) == (crit_on, was_braced))
                target = self.ctx.gs.get_ship_by_id(target_id)
                if not target or (target.is_destroyed and not target.is_hulk):
                    continue
                self._log(f"  >> {target.name}: {total} total hits"
                          + (f" (crits on {crit_on}+)" if crit_on != 6 else "")
                          + (" (braced)" if was_braced else ""))
                gunnery = any(e[1] == "battery" for e in hit_list
                              if (e[3], e[4]) == (crit_on, was_braced))
                self.panel._apply_hits_to_target(self.attacker, target, total, self._log,
                                                 crit_on=crit_on, braced=was_braced,
                                                 bypass_hits=bypass, gunnery=gunnery)
            del all_damage[target_id]

    def _brace_targets(self, kinds=("battery", "lance", "nova_cannon")) -> dict:
        """Ask each target of this ship's weapons of `kinds` (one test per
        squadron) whether it braces, before those weapons roll anything (s.7).
        A target that declined earlier in the volley is asked again; one that
        failed or is braced isn't (`_brace_before_attack`). Merges into and
        returns self._braced, {ship id: braced}."""
        braced = getattr(self, "_braced", None)
        if braced is None:
            braced = self._braced = {}
        asked = set()
        by_target = {}
        for w_idx, weapon, *_ in self.weapon_assignments:
            t = self._volley_targets.get(w_idx)
            if t is None or weapon.get("weapon_type") not in kinds:
                continue
            by_target.setdefault(t.id, (t, []))[1].append(weapon)
        for t, weapons in by_target.values():
            group = squadron_group(t, self.ctx.gs.get_ships())
            key = tuple(sorted(m.id for m in group))
            if key in asked:
                continue
            asked.add(key)
            # (a nova cannon: ask the target before the scatter roll, s.7)
            expected = sum(expected_hits(self.attacker, w, t) if w.get("weapon_type") != "nova_cannon"
                           else 1.0 for w in weapons)
            b = self.panel._brace_before_attack(
                self.attacker.id, self.attacker.name, t, expected, self._log,
                group=group, attacker=self.attacker)
            for m in group:
                fresh = self.ctx.gs.get_ship_by_id(m.id)
                braced[m.id] = b or (fresh is not None and fresh.special_order
                                     == SpecialOrder.BRACE_FOR_IMPACT.value)
        return braced

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
            target = self._volley_targets.get(w_idx)
            if target is None or len(squadron_group(target, self.ctx.gs.get_ships())) > 1:
                continue
            groups.setdefault(target.id, (target, []))[1].append((w_idx, weapon))
        for target, ws in groups.values():
            macro = [(i, w) for i, w in ws if not w.get("hits_on")]
            bcs = [(i, w) for i, w in ws if w.get("hits_on")]
            if not macro or not bcs:
                continue
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
                        (res.hits, wtype, target, crit_on,
                         self._braced.get(target.id, False)))
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

