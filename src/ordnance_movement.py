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
        the raids are rolled (s.28). Returns fn(target, msg, n_raids=None)
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
        may turn up to 45° (s.13). The owner chooses; the AI points it at the
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

    def _choose_mr_attack_modes(self, ships, removed, mover=None) -> dict:
        """{marker id: "bomber" | "assault_boat"} for multi-role craft touching an
        enemy ship. Craft with only one attacking role use it; craft that can do
        both attack the same way as the rest of their wave on that ship (s.21):
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
                           and circle_touches_square(s.x, s.y, s.base_radius,
                                                     m.x, m.y, m.heading)), None)
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

    def _resolve_ordnance_movement(self):
        """Move all ordnance markers in the ordnance phase.
        Order: degrade Tau missiles, move all, blast checks,
        ordnance-vs-ordnance interactions, then ship contacts."""
        from .ordnance import (move_ordnance, degrade_tau_missiles,
                                check_torpedo_contact, resolve_torpedo_attack,
                                torpedo_may_attack, is_torpedo_salvo,
                                resolve_bomber_attack, resolve_mine_contact,
                                check_ordnance_vs_blast,
                                check_ordnance_vs_phenomena,
                                resolve_ordnance_interactions,
                                resolve_bomber_interception, attacks_ships)
        from .geometry import circle_touches_square

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

        # AI attack craft pick their targets for this move (s.15)
        from .ordnance import assign_ai_craft_targets
        for player in (1, 2):
            if self.ctx.is_ai_controlled(player):
                assign_ai_craft_targets(self.ctx.gs, player)

        # Both players move and attack with all their ordnance; the player whose
        # turn it is moves all of theirs first (s.12)
        active = self.ctx.gs.active_player
        for mover in (active, 2 if active == 1 else 1):
            ships = self.ctx.gs.get_ships()
            blast_markers = self.ctx.gs.get_blast_markers()
            phenomena = self.ctx.gs.get_phenomena()
            to_remove = set()

            # 1. Move this player's ordnance
            self._turn_boarding_torps(ships, mover)

            for i, o_dict in enumerate(list(self.ctx.gs.ordnance)):
                marker = OrdnanceMarker.from_dict(o_dict)
                if marker.owner_player != mover:
                    continue
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

            # Phase 1: attack craft wave interception — turrets (with massed bonus) fire
            # once per ship at every incoming wave of bombers and assault boats before
            # any attack or hit-and-run raid resolves.
            live_ordnance = [OrdnanceMarker.from_dict(o) for o in self.ctx.gs.ordnance]
            for s in ships:
                if s.is_destroyed or s.is_disengaged:
                    continue
                # Collect enemy attacking craft currently contacting this ship
                wave = [
                    m for m in live_ordnance
                    if attacks_ships(m.ordnance_type)
                    and m.owner_player == mover and m.owner_player != s.player
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

            # Multi-role craft that can attack as bombers or assault boats choose
            # now, after the turrets have fired, one way per wave (s.21)
            mr_modes = self._choose_mr_attack_modes(ships, to_remove_after, mover)

            # Per-marker ship contact resolution
            for o_dict in list(self.ctx.gs.ordnance):
                marker = OrdnanceMarker.from_dict(o_dict)
                if marker.id in to_remove_after or marker.owner_player != mover:
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
                        if not check_torpedo_contact(marker, s):
                            continue

                        # CAP fighters intercept before the torpedo hits
                        if self._check_cap_intercept(marker, s, to_remove_after):
                            break

                        self.ctx.log(
                            f"  Torpedoes contact {s.name}"
                            + (" (FRIENDLY FIRE!)" if s.player == marker.owner_player else "")
                            + "!")
                        result = resolve_torpedo_attack(
                            marker, s, self.ctx.dice, self.ctx.gs,
                            all_ships=ships,
                            brace_decision_fn=self._raid_brace_fn())
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

            # Remove spent ordnance
            if to_remove_after:
                self.ctx.gs.ordnance = [
                    o for o in self.ctx.gs.ordnance
                    if o["id"] not in to_remove_after]

        self.ctx.log(
            f"  Ordnance phase complete: {len(self.ctx.gs.ordnance)} markers remain")
        self.ctx.board.redraw()

