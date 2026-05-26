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

import math
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Callable, Tuple, Dict

from .models import Ship
from .game_state import GameState
from .deployment import (
    DeploymentState, DeploymentZone, get_default_zones, COHERENCY_CM
)


# Colours for zones / highlights
_ZONE_COLORS = {1: "#AA3333", 2: "#3355AA"}
_ZONE_ALPHA_FILL = ""   # canvas doesn't support true alpha; use stipple
_PENDING_COLOR = "#FFFF44"
_PLACED_COLOR = "#44FF44"
_SQUAD_COLORS = ["#FFAA00", "#FF44FF", "#44FFFF", "#FF8844"]


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

        # Load ships from GameState
        p1_ships = [Ship.from_dict(s) for s in gs.ships if s["player"] == 1]
        p2_ships = [Ship.from_dict(s) for s in gs.ships if s["player"] == 2]

        self.zones = get_default_zones(gs.table_width, gs.table_height)
        self.state = DeploymentState(p1_ships, p2_ships, self.zones, mode=mode)

        # Track sub-placement within the current group
        self._pending_positions: List[Tuple[float, float]] = []
        self._pending_headings: List[float] = []
        self._heading_entry_val: Optional[tk.StringVar] = None

        # Bind board click for placement
        self._orig_click = board_view.canvas.bind("<Button-1>")
        board_view.canvas.bind("<Button-1>", self._on_board_click)

        self._build_ui()
        self._draw_zones()
        self._refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
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
        tk.Label(self.frame, text="Ships to deploy:",
                 bg="#1a1a2e", fg="#AAAAAA",
                 font=("Consolas", 8)).pack(anchor=tk.W, padx=4)

        list_frame = tk.Frame(self.frame, bg="#0a0a1a")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.group_listbox = tk.Listbox(
            list_frame, bg="#0a0a1a", fg="#CCCCCC",
            selectbackground="#334466", font=("Consolas", 9),
            height=8, exportselection=False)
        self.group_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.group_listbox.yview)
        self.group_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        # Heading control
        heading_frame = tk.Frame(self.frame, bg="#1a1a2e")
        heading_frame.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(heading_frame, text="Heading (°):",
                 bg="#1a1a2e", fg="#AAAAAA",
                 font=("Consolas", 9)).pack(side=tk.LEFT)
        self._heading_entry_val = tk.StringVar(value="0")
        tk.Entry(heading_frame, textvariable=self._heading_entry_val,
                 width=6, font=("Consolas", 9),
                 bg="#0a0a1a", fg="#FFFFFF",
                 insertbackground="white").pack(side=tk.LEFT, padx=4)
        tk.Label(heading_frame, text="(0=north, 90=east)",
                 bg="#1a1a2e", fg="#666666",
                 font=("Consolas", 7)).pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(self.frame, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, padx=4, pady=4)

        self.undo_btn = tk.Button(
            btn_frame, text="Undo Last",
            command=self._undo_last,
            bg="#553333", fg="white",
            font=("Consolas", 9), width=12)
        self.undo_btn.pack(side=tk.LEFT, padx=2)

        self.skip_btn = tk.Button(
            btn_frame, text="Auto-Place All",
            command=self._auto_place_remaining,
            bg="#334455", fg="white",
            font=("Consolas", 9), width=12)
        self.skip_btn.pack(side=tk.LEFT, padx=2)

        tk.Frame(self.frame, bg="#333355", height=2).pack(fill=tk.X, pady=4)

        self.info_label = tk.Label(
            self.frame, text="",
            bg="#1a1a2e", fg="#AAAAAA",
            font=("Consolas", 8), wraplength=220, justify=tk.LEFT)
        self.info_label.pack(padx=4, anchor=tk.W)

    # ── Board overlay ─────────────────────────────────────────────────────────

    def _draw_zones(self):
        """Draw deployment zone rectangles on the board canvas."""
        canvas = self.board.canvas
        canvas.delete("deploy_zone")
        for zone in self.zones:
            x0, y0 = self.board.cm_to_screen(zone.x_min, zone.y_min)
            x1, y1 = self.board.cm_to_screen(zone.x_max, zone.y_max)
            color = _ZONE_COLORS.get(zone.player, "#AAAAAA")
            canvas.create_rectangle(
                x0, min(y0, y1), x1, max(y0, y1),
                outline=color, width=2, dash=(6, 3),
                tags="deploy_zone")
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
            names = ", ".join(s.name for s in group)
            self.status_label.config(
                text=f"Squadron: {names}\n"
                     f"Place ship {placed + 1} of {total}.\n"
                     f"All must be within {COHERENCY_CM}cm of each other.\n"
                     f"({remaining} group(s) remaining)")

        # Rebuild listbox
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
            info_lines = []
            for s in group:
                info_lines.append(
                    f"{s.name}: {s.ship_type}, Spd {s.speed}, Ld {s.leadership}")
            self.info_label.config(text="\n".join(info_lines))

        self.board.redraw()
        self._draw_zones()
        self._draw_pending()

    # ── Click handling ────────────────────────────────────────────────────────

    def _get_heading(self) -> float:
        try:
            return float(self._heading_entry_val.get()) % 360.0
        except (ValueError, AttributeError):
            return 0.0

    def _on_board_click(self, event):
        cx, cy = self.board.screen_to_cm(event.x, event.y)
        group = self.state.current_group()
        if group is None:
            return

        heading = self._get_heading()

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

    # ── Group list selection ──────────────────────────────────────────────────

    def _on_group_select(self, _event):
        """Allow clicking a future group to pre-select it (display info only)."""
        sel = self.group_listbox.curselection()
        if not sel:
            return
        p = self.state.active_player
        idx = sel[0]
        groups = self.state.groups[p]
        if 0 <= idx < len(groups):
            grp = groups[idx]
            info_lines = []
            for s in grp:
                info_lines.append(
                    f"{s.name}: {s.ship_type}, Spd {s.speed}, Ld {s.leadership}")
            self.info_label.config(text="\n".join(info_lines))

    # ── Auto-placement ────────────────────────────────────────────────────────

    def _auto_place_remaining(self):
        """Auto-place all remaining ships for the current (and next) player."""
        answer = messagebox.askyesno(
            "Auto-Place",
            "Auto-place all remaining ships at default positions within their "
            "deployment zone?\n\nThis will arrange them in a grid pattern.",
            parent=self.root)
        if not answer:
            return

        self._pending_positions.clear()
        self._pending_headings.clear()

        while not self.state.is_complete():
            group = self.state.current_group()
            if group is None:
                break
            p = self.state.active_player
            zone = self.state.zones[p]
            positions = self._find_auto_positions(group, zone)
            headings = [0.0 if p == 1 else 180.0] * len(group)
            ok, errors = self.state.place_group(positions, headings)
            if not ok:
                messagebox.showerror(
                    "Auto-Place Failed",
                    f"Could not auto-place {group[0].name}:\n" + "\n".join(errors),
                    parent=self.root)
                break
            for ship in self.state.placed_ships[-len(group):]:
                self.gs.update_ship(ship)

        self._refresh()

    def _find_auto_positions(
        self,
        group: List[Ship],
        zone: DeploymentZone,
    ) -> List[Tuple[float, float]]:
        """
        Find non-overlapping positions for *group* inside *zone*.
        Ships are arranged in a horizontal row near the centre of the zone.
        """
        cx = (zone.x_min + zone.x_max) / 2.0
        cy = (zone.y_min + zone.y_max) / 2.0

        spacing = 6.0  # cm between ship centres
        n = len(group)
        x_start = cx - spacing * (n - 1) / 2.0

        placed: List[Tuple[float, float]] = []
        for i in range(n):
            x = x_start + i * spacing
            # Clamp to zone
            x = max(zone.x_min + 3.0, min(zone.x_max - 3.0, x))
            # Try to avoid placed_ships
            y = cy
            for _attempt in range(10):
                ok = True
                for sx, sy in placed:
                    if math.hypot(x - sx, y - sy) < 5.0:
                        ok = False
                        break
                for s in self.state.placed_ships:
                    if math.hypot(x - s.x, y - s.y) < 5.0:
                        ok = False
                        break
                if ok:
                    break
                y += 5.0
                if y > zone.y_max - 2.0:
                    y = zone.y_min + 2.0
                    x += 4.0
            placed.append((x, y))
        return placed

    # ── Completion ────────────────────────────────────────────────────────────

    def _finish(self):
        self.board.canvas.delete("deploy_zone")
        self.board.canvas.delete("deploy_pending")
        # Restore original canvas click handler
        self.board.canvas.bind("<Button-1>", self._orig_click)
        self.frame.destroy()
        self.board.redraw()
        self.on_complete()
