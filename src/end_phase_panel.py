"""BFG:XR — EndPhasePanel: teleport attacks and repair choice dialogs."""
from typing import List

from .models import Ship, SpecialOrder
from .game_context import GameContext


class EndPhasePanel:
    """Handles end phase UI: teleport attack resolution, repair choice dialogs."""

    def __init__(self, ctx: GameContext):
        self.ctx = ctx

    def _resolve_boarding_actions(self):
        """Resolve boarding actions in the attacker's end phase."""
        if not self.ctx.gs.rule_boarding:
            return
        from .boarding import resolve_boarding, ships_in_base_contact

        active = self.ctx.gs.active_player
        ships = self.ctx.gs.get_ships()

        # Find active-player ships that declared boarding this turn
        boarders = [s for s in ships
                    if s.player == active and s.boarding_target_id
                    and not s.is_destroyed and not s.is_disengaged
                    and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
        # Also find grappled ships still in contact with their opponent
        grappled = [s for s in ships
                    if s.player == active and s.is_grappled and s.grappled_with_id
                    and not s.is_destroyed
                    and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]

        # Group fresh boarders by target
        by_target: dict = {}
        for ship in boarders:
            target = self.ctx.gs.get_ship_by_id(ship.boarding_target_id)
            if not target or target.is_destroyed:
                continue
            if not ships_in_base_contact(ship, target):
                self.ctx.log(f"  {ship.name} boarding target {target.name} no longer in contact")
                continue
            by_target.setdefault(ship.boarding_target_id, []).append(ship)

        # Also process ongoing grapples
        for ship in grappled:
            peer = self.ctx.gs.get_ship_by_id(ship.grappled_with_id)
            if not peer or peer.is_destroyed:
                ship.is_grappled = False
                ship.grappled_with_id = None
                self.ctx.gs.update_ship(ship)
                continue
            if ship.boarding_target_id == peer.id:
                by_target.setdefault(peer.id, [ship])
            elif peer.id not in by_target:
                by_target.setdefault(peer.id, [ship])

        for target_id, attackers in by_target.items():
            target = self.ctx.gs.get_ship_by_id(target_id)
            if not target:
                continue
            attackers = [self.ctx.gs.get_ship_by_id(a.id) for a in attackers
                         if self.ctx.gs.get_ship_by_id(a.id)]

            self.ctx.log(
                f"  BOARDING: {'+'.join(a.name for a in attackers)} vs {target.name}")

            result = resolve_boarding(attackers, target, self.ctx.dice, self.ctx.gs)

            # Artefact transfer on boarding win
            gs = self.ctx.gs
            if (gs.scenario_mode == "capture_artefact"
                    and target.id == gs.artefact_carrier_id
                    and result.get("winner") == "attacker"
                    and attackers):
                new_carrier = attackers[0]
                gs.artefact_carrier_id = new_carrier.id
                gs.artefact_owner = new_carrier.player
                gs.add_log(f"[ARTEFACT] Artefact seized by {new_carrier.name}!")
                self.ctx.prompt.notify("Artefact Seized!",
                    f"{new_carrier.name} has seized the artefact!\n"
                    f"{'Escape the board to win!' if new_carrier.player == gs.scenario_attacker else 'Defend it!'}")

            if result["grapple"]:
                # Mutual grapple — link ships together
                for attacker in attackers:
                    attacker.is_grappled = True
                    attacker.grappled_with_id = target.id
                    attacker.boarding_target_id = target.id
                    self.ctx.gs.update_ship(attacker)
                target.is_grappled = True
                target.grappled_with_id = attackers[0].id if attackers else None
                self.ctx.gs.update_ship(target)
            else:
                # Clear grapple/boarding state on all involved ships
                for attacker in attackers:
                    attacker.is_grappled = False
                    attacker.grappled_with_id = None
                    attacker.boarding_target_id = None
                    self.ctx.gs.update_ship(attacker)
                target.is_grappled = False
                target.grappled_with_id = None
                self.ctx.gs.update_ship(target)

            # Check destruction
            for attacker in attackers:
                self.ctx.check_destruction(attacker)
            self.ctx.check_destruction(target)
            self.ctx.board.redraw()

    def _resolve_teleport_attacks(self):
        """Allow the active player to make teleport attacks during the end phase."""
        if not self.ctx.gs.rule_teleport or not self.ctx.gs.rule_hit_and_run:
            return                 # teleports are raids: both rules needed (owner)
        from .hit_and_run import check_teleport_eligibility, resolve_teleport_attack
        from .movement import attempt_brace

        active = self.ctx.gs.active_player
        ships = self.ctx.gs.get_ships()
        attackers = [s for s in ships
                     if s.player == active
                     and not s.is_destroyed and not s.is_disengaged
                     and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]
        enemies = [s for s in ships
                   if s.player != active
                   and not s.is_destroyed and not s.is_disengaged
                   and s.status not in ("drifting_hulk", "burning_hulk", "destroyed")]

        if not attackers or not enemies:
            return

        # Track which ships have already teleported this end phase
        teleported = set()

        # Offer each eligible attacker a teleport opportunity
        for attacker in attackers:
            eligible_targets = []
            for target in enemies:
                ok, reason = check_teleport_eligibility(attacker, target, self.ctx.gs)
                if ok:
                    eligible_targets.append(target)

            if not eligible_targets or attacker.id in teleported:
                continue

            if self.ctx.is_ai_controlled(attacker.player):
                # The AI decides for its own ships (it used to get the human's
                # dialog): a teleport attack costs nothing, so it raids the target
                # where one raid is worth the most expected VP
                from .waves import raid_squadron_value
                gs = self.ctx.gs
                target, best_v = None, 0.0
                for t in eligible_targets:
                    v = raid_squadron_value(t, gs, attacker.player, attacker.special_rules)
                    if v > best_v:
                        target, best_v = t, v
                if target is None:
                    continue
                self.ctx.log(f"  [AI] {attacker.name} teleports against {target.name} "
                             f"(about {best_v:.1f} VP a raid)")
            else:
                target_names = ", ".join(
                    f"{t.name} ({attacker.distance_to(t):.0f}cm)"
                    for t in eligible_targets)
                want = self.ctx.prompt.yes_no(
                    "Teleport Attack",
                    f"{attacker.name} can teleport against:\n{target_names}\n\n"
                    f"Attempt a teleport attack?")
                if not want:
                    continue

                # Pick target if multiple eligible
                if len(eligible_targets) == 1:
                    target = eligible_targets[0]
                else:
                    target = self.ctx.prompt.pick_ship("Select teleport target",
                                                       eligible_targets)
                    if not target:
                        continue

            # Re-fetch both ships to get live state
            attacker = self.ctx.gs.get_ship_by_id(attacker.id)
            target = self.ctx.gs.get_ship_by_id(target.id)
            if not attacker or not target:
                continue

            def _brace_fn(target_ship, msg):
                if target_ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                    self.ctx.log(
                        f"  {target_ship.name} already braced — saves apply automatically")
                    return True, True
                if self.ctx.is_ai_controlled(target_ship.player):
                    # Priced by the raid's value (To do 8 j (3))
                    from .ai_player import ai_should_brace_vs_raid
                    if ai_should_brace_vs_raid(self.ctx.gs, target_ship, attacker):
                        check = attempt_brace(target_ship, self.ctx.gs,
                                              self.ctx.dice)
                        self.ctx.log(
                            f"  [AI] {target_ship.name} brace: "
                            f"{'PASSED' if check['passed'] else 'FAILED'} "
                            f"(rolled {check['roll']} vs Ld {check['needed']})")
                        return True, check["passed"]
                    return False, False
                want_b = self.ctx.prompt.yes_no("Teleport Attack — Brace?", msg)
                if not want_b:
                    return False, False
                check = attempt_brace(target_ship, self.ctx.gs, self.ctx.dice)
                self.ctx.log(
                    f"  {target_ship.name} brace: "
                    f"{'PASSED' if check['passed'] else 'FAILED'} "
                    f"(rolled {check['roll']} vs Ld {check['needed']})")
                return True, check["passed"]

            result = resolve_teleport_attack(
                attacker, target, self.ctx.dice, self.ctx.gs, _brace_fn)
            teleported.add(attacker.id)

            n_crits = len(result["crits_applied"])
            n_repelled = result["repelled"]
            n_failed = result["failures"]
            self.ctx.log(
                f"  Teleport result: {n_crits} crit(s) applied, "
                f"{n_repelled} repelled, {n_failed} failed")
            self.ctx.check_destruction(target)
            self.ctx.board.redraw()

    def _repair_choice_dialog(self, ship: Ship, repairable: List[str],
                               max_repairs: int) -> List[str]:
        """Show dialog for player to choose which crits to repair."""
        if max_repairs >= len(repairable):
            # Can repair everything, no choice needed
            return list(repairable)

        if max_repairs == 1 and len(repairable) == 1:
            return list(repairable)

        from .ai_player import AIPlayer
        best = AIPlayer.auto_repair_choices(repairable, max_repairs)
        return self.ctx.prompt.pick_many(
            f"Repair Choice - {ship.name}",
            f"{ship.name}: Choose {max_repairs} crit(s) to repair", list(repairable),
            max_repairs, best)
