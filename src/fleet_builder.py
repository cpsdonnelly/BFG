"""BFG:XR Fleet Builder — Tkinter UI for constructing and saving fleet lists."""
import json
import os
import uuid
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from typing import List, Dict, Optional, Callable

from .ship_catalog import (
    ShipClassEntry, UpgradeEntry,
    list_factions, get_faction_ships, get_ship_class,
    get_upgrades_for_ship, faction_display_name,
)


_ADMIRAL_THRESHOLDS = [
    (1500, "Full Admiral / Kor'O"),
    (1000, "Vice Admiral / Kor'Vre"),
    (500,  "Rear Admiral / Kor'El"),
    (0,    "No Admiral"),
]

_FONT_BODY  = ("Consolas", 9)
_FONT_BOLD  = ("Consolas", 9,  "bold")
_FONT_TITLE = ("Consolas", 11, "bold")
_BG         = "#0d0d1a"
_FG         = "#CCCCCC"
_ACCENT     = "#FFAA00"
_SEL_BG     = "#1a1a2e"


# ---------------------------------------------------------------------------
# Ship upgrade/name editor dialog
# ---------------------------------------------------------------------------

class _ShipEditDialog:
    def __init__(self, root: tk.Tk, entry: ShipClassEntry,
                 current_name: str, current_upgrades: List[str],
                 on_save: Callable):
        self._on_save = on_save
        self._entry = entry

        self.dialog = tk.Toplevel(root)
        self.dialog.title(f"Edit — {entry.ship_class}")
        self.dialog.geometry("480x520")
        self.dialog.configure(bg=_BG)
        self.dialog.transient(root)
        self.dialog.grab_set()

        tk.Label(self.dialog, text=entry.ship_class, font=_FONT_TITLE,
                 bg=_BG, fg=_ACCENT).pack(pady=(10, 2))
        tk.Label(self.dialog, text=f"{entry.ship_type.capitalize()}  •  {entry.points_cost} pts base",
                 font=_FONT_BODY, bg=_BG, fg=_FG).pack()

        # Custom name
        name_frame = tk.Frame(self.dialog, bg=_BG)
        name_frame.pack(fill=tk.X, padx=15, pady=(10, 2))
        tk.Label(name_frame, text="Ship name:", font=_FONT_BODY,
                 bg=_BG, fg=_FG, width=12, anchor="w").pack(side=tk.LEFT)
        self._name_var = tk.StringVar(value=current_name)
        tk.Entry(name_frame, textvariable=self._name_var,
                 font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                 insertbackground=_FG, width=28).pack(side=tk.LEFT, padx=5)

        # Upgrades
        tk.Label(self.dialog, text="Available upgrades:", font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(anchor="w", padx=15, pady=(10, 2))

        upgrade_frame = tk.Frame(self.dialog, bg=_BG)
        upgrade_frame.pack(fill=tk.BOTH, expand=True, padx=15)

        self._upgrade_vars: Dict[str, tk.BooleanVar] = {}
        upgrades = get_upgrades_for_ship(entry)
        if not upgrades:
            tk.Label(upgrade_frame, text="(no upgrades available)",
                     font=_FONT_BODY, bg=_BG, fg="#666666").pack(anchor="w")
        for u in upgrades:
            var = tk.BooleanVar(value=(u.name in current_upgrades))
            self._upgrade_vars[u.name] = var
            row = tk.Frame(upgrade_frame, bg=_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Checkbutton(row, variable=var, bg=_BG, fg=_FG,
                           selectcolor=_SEL_BG,
                           activebackground=_BG,
                           command=self._refresh_total).pack(side=tk.LEFT)
            tk.Label(row, text=f"{u.name}  (+{u.points_cost} pts)",
                     font=_FONT_BODY, bg=_BG, fg=_FG, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=u.description, font=("Consolas", 8),
                     bg=_BG, fg="#888888", wraplength=340, justify="left",
                     anchor="w").pack(side=tk.LEFT, padx=8)

        # Total cost display
        self._total_var = tk.StringVar()
        tk.Label(self.dialog, textvariable=self._total_var, font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(pady=5)
        self._refresh_total()

        # Buttons
        btn_frame = tk.Frame(self.dialog, bg=_BG)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Save", font=_FONT_BOLD,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=12,
                  command=self._save).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Cancel", font=_FONT_BODY,
                  bg="#221111", fg=_FG, relief=tk.FLAT, padx=12,
                  command=self.dialog.destroy).pack(side=tk.LEFT, padx=6)

        root.wait_window(self.dialog)

    def _refresh_total(self):
        chosen = [name for name, v in self._upgrade_vars.items() if v.get()]
        total = self._entry.points_cost
        upgrade_map = {u.name: u for u in get_upgrades_for_ship(self._entry)}
        for name in chosen:
            if name in upgrade_map:
                total += upgrade_map[name].points_cost
        self._total_var.set(f"Total cost: {total} pts")

    def _save(self):
        chosen = [name for name, v in self._upgrade_vars.items() if v.get()]
        self._on_save(self._name_var.get().strip() or self._entry.ship_class,
                      chosen)
        self.dialog.destroy()


# ---------------------------------------------------------------------------
# Fleet entry (in-memory row)
# ---------------------------------------------------------------------------

def _make_fleet_row(entry: ShipClassEntry, custom_name: str = "",
                    upgrades: Optional[List[str]] = None,
                    is_flagship: bool = False,
                    squadron_id: str = "") -> dict:
    upgrade_map = {u.name: u for u in get_upgrades_for_ship(entry)}
    upgrade_cost = sum(upgrade_map[u].points_cost
                       for u in (upgrades or []) if u in upgrade_map)
    return {
        "entry":       entry,
        "custom_name": custom_name or entry.ship_class,
        "upgrades":    list(upgrades or []),
        "is_flagship": is_flagship,
        "squadron_id": squadron_id,
        "points":      entry.points_cost + upgrade_cost,
    }


# ---------------------------------------------------------------------------
# Main fleet builder window
# ---------------------------------------------------------------------------

class FleetBuilderWindow:
    """
    Top-level Tkinter window for building a fleet list.
    Call FleetBuilderWindow.open(root, on_save_callback) to launch.
    """

    def __init__(self, root: tk.Tk, on_save: Optional[Callable] = None,
                 load_path: Optional[str] = None):
        self._root = root
        self._on_save = on_save
        self._fleet: List[dict] = []       # list of fleet rows
        self._faction: Optional[str] = None
        self._points_limit = 1000
        self._fleet_name = "My Fleet"

        self.win = tk.Toplevel(root)
        self.win.title("BFG:XR Fleet Builder")
        self.win.geometry("1000x680")
        self.win.configure(bg=_BG)
        self.win.transient(root)

        self._build_ui()

        if load_path:
            self._load_fleet_from_path(load_path)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top bar ──
        top = tk.Frame(self.win, bg=_BG)
        top.pack(fill=tk.X, padx=10, pady=6)

        tk.Label(top, text="FLEET BUILDER", font=_FONT_TITLE,
                 bg=_BG, fg=_ACCENT).pack(side=tk.LEFT)

        # Fleet name
        tk.Label(top, text="Fleet name:", font=_FONT_BODY,
                 bg=_BG, fg=_FG).pack(side=tk.LEFT, padx=(20, 4))
        self._fleet_name_var = tk.StringVar(value=self._fleet_name)
        tk.Entry(top, textvariable=self._fleet_name_var,
                 font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                 insertbackground=_FG, width=22).pack(side=tk.LEFT)

        # Points limit
        tk.Label(top, text="Points limit:", font=_FONT_BODY,
                 bg=_BG, fg=_FG).pack(side=tk.LEFT, padx=(14, 4))
        self._pts_limit_var = tk.StringVar(value=str(self._points_limit))
        tk.Entry(top, textvariable=self._pts_limit_var,
                 font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                 insertbackground=_FG, width=7).pack(side=tk.LEFT)
        self._pts_limit_var.trace_add("write", lambda *_: self._refresh_totals())

        # ── Faction + action buttons ──
        bar = tk.Frame(self.win, bg=_BG)
        bar.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(bar, text="Faction:", font=_FONT_BODY, bg=_BG, fg=_FG).pack(side=tk.LEFT)
        self._faction_var = tk.StringVar(value="")
        factions = list_factions()
        faction_names = [faction_display_name(f) for f in factions]
        self._faction_ids = factions
        self._faction_combo = ttk.Combobox(bar, textvariable=self._faction_var,
                                           values=faction_names, state="readonly",
                                           font=_FONT_BODY, width=24)
        self._faction_combo.pack(side=tk.LEFT, padx=5)
        self._faction_combo.bind("<<ComboboxSelected>>", self._on_faction_selected)

        for text, cmd in [
            ("Load Fleet", self._load_fleet),
            ("Save Fleet", self._save_fleet),
            ("Validate",   self._validate_and_report),
        ]:
            tk.Button(bar, text=text, font=_FONT_BODY,
                      bg=_SEL_BG, fg=_FG, relief=tk.FLAT, padx=8,
                      command=cmd).pack(side=tk.RIGHT, padx=3)

        # ── Main panes ──
        pane = tk.PanedWindow(self.win, orient=tk.HORIZONTAL,
                              bg=_BG, sashwidth=4, sashrelief=tk.FLAT)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left: ship browser
        left = tk.Frame(pane, bg=_BG)
        pane.add(left, minsize=260, width=320)
        tk.Label(left, text="Ship Catalog", font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(anchor="w", pady=(4, 2))
        self._catalog_list = tk.Listbox(left, font=_FONT_BODY,
                                        bg=_SEL_BG, fg=_FG,
                                        selectbackground="#334466",
                                        activestyle="none", height=22)
        self._catalog_list.pack(fill=tk.BOTH, expand=True)
        self._catalog_scroll = tk.Scrollbar(left, command=self._catalog_list.yview)
        self._catalog_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._catalog_list.config(yscrollcommand=self._catalog_scroll.set)
        self._catalog_entries: List[ShipClassEntry] = []

        tk.Button(left, text="Add to Fleet ▶", font=_FONT_BODY,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=8,
                  command=self._add_selected).pack(pady=4)

        # Right: fleet list
        right = tk.Frame(pane, bg=_BG)
        pane.add(right, minsize=340)
        tk.Label(right, text="Fleet List", font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(anchor="w", pady=(4, 2))
        self._fleet_list = tk.Listbox(right, font=_FONT_BODY,
                                      bg=_SEL_BG, fg=_FG,
                                      selectbackground="#334466",
                                      activestyle="none", height=22)
        self._fleet_list.pack(fill=tk.BOTH, expand=True)
        self._fleet_scroll = tk.Scrollbar(right, command=self._fleet_list.yview)
        self._fleet_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._fleet_list.config(yscrollcommand=self._fleet_scroll.set)
        self._fleet_list.bind("<Double-Button-1>", lambda _: self._edit_selected())

        btn_row = tk.Frame(right, bg=_BG)
        btn_row.pack(fill=tk.X, pady=4)
        for text, cmd in [
            ("Edit",     self._edit_selected),
            ("Flagship", self._toggle_flagship),
            ("Remove",   self._remove_selected),
        ]:
            tk.Button(btn_row, text=text, font=_FONT_BODY,
                      bg=_SEL_BG, fg=_FG, relief=tk.FLAT, padx=8,
                      command=cmd).pack(side=tk.LEFT, padx=3)

        # Status bar
        self._status_var = tk.StringVar(value="Select a faction to begin.")
        self._pts_var = tk.StringVar(value="")
        status_bar = tk.Frame(self.win, bg="#111122")
        status_bar.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(status_bar, textvariable=self._pts_var,
                 font=_FONT_BOLD, bg="#111122", fg=_ACCENT).pack(side=tk.RIGHT, padx=8)
        tk.Label(status_bar, textvariable=self._status_var,
                 font=_FONT_BODY, bg="#111122", fg=_FG).pack(side=tk.LEFT, padx=4)

    # ── Faction loading ───────────────────────────────────────────────────────

    def _on_faction_selected(self, _event=None):
        idx = self._faction_combo.current()
        if idx < 0:
            return
        faction_id = self._faction_ids[idx]
        if self._faction and self._faction != faction_id and self._fleet:
            if not messagebox.askyesno("Change Faction",
                                       "Changing faction will clear the fleet list. Continue?"):
                return
            self._fleet.clear()
            self._refresh_fleet_list()
        self._faction = faction_id
        self._populate_catalog(faction_id)
        self._status_var.set(f"Faction: {faction_display_name(faction_id)}")

    def _populate_catalog(self, faction: str):
        self._catalog_list.delete(0, tk.END)
        self._catalog_entries = get_faction_ships(faction)
        for e in self._catalog_entries:
            self._catalog_list.insert(
                tk.END,
                f"[{e.ship_type[:3].upper()}] {e.ship_class}  {e.points_cost}pts")

    # ── Fleet manipulation ────────────────────────────────────────────────────

    def _add_selected(self):
        sel = self._catalog_list.curselection()
        if not sel:
            self._status_var.set("Select a ship class first.")
            return
        entry = self._catalog_entries[sel[0]]
        row = _make_fleet_row(entry)
        self._fleet.append(row)
        self._refresh_fleet_list()
        self._status_var.set(f"Added {entry.ship_class}.")

    def _edit_selected(self):
        sel = self._fleet_list.curselection()
        if not sel:
            return
        idx = sel[0]
        row = self._fleet[idx]

        def _save(name, upgrades):
            row["custom_name"] = name
            row["upgrades"] = upgrades
            upgrade_map = {u.name: u for u in get_upgrades_for_ship(row["entry"])}
            upgrade_cost = sum(upgrade_map[u].points_cost
                               for u in upgrades if u in upgrade_map)
            row["points"] = row["entry"].points_cost + upgrade_cost
            self._refresh_fleet_list()

        _ShipEditDialog(self.win, row["entry"], row["custom_name"],
                        row["upgrades"], on_save=_save)

    def _toggle_flagship(self):
        sel = self._fleet_list.curselection()
        if not sel:
            return
        idx = sel[0]
        new_val = not self._fleet[idx]["is_flagship"]
        # Clear flagship flag on all others if setting one
        if new_val:
            for r in self._fleet:
                r["is_flagship"] = False
        self._fleet[idx]["is_flagship"] = new_val
        self._refresh_fleet_list()

    def _remove_selected(self):
        sel = self._fleet_list.curselection()
        if not sel:
            return
        self._fleet.pop(sel[0])
        self._refresh_fleet_list()

    def _refresh_fleet_list(self):
        self._fleet_list.delete(0, tk.END)
        for row in self._fleet:
            flagship = " ★" if row["is_flagship"] else ""
            upgrades = f" [{', '.join(row['upgrades'])}]" if row["upgrades"] else ""
            self._fleet_list.insert(
                tk.END,
                f"{row['custom_name']}{flagship}  {row['points']}pts{upgrades}")
        self._refresh_totals()

    def _refresh_totals(self):
        total = sum(r["points"] for r in self._fleet)
        try:
            limit = int(self._pts_limit_var.get())
        except ValueError:
            limit = 0
        color = _ACCENT if total <= limit else "#FF4444"
        self._pts_var.set(f"Total: {total} / {limit} pts")
        self._pts_var  # accessed only for side-effect; color applied via label ref
        # Re-color the pts label
        for widget in self.win.winfo_children():
            pass  # pts label is in status_bar — update directly
        self.win.after_idle(lambda: self._pts_label_color(color, total, limit))

    def _pts_label_color(self, color, total, limit):
        self._pts_var.set(f"Total: {total} / {limit} pts")

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_fleet(self) -> tuple:
        errors: List[str] = []
        if not self._fleet:
            errors.append("Fleet is empty.")
            return False, errors

        total = sum(r["points"] for r in self._fleet)
        try:
            limit = int(self._pts_limit_var.get())
        except ValueError:
            limit = 0
            errors.append("Invalid points limit.")

        if total > limit:
            errors.append(f"Fleet exceeds points limit: {total} > {limit} pts.")

        flagship_count = sum(1 for r in self._fleet if r["is_flagship"])
        if flagship_count > 1:
            errors.append("Fleet has more than one flagship.")

        # Check escort squadrons: each squadron_id group must be 2–6 escorts of same class
        squadrons: Dict[str, List[dict]] = {}
        for r in self._fleet:
            sid = r.get("squadron_id", "")
            if sid:
                squadrons.setdefault(sid, []).append(r)
        for sid, members in squadrons.items():
            if len(members) < 2 or len(members) > 6:
                errors.append(f"Squadron {sid}: must have 2–6 ships (has {len(members)}).")
            classes = {m["entry"].ship_class for m in members}
            if len(classes) > 1:
                errors.append(f"Squadron {sid}: ships must all be the same class.")

        return len(errors) == 0, errors

    def _validate_and_report(self):
        ok, errors = self._validate_fleet()
        if ok:
            messagebox.showinfo("Fleet Valid", "Fleet list is valid.")
        else:
            messagebox.showwarning("Validation Errors", "\n".join(errors))

    # ── Save / Load ───────────────────────────────────────────────────────────

    def _save_fleet(self):
        ok, errors = self._validate_fleet()
        if not ok:
            if not messagebox.askyesno("Save with Errors",
                                       "Fleet has validation errors:\n" +
                                       "\n".join(errors) + "\n\nSave anyway?"):
                return

        path = filedialog.asksaveasfilename(
            title="Save Fleet",
            defaultextension=".json",
            filetypes=[("Fleet JSON", "*.json"), ("All files", "*.*")],
            initialdir=os.path.join(os.getcwd(), "data", "fleets"),
        )
        if not path:
            return

        try:
            limit = int(self._pts_limit_var.get())
        except ValueError:
            limit = 0

        data = {
            "fleet_name":   self._fleet_name_var.get().strip() or "My Fleet",
            "faction":      self._faction or "",
            "description":  "",
            "points_limit": limit,
            "total_points": sum(r["points"] for r in self._fleet),
            "ships": [],
        }

        for row in self._fleet:
            entry = row["entry"]
            ship_dict = entry.to_ship_dict(
                name=row["custom_name"],
                player=1,
                upgrades=row["upgrades"],
                is_flagship=row["is_flagship"],
            )
            # Strip runtime-only keys; keep only fleet-storable fields
            storable = {k: v for k, v in ship_dict.items()
                        if k not in ("id", "player", "x", "y", "heading")}
            storable["squadron_id"] = row.get("squadron_id", "")
            data["ships"].append(storable)

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self._status_var.set(f"Saved to {os.path.basename(path)}")
        if self._on_save:
            self._on_save(data)

    def _load_fleet(self):
        path = filedialog.askopenfilename(
            title="Load Fleet",
            filetypes=[("Fleet JSON", "*.json"), ("All files", "*.*")],
            initialdir=os.path.join(os.getcwd(), "data", "fleets"),
        )
        if not path:
            return
        self._load_fleet_from_path(path)

    def _load_fleet_from_path(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Load Error", str(exc))
            return

        faction = data.get("faction", "")
        # Select faction in combo
        if faction in self._faction_ids:
            idx = self._faction_ids.index(faction)
            self._faction_combo.current(idx)
            self._faction = faction
            self._populate_catalog(faction)
        else:
            self._status_var.set(f"Warning: unknown faction '{faction}'.")

        self._fleet_name_var.set(data.get("fleet_name", "My Fleet"))
        self._pts_limit_var.set(str(data.get("points_limit", 1000)))
        self._fleet.clear()

        for s in data.get("ships", []):
            sc = s.get("ship_class", "")
            entry = get_ship_class(faction, sc)
            if not entry:
                self._status_var.set(f"Warning: unknown ship class '{sc}' — skipped.")
                continue
            row = _make_fleet_row(
                entry,
                custom_name=s.get("name", sc),
                upgrades=s.get("upgrades", []),
                is_flagship=s.get("is_flagship", False),
                squadron_id=s.get("squadron_id", ""),
            )
            self._fleet.append(row)

        self._refresh_fleet_list()
        self._status_var.set(f"Loaded {os.path.basename(path)}")

    # ── Public factory ────────────────────────────────────────────────────────

    @classmethod
    def open(cls, root: tk.Tk, on_save: Optional[Callable] = None,
             load_path: Optional[str] = None) -> "FleetBuilderWindow":
        return cls(root, on_save=on_save, load_path=load_path)


# ---------------------------------------------------------------------------
# fleet_list_to_ships: convert saved fleet data → list of Ship dicts for game
# ---------------------------------------------------------------------------

def fleet_list_to_ships(fleet_data: dict, player: int) -> List[dict]:
    """
    Convert a saved fleet dict into Ship-compatible dicts ready for game state.
    Ships without catalog entries (loaded directly from a hand-crafted fleet
    JSON) are passed through as-is so hand-authored fleets still work.
    """
    faction = fleet_data.get("faction", "")
    result: List[dict] = []

    for i, raw in enumerate(fleet_data.get("ships", [])):
        sc = raw.get("ship_class", "")
        entry = get_ship_class(faction, sc) if faction else None

        if entry:
            ship_dict = entry.to_ship_dict(
                name=raw.get("name", sc),
                player=player,
                ship_id=raw.get("id") or str(uuid.uuid4())[:8],
                upgrades=raw.get("upgrades", []),
                is_flagship=raw.get("is_flagship", False),
                admiral_type=raw.get("admiral_type", ""),
                rerolls_remaining=raw.get("rerolls_remaining", 0),
                spawn_x=raw.get("spawn_x", raw.get("x", 10.0 + i * 5)),
                spawn_y=raw.get("spawn_y", raw.get("y", 20.0)),
                spawn_heading=raw.get("spawn_heading", raw.get("heading", 90.0)),
            )
        else:
            # Fall through: use raw dict directly (hand-crafted fleet file)
            ship_dict = dict(raw)
            ship_dict["player"] = player
            ship_dict.setdefault("id", str(uuid.uuid4())[:8])
            for spawn_key, real_key in (("spawn_x", "x"), ("spawn_y", "y"),
                                        ("spawn_heading", "heading")):
                if spawn_key in ship_dict:
                    ship_dict[real_key] = ship_dict.pop(spawn_key)

        result.append(ship_dict)

    return result
