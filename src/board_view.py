"""BFG:XR Board Viewer - Tkinter Canvas GUI"""
import tkinter as tk
from tkinter import messagebox, simpledialog
import math
from typing import Optional, Tuple
from .models import Ship, BlastMarker, OrdnanceMarker, Phenomenon, ShipType, BaseSize, Arc
from .game_state import GameState

# Ship circle sizes in screen pixels (will be scaled)
SHIP_RADII = {
    "battleship": 2.5,   # cm on table, will scale to screen
    "cruiser": 1.6,
    "escort": 1.2,
    "defense": 1.6,
}

PLAYER_COLORS = {
    "red": "#CC3333",
    "blue": "#3366CC",
    "green": "#33AA33",
    "yellow": "#CCAA00",
    "purple": "#8833AA",
    "orange": "#DD6600",
    "black": "#222222",
    "white": "#DDDDDD",
    "pink": "#DD66AA",
}

PHENOMENON_COLORS = {
    "asteroid_field": "#8B7355",
    "gas_dust_cloud": "#556B7B",
    "planet_small": "#4488AA",
    "planet_medium": "#448866",
    "planet_large": "#886644",
    "moon": "#AAAAAA",
    "warp_rift": "#9933FF",
    "ring": "#776655",
}


class BoardView:
    def __init__(self, master: tk.Tk, game_state: GameState):
        self.master = master
        self.gs = game_state
        self.master.title(f"BFG:XR - {game_state.game_name}")

        # Window layout
        self.master.geometry("1200x900")

        # Main frame
        main_frame = tk.Frame(master)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas (board)
        self.canvas = tk.Canvas(main_frame, bg="#0a0a1a", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Side panel
        self.side_panel = tk.Frame(main_frame, width=280, bg="#1a1a2e")
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.side_panel.pack_propagate(False)

        # Info label in side panel
        self.info_label = tk.Label(self.side_panel, text="BFG:XR Board",
                                   bg="#1a1a2e", fg="white", font=("Consolas", 12, "bold"),
                                   anchor="nw", justify="left", wraplength=260)
        self.info_label.pack(padx=5, pady=5, fill=tk.X)

        # Ship info text widget
        self.info_text = tk.Text(self.side_panel, bg="#1a1a2e", fg="#cccccc",
                                 font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
                                 borderwidth=0)
        self.info_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = tk.Label(master, textvariable=self.status_var,
                                    bg="#1a1a2e", fg="#aaaaaa", anchor="w",
                                    font=("Consolas", 9))
        self.status_bar.pack(fill=tk.X)

        # Scaling
        self.margin = 30  # pixels
        self.scale = 1.0  # pixels per cm

        # Tools
        self.active_tool = None  # "ruler", "ruler_ship", "arc_view", None
        self.ruler_start = None       # (cx, cy) or None
        self.ruler_start_ship = None  # ship ID if start snapped to a ship
        self.selected_ship_id = None
        self.show_arcs_ship_id = None
        self.snap_target_id = None    # ship we'd snap to on click

        # Persistent ruler lines (stay on screen until cleared)
        self.ruler_lines = []  # list of ((x1,y1), (x2,y2), dist, label)

        # Mouse tracking
        self.mouse_x = 0
        self.mouse_y = 0

        # Drag-and-drop movement state
        self.drag_ship_id: Optional[str] = None   # ship being dragged
        self.drag_result = None                    # last MovementResult from path compute
        self.drag_commands = []                    # last computed MoveCommand list
        # Callbacks set by game_panel:
        #   can_drag_ship_fn(ship) -> bool  : returns True if ship may move now
        #   commit_drag_fn(ship, commands)  : called on valid release to execute move
        self.can_drag_ship_fn = None
        self.commit_drag_fn = None

        # Ordnance launch drag state
        self.ord_drag_ship_id: Optional[str] = None  # ship being aimed
        self.ord_drag_heading: float = 0.0            # current drag heading
        self.ord_drag_in_arc: bool = False            # True if heading is in ±45° arc
        # Callbacks set by game_panel:
        #   can_ord_drag_fn(ship) -> bool
        #   commit_ord_drag_fn(ship, heading)
        self.can_ord_drag_fn = None
        self.commit_ord_drag_fn = None

        # Bindings
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Keyboard shortcuts
        master.bind("r", lambda e: self._toggle_tool("ruler"))
        master.bind("d", lambda e: self._toggle_tool("ruler_ship"))
        master.bind("a", lambda e: self._toggle_tool("arc_view"))
        master.bind("c", lambda e: self._clear_rulers())
        master.bind("Escape", lambda e: self._cancel_drag_or_clear_tool())

        # Menu bar
        self._create_menu()

        # Initial draw
        self.master.after(100, self.redraw)

    def _create_menu(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Game", command=self._save_game)
        file_menu.add_command(label="Load Game", command=self._load_game)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.master.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Ruler - Point to Point (R)",
                               command=lambda: self._toggle_tool("ruler"))
        tools_menu.add_command(label="Ruler - Ship Distance (D)",
                               command=lambda: self._toggle_tool("ruler_ship"))
        tools_menu.add_command(label="Arc View (A)",
                               command=lambda: self._toggle_tool("arc_view"))
        tools_menu.add_separator()
        tools_menu.add_command(label="Clear Rulers (C)", command=self._clear_rulers)
        tools_menu.add_command(label="Clear Tool (Esc)", command=self._clear_tool)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Show All Ship Info", command=self._show_all_ships)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Keyboard Shortcuts", command=self._show_help)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
            "BFG:XR Simulator",
            "Battlefleet Gothic: Expanded Revised\n"
            "Turn-by-turn tactical simulator\n\n"
            "Based on the BFG:XR community ruleset"))
        menubar.add_cascade(label="Help", menu=help_menu)

    def _toggle_tool(self, tool_name):
        if self.active_tool == tool_name:
            self._clear_tool()
        else:
            self.active_tool = tool_name
            self.ruler_start = None
            self.ruler_start_ship = None
            self.snap_target_id = None
            hints = {
                "ruler": "Ruler: click two points (snaps to ships nearby) | C to clear lines",
                "ruler_ship": "Ship Distance: click a ship, then click another ship or point | C to clear",
                "arc_view": "Arc View: click a ship to show its fire arcs and ranges",
            }
            self.status_var.set(hints.get(tool_name, f"Tool: {tool_name}"))
            self.redraw()

    def _clear_tool(self):
        self.active_tool = None
        self.ruler_start = None
        self.ruler_start_ship = None
        self.show_arcs_ship_id = None
        self.snap_target_id = None
        self.status_var.set("Ready")
        self.redraw()

    def _cancel_drag_or_clear_tool(self):
        """Escape: cancel active drag (movement or ordnance), then clear tool."""
        if self.drag_ship_id:
            self.drag_ship_id = None
            self.drag_commands = []
            self.drag_result = None
            self.status_var.set("Drag cancelled")
            self.redraw()
        elif self.ord_drag_ship_id:
            self.ord_drag_ship_id = None
            self.ord_drag_heading = 0.0
            self.ord_drag_in_arc = False
            self.status_var.set("Ordnance aim cancelled")
            self.redraw()
        else:
            self._clear_tool()

    def _clear_rulers(self):
        """Clear all persistent ruler lines from the board"""
        self.ruler_lines.clear()
        self.status_var.set("Rulers cleared")
        self.redraw()

    # Coordinate conversion
    def cm_to_screen(self, cx, cy) -> Tuple[float, float]:
        """Convert game cm coordinates to screen pixel coordinates"""
        sx = self.margin + cx * self.scale
        sy = self.canvas.winfo_height() - self.margin - cy * self.scale  # Y flipped
        return sx, sy

    def screen_to_cm(self, sx, sy) -> Tuple[float, float]:
        """Convert screen pixels to game cm coordinates"""
        cx = (sx - self.margin) / self.scale
        cy = (self.canvas.winfo_height() - self.margin - sy) / self.scale
        return cx, cy

    def cm_to_pixels(self, cm_val) -> float:
        """Convert a cm distance to pixels"""
        return cm_val * self.scale

    def _on_resize(self, event):
        # Recalculate scale to fit table in canvas
        cw = event.width - 2 * self.margin
        ch = event.height - 2 * self.margin
        if cw <= 0 or ch <= 0:
            return
        scale_x = cw / self.gs.table_width
        scale_y = ch / self.gs.table_height
        self.scale = min(scale_x, scale_y)
        self.redraw()

    def _on_motion(self, event):
        self.mouse_x, self.mouse_y = event.x, event.y
        cx, cy = self.screen_to_cm(event.x, event.y)
        if 0 <= cx <= self.gs.table_width and 0 <= cy <= self.gs.table_height:
            tool_str = f" | Tool: {self.active_tool}" if self.active_tool else ""
            # Check for snap target during ruler tools
            old_snap = self.snap_target_id
            self.snap_target_id = None
            if self.active_tool in ("ruler", "ruler_ship"):
                snap_ship = self._find_snap_ship(cx, cy)
                if snap_ship:
                    self.snap_target_id = snap_ship.id
                    tool_str += f" | Snap: {snap_ship.name}"
            if old_snap != self.snap_target_id:
                self.redraw()
                # Redraw live ruler preview if dragging
                if self.ruler_start and self.active_tool in ("ruler", "ruler_ship"):
                    end = self._get_snap_point(cx, cy)
                    dist = math.sqrt((end[0] - self.ruler_start[0])**2 +
                                     (end[1] - self.ruler_start[1])**2)
                    self._draw_ruler_line(self.ruler_start, end, dist, persistent=False)
            self.status_var.set(f"({cx:.1f}, {cy:.1f}) cm{tool_str}")

    def _find_snap_ship(self, cx, cy, snap_radius_cm=3.0) -> Optional[Ship]:
        """Find ship near a point for snapping (larger tolerance than selection)"""
        best = None
        best_dist = snap_radius_cm
        for s_dict in self.gs.ships:
            s = Ship.from_dict(s_dict)
            dist = math.sqrt((cx - s.x)**2 + (cy - s.y)**2)
            display_r = SHIP_RADII.get(s.ship_type, 1.6)
            if dist <= display_r + snap_radius_cm and dist < best_dist:
                best = s
                best_dist = dist
        return best

    def _get_snap_point(self, cx, cy) -> Tuple[float, float]:
        """If near a ship, return its stem position; otherwise return raw point"""
        snap_ship = self._find_snap_ship(cx, cy)
        if snap_ship:
            return (snap_ship.x, snap_ship.y)
        return (cx, cy)

    def _on_click(self, event):
        cx, cy = self.screen_to_cm(event.x, event.y)

        if self.active_tool == "ruler":
            # Point-to-point with ship snap
            point = self._get_snap_point(cx, cy)
            snap_ship = self._find_snap_ship(cx, cy)
            if self.ruler_start is None:
                self.ruler_start = point
                self.ruler_start_ship = snap_ship.id if snap_ship else None
                label = snap_ship.name if snap_ship else f"({point[0]:.1f}, {point[1]:.1f})"
                self.status_var.set(f"Ruler from {label} | Click endpoint")
            else:
                dist = math.sqrt((point[0] - self.ruler_start[0])**2 +
                                 (point[1] - self.ruler_start[1])**2)
                # Build label
                start_label = ""
                if self.ruler_start_ship:
                    s = self.gs.get_ship_by_id(self.ruler_start_ship)
                    start_label = s.name if s else ""
                end_label = snap_ship.name if snap_ship else ""
                label = f"{dist:.1f}cm"
                if start_label or end_label:
                    label = f"{start_label or 'point'} → {end_label or 'point'}: {dist:.1f}cm"
                # Store as persistent line
                self.ruler_lines.append((self.ruler_start, point, dist, label))
                self.status_var.set(f"Ruler: {label}")
                self.ruler_start = None
                self.ruler_start_ship = None
                self.redraw()
            return

        if self.active_tool == "ruler_ship":
            # Ship distance: first click MUST be on a ship
            snap_ship = self._find_snap_ship(cx, cy)
            if self.ruler_start is None:
                if not snap_ship:
                    self.status_var.set("Ship Distance: click ON a ship to start")
                    return
                self.ruler_start = (snap_ship.x, snap_ship.y)
                self.ruler_start_ship = snap_ship.id
                self.status_var.set(f"From {snap_ship.name} | Click target ship or point")
            else:
                point = self._get_snap_point(cx, cy)
                dist = math.sqrt((point[0] - self.ruler_start[0])**2 +
                                 (point[1] - self.ruler_start[1])**2)
                start_ship = self.gs.get_ship_by_id(self.ruler_start_ship)
                start_name = start_ship.name if start_ship else "?"
                end_name = snap_ship.name if snap_ship else "point"
                label = f"{start_name} → {end_name}: {dist:.1f}cm"
                self.ruler_lines.append((self.ruler_start, point, dist, label))
                self.status_var.set(label)
                self.ruler_start = None
                self.ruler_start_ship = None
                self.redraw()
            return

        if self.active_tool == "arc_view":
            ship = self._find_ship_at(cx, cy)
            if ship:
                self.show_arcs_ship_id = ship.id
                self.redraw()
            return

        # Default: select ship; start movement drag or ordnance aim drag
        ship = self._find_ship_at(cx, cy)
        if ship:
            self.selected_ship_id = ship.id
            self._show_ship_info(ship)
            if self.can_drag_ship_fn and self.can_drag_ship_fn(ship):
                self.drag_ship_id = ship.id
                self.status_var.set(
                    f"Dragging {ship.name} — release to commit, Escape to cancel")
            elif self.can_ord_drag_fn and self.can_ord_drag_fn(ship):
                self.ord_drag_ship_id = ship.id
                self.ord_drag_heading = ship.heading
                self.ord_drag_in_arc = True
                self.status_var.set(
                    f"Aim ordnance from {ship.name} — drag to set heading, Escape to cancel")
            self.redraw()
        else:
            self.selected_ship_id = None
            self.drag_ship_id = None
            self.ord_drag_ship_id = None
            self._clear_info()
            self.redraw()

    def _on_right_click(self, event):
        cx, cy = self.screen_to_cm(event.x, event.y)
        ship = self._find_ship_at(cx, cy)
        if ship:
            # Context menu
            menu = tk.Menu(self.master, tearoff=0)
            menu.add_command(label=f"--- {ship.name} ---", state=tk.DISABLED)
            menu.add_command(label="Show Arcs",
                           command=lambda: self._set_arc_view(ship.id))
            menu.add_command(label="Show Info",
                           command=lambda: self._show_ship_info(ship))
            menu.add_separator()
            menu.add_command(label="Measure from this ship",
                           command=lambda: self._start_ruler_from_ship(ship))
            menu.add_command(label="Measure to all enemies",
                           command=lambda: self._measure_to_all_enemies(ship))
            menu.post(event.x_root, event.y_root)

    def _start_ruler_from_ship(self, ship: Ship):
        """Start the ship distance tool with this ship as origin"""
        self.active_tool = "ruler_ship"
        self.ruler_start = (ship.x, ship.y)
        self.ruler_start_ship = ship.id
        self.status_var.set(f"Measuring from {ship.name} | Click target ship or point")

    def _measure_to_all_enemies(self, ship: Ship):
        """Draw ruler lines from this ship to every enemy ship"""
        enemy_player = 2 if ship.player == 1 else 1
        for s_dict in self.gs.ships:
            other = Ship.from_dict(s_dict)
            if other.player == enemy_player and not other.is_destroyed:
                dist = ship.distance_to(other)
                arc = ship.get_target_arc(other.x, other.y)
                label = f"→ {other.name}: {dist:.1f}cm ({arc.value})"
                self.ruler_lines.append(((ship.x, ship.y), (other.x, other.y), dist, label))
        self.redraw()
        self.status_var.set(f"Showing distances from {ship.name} to all enemies | C to clear")

    def _on_drag(self, event):
        if self.active_tool in ("ruler", "ruler_ship") and self.ruler_start:
            self.redraw()
            cx, cy = self.screen_to_cm(event.x, event.y)
            end = self._get_snap_point(cx, cy)
            dist = math.sqrt((end[0] - self.ruler_start[0])**2 +
                             (end[1] - self.ruler_start[1])**2)
            self._draw_ruler_line(self.ruler_start, end, dist, persistent=False)
            self.status_var.set(f"Ruler: {dist:.1f} cm")
            return

        if self.drag_ship_id:
            cx, cy = self.screen_to_cm(event.x, event.y)
            ship = self.gs.get_ship_by_id(self.drag_ship_id)
            if not ship:
                self.drag_ship_id = None
                return
            from .movement_ui import compute_drag_path
            commands, result = compute_drag_path(
                ship, cx, cy,
                ship.special_order,
                blast_markers=self.gs.get_blast_markers(),
                table_width=self.gs.table_width,
                table_height=self.gs.table_height)
            self.drag_commands = commands
            self.drag_result = result
            self.redraw()
            if result:
                color = "#44FF44" if result.valid else "#FF4444"
                # Draw path segments
                for i in range(len(result.path) - 1):
                    sx0, sy0 = self.cm_to_screen(*result.path[i])
                    sx1, sy1 = self.cm_to_screen(*result.path[i + 1])
                    self.canvas.create_line(sx0, sy0, sx1, sy1,
                                            fill=color, width=2, dash=(4, 4))
                # Ghost ship circle at end position
                gx, gy = self.cm_to_screen(result.final_x, result.final_y)
                r = self.cm_to_pixels(ship.base_radius)
                self.canvas.create_oval(gx - r, gy - r, gx + r, gy + r,
                                        outline=color, width=2, dash=(3, 3))
                # Ghost heading arrow
                head_rad = math.radians(result.final_heading)
                ax = gx + r * 2 * math.cos(head_rad)
                ay = gy - r * 2 * math.sin(head_rad)
                self.canvas.create_line(gx, gy, ax, ay,
                                        fill=color, width=2, arrow=tk.LAST)
                dist_label = f"{result.total_distance:.1f}cm"
                if not result.valid:
                    dist_label += " ✗"
                self.status_var.set(
                    f"Drag {ship.name}: {dist_label} "
                    f"→ ({result.final_x:.0f}, {result.final_y:.0f}) "
                    f"hdg {result.final_heading:.0f}°"
                    + ("  VALID — release to commit"
                       if result.valid else
                       f"  INVALID: {result.errors[0] if result.errors else ''}"))

        elif self.ord_drag_ship_id:
            cx, cy = self.screen_to_cm(event.x, event.y)
            ship = self.gs.get_ship_by_id(self.ord_drag_ship_id)
            if not ship:
                self.ord_drag_ship_id = None
                return

            dx = cx - ship.x
            dy = cy - ship.y
            drag_dist = math.sqrt(dx * dx + dy * dy)

            if drag_dist > 0.5:
                raw_bearing = math.degrees(math.atan2(dy, dx)) % 360
                # Offset from ship heading, in (-180, 180]
                diff = (raw_bearing - ship.heading + 180) % 360 - 180
                in_arc = abs(diff) <= 45
                # Snap range: ±45° to ±60° → clamp to ±45°
                snap_zone = 45 < abs(diff) <= 60
                if snap_zone:
                    diff = 45.0 * (1 if diff > 0 else -1)
                    in_arc = True
                self.ord_drag_heading = (ship.heading + diff) % 360
                self.ord_drag_in_arc = in_arc and not (abs(diff) > 60)
            else:
                self.ord_drag_heading = ship.heading
                self.ord_drag_in_arc = True

            self.redraw()
            sx, sy = self.cm_to_screen(ship.x, ship.y)
            arc_color = "#44FF44" if self.ord_drag_in_arc else "#FF4444"

            # Draw ±45° launch arc cone
            arc_r = self.cm_to_pixels(30)
            ship_hdg = ship.heading
            start_angle_screen = -(ship_hdg + 45)  # canvas angles are CCW from east
            self.canvas.create_arc(
                sx - arc_r, sy - arc_r, sx + arc_r, sy + arc_r,
                start=start_angle_screen, extent=90,
                fill="", outline="#888844", width=1, style=tk.ARC)
            # Draw two arc boundary lines
            for offset in (-45, 45):
                edge_rad = math.radians(ship_hdg + offset)
                ex = sx + arc_r * math.cos(edge_rad)
                ey = sy - arc_r * math.sin(edge_rad)
                self.canvas.create_line(sx, sy, ex, ey,
                                        fill="#888844", width=1, dash=(3, 3))

            # Draw heading arrow
            hdg_rad = math.radians(self.ord_drag_heading)
            arrow_len = self.cm_to_pixels(25)
            ax = sx + arrow_len * math.cos(hdg_rad)
            ay = sy - arrow_len * math.sin(hdg_rad)
            self.canvas.create_line(sx, sy, ax, ay,
                                    fill=arc_color, width=2, arrow=tk.LAST)

            if self.ord_drag_in_arc:
                self.status_var.set(
                    f"Launch from {ship.name}: heading {self.ord_drag_heading:.0f}° "
                    f"— VALID  (release to open launch dialog)")
            else:
                self.status_var.set(
                    f"Launch from {ship.name}: heading {self.ord_drag_heading:.0f}° "
                    f"— OUTSIDE ARC (>{60}° off bow — release cancels)")

    def _on_release(self, event):
        if self.drag_ship_id:
            ship = self.gs.get_ship_by_id(self.drag_ship_id)
            if (ship and self.drag_result and self.drag_result.valid
                    and self.commit_drag_fn and self.drag_commands):
                self.commit_drag_fn(ship, self.drag_commands)
            self.drag_ship_id = None
            self.drag_commands = []
            self.drag_result = None
            self.status_var.set("Ready")
            self.redraw()

        elif self.ord_drag_ship_id:
            ship = self.gs.get_ship_by_id(self.ord_drag_ship_id)
            if ship and self.ord_drag_in_arc and self.commit_ord_drag_fn:
                self.commit_ord_drag_fn(ship, self.ord_drag_heading)
            elif ship and not self.ord_drag_in_arc:
                self.status_var.set(
                    f"Launch cancelled — heading too far off arc")
            self.ord_drag_ship_id = None
            self.ord_drag_heading = 0.0
            self.ord_drag_in_arc = False
            self.redraw()

    def _set_arc_view(self, ship_id):
        self.show_arcs_ship_id = ship_id
        self.redraw()

    def _find_ship_at(self, cx, cy) -> Optional[Ship]:
        """Find ship whose base contains the point (cx, cy)"""
        for s_dict in self.gs.ships:
            s = Ship.from_dict(s_dict)
            display_r = SHIP_RADII.get(s.ship_type, 1.6)
            dist = math.sqrt((cx - s.x)**2 + (cy - s.y)**2)
            if dist <= display_r + 0.5:  # small tolerance
                return s
        return None

    # Drawing
    def redraw(self):
        self.canvas.delete("all")
        if self.scale <= 0:
            return
        self._draw_grid()
        self._draw_phenomena()
        self._draw_blast_markers()
        self._draw_ordnance()
        self._draw_ships()
        self._draw_persistent_rulers()
        self._draw_snap_indicator()
        if self.show_arcs_ship_id:
            self._draw_arc_overlay(self.show_arcs_ship_id)

    def _draw_persistent_rulers(self):
        """Draw all stored ruler lines"""
        for start, end, dist, label in self.ruler_lines:
            self._draw_ruler_line(start, end, dist, persistent=True, label=label)

    def _draw_snap_indicator(self):
        """Draw a highlight ring around the ship we'd snap to"""
        if self.snap_target_id and self.active_tool in ("ruler", "ruler_ship"):
            ship = self.gs.get_ship_by_id(self.snap_target_id)
            if ship:
                sx, sy = self.cm_to_screen(ship.x, ship.y)
                r = self.cm_to_pixels(SHIP_RADII.get(ship.ship_type, 1.6)) + 4
                self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                         outline="#FFFF00", width=2, dash=(3, 3))

    def _draw_grid(self):
        """Draw table boundary and grid lines"""
        # Table boundary
        x0, y0 = self.cm_to_screen(0, 0)
        x1, y1 = self.cm_to_screen(self.gs.table_width, self.gs.table_height)
        self.canvas.create_rectangle(x0, y1, x1, y0, outline="#333355", width=2)

        # Grid lines every 10cm
        for i in range(0, int(self.gs.table_width) + 1, 10):
            sx, sy0 = self.cm_to_screen(i, 0)
            _, sy1 = self.cm_to_screen(i, self.gs.table_height)
            color = "#222244" if i % 30 != 0 else "#333366"
            self.canvas.create_line(sx, sy0, sx, sy1, fill=color, dash=(2, 4))
        for j in range(0, int(self.gs.table_height) + 1, 10):
            sx0, sy = self.cm_to_screen(0, j)
            sx1, _ = self.cm_to_screen(self.gs.table_width, j)
            color = "#222244" if j % 30 != 0 else "#333366"
            self.canvas.create_line(sx0, sy, sx1, sy, fill=color, dash=(2, 4))

        # Scale indicator
        sx0, sy = self.cm_to_screen(5, -2)
        sx1, _ = self.cm_to_screen(15, -2)
        self.canvas.create_line(sx0, sy, sx1, sy, fill="#666688", width=2)
        self.canvas.create_text((sx0 + sx1) / 2, sy - 10, text="10cm",
                                fill="#666688", font=("Consolas", 8))

        # Compass rose (top-right corner, outside board)
        self._draw_compass_rose()

    def _draw_compass_rose(self):
        """Draw a compass rose showing sunward direction."""
        # Position in top-right margin area
        cx = self.canvas.winfo_width() - 50
        cy = 45
        arm = 20

        # Sunward direction mapping to angle
        sunward_angles = {"north": 90, "south": 270, "east": 0, "west": 180}
        sun_angle = sunward_angles.get(self.gs.sunward_edge, 0)

        # Draw cross arms
        for label, angle in [("N", 90), ("S", 270), ("E", 0), ("W", 180)]:
            rad = math.radians(angle)
            ex = cx + arm * math.cos(rad)
            ey = cy - arm * math.sin(rad)
            color = "#FFDD44" if angle == sun_angle else "#556677"
            width = 2 if angle == sun_angle else 1
            self.canvas.create_line(cx, cy, ex, ey, fill=color, width=width)
            tx = cx + (arm + 10) * math.cos(rad)
            ty = cy - (arm + 10) * math.sin(rad)
            lbl = label
            if angle == sun_angle:
                lbl = f"☀{label}"
            self.canvas.create_text(tx, ty, text=lbl, fill=color,
                                     font=("Consolas", 7, "bold" if angle == sun_angle else ""))

        # Center dot
        self.canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2,
                                 fill="#556677", outline="")

    def _draw_phenomena(self):
        for p_dict in self.gs.phenomena:
            p = Phenomenon.from_dict(p_dict)
            color = PHENOMENON_COLORS.get(p.phenomenon_type, "#555555")

            if "planet" in p.phenomenon_type:
                sx, sy = self.cm_to_screen(p.x, p.y)
                r = self.cm_to_pixels(p.radius)
                self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                         fill=color, outline="#ffffff", width=1, stipple="gray50")
                # Gravity well circle
                gw = self.cm_to_pixels(p.gravity_well_radius)
                if gw > 0:
                    self.canvas.create_oval(sx - gw, sy - gw, sx + gw, sy + gw,
                                             outline="#336699", width=1, dash=(4, 4))

            elif p.phenomenon_type == "asteroid_field":
                # Lattice of small brown circles
                sx1, sy1 = self.cm_to_screen(p.x - p.width / 2, p.y + p.height / 2)
                sx2, sy2 = self.cm_to_screen(p.x + p.width / 2, p.y - p.height / 2)
                # Border
                self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                              fill="", outline="#665544", width=1, dash=(3, 5))
                # Scatter small circles inside
                import random as _rng
                _rng.seed(hash(p.id))  # deterministic per field
                w_px = abs(sx2 - sx1)
                h_px = abs(sy2 - sy1)
                num_rocks = max(8, int(w_px * h_px / 400))
                for _ in range(num_rocks):
                    rx = min(sx1, sx2) + _rng.random() * w_px
                    ry = min(sy1, sy2) + _rng.random() * h_px
                    rr = _rng.uniform(2, 5)
                    shade = _rng.choice(["#7B6B4F", "#8B7355", "#6B5B3F", "#9B8365"])
                    self.canvas.create_oval(rx - rr, ry - rr, rx + rr, ry + rr,
                                             fill=shade, outline="#554433", width=1)

            elif p.phenomenon_type == "gas_dust_cloud":
                # Cloud-like shape using overlapping ovals
                cx_s, cy_s = self.cm_to_screen(p.x, p.y)
                rw = self.cm_to_pixels(p.width / 2)
                rh = self.cm_to_pixels(p.height / 2)
                cloud_color = "#2a3a4a"
                outline_color = "#556B7B"
                # Draw multiple overlapping ellipses for cloud shape
                offsets = [(0, 0, 1.0, 0.8), (-0.4, 0.2, 0.7, 0.6),
                           (0.3, 0.15, 0.75, 0.65), (-0.2, -0.25, 0.6, 0.5),
                           (0.35, -0.2, 0.65, 0.55)]
                for ox, oy, sw, sh in offsets:
                    ex = cx_s + ox * rw
                    ey = cy_s + oy * rh
                    erw = rw * sw
                    erh = rh * sh
                    self.canvas.create_oval(ex - erw, ey - erh, ex + erw, ey + erh,
                                             fill=cloud_color, outline=outline_color,
                                             width=1, stipple="gray25")

            elif p.phenomenon_type == "warp_rift":
                sx, sy = self.cm_to_screen(p.x - p.width / 2, p.y + p.height / 2)
                sx2, sy2 = self.cm_to_screen(p.x + p.width / 2, p.y - p.height / 2)
                self.canvas.create_rectangle(sx, sy, sx2, sy2,
                                              fill="#1a0033", outline="#9933FF", width=2)

    def _draw_blast_markers(self):
        for bm_dict in self.gs.blast_markers:
            bm = BlastMarker.from_dict(bm_dict)
            sx, sy = self.cm_to_screen(bm.x, bm.y)
            # Blast marker trefoil: 3 overlapping circles, ~2.5x3cm matching PDF
            r_circle = self.cm_to_pixels(0.75)   # each sub-circle radius
            offset = self.cm_to_pixels(0.65)      # center to circle center
            # Triangle points: top, bottom-left, bottom-right
            for angle in [90, 210, 330]:
                rad = math.radians(angle)
                cx = sx + offset * math.cos(rad)
                cy = sy - offset * math.sin(rad)
                self.canvas.create_oval(
                    cx - r_circle, cy - r_circle,
                    cx + r_circle, cy + r_circle,
                    fill="#CC5500", outline="#FF8800", width=1)
            # Hot center glow
            cr = self.cm_to_pixels(0.3)
            self.canvas.create_oval(sx - cr, sy - cr, sx + cr, sy + cr,
                                     fill="#FFAA33", outline="")

    def _draw_ordnance(self):
        for o_dict in self.gs.ordnance:
            o = OrdnanceMarker.from_dict(o_dict)
            sx, sy = self.cm_to_screen(o.x, o.y)
            player_col = self.gs.player1_color if o.owner_player == 1 else self.gs.player2_color
            color = PLAYER_COLORS.get(player_col, "#FFFFFF")
            # Darker version for fill, brighter for outline = team visible
            outline = color
            fill = self._darken(color, 0.6)
            heading_rad = math.radians(o.heading)

            otype = o.ordnance_type

            if "torpedo" in otype:
                # Torpedo: rectangle with arrow tip, ~2x2.5cm scale
                hw = self.cm_to_pixels(1.0)   # half-width
                hh = self.cm_to_pixels(0.75)  # half-height
                tip = self.cm_to_pixels(0.5)  # arrow tip extension
                # Build polygon in local coords then rotate
                # Rectangle body + triangle tip pointing forward
                local_pts = [
                    (-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh),  # body
                ]
                # Arrow tip at front
                arrow_pts = [
                    (hw, -hh), (hw + tip, 0), (hw, hh),
                ]
                # Rotate and draw body
                body_screen = self._rotate_polygon(local_pts, heading_rad, sx, sy)
                self.canvas.create_polygon(body_screen, fill=fill, outline=outline, width=1)
                # Arrow tip
                tip_screen = self._rotate_polygon(arrow_pts, heading_rad, sx, sy)
                self.canvas.create_polygon(tip_screen, fill=fill, outline=outline, width=1)
                # Strength label
                self.canvas.create_text(sx, sy, text=f"T{o.strength}",
                                         fill="white", font=("Consolas", 7, "bold"))

            elif otype in ("fighter", "barracuda"):
                # Fighter: square 2x2cm with diagonal cross
                hs = self.cm_to_pixels(1.0)  # half-size
                pts = self._rotate_polygon(
                    [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)],
                    heading_rad, sx, sy)
                self.canvas.create_polygon(pts, fill=fill, outline=outline, width=2)
                label = "F" if otype == "fighter" else "Br"
                self.canvas.create_text(sx, sy, text=label,
                                         fill="white", font=("Consolas", 8, "bold"))

            elif otype == "bomber":
                # Bomber: square 2x2cm with X marker
                hs = self.cm_to_pixels(1.0)
                pts = self._rotate_polygon(
                    [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)],
                    heading_rad, sx, sy)
                self.canvas.create_polygon(pts, fill=fill, outline=outline, width=1)
                # X through it to distinguish from fighter
                d = hs * 0.6
                for dx, dy in [(d, d), (-d, d)]:
                    x1 = sx + dx * math.cos(heading_rad) - dy * math.sin(heading_rad)
                    y1 = sy - dx * math.sin(heading_rad) - dy * math.cos(heading_rad)
                    x2 = sx - dx * math.cos(heading_rad) + dy * math.sin(heading_rad)
                    y2 = sy + dx * math.sin(heading_rad) + dy * math.cos(heading_rad)
                    self.canvas.create_line(x1, y1, x2, y2, fill="white", width=1)
                self.canvas.create_text(sx, sy, text="B",
                                         fill="white", font=("Consolas", 8, "bold"))

            elif otype == "manta":
                # Manta: larger square 2x2cm with thick yellow border (resilient)
                hs = self.cm_to_pixels(1.0)
                pts = self._rotate_polygon(
                    [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)],
                    heading_rad, sx, sy)
                self.canvas.create_polygon(pts, fill=fill, outline="#FFDD00", width=2)
                self.canvas.create_text(sx, sy, text="M",
                                         fill="white", font=("Consolas", 9, "bold"))

            elif otype == "assault_boat":
                hs = self.cm_to_pixels(1.0)
                pts = self._rotate_polygon(
                    [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)],
                    heading_rad, sx, sy)
                self.canvas.create_polygon(pts, fill=fill, outline=outline, width=1)
                self.canvas.create_text(sx, sy, text="AB",
                                         fill="white", font=("Consolas", 7, "bold"))

            elif otype == "mine_field":
                # Single mine: 20mm square marker (2cm side), dashed orange
                hs = self.cm_to_pixels(1.0)
                pts = self._rotate_polygon(
                    [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)],
                    0, sx, sy)
                self.canvas.create_polygon(pts, fill="#331100", outline="#FF8800",
                                            width=2, dash=(3, 2))
                self.canvas.create_text(sx, sy, text="M",
                                         fill="#FF8800", font=("Consolas", 8, "bold"))

            else:
                hs = self.cm_to_pixels(0.8)
                self.canvas.create_rectangle(sx - hs, sy - hs, sx + hs, sy + hs,
                                              fill=fill, outline=outline, width=1)

    def _rotate_polygon(self, local_pts, angle_rad, cx, cy):
        """Rotate local (x,y) points around (cx,cy) by angle_rad. Returns flat list for create_polygon."""
        result = []
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        for lx, ly in local_pts:
            rx = cx + lx * cos_a - ly * sin_a
            ry = cy - (lx * sin_a + ly * cos_a)  # Y inverted for screen
            result.extend([rx, ry])
        return result

    def _draw_special_order_icon(self, cx, cy, order):
        """Draw a geometric icon for a special order at (cx, cy) screen coords."""
        s = 6  # icon half-size in pixels
        col = "#FFAA00"  # amber for all orders
        bg = "#1a1a2e"

        # Background circle
        self.canvas.create_oval(cx - s - 2, cy - s - 2, cx + s + 2, cy + s + 2,
                                 fill=bg, outline=col, width=1)

        if order == "all_ahead_full":
            # Double upward chevrons
            for dy in [-2, 3]:
                self.canvas.create_line(cx - s + 2, cy + dy + 2,
                                         cx, cy + dy - 3,
                                         cx + s - 2, cy + dy + 2,
                                         fill=col, width=2)

        elif order == "come_to_new_heading":
            # Curved double arrow (simplified as two small arcs)
            self.canvas.create_arc(cx - s, cy - s, cx + s, cy + s,
                                    start=30, extent=120, style="arc",
                                    outline=col, width=2)
            self.canvas.create_arc(cx - s, cy - s, cx + s, cy + s,
                                    start=210, extent=120, style="arc",
                                    outline=col, width=2)

        elif order == "burn_retros":
            # Starburst: 6 short lines radiating from center
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                x1 = cx + 2 * math.cos(rad)
                y1 = cy - 2 * math.sin(rad)
                x2 = cx + s * math.cos(rad)
                y2 = cy - s * math.sin(rad)
                self.canvas.create_line(x1, y1, x2, y2, fill=col, width=2)

        elif order == "lock_on":
            # Crosshair: circle with + through it
            r = s - 1
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     outline=col, width=2)
            self.canvas.create_line(cx - s, cy, cx + s, cy, fill=col, width=1)
            self.canvas.create_line(cx, cy - s, cx, cy + s, fill=col, width=1)

        elif order == "reload_ordnance":
            # Lightning bolt
            pts = [cx - 2, cy - s + 1,  cx + 2, cy - 2,
                   cx, cy - 1,  cx + 3, cy + 1,
                   cx - 1, cy + s - 1,  cx, cy + 1,
                   cx - 3, cy - 1]
            self.canvas.create_polygon(pts, fill=col, outline="")

        elif order == "brace_for_impact":
            # Exclamation mark in diamond
            self.canvas.create_polygon(
                cx, cy - s, cx + s, cy, cx, cy + s, cx - s, cy,
                fill="", outline=col, width=2)
            self.canvas.create_line(cx, cy - 3, cx, cy + 1, fill=col, width=2)
            self.canvas.create_oval(cx - 1, cy + 2, cx + 1, cy + 4, fill=col, outline="")

    def draw_nova_template(self, cx_cm, cy_cm, hit=False):
        """Draw a nova cannon template at the given game coordinates.
        5cm outer diameter circle with 1.2cm center hole."""
        sx, sy = self.cm_to_screen(cx_cm, cy_cm)
        outer_r = self.cm_to_pixels(2.5)   # 5cm diameter = 2.5cm radius
        inner_r = self.cm_to_pixels(0.6)   # 1.2cm diameter = 0.6cm radius
        color = "#FF4444" if hit else "#FF8844"

        # Outer circle
        self.canvas.create_oval(sx - outer_r, sy - outer_r,
                                 sx + outer_r, sy + outer_r,
                                 outline=color, width=2, dash=(4, 3))
        # Center hole
        self.canvas.create_oval(sx - inner_r, sy - inner_r,
                                 sx + inner_r, sy + inner_r,
                                 outline=color, fill="#1a1a2e", width=2)
        # Crosshair
        self.canvas.create_line(sx - outer_r - 3, sy, sx + outer_r + 3, sy,
                                 fill=color, width=1, dash=(2, 4))
        self.canvas.create_line(sx, sy - outer_r - 3, sx, sy + outer_r + 3,
                                 fill=color, width=1, dash=(2, 4))
        # Label
        self.canvas.create_text(sx, sy + outer_r + 8, text="Nova Template",
                                 fill=color, font=("Consolas", 7))

    def _draw_ships(self):
        for s_dict in self.gs.ships:
            s = Ship.from_dict(s_dict)
            # Don't draw disengaged or fully destroyed ships
            if s.is_disengaged or s.status == "disengaged":
                continue
            if s.status == "destroyed":
                continue  # removed from play (explosion, escort destruction)
            # Hulks are still drawn (greyed out, drifting)
            self._draw_single_ship(s)

    def _draw_single_ship(self, s: Ship):
        sx, sy = self.cm_to_screen(s.x, s.y)
        display_r = self.cm_to_pixels(SHIP_RADII.get(s.ship_type, 1.6))
        player_col = self.gs.player1_color if s.player == 1 else self.gs.player2_color
        color = PLAYER_COLORS.get(player_col, "#FFFFFF")

        is_selected = (s.id == self.selected_ship_id)
        outline_color = "#FFFFFF" if is_selected else "#888888"
        outline_width = 3 if is_selected else 1

        # Fill based on damage/status
        if s.status in ("drifting_hulk", "burning_hulk"):
            fill = "#444444"
            outline_color = "#FF6600" if s.status == "burning_hulk" else "#666666"
        elif s.is_destroyed:
            fill = "#333333"
        elif s.is_crippled:
            fill = self._darken(color, 0.5)
        else:
            fill = color

        # Ship circle
        self.canvas.create_oval(sx - display_r, sy - display_r,
                                 sx + display_r, sy + display_r,
                                 fill=fill, outline=outline_color, width=outline_width)

        # Arc crosshair lines
        heading_rad = math.radians(s.heading)
        cross_r = display_r * 1.3
        for angle_offset in [45, 135, 225, 315]:
            a = heading_rad + math.radians(angle_offset)
            x1 = sx + cross_r * 0.3 * math.cos(a)
            y1 = sy - cross_r * 0.3 * math.sin(a)
            x2 = sx + cross_r * math.cos(a)
            y2 = sy - cross_r * math.sin(a)
            self.canvas.create_line(x1, y1, x2, y2, fill=outline_color, width=1)

        # Forward arrow
        arrow_len = display_r * 1.8
        ax = sx + arrow_len * math.cos(heading_rad)
        ay = sy - arrow_len * math.sin(heading_rad)
        self.canvas.create_line(sx, sy, ax, ay, fill="#FFFF00", width=2, arrow=tk.LAST)

        # Ship name label
        self.canvas.create_text(sx, sy + display_r + 10, text=s.name,
                                 fill="#cccccc", font=("Consolas", 7), anchor="n")

        # HP indicator (small bar)
        if s.hits_max > 0 and not s.is_destroyed:
            bar_w = display_r * 1.5
            bar_h = 3
            bx = sx - bar_w / 2
            by = sy - display_r - 6
            hp_frac = s.hits_remaining / s.hits_max
            hp_color = "#33CC33" if hp_frac > 0.5 else ("#CCAA00" if hp_frac > 0.25 else "#CC3333")
            self.canvas.create_rectangle(bx, by, bx + bar_w, by + bar_h,
                                          fill="#333333", outline="")
            self.canvas.create_rectangle(bx, by, bx + bar_w * hp_frac, by + bar_h,
                                          fill=hp_color, outline="")

        # Special order indicator (drawn icon above ship)
        if s.special_order != "none":
            icon_x = sx
            icon_y = sy - display_r - 14
            self._draw_special_order_icon(icon_x, icon_y, s.special_order)

    def _draw_arc_overlay(self, ship_id: str):
        """Draw extended arc lines and range brackets for a ship"""
        ship = self.gs.get_ship_by_id(ship_id)
        if not ship:
            return

        sx, sy = self.cm_to_screen(ship.x, ship.y)
        heading_rad = math.radians(ship.heading)

        # Find max weapon range
        max_range = 0
        for w in ship.weapons:
            if w.get("range_cm", 0) > max_range:
                max_range = w["range_cm"]
        if max_range == 0:
            max_range = 45  # default

        range_px = self.cm_to_pixels(max_range)

        # Draw arc separator lines extended to max range
        arc_colors = {"front": "#FFFF44", "left": "#44FF44", "right": "#44FF44", "rear": "#FF4444"}
        for angle_offset in [45, 135, 225, 315]:
            a = heading_rad + math.radians(angle_offset)
            x2 = sx + range_px * math.cos(a)
            y2 = sy - range_px * math.sin(a)
            self.canvas.create_line(sx, sy, x2, y2, fill="#666666", width=1, dash=(4, 4))

        # Range bracket circles with notches
        range_brackets = [15, 30]  # standard range modifiers
        # Add weapon-specific ranges
        for w in ship.weapons:
            r = w.get("range_cm", 0)
            if r > 0 and r not in range_brackets:
                range_brackets.append(r)
        range_brackets.sort()

        for r_cm in range_brackets:
            r_px = self.cm_to_pixels(r_cm)
            self.canvas.create_oval(sx - r_px, sy - r_px, sx + r_px, sy + r_px,
                                     outline="#444466", width=1, dash=(2, 6))
            # Label
            label_a = heading_rad + math.radians(60)
            lx = sx + r_px * math.cos(label_a)
            ly = sy - r_px * math.sin(label_a)
            self.canvas.create_text(lx, ly, text=f"{r_cm}cm",
                                     fill="#666688", font=("Consolas", 7))

        # Arc labels
        for arc_name, angle_off in [("FRONT", 0), ("LEFT", 90), ("REAR", 180), ("RIGHT", 270)]:
            a = heading_rad + math.radians(angle_off)
            label_r = range_px * 0.4
            lx = sx + label_r * math.cos(a)
            ly = sy - label_r * math.sin(a)
            self.canvas.create_text(lx, ly, text=arc_name,
                                     fill="#555577", font=("Consolas", 8))

        # Highlight ships in each arc
        for other_dict in self.gs.ships:
            other = Ship.from_dict(other_dict)
            if other.id == ship_id:
                continue
            dist = ship.distance_to(other)
            if dist <= max_range:
                arc = ship.get_target_arc(other.x, other.y)
                osx, osy = self.cm_to_screen(other.x, other.y)
                arc_col = {"front": "#FFFF44", "left": "#44FF44",
                           "right": "#FF8844", "rear": "#FF4444"}.get(arc.value, "#FFFFFF")
                self.canvas.create_line(sx, sy, osx, osy, fill=arc_col, width=1, dash=(3, 3))
                self.canvas.create_text(osx + 15, osy - 10,
                                         text=f"{arc.value} {dist:.0f}cm",
                                         fill=arc_col, font=("Consolas", 7))

    def _draw_ruler_line(self, start_cm, end_cm, dist, persistent=False, label=None):
        sx0, sy0 = self.cm_to_screen(*start_cm)
        sx1, sy1 = self.cm_to_screen(*end_cm)
        line_color = "#FFFFFF" if persistent else "#FFFF88"
        text_color = "#FFFFFF" if persistent else "#FFFF88"
        self.canvas.create_line(sx0, sy0, sx1, sy1, fill=line_color, width=2, dash=(5, 3))

        # Endpoint dots
        for ex, ey in [(sx0, sy0), (sx1, sy1)]:
            self.canvas.create_oval(ex - 3, ey - 3, ex + 3, ey + 3,
                                     fill=line_color, outline="")

        # Distance label at midpoint
        mx, my = (sx0 + sx1) / 2, (sy0 + sy1) / 2
        display_label = label if label else f"{dist:.1f} cm"
        self.canvas.create_text(mx, my - 12, text=display_label,
                                 fill=text_color, font=("Consolas", 9, "bold"))

        # Notches every 10cm
        if dist > 0:
            dx = end_cm[0] - start_cm[0]
            dy = end_cm[1] - start_cm[1]
            for d in range(10, int(dist) + 1, 10):
                frac = d / dist
                nx = start_cm[0] + dx * frac
                ny = start_cm[1] + dy * frac
                nsx, nsy = self.cm_to_screen(nx, ny)
                self.canvas.create_oval(nsx - 2, nsy - 2, nsx + 2, nsy + 2,
                                         fill=line_color, outline="")
                # Label every 30cm
                if d % 30 == 0:
                    self.canvas.create_text(nsx + 8, nsy - 8, text=f"{d}",
                                             fill="#888888", font=("Consolas", 7))

    def _show_ship_info(self, s: Ship):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)

        lines = []
        lines.append(f"=== {s.name} ===")
        lines.append(f"Class: {s.ship_class}")
        lines.append(f"Type: {s.ship_type.upper()}")
        lines.append(f"Faction: {s.faction}")
        lines.append(f"")
        lines.append(f"HP: {s.hits_remaining}/{s.hits_max}" +
                     (" [CRIPPLED]" if s.is_crippled else "") +
                     (" [DESTROYED]" if s.is_destroyed else ""))

        # Calculate actual shields (reduced by touching blast markers)
        blast_touching = 0
        for bm_dict in self.gs.blast_markers:
            bm = BlastMarker.from_dict(bm_dict)
            dist = math.sqrt((bm.x - s.x)**2 + (bm.y - s.y)**2)
            if dist <= s.base_radius + 2.0:
                blast_touching += 1
        actual_shields = max(0, s.effective_shields - blast_touching)
        lines.append(f"Shields: {actual_shields}/{s.shields_max}"
                     + (f" ({blast_touching} blast markers)" if blast_touching > 0 else ""))
        lines.append(f"Speed: {s.effective_speed}cm")
        lines.append(f"Turn: {s.turn_angle}°")
        lines.append(f"Armor: {s.armor_prow} prow / {s.armor_side} side")
        lines.append(f"Turrets: {s.effective_turrets}")
        lines.append(f"Leadership: {s.leadership}")
        lines.append(f"Position: ({s.x:.1f}, {s.y:.1f})")
        lines.append(f"Heading: {s.heading:.0f}°")
        lines.append(f"")

        if s.special_order != "none":
            lines.append(f"Order: {s.special_order}")
        if s.is_flagship:
            lines.append(f"FLAGSHIP ({s.admiral_type})")
            lines.append(f"Re-rolls: {s.rerolls_remaining}")
        lines.append(f"")

        # Weapons
        lines.append("--- WEAPONS ---")
        for w in s.weapons:
            arcs = "/".join(w.get("arcs", []))
            wtype = w.get("weapon_type", "?")
            if wtype == "battery":
                lines.append(f"  {w['name']}: FP {w['strength']} {w['range_cm']}cm [{arcs}]")
            elif wtype == "lance":
                lines.append(f"  {w['name']}: Str {w['strength']} {w['range_cm']}cm [{arcs}]")
            elif wtype == "nova_cannon":
                lines.append(f"  {w['name']}: Nova 30-150cm [{arcs}]")
            elif wtype == "launch_bay":
                types = "/".join(w.get("craft_types", []))
                lines.append(f"  {w['name']}: {w['strength']} sqn ({types}) [{arcs}]")
            elif wtype == "torpedo":
                lines.append(f"  {w['name']}: Str {w['strength']} {w.get('torpedo_speed', 30)}cm [{arcs}]")
            elif wtype == "gravitic_launcher":
                lines.append(f"  {w['name']}: Str {w['strength']} {w['range_cm']}cm [{arcs}]")
        lines.append(f"")

        # Ordnance status
        lines.append("--- ORDNANCE ---")
        lines.append(f"  Torps/Missiles: {'LOADED' if s.ordnance_loaded_torps else 'EMPTY'}")
        lines.append(f"  Attack Craft: {'LOADED' if s.ordnance_loaded_craft else 'EMPTY'}")
        lines.append(f"")

        # Critical damage (grouped with effect descriptions)
        if s.critical_damage:
            lines.append("--- CRITICAL DAMAGE ---")

            # Group crits by type and count
            crit_counts = {}
            for c in s.critical_damage:
                ct = c.get("crit_type", "unknown")
                if ct not in crit_counts:
                    crit_counts[ct] = {
                        "count": 0,
                        "description": c["description"],
                        "repairable": c.get("repairable", False),
                    }
                crit_counts[ct]["count"] += 1

            # Effect descriptions per crit type
            CRIT_EFFECTS = {
                "dorsal_armament": "Dorsal weapons disabled",
                "starboard_armament": "Starboard weapons disabled",
                "port_armament": "Port weapons disabled",
                "prow_armament": "Prow weapons disabled",
                "engine_room": "No turns until repaired",
                "fire": None,  # handled specially
                "thrusters_damaged": "-10cm speed until ALL repaired",
                "bridge_smashed": "-3 Leadership (permanent)",
                "shields_collapse": "Shields disabled (permanent)",
                "hull_breach": "Extra D3 hull damage",
                "bulkhead_collapse": "Extra D6 hull damage",
            }

            for ct, info in crit_counts.items():
                count = info["count"]
                desc = info["description"]
                repair = "repairable" if info["repairable"] else "PERMANENT"
                count_str = f" x{count}" if count > 1 else ""

                if ct == "fire":
                    # Fire IS cumulative in effect
                    effect = f"{count} damage per end phase"
                else:
                    effect = CRIT_EFFECTS.get(ct, "")
                    if count > 1 and info["repairable"]:
                        effect += f" (all {count} must be repaired)"

                line = f"  {desc}{count_str} [{repair}]"
                if effect:
                    line += f" → {effect}"
                lines.append(line)

            lines.append(f"")

        # Special rules
        if s.special_rules:
            lines.append("--- SPECIAL ---")
            for sr in s.special_rules:
                lines.append(f"  {sr}")

        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.config(state=tk.DISABLED)

    def _clear_info(self):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", "Click a ship to inspect")
        self.info_text.config(state=tk.DISABLED)

    def _show_all_ships(self):
        text = ""
        for p in [1, 2]:
            pname = self.gs.player1_name if p == 1 else self.gs.player2_name
            text += f"\n=== {pname} ===\n"
            for s_dict in self.gs.ships:
                if s_dict["player"] == p:
                    s = Ship.from_dict(s_dict)
                    status = ""
                    if s.is_destroyed:
                        status = " [DESTROYED]"
                    elif s.is_crippled:
                        status = " [CRIPPLED]"
                    text += f"  {s.name} ({s.ship_class}) - HP {s.hits_remaining}/{s.hits_max}{status}\n"
        messagebox.showinfo("Fleet Summary", text)

    def _show_help(self):
        help_text = (
            "=== KEYBOARD SHORTCUTS ===\n\n"
            "R  -  Ruler (point-to-point, snaps to ships)\n"
            "D  -  Distance (ship-to-ship/point)\n"
            "A  -  Arc View (click ship to show fire arcs)\n"
            "C  -  Clear all ruler lines\n"
            "Esc - Cancel drag / clear active tool\n\n"
            "=== MOVEMENT SHORTCUTS ===\n\n"
            "M  -  Min-move selected ship straight forward\n"
            "      (half speed, or exact AAF distance)\n"
            "      Click a ship first, then press M\n\n"
            "=== MOUSE ===\n\n"
            "Left click        - Select ship / use tool\n"
            "Left drag (ship)  - Drag-and-drop movement preview\n"
            "Scroll (in dialog)- Turn ship heading 5° per tick\n"
            "Right click       - Context menu (arcs, info, measure)\n\n"
            "=== GAME FLOW ===\n\n"
            "1. MOVEMENT: Issue orders, then move each ship\n"
            "2. SHOOTING: Fire weapons at targets\n"
            "3. ORDNANCE: Torpedoes/craft move and attack\n"
            "4. END:      Repairs, fire damage, blast removal\n\n"
            "=== TIPS ===\n\n"
            "Right-click a ship for 'Measure to all enemies'\n"
            "Use Auto buttons in Move dialog for quick moves\n"
            "Clockwise = starboard, Anticlockwise = port\n"
        )
        messagebox.showinfo("Help - BFG:XR Simulator", help_text)

    def _save_game(self):
        self.gs.save()
        messagebox.showinfo("Saved", f"Game saved to saves/{self.gs.game_name}/")

    def _load_game(self):
        dir_name = simpledialog.askstring("Load Game", "Enter save directory name:")
        if dir_name:
            try:
                path = os.path.join("saves", dir_name)
                self.gs = GameState.load(path)
                self.redraw()
                messagebox.showinfo("Loaded", f"Game loaded from {path}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    @staticmethod
    def _darken(hex_color, factor):
        """Darken a hex color by a factor (0-1)"""
        hex_color = hex_color.lstrip("#")
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
