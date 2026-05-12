"""BFG:XR — extracted panel mixin (see game_panel.py for context)."""
import tkinter as tk
from tkinter import messagebox, simpledialog
import math
from typing import Optional, Callable, List

from .models import Ship, SpecialOrder, OrdnanceMarker, OrdnanceType
from .game_state import GameState
from .turn_controller import TurnController
from .dice import DiceRoller
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE)
from .combat import (check_weapon_in_arc, check_weapon_in_range,
                     resolve_batteries, resolve_lances, resolve_nova_cannon,
                     apply_damage, check_los_clear)
from .end_phase import resolve_end_phase
from .geometry import (circle_touches_square, circle_touches_torpedo,
                        ATTACK_CRAFT_HALF_SIDE_CM)


class _EndPhaseMixin:
    """Mixin — methods injected into GamePanel."""

    def _resolve_teleport_attacks(self):
        """Allow the active player to make teleport attacks during the end phase."""
        from .hit_and_run import check_teleport_eligibility, resolve_teleport_attack
        from .movement import do_command_check

        active = self.gs.active_player
        ships = self.gs.get_ships()
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
                ok, reason = check_teleport_eligibility(attacker, target, self.gs)
                if ok:
                    eligible_targets.append(target)

            if not eligible_targets or attacker.id in teleported:
                continue

            target_names = ", ".join(
                f"{t.name} ({attacker.distance_to(t):.0f}cm)"
                for t in eligible_targets)
            want = messagebox.askyesno(
                "Teleport Attack",
                f"{attacker.name} can teleport against:\n{target_names}\n\n"
                f"Attempt a teleport attack?")
            if not want:
                continue

            # Pick target if multiple eligible
            if len(eligible_targets) == 1:
                target = eligible_targets[0]
            else:
                target = self._pick_ship_dialog(eligible_targets,
                                                "Select teleport target")
                if not target:
                    continue

            # Re-fetch both ships to get live state
            attacker = self.gs.get_ship_by_id(attacker.id)
            target = self.gs.get_ship_by_id(target.id)
            if not attacker or not target:
                continue

            def _brace_fn(target_ship, msg):
                if target_ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                    self._append_log(
                        f"  {target_ship.name} already braced — saves apply automatically")
                    return True, True
                want_b = messagebox.askyesno("Teleport Attack — Brace?", msg)
                if not want_b:
                    return False, False
                check = do_command_check(target_ship, "brace_for_impact",
                                         self.dice)
                self._append_log(
                    f"  {target_ship.name} brace: "
                    f"{'PASSED' if check['passed'] else 'FAILED'} "
                    f"(rolled {check['roll']} vs Ld {check['needed']})")
                if check["passed"]:
                    target_ship.previous_order = target_ship.special_order
                    target_ship.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
                    target_ship.brace_set_on_turn = self.gs.turn_number
                    self.gs.update_ship(target_ship)
                return True, check["passed"]

            result = resolve_teleport_attack(
                attacker, target, self.dice, self.gs, _brace_fn)
            teleported.add(attacker.id)

            n_crits = len(result["crits_applied"])
            n_repelled = result["repelled"]
            n_failed = result["failures"]
            self._append_log(
                f"  Teleport result: {n_crits} crit(s) applied, "
                f"{n_repelled} repelled, {n_failed} failed")
            self._check_destruction(target)
            self.board.redraw()

    def _repair_choice_dialog(self, ship: Ship, repairable: List[str],
                               max_repairs: int) -> List[str]:
        """Show dialog for player to choose which crits to repair."""
        if max_repairs >= len(repairable):
            # Can repair everything, no choice needed
            return list(repairable)

        if max_repairs == 1 and len(repairable) == 1:
            return list(repairable)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Repair Choice - {ship.name}")
        dialog.geometry("400x350")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"{ship.name}: Choose {max_repairs} crit(s) to repair",
                 font=("Consolas", 10, "bold")).pack(pady=5)

        chosen = []
        check_vars = {}
        for crit_desc in repairable:
            var = tk.BooleanVar(value=False)
            check_vars[crit_desc] = var
            tk.Checkbutton(dialog, text=crit_desc, variable=var,
                           font=("Consolas", 9)).pack(anchor=tk.W, padx=20)

        result = [None]

        def confirm():
            selected = [desc for desc, var in check_vars.items() if var.get()]
            if len(selected) > max_repairs:
                messagebox.showwarning("Too Many",
                    f"Select at most {max_repairs} crit(s) to repair.")
                return
            result[0] = selected
            dialog.destroy()

        def skip():
            result[0] = []
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Repair Selected", command=confirm,
                  bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Skip Repairs", command=skip,
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)
        return result[0] if result[0] is not None else []

