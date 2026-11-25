"""BFG:XR Deployment Phase UI Panel.

Provides DeploymentPanel — a Tkinter overlay that manages ship placement
before Turn 1.  Called from GamePanel._start_game().

Flow (sequential mode):
  1. P1 selects a group from the list on the left.
  2. P1 clicks on the board to place each ship in the group.
  3. After all P1 ships are placed the panel automatically switches to P2.
  4. After all P2 ships are placed, on_complete() is called and the panel
     is destroyed so the normal game loop can begin.

Squadron groups: all members are placed one click at a time. Each member
is highlighted in turn; the panel validates coherency when the last member
is placed.  If coherency fails the whole group's placements are rolled back.

The panel also draws deployment zone outlines on the board canvas.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Callable, Tuple

from .game_state import GameState
from .deployment import COHERENCY_CM


# Colours for zones / highlights
_ZONE_COLORS = {1: "#AA3333", 2: "#3355AA"}
_ZONE_ALPHA_FILL = ""   # canvas doesn't support true alpha; use stipple
_PENDING_COLOR = "#FFFF44"
_PLACED_COLOR = "#44FF44"
_SQUAD_COLORS = ["#FFAA00", "#FF44FF", "#44FFFF", "#FF8844"]


def _group_info(group) -> str:
    """One line per kind of ship in the group (not one per escort)."""
    lines = {}
    for sh in group:
        key = f"{sh.ship_class}: {sh.ship_type}, Spd {sh.speed}, Ld {sh.leadership}"
        lines[key] = lines.get(key, 0) + 1
    return "\n".join(f"{n} × {k}" if n > 1 else k for k, n in lines.items())


class DeploymentPanel:
    """
    Manages the deployment phase UI.

    Parameters
    ----------
    parent_frame : tk.Frame
        The side-panel frame (same as the one GamePanel uses).
    board_view :
        The BoardView instance so we can draw zone overlays on its canvas.
    gs : GameState
    root : tk.Tk
    on_complete : Callable
        Called with no arguments when all ships are deployed.
    mode : "sequential" | "alternating"
    """

    def __init__(
        self,
        parent_frame: tk.Frame,
        board_view,
        gs: GameState,
        root: tk.Tk,
        on_complete: Callable,
        mode: str = "sequential",
    ):
        self.parent = parent_frame
        self.board = board_view
        self.gs = gs
        self.root = root
        self.on_complete = on_complete
        self.mode = mode

        # Capital ship squadrons are formed before any ship is deployed (s.8):
        # the AI forms its own here (squadrons.ai_form_squadrons)
        from .squadrons import ai_form_squadrons
        from .commanders import ai_place_commander
        from .dice import DiceRoller
        for p in (1, 2):
            if self._ai_deploys(p):
                ai_form_squadrons(gs, p, log=gs.report)
                # commanders are assigned at deployment, after the Ld roll (To do 29)
                ai_place_commander(gs, p, DiceRoller(mode="auto"), log=gs.report)
        # Fixed placements, reserves left out, the scenario's zones and rules
        from .deployment import deployment_state
        self.state = deployment_state(gs, mode)
        self.zones = list(self.state.zones.values())

        # Track sub-placement within the current group
        self._pending_positions: List[Tuple[float, float]] = []
        self._pending_headings: List[float] = []
        self._heading_entry_val: Optional[tk.StringVar] = None
        self._list_player = None        # whose groups the list shows

        # Bind board click for placement
        self._orig_click = board_view.canvas.bind("<Button-1>")
        board_view.canvas.bind("<Button-1>", self._on_board_click)
        # Right-click a ship you've placed: turn it 45 degrees (Shift: the other way)
        self._orig_rclick = board_view.canvas.bind("<Button-3>")
        board_view.canvas.bind("<Button-3>", lambda e: self._rotate_placed_at(e, 45))
        board_view.canvas.bind("<Shift-Button-3>", lambda e: self._rotate_placed_at(e, -45))

        self._build_ui()
        self._draw_zones()
        self._refresh()
        # The AI places its own ships when its turn to deploy comes (To do 28;
        # spectator games: both fleets), from _refresh

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # The deployment panel takes the whole side panel while it is open
        # (owner: the ship list was squeezed into a small box below the
        # game's buttons and log); _finish puts them back in their order
        self._hidden = []
        info = getattr(self.board, "info_text", None)      # the empty ship info box
        if info is not None and info.winfo_manager() == "pack":
            self._hidden.append((info, info.pack_info()))
            info.pack_forget()
        for w in self.parent.pack_slaves():
            if any(w is h for h, _i in self._hidden):
                continue                # the info box itself (panel opened on its frame)
            self._hidden.append((w, w.pack_info()))
            w.pack_forget()
        self.frame = tk.Frame(self.parent, bg="#1a1a2e")
        self.frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        tk.Label(self.frame, text="DEPLOYMENT PHASE",
                 bg="#1a1a2e", fg="#FFAA00",
                 font=("Consolas", 11, "bold")).pack(pady=(4, 2))

        self.player_label = tk.Label(
            self.frame, text="", bg="#1a1a2e", fg="#AACCFF",
            font=("Consolas", 10))
        self.player_label.pack()

        self.status_label = tk.Label(
            self.frame, text="", bg="#1a1a2e", fg="#CCCCCC",
            font=("Consolas", 9), wraplength=220, justify=tk.LEFT)
        self.status_label.pack(pady=2)

        tk.Frame(self.frame, bg="#333355", height=2).pack(fill=tk.X, pady=4)

        # Group list
        tk.Label(self.frame, text="Ships to deploy (click one to place it next; "
                 "double-click a placed one to take it back):",
                 wraplength=250, justify=tk.LEFT,
                 bg="#1a1a2e", fg="#AAAAAA",
                 font=("Consolas", 8)).pack(anchor=tk.W, padx=4)

        list_frame = tk.Frame(self.frame, bg="#0a0a1a")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.group_listbox = tk.Listbox(
            list_frame, bg="#0a0a1a", fg="#CCCCCC",
            selectbackground="#334466", font=("Consolas", 9),
            height=6, exportselection=False)
        self.group_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.group_listbox.yview)
        self.group_listbox.bind("<<ListboxSelect>>", self._on_group_select)
        self.group_listbox.bind("<Double-Button-1>", lambda _e: self._take_back_selected())

        # Heading control
        heading_frame = tk.Frame(self.frame, bg="#1a1a2e")
        heading_frame.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(heading_frame, text="Heading:",
                 bg="#1a1a2e", fg="#AAAAAA",
                 font=("Consolas", 9)).pack(side=tk.LEFT)
        # "auto": face the enemy's zone (or the scenario's required facing)
        self._heading_entry_val = tk.StringVar(value="auto")
        tk.Entry(heading_frame, textvariable=self._heading_entry_val,
                 width=6, font=("Consolas", 9),
                 bg="#0a0a1a", fg="#FFFFFF",
                 insertbackground="white").pack(side=tk.LEFT, padx=4)
        for txt, d in (("⟲45", -45), ("⟳45", 45)):
            tk.Button(heading_frame, text=txt, command=lambda d=d: self._nudge_heading(d),
                      bg="#334455", fg="white", font=("Consolas", 8)).pack(side=tk.LEFT, padx=1)
        tk.Button(heading_frame, text="Auto", command=lambda: self._heading_entry_val.set("auto"),
                  bg="#334455", fg="white", font=("Consolas", 8)).pack(side=tk.LEFT, padx=1)
        tk.Label(self.frame, text="Heading: auto = face the enemy; 0 = right, 90 = down, "
                 "180 = left, 270 = up. Right-click a placed ship to turn it 45° "
                 "(Shift+right-click the other way). Ctrl+Z takes back the last "
                 "ship or group placed.",
                 bg="#1a1a2e", fg="#888888", font=("Consolas", 7), wraplength=255,
                 justify=tk.LEFT).pack(anchor=tk.W, padx=4)

        # Buttons, two rows so every one fits the side panel's width
        btn_frame = tk.Frame(self.frame, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, padx=4, pady=4)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        self.undo_btn = tk.Button(
            btn_frame, text="Undo (Ctrl+Z)", command=self._undo_any,
            bg="#553333", fg="white", font=("Consolas", 9))
        self.undo_btn.grid(row=0, column=0, sticky="ew", padx=2, pady=1)
        tk.Button(btn_frame, text="Take back selected", command=self._take_back_selected,
                  bg="#553333", fg="white", font=("Consolas", 9)
                  ).grid(row=0, column=1, sticky="ew", padx=2, pady=1)
        tk.Button(btn_frame, text="Start over", command=self._start_over,
                  bg="#553333", fg="white", font=("Consolas", 9)
                  ).grid(row=1, column=0, sticky="ew", padx=2, pady=1)
        self.skip_btn = tk.Button(
            btn_frame, text="Auto-Place All",
            command=self._auto_place_remaining,
            bg="#334455", fg="white", font=("Consolas", 9))
        self.skip_btn.grid(row=1, column=1, sticky="ew", padx=2, pady=1)
        # Any order inside a squadron too, and capital squadrons before deploying
        tk.Button(btn_frame, text="Next ship in squadron", command=self._next_member,
                  bg="#334455", fg="white", font=("Consolas", 9)
                  ).grid(row=2, column=0, sticky="ew", padx=2, pady=1)
        self.squad_btn = tk.Button(btn_frame, text="Capital squadrons...",
                                   command=self._squadron_dialog,
                                   bg="#334455", fg="white", font=("Consolas", 9))
        self.squad_btn.grid(row=2, column=1, sticky="ew", padx=2, pady=1)
        tk.Button(btn_frame, text="Move commander...", command=self._commander_dialog,
                  bg="#334455", fg="white", font=("Consolas", 9)
                  ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=2, pady=1)
        self.root.bind("<Control-z>", lambda _e: self._undo_any())

        tk.Frame(self.frame, bg="#333355", height=2).pack(fill=tk.X, pady=4)

        self.info_label = tk.Label(
            self.frame, text="",
            bg="#1a1a2e", fg="#AAAAAA",
            font=("Consolas", 8), wraplength=220, justify=tk.LEFT)
        self.info_label.pack(padx=4, anchor=tk.W)

        # Everything below the list keeps its room and the list takes what is
        # left: repack those widgets from the bottom up, same order on screen
        slaves = self.frame.pack_slaves()
        below = slaves[slaves.index(list_frame) + 1:]
        infos = [w.pack_info() for w in below]
        for w in below:
            w.pack_forget()
        for w, info in reversed(list(zip(below, infos))):
            info.pop("in", None)
            info["side"] = tk.BOTTOM
            w.pack(**info)

    # ── Board overlay ─────────────────────────────────────────────────────────

    def _draw_zones(self):
        """Draw deployment zone rectangles on the board canvas."""
        canvas = self.board.canvas
        canvas.delete("deploy_zone")
        for zone in self.zones:
            color = _ZONE_COLORS.get(zone.player, "#AAAAAA")
            for r in zone.rects():
                rx0, ry0 = self.board.cm_to_screen(r.x_min, r.y_min)
                rx1, ry1 = self.board.cm_to_screen(r.x_max, r.y_max)
                canvas.create_rectangle(
                    rx0, min(ry0, ry1), rx1, max(ry0, ry1),
                    outline=color, width=2, dash=(6, 3),
                    tags="deploy_zone")
            x0, y0 = self.board.cm_to_screen(zone.x_min, zone.y_min)
            x1, y1 = self.board.cm_to_screen(zone.x_max, zone.y_max)
            canvas.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2,
                text=zone.label,
                fill=color, font=("Consolas", 8),
                tags="deploy_zone")

    def _draw_pending(self):
        """Draw markers for ships placed so far in the current group."""
        canvas = self.board.canvas
        canvas.delete("deploy_pending")
        group = self.state.current_group()
        if not group:
            return
        for i, (x, y) in enumerate(self._pending_positions):
            sx, sy = self.board.cm_to_screen(x, y)
            r = self.board.cm_to_pixels(1.5)
            canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                fill=_PENDING_COLOR, outline="white",
                                tags="deploy_pending")
            if i < len(group):
                canvas.create_text(sx, sy, text=group[i].name[:6],
                                   fill="#000000", font=("Consolas", 7),
                                   tags="deploy_pending")

    # ── Refresh UI state ──────────────────────────────────────────────────────

    def _refresh(self):
        """Update all UI widgets to reflect current deployment state."""
        if self.state.is_complete():
            self._finish()
            return

        p = self.state.active_player
        if self._ai_deploys(p) and not getattr(self, "_ai_deploying", False):
            self._ai_deploying = True
            self.root.after(300, lambda: self._ai_deploy_turn(p))
        pname = self.gs.player1_name if p == 1 else self.gs.player2_name
        self.player_label.config(text=f"{pname}'s turn")

        group = self.state.current_group()
        remaining = self.state.groups_remaining(p)

        if group is None:
            self.status_label.config(text="All ships placed!")
        elif len(group) == 1:
            placed = len(self._pending_positions)
            if placed == 0:
                self.status_label.config(
                    text=f"Click board to place {group[0].name}.\n"
                         f"({remaining} group(s) remaining)")
            else:
                self.status_label.config(text="Confirming placement…")
        else:
            placed = len(self._pending_positions)
            total = len(group)
            classes = {}
            for sh in group:
                classes[sh.ship_class] = classes.get(sh.ship_class, 0) + 1
            names = ", ".join(f"{c} ×{n}" if n > 1 else c for c, n in classes.items())
            nxt = group[placed].name if placed < total else ""
            self.status_label.config(
                text=f"Squadron: {names}\n"
                     f"Place ship {placed + 1} of {total}: {nxt}\n"
                     f"(Next ship in squadron picks another.)\n"
                     f"All must be within {COHERENCY_CM}cm of each other.\n"
                     f"({remaining} group(s) remaining)")

        # Rebuild listbox
        self._list_player = p
        self.group_listbox.delete(0, tk.END)
        for idx, grp in enumerate(self.state.groups[p]):
            if idx < self.state.next_idx[p]:
                tag = "✓ "
            elif idx == self.state.next_idx[p]:
                tag = "▶ "
            else:
                tag = "  "
            if len(grp) == 1:
                entry = f"{tag}{grp[0].name}"
            else:
                entry = f"{tag}[SQ] {grp[0].ship_class} ×{len(grp)}"
            self.group_listbox.insert(tk.END, entry)
        # Highlight current
        cur = self.state.next_idx[p]
        if cur < self.group_listbox.size():
            self.group_listbox.selection_clear(0, tk.END)
            self.group_listbox.selection_set(cur)
            self.group_listbox.see(cur)

        # Info for selected group
        if group:
            self.info_label.config(text=_group_info(group))

        self.board.redraw()
        self._draw_zones()
        self._draw_pending()

    # ── Click handling ────────────────────────────────────────────────────────

    def _get_heading(self, x: float = None, y: float = None) -> float:
        """The heading entered, or for "auto" (or anything not a number) the
        facing the scenario requires there, else towards the enemy's zone."""
        try:
            return float(self._heading_entry_val.get()) % 360.0
        except (ValueError, AttributeError):
            from .deployment import placement_heading
            if x is None:
                return 0.0
            return placement_heading(self.gs, self.state, self.state.active_player, x, y)

    def _nudge_heading(self, d: float):
        try:
            h = float(self._heading_entry_val.get())
        except (ValueError, AttributeError):
            group = self.state.current_group()
            zone = self.state.zones[self.state.active_player]
            h = self._get_heading((zone.x_min + zone.x_max) / 2, (zone.y_min + zone.y_max) / 2) \
                if group else 0.0
        self._heading_entry_val.set(f"{(h + d) % 360:.0f}")

    def _undo_group(self):
        """Take back the last placed group, to place it again."""
        self._pending_positions.clear()
        self._pending_headings.clear()
        group = self.state.undo_group()
        if group is None:
            self.board.status_var.set("Nothing placed to take back")
            return
        self._off_table(group)
        self.board.redraw()
        self._draw_zones()
        self._refresh()

    def _rotate_placed_at(self, event, degrees: float):
        """Right-click on a ship you have placed: turn it (and its squadron)."""
        cx, cy = self.board.screen_to_cm(event.x, event.y)
        mine = [s for s in self.state.placed_ships if s.player == self.state.active_player]
        hit = min(mine, key=lambda s: (s.x - cx) ** 2 + (s.y - cy) ** 2, default=None)
        if hit is None or (hit.x - cx) ** 2 + (hit.y - cy) ** 2 > (hit.base_radius + 2) ** 2:
            return
        if self.state.rotate_placed(hit.id, degrees) is None:
            self.board.status_var.set(f"{hit.name} can't face that way here")
            return
        for s in self.state.placed_ships:
            if s is hit or (hit.squadron_id and s.squadron_id == hit.squadron_id
                            and s.player == hit.player):
                self.gs.update_ship(s)
        self.board.redraw()
        self._draw_zones()
        self._draw_pending()

    def _on_board_click(self, event):
        cx, cy = self.board.screen_to_cm(event.x, event.y)
        group = self.state.current_group()
        if group is None:
            return

        heading = self._get_heading(cx, cy)

        # Validate this position before accepting it
        zone = self.state.zones[self.state.active_player]
        already_placed = list(self.state.placed_ships)
        # Temporarily treat pending ships as placed (so they block each other)
        from .deployment import validate_placement
        ship = group[len(self._pending_positions)]
        ok, reason = validate_placement(ship, cx, cy, zone, already_placed)
        if not ok:
            self.board.status_var.set(f"Cannot place here: {reason}")
            return

        self._pending_positions.append((cx, cy))
        self._pending_headings.append(heading)

        if len(self._pending_positions) == len(group):
            self._commit_group()
        else:
            self._refresh()

    def _commit_group(self):
        """Try to commit the current group's placement."""
        ok, errors = self.state.place_group(
            self._pending_positions, self._pending_headings)

        if not ok:
            messagebox.showwarning(
                "Placement Invalid",
                "Cannot place squadron here:\n\n" + "\n".join(errors),
                parent=self.root)
            self._pending_positions.clear()
            self._pending_headings.clear()
            self._refresh()
            return

        # Write positions back to GameState
        n = len(self._pending_positions)
        for ship in self.state.placed_ships[-n:]:
            self.gs.update_ship(ship)

        self._pending_positions.clear()
        self._pending_headings.clear()
        self._refresh()

    def _undo_last(self):
        """Remove the last pending position (within the current group)."""
        if self._pending_positions:
            self._pending_positions.pop()
            self._pending_headings.pop()
            self._draw_pending()
            self._refresh()

    def _undo_any(self):
        """Ctrl+Z: the last ship of a squadron being placed, else the last
        group placed."""
        if self._pending_positions:
            self._undo_last()
        else:
            self._undo_group()

    def _off_table(self, group):
        for ship in group:              # off the table again until re-placed
            ship.x, ship.y = -1000.0, -1000.0
            self.gs.update_ship(ship)

    def _take_back_selected(self):
        """Take back the placed group selected in the list (any of them)."""
        sel = self.group_listbox.curselection()
        p = self.state.active_player
        idx = sel[0] if sel else -1
        if self._list_player is not None:
            p = self._list_player
        group = self.state.unplace_group(p, idx) if idx >= 0 else None
        if group is None:
            self.board.status_var.set("Select a placed ship (✓) in the list to take it back")
            return
        self._pending_positions.clear()
        self._pending_headings.clear()
        self._off_table(group)
        self._refresh()

    def _start_over(self):
        """Take back every ship placed by players at this screen."""
        if not messagebox.askyesno("Start over", "Take back every ship placed so far?",
                                   parent=self.root):
            return
        self._pending_positions.clear()
        self._pending_headings.clear()
        while True:
            group = self.state.undo_group()
            if group is None:
                break
            self._off_table(group)
        self._refresh()

    # ── Squadrons ─────────────────────────────────────────────────────────────

    def _next_member(self):
        """Place the squadron's ships in any order: the next unplaced one."""
        group = self.state.current_group()
        k = len(self._pending_positions)
        if not group or len(group) - k < 2:
            self.board.status_var.set("No other ship of this squadron left to choose")
            return
        self.state.select_member(k, group[-1].id)    # rotate the unplaced ones
        self._refresh()

    def _commander_dialog(self):
        """Move the fleet commander to another capital ship after the Ld roll
        (s.5, To do 29), before any ship is deployed, where the fleet list
        allows it (commanders.allowed_ships); "Auto" picks what the AI would."""
        from .commanders import allowed_ships, best_ship, move_commander, commander_options
        p = self.state.active_player
        if not self.state.can_regroup():
            messagebox.showinfo("Move commander", "Commanders are assigned before any ship "
                                "is deployed.", parent=self.root)
            return
        ships = allowed_ships(self.gs, p)
        if not ships:
            messagebox.showinfo("Move commander", "Your fleet commander can't move: the "
                                "fleet list fixes his ship, or there's no other choice.",
                                parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Move commander")
        dlg.transient(self.root)
        tk.Label(dlg, text="Choose the ship to lead the fleet (Ld shown is the ship's "
                 "own rolled Ld; the commander's ship hasn't rolled yet).",
                 font=("Consolas", 9), wraplength=380).pack(padx=6, pady=4)
        lb = tk.Listbox(dlg, width=52, height=min(12, len(ships)), font=("Consolas", 9),
                        exportselection=False)
        lb.pack(padx=6, pady=4)
        for s in ships:
            mark = "  (commander)" if commander_options(s) else ""
            lb.insert(tk.END, f"{s.name} ({s.ship_class}) Ld {s.leadership}{mark}")

        def apply(target):
            from .dice import DiceRoller, mode_for
            move_commander(self.gs, target.id, DiceRoller(mode=mode_for(self.gs),
                                                          root=self.root), log=self.gs.report)
            for g in self.state.groups[p]:          # the placed list shows fresh copies
                for i, s in enumerate(g):
                    g[i] = self.gs.get_ship_by_id(s.id) or s
            dlg.destroy()
            self._refresh()

        def pick():
            sel = lb.curselection()
            if sel:
                apply(ships[sel[0]])

        def auto():
            b = best_ship(self.gs, p)
            if b is not None:
                apply(b)
        row = tk.Frame(dlg)
        row.pack(pady=4)
        for text, cmd in (("Move here", pick), ("Auto", auto), ("Cancel", dlg.destroy)):
            tk.Button(row, text=text, command=cmd, font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)

    def _squadron_dialog(self):
        """Form or break up capital ship squadrons (s.8: at the start of the
        game, before any ship is deployed), with the squadron rules checked
        (squadrons.squadron_errors); "Auto" forms what the AI would."""
        p = self.state.active_player
        if not self.state.can_regroup():
            messagebox.showinfo("Capital squadrons", "Capital ship squadrons are formed "
                                "before any ship is deployed (s.8).", parent=self.root)
            return
        from .squadrons import squadron_errors, form_capital_squadrons
        ships = [s for g in self.state.groups[p] for s in g if s.ship_type != "escort"]
        if not ships:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Capital ship squadrons")
        dlg.transient(self.root)
        tk.Label(dlg, text="Select ships (Ctrl / Shift-click), then Squadron or Break up.",
                 font=("Consolas", 9)).pack(padx=6, pady=4)
        lb = tk.Listbox(dlg, selectmode=tk.EXTENDED, width=48, height=min(16, len(ships)),
                        font=("Consolas", 9), exportselection=False)
        lb.pack(padx=6, pady=4, fill=tk.BOTH, expand=True)

        def fill():
            lb.delete(0, tk.END)
            for s in ships:
                lb.insert(tk.END, f"{s.name} ({s.ship_class})"
                          + (f"  [{s.squadron_id}]" if s.squadron_id else ""))

        def apply():
            for s in ships:
                self.gs.update_ship(s)
            self.state.regroup(p)
            fill()
            self._refresh()

        def squadron():
            members = [ships[i] for i in lb.curselection()]
            used = {s.squadron_id for g in self.state.groups[p] for s in g}
            n = 1
            while f"csq{n}" in used:
                n += 1
            errors = (["Select two or more ships."] if len(members) < 2
                      else squadron_errors(members, f"csq{n}"))
            if errors:
                messagebox.showwarning("Squadron", "\n".join(errors), parent=dlg)
                return
            for s in members:
                s.squadron_id = f"csq{n}"
            apply()

        def break_up():
            sids = {ships[i].squadron_id for i in lb.curselection()} - {""}
            for s in ships:
                if s.squadron_id in sids:
                    s.squadron_id = ""
            apply()

        def auto():
            from .rng import game_random
            form_capital_squadrons(ships, rng=game_random(self.gs, "squadrons"),
                                   log=self.gs.report)
            apply()

        row = tk.Frame(dlg)
        row.pack(pady=4)
        for text, cmd in (("Squadron", squadron), ("Break up", break_up), ("Auto", auto),
                          ("Close", dlg.destroy)):
            tk.Button(row, text=text, command=cmd, font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
        fill()

    # ── Group list selection ──────────────────────────────────────────────────

    def _on_group_select(self, _event):
        """Clicking a ship / squadron not yet placed makes it the one to place
        next (any order, owner); a placed one is selected to take back."""
        sel = self.group_listbox.curselection()
        if not sel:
            return
        p = self.state.active_player
        idx = sel[0]
        if idx > self.state.next_idx[p] and self.state.select_group(idx):
            self._pending_positions.clear()
            self._pending_headings.clear()
            self._refresh()
            return
        groups = self.state.groups[p]
        if 0 <= idx < len(groups):
            grp = groups[idx]
            self.info_label.config(text=_group_info(grp))

    # ── Auto-placement ────────────────────────────────────────────────────────

    def _ai_deploys(self, player: int) -> bool:
        """The AI places this player's ships: the AI's side in a game against
        the AI, both sides in spectator mode with pop-ups answered for them."""
        from .dice import spectating_auto
        gs = self.gs
        if getattr(gs, "ai_spectator", False):
            return spectating_auto(gs)
        return getattr(gs, "ai_player", None) == player

    def _ai_deploy_turn(self, player: int):
        """The AI places its groups for this turn to deploy (ai_deployment)."""
        from .ai_deployment import ai_deploy
        self._pending_positions.clear()
        self._pending_headings.clear()
        errors = ai_deploy(self.gs, self.state, player, log=self.gs.report)
        self._ai_deploying = False
        if errors:
            messagebox.showerror("AI deployment failed",
                                 "The AI could not place:\n" + "\n".join(errors),
                                 parent=self.root)
            return
        self._refresh()

    def _auto_place_remaining(self, ask: bool = True):
        """Auto-place all remaining ships for the current (and next) player."""
        answer = (not ask) or messagebox.askyesno(
            "Auto-Place",
            "Auto-place all remaining ships at default positions within their "
            "deployment zone?\n\nThis will arrange them in a grid pattern.",
            parent=self.root)
        if not answer:
            return

        self._pending_positions.clear()
        self._pending_headings.clear()
        from .deployment import auto_place
        p = self.state.active_player
        # against the AI, only the human's own ships (the AI places its own)
        errors = auto_place(self.gs, self.state,
                            p if self._ai_deploys(3 - p) and not self._ai_deploys(p) else None)
        if errors:
            messagebox.showerror("Auto-Place Failed",
                                 "Could not auto-place:\n" + "\n".join(errors),
                                 parent=self.root)
        self._refresh()

    # ── Completion ────────────────────────────────────────────────────────────

    def _finish(self):
        from .scenarios import division_errors, fe_division_errors
        for p in (1, 2):
            errs = division_errors(self.gs, p) + fe_division_errors(self.gs, p)
            if errs:
                messagebox.showwarning(
                    "Warp Storm divisions",
                    f"Player {p}'s two divisions should be as close to the same size as "
                    f"possible: " + ", ".join(errs), parent=self.root)
        self.board.canvas.delete("deploy_zone")
        self.board.canvas.delete("deploy_pending")
        # Restore original canvas click handler
        self.board.canvas.bind("<Button-1>", self._orig_click)
        self.board.canvas.bind("<Button-3>", self._orig_rclick or "")
        self.board.canvas.unbind("<Shift-Button-3>")
        self.root.unbind("<Control-z>")
        self.frame.destroy()
        for w, info in self._hidden:        # the game's side panel back, in order
            info.pop("in", None)
            if (w is getattr(self.board, "info_text", None)
                    and w.master is self.parent.master):
                w.pack(before=self.parent, **info)
            else:
                w.pack(**info)
        self.board.redraw()
        self.on_complete()
