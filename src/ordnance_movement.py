"""BFG:XR — Ordnance phase movement & contact resolution.

Mixin for OrdnancePanel: moves every ordnance marker, then resolves
ship contacts (torpedoes, bombers, assault boats, mines), CAP fighter
interception, ordnance-vs-ordnance clashes, and terrain effects.
Split out of ordnance_panel.py, which keeps the launch dialogs.
"""
from tkinter import messagebox
import math

from .models import SpecialOrder, OrdnanceMarker, OrdnanceType


class OrdnanceMovementMixin:
    """Ordnance-phase resolution methods shared into OrdnancePanel."""

    def _get_player_bay_capacity(self, player: int) -> int:
        """Total launch bay strength across all non-destroyed, non-disengaged ships for player."""
        total = 0
        for ship in self.ctx.gs.player_ships(player):
            if ship.is_destroyed or ship.is_disengaged:
                continue
            for w in ship.weapons:
                if w.get("weapon_type") == "launch_bay":
                    total += w.get("strength", 0)
        return total

    def _count_active_craft(self, player: int) -> int:
        """Count attack craft markers currently on the board for player.
        Mines are excluded — they behave like torpedoes, not attack craft."""
        from .ordnance import ATTACK_CRAFT_TYPES
        return sum(1 for o in self.ctx.gs.ordnance
                   if o.get("owner_player") == player
                   and o.get("ordnance_type") in ATTACK_CRAFT_TYPES)

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

    def _raid_brace_fn(self, default_raids: int = 1):
        """Callback asking a raid target whether to Brace for Impact before
        the raids are rolled (s.31). Returns fn(target, msg, n_raids=None)
        -> (wanted, passed). The AI braces against more than two raids or
        when it has fewer than 6 hits left."""
        def _brace_fn(target_ship, msg, n_raids=None):
            from .movement import attempt_brace
            n = default_raids if n_raids is None else n_raids
            if target_ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                self.ctx.log(f"  {target_ship.name} already braced — "
                             f"will roll to repel each raid")
                return True, True
            if self.ctx.is_ai_controlled(target_ship.player):
                if not (n > 2 or target_ship.hits_remaining < 6):
                    return False, False
                check = attempt_brace(target_ship, self.ctx.gs, self.ctx.dice)
                self.ctx.log(
                    f"  [AI] {target_ship.name} brace: "
                    f"{'PASSED' if check['passed'] else 'FAILED'} "
                    f"(rolled {check['roll']} vs Ld {check['needed']})")
                return True, check["passed"]
            if not messagebox.askyesno("Hit-and-Run Raid — Brace?", msg):
                return False, False
            check = attempt_brace(target_ship, self.ctx.gs, self.ctx.dice)
            self.ctx.log(
                f"  {target_ship.name} brace check: "
                f"{'PASSED' if check['passed'] else 'FAILED'} "
                f"(rolled {check['roll']} vs Ld {check['needed']})")
            return True, check["passed"]
        return _brace_fn

    def _turn_boarding_torps(self, ships, mover=None):
        """Before ordnance moves, each boarding salvo launched on an earlier turn
        may turn up to 45° (s.16). The owner chooses; the AI points it at the
        nearest enemy."""
        from tkinter import simpledialog
        from .ordnance import (boarding_torp_may_turn, boarding_torp_suggested_turn,
                               turn_boarding_torp)
        gs = self.ctx.gs
        for i, o_dict in enumerate(list(gs.ordnance)):
            marker = OrdnanceMarker.from_dict(o_dict)
            if mover is not None and marker.owner_player != mover:
                continue
            if not boarding_torp_may_turn(marker, gs.turn_number):
                continue
            suggested = boarding_torp_suggested_turn(marker, ships)
            if self.ctx.is_ai_controlled(marker.owner_player):
                deg = suggested
            else:
                deg = simpledialog.askfloat(
                    "Boarding Torpedoes",
                    f"Player {marker.owner_player}: boarding torpedoes Str "
                    f"{marker.strength} at ({marker.x:.0f}, {marker.y:.0f}), "
                    f"heading {marker.heading:.0f}°.\n"
                    f"Turn before moving: -45 (clockwise) to +45 (anticlockwise).\n"
                    f"Suggested {suggested:+.0f}° points at the nearest enemy.",
                    initialvalue=round(suggested), minvalue=-45, maxvalue=45,
                    parent=self.ctx.root)
                if deg is None:
                    deg = 0.0
            if abs(deg) >= 0.5:
                turn_boarding_torp(marker, deg)
                gs.ordnance[i] = marker.to_dict()
                self.ctx.log(f"  Boarding torpedoes Str {marker.strength} turn "
                             f"{deg:+.0f}° to heading {marker.heading:.0f}°")
        self._turn_guided_and_seeking(ships, mover)

    def _guided_reroll(self, player, ship, roll) -> bool:
        """A failed guided-torpedo Leadership test may use a fleet commander
        re-roll: the AI always does, a human player is asked."""
        tc = self.ctx.tc
        if tc.get_fleet_rerolls(player, ship) <= 0:
            return False
        if not self.ctx.is_ai_controlled(player) and not messagebox.askyesno(
                "Guided Torpedoes - Re-roll?",
                f"{ship.name} rolled {roll} against Leadership {ship.leadership}.\n"
                f"Use a fleet commander re-roll ({tc.get_fleet_rerolls(player, ship)} left)?",
                parent=self.ctx.root):
            return False
        return tc.use_fleet_reroll(player, ship)

    def _guided_enemy_choice(self, enemy_player, candidates):
        """The enemy player chooses which of its ships tries to take control of
        guided torpedoes whose launcher failed its test (owner ruling); the AI
        uses its best Leadership."""
        if self.ctx.is_ai_controlled(enemy_player):
            return max(candidates, key=lambda s: s.leadership)
        from tkinter import simpledialog
        names = [f"{i + 1}. {s.name} (Ld {s.leadership})" for i, s in enumerate(candidates)]
        pick = simpledialog.askinteger(
            "Guided Torpedoes - Take Control?",
            f"Player {enemy_player}: the enemy's guided torpedoes failed their guidance "
            f"test. Choose a ship to try to take control (Leadership test), or Cancel:\n\n"
            + "\n".join(names),
            minvalue=1, maxvalue=len(candidates), parent=self.ctx.root)
        return candidates[pick - 1] if pick else None

    def _turn_guided_and_seeking(self, ships, mover=None):
        """Seeking torpedoes turn up to 45° at the nearest enemy ship; guided
        torpedoes turn up to 45° for whoever wins the Leadership tests (s.16).
        Neither turns in the ordnance phase of its launch turn."""
        from tkinter import simpledialog
        from .ordnance import (seeking_turn, guided_control, guided_suggested_turn,
                               turn_boarding_torp)
        gs = self.ctx.gs
        for i, o_dict in enumerate(list(gs.ordnance)):
            marker = OrdnanceMarker.from_dict(o_dict)
            if mover is not None and marker.owner_player != mover:
                continue
            if marker.launched_turn >= gs.turn_number:
                continue
            if marker.ordnance_type == OrdnanceType.TORPEDO_SEEKING.value:
                deg = seeking_turn(marker, ships)
                label = "Seeking torpedoes"
            elif marker.ordnance_type == OrdnanceType.TORPEDO_GUIDED_LD.value:
                controller, logs = guided_control(marker, gs, self.ctx.dice,
                                                  reroll_fn=self._guided_reroll,
                                                  choose_enemy_fn=self._guided_enemy_choice)
                for line in logs:
                    self.ctx.log(line)
                if controller is None:
                    continue
                suggested = guided_suggested_turn(marker, ships, controller)
                if self.ctx.is_ai_controlled(controller):
                    deg = suggested
                else:
                    who = "your" if controller == marker.owner_player else "the enemy's"
                    deg = simpledialog.askfloat(
                        "Guided Torpedoes",
                        f"Player {controller}: you control {who} guided torpedoes Str "
                        f"{marker.strength} at ({marker.x:.0f}, {marker.y:.0f}), heading "
                        f"{marker.heading:.0f}°.\nTurn before moving: -45 (clockwise) to "
                        f"+45 (anticlockwise).\nSuggested {suggested:+.0f}° points at the "
                        f"nearest of your enemy's ships.",
                        initialvalue=round(suggested), minvalue=-45, maxvalue=45,
                        parent=self.ctx.root)
                    if deg is None:
                        deg = 0.0
                label = "Guided torpedoes"
            else:
                continue
            if abs(deg) >= 0.5:
                turn_boarding_torp(marker, deg)
                gs.ordnance[i] = marker.to_dict()
                self.ctx.log(f"  {label} Str {marker.strength} turn {deg:+.0f}° to "
                             f"heading {marker.heading:.0f}°")

    def _choose_mr_attack_modes(self, ships, removed, mover=None, touching=None) -> dict:
        """{marker id: "bomber" | "assault_boat"} for multi-role craft touching an
        enemy ship. Craft with only one attacking role use it; craft that can do
        both attack the same way as the rest of their wave on that ship (s.24):
        the owner chooses (the AI raids ships with 3+ turrets, else bombs)."""
        from .geometry import circle_touches_square
        from .ordnance import craft_roles, MULTI_ROLE_TYPES, mr_attack_mode_ai
        gs = self.ctx.gs
        modes, groups = {}, {}
        for o in gs.ordnance:
            m = OrdnanceMarker.from_dict(o)
            if m.id in removed or m.ordnance_type not in MULTI_ROLE_TYPES:
                continue
            if mover is not None and m.owner_player != mover:
                continue
            roles = craft_roles(m.ordnance_type)
            can_bomb = "bomber" in roles
            can_raid = "assault_boat" in roles and gs.rule_hit_and_run
            if not (can_bomb or can_raid):
                continue
            target = next((s for s in ships
                           if s.player != m.owner_player
                           and not s.is_destroyed and not s.is_disengaged
                           and s.status not in ("drifting_hulk", "burning_hulk")
                           and (touching(m, s) if touching else
                                circle_touches_square(s.x, s.y, s.base_radius,
                                                      m.x, m.y, m.heading))), None)
            if target is None:
                continue
            if can_bomb and can_raid:
                groups.setdefault((target.id, m.owner_player), (target, []))[1].append(m)
            else:
                modes[m.id] = "bomber" if can_bomb else "assault_boat"
        for (_sid, owner), (target, ms) in groups.items():
            names = ms[0].ordnance_type.replace("_", " ").title()
            if self.ctx.is_ai_controlled(owner):
                mode = mr_attack_mode_ai(target)
            else:
                mode = "bomber" if messagebox.askyesno(
                    "Multi-role Attack Craft",
                    f"{len(ms)} {names} squadron(s) attack {target.name} "
                    f"({target.effective_turrets} turrets).\n\n"
                    f"Attack as BOMBERS? (No = as assault boats, hit-and-run raids)",
                    parent=self.ctx.root) else "assault_boat"
            self.ctx.log(f"  {len(ms)} {names} attack {target.name} as "
                         f"{'bombers' if mode == 'bomber' else 'assault boats'}")
            for m in ms:
                modes[m.id] = mode
        return modes

    def _brace_vs_ordnance(self, marker, ship, expected):
        """Offer Brace for Impact to a ship about to be attacked by ordnance,
        before turrets or attack rolls (s.7). The launching ship counts as the
        attacker (one attempt per attacker per turn). Returns the decision, or
        None when there is no combat panel to ask through."""
        combat = getattr(self.ctx, "combat", None)
        if combat is None:
            return None
        from .combat import squadron_group
        launcher = self.ctx.gs.get_ship_by_id(marker.launched_by)
        name = f"{marker.ordnance_type.replace('_', ' ')}" + (
            f" from {launcher.name}" if launcher else "")
        return combat._brace_before_attack(
            marker.launched_by or marker.id, name, ship, expected,
            group=squadron_group(ship, self.ctx.gs.get_ships()), attacker=launcher)

    def _resolve_moving_ship_contacts(self):
        """Ships that moved into ordnance during their own move are attacked by
        it now (s.15). execute_movement records the markers each ship touched."""
        gs = self.ctx.gs
        live = {o["id"] for o in gs.ordnance}
        for sd in list(gs.ships):
            pending = sd.get("pending_ordnance_contacts") or []
            if not pending:
                continue
            ship = gs.get_ship_by_id(sd["id"])
            ship.pending_ordnance_contacts = []
            gs.update_ship(ship)
            forced = {mid: ship.id for mid in pending if mid in live}
            if not forced or ship.is_destroyed or ship.is_disengaged:
                continue
            self.ctx.log(f"  {ship.name} moved into {len(forced)} ordnance marker(s)")
            self._resolve_ship_contacts([ship], forced=forced)
        self.ctx.board.redraw()

    def _resolve_ship_contacts(self, ships, mover=None, skip_ids=frozenset(),
                               forced=None):
        """Ordnance touching ships attacks them (s.15): turrets fire at incoming
        attack craft, multi-role craft choose how to attack, then torpedoes,
        bombers, mines and assault boats resolve.

        mover: only this player's markers (the ordnance phase runs one pass per
        player); None for all. forced: {marker id: ship id} contacts made by a
        ship moving into ordnance during its own move; only those resolve, and
        they count as touching whatever the end positions."""
        from .ordnance import craft_roles
        from .ordnance import (check_torpedo_contact, resolve_torpedo_attack,
                               torpedo_may_attack, is_torpedo_salvo,
                               resolve_bomber_attack, resolve_mine_contact,
                               resolve_bomber_interception, attacks_ships,
                               ATTACK_CRAFT_TYPES)
        from .geometry import circle_touches_square

        path_start = getattr(self, "_ord_path_start", None) or {}

        def contact_point(m, s):
            """Where a torpedo salvo touched the ship during this move (its
            whole path counts, s.15), else None."""
            from .geometry import torpedo_first_contact
            x0, y0 = path_start.get(m.id, (m.x, m.y))
            return torpedo_first_contact(s.x, s.y, s.base_radius, x0, y0, m.x, m.y, m.heading)

        def touching(m, s):
            if forced is not None:
                return forced.get(m.id) == s.id
            if is_torpedo_salvo(m):
                return check_torpedo_contact(m, s) or contact_point(m, s) is not None
            return circle_touches_square(s.x, s.y, s.base_radius, m.x, m.y, m.heading)

        # Optional Modern / Remastered blast markers (s.11): ordnance attacking a
        # ship in contact with blast markers is treated as moving through them
        # (destroyed on a 6); a wave rolls once
        from .optional_rules import blast_rules, in_blast_contact
        from .ordnance import check_ordnance_vs_blast_contact
        if blast_rules() != "standard":
            bms = self.ctx.gs.get_blast_markers()
            rolled, gone = set(), set()
            for m in [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance]:
                key = m.wave_id or m.id
                if (m.id in skip_ids or key in rolled or m.cap_ship_id
                        or (mover is not None and m.owner_player != mover)):
                    continue
                hit = next((s for s in ships if not s.is_destroyed and s.player != m.owner_player
                            and touching(m, s) and in_blast_contact(s, bms, ships)), None)
                if hit is None:
                    continue
                rolled.add(key)
                if check_ordnance_vs_blast_contact(self.ctx.dice):
                    gone.update(o["id"] for o in self.ctx.gs.ordnance
                                if (o.get("wave_id") or o["id"]) == key)
                    self.ctx.log(f"  {m.ordnance_type} attacking {hit.name} destroyed by "
                                 f"its blast markers")
            if gone:
                self.ctx.gs.ordnance = [o for o in self.ctx.gs.ordnance if o["id"] not in gone]
                skip_ids = frozenset(skip_ids) | gone

        # 3. Check ordnance contact with ships
        to_remove_after = set()

        # Phase 1: attack craft wave interception — turrets (with massed bonus) fire
        # once per ship at every incoming wave of bombers and assault boats before
        # any attack or hit-and-run raid resolves.
        live_ordnance = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance]
        from .waves import ship_attack_plan
        self._wave_plan = {}            # attacking marker id -> how it attacks which ship
        planned = set()
        wave_spent = set()              # whole waves removed after attacking (s.25)
        for s in ships:
            if s.is_destroyed or s.is_disengaged:
                continue
            # Enemy attack craft touching this ship, by wave (a lone squadron is
            # its own group). Turrets fire once at each group that must attack.
            touching_craft = [
                m for m in live_ordnance
                if m.ordnance_type in ATTACK_CRAFT_TYPES and not m.cap_ship_id
                and (mover is None or m.owner_player == mover)
                and m.owner_player != s.player
                and m.id not in skip_ids and m.id not in planned
                and touching(m, s)]
            groups = {}
            for m in touching_craft:
                groups.setdefault(m.wave_id or m.id, []).append(m)
            for key, group in groups.items():
                if not any(attacks_ships(m.ordnance_type) for m in group):
                    continue            # fighters alone don't attack ships
                if group[0].wave_id:    # the whole wave, lead first
                    group = sorted((m for m in live_ordnance if m.wave_id == key
                                    and m.id not in to_remove_after), key=lambda m: m.wave_order)
                planned.update(m.id for m in group)
                # Brace for Impact before the turrets fire at a wave that may make
                # attack runs (s.7); raids keep their own order (s.31)
                if any("bomber" in craft_roles(m.ordnance_type) for m in group):
                    self._brace_vs_ordnance(group[0], s, 2.0 * len(group))
                    s = self.ctx.gs.get_ship_by_id(s.id) or s     # keep the brace
                p1 = resolve_bomber_interception(
                    len(group), s, ships, self.ctx.dice, self.ctx.gs)
                for msg in p1["log"]:
                    self.ctx.log(msg)
                plan = ship_attack_plan(group, p1["killed"])
                for m in group[:p1["killed"]]:
                    self.ctx.log(f"  {m.ordnance_type} [{m.id[:8]}] destroyed by turrets")
                    to_remove_after.add(m.id)
                n_bombers = sum(1 for m in plan["attackers"]
                                if "bomber" in craft_roles(m.ordnance_type))
                for m in plan["attackers"]:
                    self._wave_plan[m.id] = {"ship": s.id,
                                             "suppressed": m.id in plan["suppressed"],
                                             "fighters": plan["suppressors"],
                                             "bombers": n_bombers}
                if group[0].wave_id:
                    if plan["suppressors"]:
                        self.ctx.log(f"  {plan['suppressors']} fighter squadron(s) in the "
                                     f"wave suppress turrets for "
                                     f"{len(plan['suppressed'])} bomber squadron(s)")
                    wave_spent.update(plan["removed_after"])

        # Multi-role craft that can attack as bombers or assault boats choose
        # now, after the turrets have fired, one way per wave (s.24)
        mr_modes = self._choose_mr_attack_modes(ships, to_remove_after | skip_ids, mover,
                                                touching)

        # Per-marker ship contact resolution
        for o_dict in list(self.ctx.gs.ordnance):
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.id in to_remove_after or marker.id in skip_ids:
                continue
            if mover is not None and marker.owner_player != mover:
                continue
            if forced is not None and marker.id not in forced:
                continue

            is_torp = is_torpedo_salvo(marker)
            is_bomber = (marker.ordnance_type in (
                OrdnanceType.BOMBER.value, OrdnanceType.MANTA.value)
                or mr_modes.get(marker.id) == "bomber")
            is_assault_boat = (marker.ordnance_type == OrdnanceType.ASSAULT_BOAT.value
                               or mr_modes.get(marker.id) == "assault_boat")

            if is_torp:
                # Torpedoes attack ANY ship they contact (friend or foe), except
                # friendly ships that were in base contact with the launcher at
                # launch (captured in marker.launch_exempt_ships).
                # Ships in the order the salvo reaches them along its path
                _h = math.radians(marker.heading)
                for s in sorted(ships, key=lambda sh: (sh.x - marker.x) * math.cos(_h)
                                + (sh.y - marker.y) * math.sin(_h)):
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status == "destroyed":
                        continue
                    if (s.id in (marker.launch_exempt_ships or [])
                            and marker.launched_turn == self.ctx.gs.turn_number):
                        continue
                    if not torpedo_may_attack(marker, s, self.ctx.gs):
                        continue   # not a valid target, outside the launch arc, or already attacked
                    if not touching(marker, s):
                        continue

                    # CAP fighters intercept before the torpedo hits
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  Torpedoes contact {s.name}"
                        + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                        + "!")
                    # The attack comes from where the salvo touched the ship
                    # (armour facing, shield impacts), not where it ended up
                    hit_at = (None if forced is not None or check_torpedo_contact(marker, s)
                              else contact_point(marker, s))
                    attacker = marker
                    if hit_at is not None:
                        attacker = OrdnanceMarker.from_dict(
                            {**marker.to_dict(), "x": hit_at[0], "y": hit_at[1]})
                    # Brace for Impact before turrets and to-hit rolls (s.7)
                    braced = self._brace_vs_ordnance(
                        marker, s, marker.strength * max(0, 7 - s.armor_vs(attacker.x, attacker.y)) / 6)
                    s = self.ctx.gs.get_ship_by_id(s.id) or s     # keep the brace
                    result = resolve_torpedo_attack(
                        attacker, s, self.ctx.dice, self.ctx.gs,
                        all_ships=ships,
                        brace_decision_fn=None if braced is not None else self._raid_brace_fn())
                    marker.attacked_turns = {**(marker.attacked_turns or {}),
                                             s.id: self.ctx.gs.turn_number}
                    raids = result.get("raids")
                    if raids:
                        self.ctx.log(
                            f"  Raid result: {len(raids['crits_applied'])} crit(s), "
                            f"{raids['damage']} damage, {raids['repelled']} repelled, "
                            f"{raids['failures']} failed")

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
                # Bombers attack the enemy ship their wave (or they alone)
                # contacted and faced turrets from
                plan = self._wave_plan.get(marker.id)
                for s in ships:
                    if plan is None or s.id != plan["ship"]:
                        continue
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    # CAP fighters intercept before the bomber attacks
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  {marker.ordnance_type} attacks {s.name}!")

                    # Turret suppression by fighters in the same wave (s.27)
                    suppressing_fighters = plan["fighters"] if (
                        plan["suppressed"] or self.ctx.gs.rule_turret_suppression_remastered) else 0
                    total_bombers_on_target = plan["bombers"]

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
                    if not touching(marker, s):
                        continue

                    # CAP fighters intercept the mine before it detonates
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  Mine contacts {s.name}"
                        + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                        + "!")
                    self._brace_vs_ordnance(
                        marker, s, 8 * max(0, 7 - s.armor_vs(marker.x, marker.y)) / 6)
                    s = self.ctx.gs.get_ship_by_id(s.id) or s     # keep the brace
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
                plan = self._wave_plan.get(marker.id)
                for s in ships:
                    if plan is None or s.id != plan["ship"]:
                        continue
                    if s.is_destroyed or s.is_disengaged:
                        continue
                    if s.status in ("drifting_hulk", "burning_hulk", "destroyed"):
                        continue

                    # CAP fighters intercept before the raid
                    if self._check_cap_intercept(marker, s, to_remove_after):
                        break

                    self.ctx.log(
                        f"  Assault boats contact {s.name} — hit-and-run raid!")

                    _brace_fn = self._raid_brace_fn(marker.strength)

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

        # Remove spent ordnance; a wave that attacked a ship is removed whole,
        # squadrons that didn't attack included (s.25)
        to_remove_after |= wave_spent
        if to_remove_after:
            self.ctx.gs.ordnance = [
                o for o in self.ctx.gs.ordnance
                if o["id"] not in to_remove_after]
        from .waves import tidy_waves
        tidy_waves(self.ctx.gs)


    def _resolve_ordnance_movement(self):
        """Move all ordnance markers in the ordnance phase.
        Order: degrade Tau missiles, move all, blast checks,
        ordnance-vs-ordnance interactions, then ship contacts."""
        from .ordnance import (move_ordnance, degrade_tau_missiles,
                                check_ordnance_vs_blast,
                                check_ordnance_vs_phenomena,
                                resolve_ordnance_interactions)

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

        # AI attack craft pick their targets for this move (s.18)
        from .ordnance import assign_ai_craft_targets
        for player in (1, 2):
            if self.ctx.is_ai_controlled(player):
                assign_ai_craft_targets(self.ctx.gs, player)

        # Both players move and attack with all their ordnance; the player whose
        # turn it is moves all of theirs first (s.15)
        active = self.ctx.gs.active_player
        for mover in (active, 2 if active == 1 else 1):
            ships = self.ctx.gs.get_ships()
            blast_markers = self.ctx.gs.get_blast_markers()
            phenomena = self.ctx.gs.get_phenomena()
            to_remove = set()

            # 1. Move this player's ordnance
            self._turn_boarding_torps(ships, mover)

            self._ord_path_start = {}
            from .waves import members as wave_members, wave_speed
            all_markers = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance]
            wave_of = {}                 # lead id -> its wave's other member ids
            for i, o_dict in enumerate(list(self.ctx.gs.ordnance)):
                marker = OrdnanceMarker.from_dict(o_dict)
                if marker.owner_player != mover:
                    continue
                if marker.wave_id:
                    # A wave moves as one marker, at its slowest squadron's
                    # speed, with one blast marker roll (s.25)
                    ms = wave_members(all_markers, marker.wave_id)
                    if ms[0].id != marker.id:
                        continue                         # follows its lead
                    wave_of[marker.id] = [m.id for m in ms[1:]]
                    marker.speed = wave_speed(ms)
                self._ord_path_start[marker.id] = (marker.x, marker.y)
                move_ordnance(marker, self.ctx.gs)
                if marker.wave_id:
                    marker.speed = o_dict["speed"]

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

            # Waves: the rest of each wave goes where its lead went, or with it
            for lead_id, others in wave_of.items():
                lead = next((o for o in self.ctx.gs.ordnance if o["id"] == lead_id), None)
                for j, o in enumerate(self.ctx.gs.ordnance):
                    if o["id"] not in others:
                        continue
                    if lead_id in to_remove or lead is None:
                        to_remove.add(o["id"])
                    else:
                        self.ctx.gs.ordnance[j] = {**o, "x": lead["x"], "y": lead["y"],
                                                   "heading": lead["heading"]}
                        self._ord_path_start[o["id"]] = self._ord_path_start.get(lead_id)

            # Remove off-table and blast-destroyed ordnance
            if to_remove:
                self.ctx.gs.ordnance = [
                    o for o in self.ctx.gs.ordnance if o["id"] not in to_remove]

            # 2. Ordnance-vs-ordnance interactions (fighters intercept, torp collisions)
            interaction_logs = resolve_ordnance_interactions(self.ctx.gs, self.ctx.dice)
            for log in interaction_logs:
                self.ctx.log(log)

            self._resolve_ship_contacts(ships, mover, frozenset(to_remove))

            # 3. Short burn torpedoes that moved may run out of fuel (s.16)
            from .ordnance import short_burn_fuel_checks
            for log in short_burn_fuel_checks(self.ctx.gs, self.ctx.dice, mover):
                self.ctx.log(log)

        self.ctx.log(
            f"  Ordnance phase complete: {len(self.ctx.gs.ordnance)} markers remain")
        self.ctx.board.redraw()

