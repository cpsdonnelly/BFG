"""BFG:XR — Special-order issuing UI (single ship and squadron).

Mixin for MovementPanel: the special-order dialog, fleet re-roll handling,
and squadron coherency group selection. Split out of movement_panel.py.
"""
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

from .models import Ship, SpecialOrder


def _pick_coherency_group(
    root: tk.Tk, groups: List[List["Ship"]]
) -> Optional[List["Ship"]]:
    """Dialog for the player to choose which coherent sub-group issues the order.

    Returns the selected group, or None if cancelled.
    """
    result: List = [None]

    dlg = tk.Toplevel(root)
    dlg.title("Select Coherent Group")
    dlg.geometry("380x260")
    dlg.transient(root)
    dlg.grab_set()

    tk.Label(
        dlg,
        text="Squadron coherency is broken.\nChoose which group issues the order:",
        font=("Consolas", 9), justify=tk.LEFT,
    ).pack(pady=(10, 4), padx=12, anchor=tk.W)

    var = tk.IntVar(value=0)
    for i, grp in enumerate(groups):
        names = ", ".join(s.name for s in grp)
        label = f"Group {i+1} ({len(grp)} ships): {names}"
        if i == 0:
            label += "  [default]"
        tk.Radiobutton(
            dlg, text=label, variable=var, value=i,
            font=("Consolas", 8), wraplength=340,
            justify=tk.LEFT, anchor=tk.W,
        ).pack(anchor=tk.W, padx=16, pady=2)

    def _ok():
        result[0] = groups[var.get()]
        dlg.destroy()

    def _cancel():
        dlg.destroy()

    btn = tk.Frame(dlg)
    btn.pack(pady=8)
    tk.Button(btn, text="OK",     command=_ok,     width=10).pack(side=tk.LEFT, padx=6)
    tk.Button(btn, text="Cancel", command=_cancel, width=10).pack(side=tk.LEFT, padx=6)
    dlg.bind("<Return>", lambda e: _ok())
    dlg.bind("<Escape>", lambda e: _cancel())
    root.wait_window(dlg)
    return result[0]



class SpecialOrderMixin:
    """Special-order dialog methods shared into MovementPanel."""

    def _special_order_dialog(self):
        """Dialog to issue a special order to a ship."""
        # Include ships that haven't yet been fully committed (M-key staged moves
        # don't mark a ship as moved, so those ships still appear here).
        unmoved = self.ctx.tc.get_unmoved_ships()
        if not unmoved:
            messagebox.showinfo(
                "No Ships Available",
                "All active ships have already moved.\n"
                "Special orders must be issued before a ship moves.")
            return

        if self.ctx.tc.command_check_failed:
            messagebox.showinfo("Command Failed",
                "A command check already failed this turn.\n"
                "No more special orders can be issued (except Brace).")
            return

        # Pick ship
        ship = self.ctx.pick_ship(unmoved, "Select ship for special order")
        if not ship:
            return

        # Detect squadron membership for optional squadron-order mechanic
        from .squadron import get_squadrons
        unmoved_ids = {s.id for s in unmoved}
        sq_members: list = []  # other active unmoved members in same squadron
        if ship.squadron_id:
            all_squads = get_squadrons(self.ctx.gs, ship.player)
            sq_all = all_squads.get(ship.squadron_id, [])
            sq_members = [s for s in sq_all
                          if s.id != ship.id and s.id in unmoved_ids]

        # Pick order
        orders = [
            ("All Ahead Full", SpecialOrder.ALL_AHEAD_FULL.value),
            ("Burn Retros", SpecialOrder.BURN_RETROS.value),
            ("Come to New Heading", SpecialOrder.COME_TO_NEW_HEADING.value),
            ("Lock On", SpecialOrder.LOCK_ON.value),
            ("Reload Ordnance", SpecialOrder.RELOAD_ORDNANCE.value),
        ]

        # Filter out CtNH for ponderous ships
        if "ponderous" in ship.special_rules:
            orders = [(n, v) for n, v in orders
                      if v != SpecialOrder.COME_TO_NEW_HEADING.value]

        dialog = tk.Toplevel(self.ctx.root)
        dialog.title(f"Special Order - {ship.name}")
        dialog.geometry("320x360" if sq_members else "300x300")
        dialog.transient(self.ctx.root)
        # dialog.grab_set()  # removed: conflicts with dice popups

        tk.Label(dialog, text=f"Order for {ship.name}",
                 font=("Consolas", 11, "bold")).pack(pady=5)
        tk.Label(dialog, text=f"Leadership: {ship.leadership}",
                 font=("Consolas", 9)).pack()

        selected = tk.StringVar(value=orders[0][1])  # default to first option

        for name, value in orders:
            tk.Radiobutton(dialog, text=name, variable=selected, value=value,
                          font=("Consolas", 9)).pack(anchor=tk.W, padx=20)

        # Squadron order option
        sq_order_var = tk.BooleanVar(value=False)
        if sq_members:
            from .squadron import get_coherency_components
            all_sq_members = [ship] + sq_members
            groups, isolated_sq = get_coherency_components(all_sq_members)

            if not groups:
                coh_text = "⚠ All ships isolated — squadron order not possible"
            elif len(groups) == 1:
                leader = max(groups[0], key=lambda s: s.leadership)
                coh_text = (f"Leader: {leader.name}  •  Ld {leader.leadership}\n"
                            f"Members: {', '.join(s.name for s in all_sq_members)}")
            else:
                sizes = " | ".join(f"{len(g)} ships" for g in groups)
                coh_text = (f"⚠ Broken coherency — {len(groups)} groups ({sizes})\n"
                            f"You will choose which group issues the order.")
            if isolated_sq:
                coh_text += f"\n  Isolated (excluded): {', '.join(s.name for s in isolated_sq)}"

            sq_frame = tk.LabelFrame(dialog, text="Squadron Order",
                                     font=("Consolas", 8, "bold"), padx=6, pady=4)
            sq_frame.pack(fill=tk.X, padx=10, pady=4)
            tk.Checkbutton(
                sq_frame,
                text="Apply to whole squadron (roll once for all)",
                variable=sq_order_var,
                font=("Consolas", 8),
            ).pack(anchor=tk.W)
            tk.Label(
                sq_frame,
                text=coh_text,
                font=("Consolas", 7), fg="#AAAAAA", justify=tk.LEFT,
            ).pack(anchor=tk.W)

        def _handle_failed_individual(result, order_str):
            """Show failure UI and offer re-roll for an individual order."""
            rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
            if rerolls > 0:
                use_reroll = messagebox.askyesno(
                    "Order Failed - Re-roll Available",
                    f"{ship.name}: {order_str} FAILED\n"
                    f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}\n\n"
                    f"Fleet commander has {rerolls} re-roll(s) remaining.\n"
                    f"Use a re-roll? (Cannot be undone)")
                if use_reroll:
                    reroll_result = self.ctx.tc.attempt_reroll_command_check(
                        ship, order_str)
                    rr_info = (f" (RE-ROLL: rolled {reroll_result.get('roll', '?')} "
                               f"vs Ld {reroll_result.get('needed', '?')})")
                    if reroll_result["success"]:
                        self.ctx.log(
                            f"{ship.name}: {order_str} RE-ROLL PASSED{rr_info}")
                        messagebox.showinfo("Re-roll Passed!",
                            f"{ship.name}: {order_str} RE-ROLL PASSED\n"
                            f"Rolled {reroll_result.get('roll')} vs "
                            f"Leadership {reroll_result.get('needed')}")
                    else:
                        msg = reroll_result.get("error",
                                                f"{order_str} RE-ROLL FAILED")
                        self.ctx.log(f"{ship.name}: {msg}")
                        messagebox.showwarning("Re-roll Failed",
                            f"{ship.name}: {order_str} RE-ROLL ALSO FAILED\n"
                            f"Rolled {reroll_result.get('roll')} vs "
                            f"Leadership {reroll_result.get('needed')}\n"
                            f"No more special orders this turn!")
                else:
                    msg = result.get("error", f"{order_str} FAILED")
                    self.ctx.log(f"{ship.name}: {msg}")
            else:
                msg = result.get("error", f"{order_str} FAILED")
                self.ctx.log(f"{ship.name}: {msg}")
                messagebox.showwarning("Order Failed",
                    f"{ship.name}: {order_str} FAILED\n"
                    f"Rolled {result.get('roll')} vs Leadership {result.get('needed')}\n"
                    f"No fleet re-rolls available.\n"
                    f"No more special orders this turn!")

        def confirm():
            order = selected.get()
            if not order:
                return
            dialog.destroy()

            if sq_order_var.get() and sq_members:
                # --- Squadron order path ---
                from .squadron import get_coherency_components
                all_sq = [ship] + sq_members
                groups, isolated_sq = get_coherency_components(all_sq)

                for s in isolated_sq:
                    self.ctx.log(
                        f"  {s.name}: isolated from squadron — cannot join order")

                if not groups:
                    messagebox.showinfo("No Coherency",
                        "No ships are in coherency — cannot issue a squadron order.")
                    return

                if len(groups) == 1:
                    all_sq = groups[0]
                else:
                    chosen = _pick_coherency_group(self.ctx.root, groups)
                    if chosen is None:
                        return   # player cancelled
                    all_sq = chosen

                result = self.ctx.tc.issue_squadron_order(all_sq, order)
                roll_info = (f" (rolled {result.get('roll', '?')} "
                             f"vs Ld {result.get('needed', '?')} "
                             f"via {result.get('leader', '?')})")
                if result["success"]:
                    affected = result.get("ships_affected", [])
                    self.ctx.log(
                        f"Squadron {order} PASSED{roll_info}")
                    messagebox.showinfo("Squadron Order Passed",
                        f"Squadron {order} PASSED{roll_info}\n"
                        f"Applied to: {', '.join(affected)}")
                else:
                    err = result.get("error", f"Squadron {order} FAILED")
                    self.ctx.log(err)
                    # Offer re-roll on squadron fail (rolls against the leader)
                    leader_ship = max([ship] + sq_members,
                                      key=lambda s: s.leadership)
                    rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
                    if rerolls > 0:
                        use_rr = messagebox.askyesno(
                            "Squadron Order Failed - Re-roll Available",
                            f"{err}\n\n"
                            f"Fleet commander has {rerolls} re-roll(s) remaining.\n"
                            f"Use a re-roll? (Cannot be undone)")
                        if use_rr:
                            rr = self.ctx.tc.attempt_reroll_command_check(
                                leader_ship, order)
                            if rr["success"]:
                                # Apply order to all non-braced members
                                from .models import SpecialOrder as _SO
                                affected2 = []
                                for m in [ship] + sq_members:
                                    fresh = self.ctx.gs.get_ship_by_id(m.id)
                                    if (fresh and fresh.special_order
                                            != _SO.BRACE_FOR_IMPACT.value):
                                        fresh.special_order = order
                                        self.ctx.gs.update_ship(fresh)
                                        affected2.append(fresh.name)
                                        self.ctx.gs.add_log(
                                            f"  {fresh.name}: {order} "
                                            f"(squadron re-roll)")
                                self.ctx.log(
                                    f"Squadron {order} RE-ROLL PASSED "
                                    f"(rolled {rr.get('roll')} vs "
                                    f"Ld {rr.get('needed')})")
                                messagebox.showinfo("Re-roll Passed!",
                                    f"Squadron {order} RE-ROLL PASSED\n"
                                    f"Applied to: {', '.join(affected2)}")
                            else:
                                rr_err = rr.get("error",
                                                f"Squadron {order} RE-ROLL FAILED")
                                self.ctx.log(rr_err)
                                messagebox.showwarning("Re-roll Failed",
                                    f"Squadron {order} RE-ROLL ALSO FAILED\n"
                                    f"Rolled {rr.get('roll')} vs "
                                    f"Ld {rr.get('needed')}\n"
                                    f"No more special orders this turn!")
                    else:
                        messagebox.showwarning("Squadron Order Failed", err)
            else:
                # --- Individual order path (original behaviour) ---
                result = self.ctx.tc.issue_special_order(ship, order)
                roll_info = (f" (rolled {result.get('roll', '?')} "
                             f"vs Ld {result.get('needed', '?')})")
                if result["success"]:
                    self.ctx.log(f"{ship.name}: {order} PASSED{roll_info}")
                    messagebox.showinfo("Order Passed",
                        f"{ship.name}: {order} PASSED\n"
                        f"Rolled {result.get('roll')} vs "
                        f"Leadership {result.get('needed')}")
                else:
                    _handle_failed_individual(result, order)
            self.ctx.board.redraw()

        # Show re-roll count
        rerolls = self.ctx.tc.get_fleet_rerolls(ship.player)
        reroll_text = f"Fleet re-rolls available: {rerolls}" if rerolls > 0 else ""
        if reroll_text:
            tk.Label(dialog, text=reroll_text, font=("Consolas", 8),
                     fg="#FFAA00").pack(pady=2)

        tk.Button(dialog, text="Issue Order", command=confirm,
                  bg="#336633", fg="white", font=("Consolas", 10)).pack(pady=10)

