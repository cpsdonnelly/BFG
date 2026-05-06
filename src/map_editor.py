"""BFG:XR Map Editor - Drag-and-drop terrain placement with mouse wheel rotation"""
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import math
import os
from typing import Optional, List
from .models import Phenomenon
from .game_state import GameState
from .board_view import BoardView, PHENOMENON_COLORS
from .map_maker import save_map, load_map, generate_random_map, BATTLEZONES
from .dice import DiceRoller


# Terrain templates for the palette
TERRAIN_PALETTE = [
    {"label": "Asteroid Field", "type": "asteroid_field", "width": 18, "height": 14, "radius": 0},
    {"label": "Dust Cloud", "type": "gas_dust_cloud", "width": 15, "height": 12, "radius": 0},
    {"label": "Small Planet", "type": "planet_small", "width": 6, "height": 6, "radius": 3},
    {"label": "Medium Planet", "type": "planet_medium", "width": 10, "height": 10, "radius": 5},
    {"label": "Large Planet", "type": "planet_large", "width": 16, "height": 16, "radius": 8},
    {"label": "Warp Rift", "type": "warp_rift", "width": 12, "height": 12, "radius": 0},
]


class MapEditor:
    """Map editor with drag-and-drop terrain placement."""

    def __init__(self, root: tk.Tk, table_width: float = 120,
                 table_height: float = 120, sunward: str = "north"):
        self.root = root
        self.root.title("BFG:XR - Map Editor")

        # Create a minimal game state for the board viewer
        self.gs = GameState(
            game_name="map_editor",
            table_width=table_width,
            table_height=table_height,
            sunward_edge=sunward,
        )

        self.next_id = 0
        self.dragging = None       # phenomenon ID being dragged
        self.drag_offset = (0, 0)  # offset from click to phenomenon center
        self.selected_id = None    # selected terrain piece
        self.placing_type = None   # terrain type being placed from palette

        # Main layout
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Board viewer (reuse existing)
        self.board = BoardView(root, self.gs)

        # Replace side panel content with editor tools
        for w in self.board.side_panel.winfo_children():
            w.destroy()

        self._build_palette()

        # Override board mouse bindings for editor mode
        self.board.canvas.bind("<Button-1>", self._on_click)
        self.board.canvas.bind("<B1-Motion>", self._on_drag)
        self.board.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.board.canvas.bind("<Button-3>", self._on_right_click)
        self.board.canvas.bind("<MouseWheel>", self._on_mousewheel)
        # Linux scroll
        self.board.canvas.bind("<Button-4>", lambda e: self._on_scroll(e, 1))
        self.board.canvas.bind("<Button-5>", lambda e: self._on_scroll(e, -1))

        self.board.redraw()

    def _build_palette(self):
        """Build terrain palette in the side panel."""
        panel = self.board.side_panel

        tk.Label(panel, text="MAP EDITOR", bg="#1a1a2e", fg="white",
                 font=("Consolas", 11, "bold")).pack(pady=2)

        tk.Label(panel, text="Click terrain, then board.\nScroll to rotate. Right-click to resize.",
                 bg="#1a1a2e", fg="#888888", font=("Consolas", 7),
                 justify=tk.LEFT).pack(padx=5)

        # Terrain palette buttons
        for template in TERRAIN_PALETTE:
            color = PHENOMENON_COLORS.get(template["type"], "#555555")
            btn = tk.Button(
                panel, text=template["label"],
                bg="#2a2a3e", fg=color,
                font=("Consolas", 8), width=22, anchor=tk.W,
                command=lambda t=template: self._select_palette(t))
            btn.pack(padx=5, pady=0)

        # Tools
        tk.Button(panel, text="Select / Move (Esc)",
                  command=self._select_mode,
                  bg="#2a2a3e", fg="white",
                  font=("Consolas", 8), width=22).pack(padx=5, pady=1)

        tk.Button(panel, text="Clear All Terrain",
                  command=self._clear_all,
                  bg="#553333", fg="white",
                  font=("Consolas", 8), width=22).pack(padx=5, pady=1)

        # Sunward edge selector
        sun_frame = tk.Frame(panel, bg="#1a1a2e")
        sun_frame.pack(padx=5, fill=tk.X, pady=2)
        tk.Label(sun_frame, text="Sun:", bg="#1a1a2e", fg="#AAAAAA",
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        self.sunward_var = tk.StringVar(value=self.gs.sunward_edge)
        for edge in ["north", "south", "east", "west"]:
            tk.Radiobutton(sun_frame, text=edge[0].upper(), variable=self.sunward_var,
                           value=edge, bg="#1a1a2e", fg="#FFDD44",
                           font=("Consolas", 7), selectcolor="#1a1a2e",
                           command=self._update_sunward).pack(side=tk.LEFT)

        # Random generation
        bz_frame = tk.Frame(panel, bg="#1a1a2e")
        bz_frame.pack(padx=5, fill=tk.X, pady=2)
        self.bz_var = tk.StringVar(value="4")
        for i in range(1, 7):
            short = BATTLEZONES[i].split()[0][:4]
            tk.Radiobutton(bz_frame, text=short, variable=self.bz_var,
                           value=str(i), bg="#1a1a2e", fg="#888888",
                           font=("Consolas", 6), selectcolor="#1a1a2e"
                           ).pack(side=tk.LEFT)

        tk.Button(panel, text="Auto-Generate",
                  command=self._auto_generate,
                  bg="#334433", fg="white",
                  font=("Consolas", 8), width=22).pack(padx=5, pady=1)

        # Save/Load
        tk.Button(panel, text="Save Map",
                  command=self._save_map,
                  bg="#333355", fg="white",
                  font=("Consolas", 8), width=22).pack(padx=5, pady=1)

        tk.Button(panel, text="Load Map",
                  command=self._load_map,
                  bg="#333355", fg="white",
                  font=("Consolas", 8), width=22).pack(padx=5, pady=1)

        tk.Button(panel, text="Done - Start Game",
                  command=self._finish,
                  bg="#336633", fg="white",
                  font=("Consolas", 9, "bold"), width=22).pack(padx=5, pady=5)

        # Status
        self.status_var = tk.StringVar(value="Select terrain from palette")
        tk.Label(panel, textvariable=self.status_var, bg="#1a1a2e",
                 fg="#AAAAAA", font=("Consolas", 7),
                 wraplength=250).pack(padx=5, pady=2)

        # Status
        self.status_var = tk.StringVar(value="Select terrain from palette")
        tk.Label(panel, textvariable=self.status_var, bg="#1a1a2e",
                 fg="#AAAAAA", font=("Consolas", 8),
                 wraplength=250).pack(padx=5, pady=5)

        # Key bindings
        self.root.bind("Escape", lambda e: self._select_mode())
        self.root.bind("Delete", lambda e: self._delete_selected())

    def _select_palette(self, template):
        """Select a terrain type from the palette for placement."""
        self.placing_type = template
        self.selected_id = None
        self.status_var.set(f"Click board to place: {template['label']}")

    def _select_mode(self):
        """Switch to select/move mode."""
        self.placing_type = None
        self.status_var.set("Click terrain to select, drag to move, scroll to rotate")

    def _update_sunward(self):
        """Update sunward edge from selector."""
        self.gs.sunward_edge = self.sunward_var.get()
        self.board.redraw()
        self.status_var.set(f"Sunward edge: {self.gs.sunward_edge}")

    def _on_click(self, event):
        cx, cy = self.board.screen_to_cm(event.x, event.y)

        if self.placing_type:
            # Place new terrain
            self._place_terrain(cx, cy, self.placing_type)
            return

        # Select mode: find terrain at click
        self.selected_id = None
        for p_dict in reversed(self.gs.phenomena):
            p = Phenomenon.from_dict(p_dict)
            if self._point_in_phenomenon(cx, cy, p):
                self.selected_id = p.id
                self.dragging = p.id
                self.drag_offset = (cx - p.x, cy - p.y)
                self.status_var.set(
                    f"Selected: {p.phenomenon_type} | Scroll to rotate | Del to remove")
                break

        self.board.redraw()
        if self.selected_id:
            self._highlight_selected()

    def _on_drag(self, event):
        if not self.dragging:
            return
        cx, cy = self.board.screen_to_cm(event.x, event.y)
        new_x = cx - self.drag_offset[0]
        new_y = cy - self.drag_offset[1]
        # Clamp to board
        new_x = max(5, min(self.gs.table_width - 5, new_x))
        new_y = max(5, min(self.gs.table_height - 5, new_y))

        # Update phenomenon position
        for i, p_dict in enumerate(self.gs.phenomena):
            if p_dict["id"] == self.dragging:
                self.gs.phenomena[i]["x"] = new_x
                self.gs.phenomena[i]["y"] = new_y
                break

        self.board.redraw()
        self._highlight_selected()

    def _on_release(self, event):
        self.dragging = None

    def _on_right_click(self, event):
        cx, cy = self.board.screen_to_cm(event.x, event.y)
        for p_dict in reversed(self.gs.phenomena):
            p = Phenomenon.from_dict(p_dict)
            if self._point_in_phenomenon(cx, cy, p):
                self.selected_id = p.id
                menu = tk.Menu(self.root, tearoff=0)
                menu.add_command(label=f"--- {p.phenomenon_type} ---", state=tk.DISABLED)
                menu.add_command(label="Delete",
                               command=lambda pid=p.id: self._delete_phenomenon(pid))
                menu.add_separator()
                menu.add_command(label="Wider (+5cm)",
                               command=lambda pid=p.id: self._resize(pid, 5, 0))
                menu.add_command(label="Narrower (-5cm)",
                               command=lambda pid=p.id: self._resize(pid, -5, 0))
                menu.add_command(label="Taller (+5cm)",
                               command=lambda pid=p.id: self._resize(pid, 0, 5))
                menu.add_command(label="Shorter (-5cm)",
                               command=lambda pid=p.id: self._resize(pid, 0, -5))
                menu.add_command(label="Bigger (+5cm both)",
                               command=lambda pid=p.id: self._resize(pid, 5, 5))
                menu.add_command(label="Smaller (-5cm both)",
                               command=lambda pid=p.id: self._resize(pid, -5, -5))
                menu.post(event.x_root, event.y_root)
                return

    def _on_mousewheel(self, event):
        """Mouse wheel to rotate selected terrain."""
        if not self.selected_id:
            return
        delta = 15 if event.delta > 0 else -15
        self._rotate(self.selected_id, delta)

    def _on_scroll(self, event, direction):
        """Linux scroll wheel handler."""
        if not self.selected_id:
            return
        self._rotate(self.selected_id, direction * 15)

    def _rotate(self, pid, degrees):
        """Rotate a terrain piece by the given degrees."""
        for i, p_dict in enumerate(self.gs.phenomena):
            if p_dict["id"] == pid:
                current = p_dict.get("rotation", 0)
                self.gs.phenomena[i]["rotation"] = (current + degrees) % 360
                break
        self.board.redraw()
        self._highlight_selected()

    def _place_terrain(self, x, y, template):
        """Place a new terrain piece at the given position."""
        pid = f"{template['type']}_{self.next_id}"
        self.next_id += 1

        p = Phenomenon(
            id=pid,
            phenomenon_type=template["type"],
            x=x, y=y,
            width=template["width"],
            height=template["height"],
            radius=template["radius"],
        )
        self.gs.add_phenomenon(p)
        self.selected_id = pid
        self.status_var.set(f"Placed {template['label']} | Click to place another or Esc for select mode")
        self.board.redraw()
        self._highlight_selected()

    def _delete_phenomenon(self, pid):
        self.gs.phenomena = [p for p in self.gs.phenomena if p["id"] != pid]
        if self.selected_id == pid:
            self.selected_id = None
        self.board.redraw()
        self.status_var.set("Terrain deleted")

    def _delete_selected(self):
        if self.selected_id:
            self._delete_phenomenon(self.selected_id)

    def _resize(self, pid, dw, dh):
        for i, p_dict in enumerate(self.gs.phenomena):
            if p_dict["id"] == pid:
                new_w = max(4, p_dict.get("width", 10) + dw)
                new_h = max(4, p_dict.get("height", 10) + dh)
                self.gs.phenomena[i]["width"] = new_w
                self.gs.phenomena[i]["height"] = new_h
                if "planet" in p_dict.get("phenomenon_type", ""):
                    self.gs.phenomena[i]["radius"] = new_w / 2
                break
        self.board.redraw()
        if self.selected_id:
            self._highlight_selected()

    def _highlight_selected(self):
        """Draw a highlight border around the selected terrain."""
        if not self.selected_id:
            return
        for p_dict in self.gs.phenomena:
            if p_dict["id"] == self.selected_id:
                p = Phenomenon.from_dict(p_dict)
                if "planet" in p.phenomenon_type and p.radius > 0:
                    sx, sy = self.board.cm_to_screen(p.x, p.y)
                    r = self.board.cm_to_pixels(p.radius) + 3
                    self.board.canvas.create_oval(
                        sx - r, sy - r, sx + r, sy + r,
                        outline="#FFFF00", width=2, dash=(4, 3))
                else:
                    sx1, sy1 = self.board.cm_to_screen(
                        p.x - p.width/2, p.y + p.height/2)
                    sx2, sy2 = self.board.cm_to_screen(
                        p.x + p.width/2, p.y - p.height/2)
                    self.board.canvas.create_rectangle(
                        sx1, sy1, sx2, sy2,
                        outline="#FFFF00", width=2, dash=(4, 3))
                break

    def _point_in_phenomenon(self, cx, cy, p: Phenomenon) -> bool:
        """Check if a point is inside a phenomenon's bounds."""
        if "planet" in p.phenomenon_type and p.radius > 0:
            dist = math.sqrt((cx - p.x)**2 + (cy - p.y)**2)
            return dist <= p.radius
        else:
            return (abs(cx - p.x) <= p.width / 2 and
                    abs(cy - p.y) <= p.height / 2)

    def _clear_all(self):
        if messagebox.askyesno("Clear All", "Remove all terrain?"):
            self.gs.phenomena.clear()
            self.selected_id = None
            self.board.redraw()
            self.status_var.set("All terrain cleared")

    def _auto_generate(self):
        if self.gs.phenomena and not messagebox.askyesno(
                "Replace Terrain", "This will replace existing terrain. Continue?"):
            return
        self.gs.phenomena.clear()
        dice = DiceRoller(mode="auto")
        bz = int(self.bz_var.get())

        # Randomize sunward edge
        import random as _rng
        self.gs.sunward_edge = _rng.choice(["north", "south", "east", "west"])
        self.sunward_var.set(self.gs.sunward_edge)

        phenomena = generate_random_map(
            self.gs.table_width, self.gs.table_height, bz, dice)
        for p in phenomena:
            self.gs.add_phenomenon(Phenomenon.from_dict(p))
        self.next_id = len(phenomena)
        self.board.redraw()
        self.status_var.set(
            f"Generated {len(phenomena)} features for {BATTLEZONES[bz]}")

    def _save_map(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialdir="saves",
            title="Save Map")
        if filepath:
            save_map(self.gs.phenomena, self.gs.table_width,
                    self.gs.table_height, self.gs.sunward_edge, filepath)
            self.status_var.set(f"Map saved to {os.path.basename(filepath)}")

    def _load_map(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            initialdir="saves",
            title="Load Map")
        if filepath:
            data = load_map(filepath)
            self.gs.phenomena.clear()
            self.gs.table_width = data["table_width"]
            self.gs.table_height = data["table_height"]
            self.gs.sunward_edge = data.get("sunward_edge", "north")
            for p in data["phenomena"]:
                self.gs.add_phenomenon(Phenomenon.from_dict(p))
            self.next_id = len(data["phenomena"])
            self.board.redraw()
            self.status_var.set(
                f"Loaded {len(data['phenomena'])} features from {os.path.basename(filepath)}")

    def _finish(self):
        """Close map editor and return phenomena for use in game."""
        self.root.quit()

    def get_phenomena(self) -> List[dict]:
        """Get the current phenomena list."""
        return list(self.gs.phenomena)

    def get_map_settings(self) -> dict:
        """Get map dimensions and sunward."""
        return {
            "table_width": self.gs.table_width,
            "table_height": self.gs.table_height,
            "sunward_edge": self.gs.sunward_edge,
        }
