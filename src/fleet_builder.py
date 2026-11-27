"""BFG:XR Fleet Builder — Tkinter UI for constructing and saving fleet lists."""
import json
import os
import uuid
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from typing import List, Dict, Optional, Callable

from . import homebrew_catalog as _hb
from .ship_catalog import (
    ShipClassEntry, list_factions,
    get_faction_ships, get_ship_class, get_upgrades_for_ship,
    faction_display_name,
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

_OPTION_GROUPS = ["Refits and weapon options", "Torpedo types",
                  "Fleet commander and re-rolls", "Other options"]
_COMMANDER_WORDS = ("Admiral", "Commander", "Captain", "Lord", "re-roll", "Master",
                    "Warmaster", "Kor'", "Boss", "Archmagos", "Magos", "Champion",
                    "Inquisitor", "Daemonhunter", "Kaptin", "Warboss", "Big Mek",
                    "Abaddon", "Rath", "Mesme", "Overlord", "Nemesor", "Obelisk",
                    "Monolith", "Sepulchre", "honour guard", "Chapter tactic", "Nob")


def _option_group(name: str) -> str:
    """The heading an option is listed under in the Edit dialog (display only)."""
    if name.startswith("Torpedoes") or "torpedo" in name.lower():
        return "Torpedo types"
    if any(w in name for w in _COMMANDER_WORDS):
        return "Fleet commander and re-rolls"
    if name.startswith("Refit") or "refit" in name.lower() or "Variant" in name:
        return "Refits and weapon options"
    return "Other options"


class _ShipEditDialog:
    def __init__(self, root: tk.Tk, entry: ShipClassEntry,
                 current_name: str, current_upgrades: List[str],
                 on_save: Callable, current_damage: Optional[dict] = None,
                 base_cost: Optional[int] = None, list_keys: Optional[List[str]] = None):
        self._on_save = on_save
        self._entry = entry
        self._base_cost = entry.points_cost if base_cost is None else base_cost
        self._list_keys = list(list_keys or [])
        dmg = current_damage or {}

        self.dialog = tk.Toplevel(root)
        self.dialog.title(f"Edit — {entry.ship_class}")
        from .tk_scroll import scroll_body, fit_height
        self.dialog.geometry(f"640x{fit_height(self.dialog, 760)}")
        self.dialog.minsize(480, 360)
        self.dialog.configure(bg=_BG)
        self.dialog.transient(root)
        self.dialog.grab_set()

        # Save / Cancel and the total stay at the bottom, outside the scrolling
        # part, so they are always on screen (To do 32)
        btn_frame = tk.Frame(self.dialog, bg=_BG)
        btn_frame.pack(side=tk.BOTTOM, pady=8)
        tk.Button(btn_frame, text="Save", font=_FONT_BOLD,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=12,
                  command=self._save).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Cancel", font=_FONT_BODY,
                  bg="#221111", fg=_FG, relief=tk.FLAT, padx=12,
                  command=self.dialog.destroy).pack(side=tk.LEFT, padx=6)
        self._total_var = tk.StringVar()
        tk.Label(self.dialog, textvariable=self._total_var, font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(side=tk.BOTTOM, pady=(5, 2))

        tk.Label(self.dialog, text=entry.ship_class, font=_FONT_TITLE,
                 bg=_BG, fg=_ACCENT).pack(pady=(10, 2))
        tk.Label(self.dialog, text=f"{entry.ship_type.capitalize()}  •  {self._base_cost} pts base",
                 font=_FONT_BODY, bg=_BG, fg=_FG).pack()

        body = scroll_body(self.dialog, bg=_BG)
        name_frame = tk.Frame(body, bg=_BG)
        name_frame.pack(fill=tk.X, padx=15, pady=(10, 2))
        tk.Label(name_frame, text="Ship name:", font=_FONT_BODY,
                 bg=_BG, fg=_FG, width=12, anchor="w").pack(side=tk.LEFT)
        self._name_var = tk.StringVar(value=current_name)
        tk.Entry(name_frame, textvariable=self._name_var,
                 font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                 insertbackground=_FG, width=28).pack(side=tk.LEFT, padx=5)

        # Upgrades
        tk.Label(body, text="Options, refits and commanders:", font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(anchor="w", padx=15, pady=(10, 2))

        upgrade_frame = tk.Frame(body, bg=_BG)
        upgrade_frame.pack(fill=tk.X, padx=15)

        self._upgrade_vars: Dict[str, tk.BooleanVar] = {}
        from .fleet_lists import option_allowed
        upgrades = [u for u in get_upgrades_for_ship(entry)
                    if option_allowed(u.name, self._list_keys) or u.name in current_upgrades]
        if not upgrades:
            tk.Label(upgrade_frame, text="(no upgrades available)",
                     font=_FONT_BODY, bg=_BG, fg="#666666").pack(anchor="w")
        last_group = None
        for u in sorted(upgrades, key=lambda u: _OPTION_GROUPS.index(_option_group(u.name))):
            group = _option_group(u.name)
            if group != last_group:
                tk.Label(upgrade_frame, text=group, font=_FONT_BOLD, bg=_BG,
                         fg="#AAAAFF").pack(anchor="w", pady=(6, 0))
                last_group = group
            var = tk.BooleanVar(value=(u.name in current_upgrades))
            self._upgrade_vars[u.name] = var
            urow = tk.Frame(upgrade_frame, bg=_BG)
            urow.pack(fill=tk.X, pady=1)
            tk.Checkbutton(urow, variable=var, bg=_BG, fg=_FG,
                           selectcolor=_SEL_BG,
                           activebackground=_BG,
                           command=self._refresh_total).pack(side=tk.LEFT)
            tk.Label(urow, text=f"{u.name}  ({u.points_cost:+d} pts)",
                     font=_FONT_BODY, bg=_BG, fg=_FG, anchor="w").pack(side=tk.LEFT)
            tk.Label(urow, text=u.description, font=("Consolas", 8),
                     bg=_BG, fg="#888888", wraplength=300, justify="left",
                     anchor="w").pack(side=tk.LEFT, padx=8)

        self._refresh_total()

        # ── Damage / Scenario State ──────────────────────────────────────────
        dmg_lf = tk.LabelFrame(body, text="Damage / Scenario State",
                                font=_FONT_BOLD, bg=_BG, fg=_ACCENT,
                                padx=8, pady=4)
        dmg_lf.pack(fill=tk.X, padx=15, pady=(6, 2))

        hits_max = getattr(entry, "hits_max", 8)

        # Hits remaining
        hits_row = tk.Frame(dmg_lf, bg=_BG)
        hits_row.pack(fill=tk.X, pady=2)
        tk.Label(hits_row, text="Hits remaining:", font=_FONT_BODY,
                 bg=_BG, fg=_FG, width=16, anchor="w").pack(side=tk.LEFT)
        self._hits_var = tk.StringVar(
            value=str(dmg.get("hits_remaining", hits_max)))
        tk.Spinbox(hits_row, from_=0, to=hits_max,
                   textvariable=self._hits_var,
                   font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                   buttonbackground=_SEL_BG, width=5).pack(side=tk.LEFT)
        tk.Label(hits_row, text=f"/ {hits_max} max",
                 font=_FONT_BODY, bg=_BG, fg="#888888").pack(side=tk.LEFT, padx=6)

        # Ordnance loaded
        ord_row = tk.Frame(dmg_lf, bg=_BG)
        ord_row.pack(fill=tk.X, pady=2)
        self._torps_var = tk.BooleanVar(value=dmg.get("ordnance_loaded_torps", True))
        self._craft_var = tk.BooleanVar(value=dmg.get("ordnance_loaded_craft", True))
        tk.Checkbutton(ord_row, text="Torpedoes loaded",
                       variable=self._torps_var,
                       bg=_BG, fg=_FG, selectcolor=_SEL_BG,
                       activebackground=_BG,
                       font=_FONT_BODY).pack(side=tk.LEFT)
        tk.Checkbutton(ord_row, text="Attack craft loaded",
                       variable=self._craft_var,
                       bg=_BG, fg=_FG, selectcolor=_SEL_BG,
                       activebackground=_BG,
                       font=_FONT_BODY).pack(side=tk.LEFT, padx=10)

        # Critical damage list
        tk.Label(dmg_lf, text="Critical damage effects:",
                 font=_FONT_BODY, bg=_BG, fg=_FG).pack(anchor="w", pady=(4, 1))

        crit_frame = tk.Frame(dmg_lf, bg=_BG)
        crit_frame.pack(fill=tk.X)

        self._crit_listbox = tk.Listbox(
            crit_frame, bg=_SEL_BG, fg=_FG,
            font=("Consolas", 8), height=4, selectbackground="#334466",
            selectforeground=_FG, relief=tk.FLAT, borderwidth=1)
        self._crit_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        existing_crits = dmg.get("critical_damage", [])
        for c in existing_crits:
            label = c.get("effect", c) if isinstance(c, dict) else str(c)
            self._crit_listbox.insert(tk.END, label)
        self._crit_raw: List = list(existing_crits)

        crit_btn_col = tk.Frame(crit_frame, bg=_BG)
        crit_btn_col.pack(side=tk.LEFT, padx=4)
        tk.Button(crit_btn_col, text="Remove", font=("Consolas", 8),
                  bg="#331111", fg=_FG, relief=tk.FLAT,
                  command=self._remove_crit).pack(pady=1)
        tk.Button(crit_btn_col, text="Clear all", font=("Consolas", 8),
                  bg="#221111", fg=_FG, relief=tk.FLAT,
                  command=self._clear_crits).pack(pady=1)

        add_row = tk.Frame(dmg_lf, bg=_BG)
        add_row.pack(fill=tk.X, pady=(3, 0))
        self._new_crit_var = tk.StringVar()
        tk.Entry(add_row, textvariable=self._new_crit_var,
                 font=("Consolas", 8), bg=_SEL_BG, fg=_FG,
                 insertbackground=_FG, width=26).pack(side=tk.LEFT)
        tk.Button(add_row, text="+ Add crit", font=("Consolas", 8),
                  bg="#223322", fg=_FG, relief=tk.FLAT,
                  command=self._add_crit).pack(side=tk.LEFT, padx=4)


        root.wait_window(self.dialog)

    def _remove_crit(self):
        sel = self._crit_listbox.curselection()
        if sel:
            idx = sel[0]
            self._crit_listbox.delete(idx)
            self._crit_raw.pop(idx)

    def _clear_crits(self):
        self._crit_listbox.delete(0, tk.END)
        self._crit_raw.clear()

    def _add_crit(self):
        text = self._new_crit_var.get().strip()
        if text:
            self._crit_listbox.insert(tk.END, text)
            self._crit_raw.append({"effect": text})
            self._new_crit_var.set("")

    def _refresh_total(self):
        chosen = [name for name, v in self._upgrade_vars.items() if v.get()]
        total = self._base_cost
        upgrade_map = {u.name: u for u in get_upgrades_for_ship(self._entry)}
        for name in chosen:
            if name in upgrade_map:
                total += upgrade_map[name].points_cost
        self._total_var.set(f"Total cost: {total} pts")

    def _save(self):
        chosen = [name for name, v in self._upgrade_vars.items() if v.get()]
        from .booklet_options import ship_option_errors
        problems = ship_option_errors(self._entry, chosen)
        if problems:
            messagebox.showerror("Options", "\n".join(problems), parent=self.dialog)
            return
        hits_max = getattr(self._entry, "hits_max", 8)
        try:
            hits = int(self._hits_var.get())
        except ValueError:
            hits = hits_max
        damage = {}
        if hits != hits_max:
            damage["hits_remaining"] = hits
        if not self._torps_var.get():
            damage["ordnance_loaded_torps"] = False
        if not self._craft_var.get():
            damage["ordnance_loaded_craft"] = False
        if self._crit_raw:
            damage["critical_damage"] = list(self._crit_raw)
        self._on_save(self._name_var.get().strip() or self._entry.ship_class,
                      chosen, damage)
        self.dialog.destroy()


# ---------------------------------------------------------------------------
# Weapon entry sub-dialog (used by _ShipBuilderDialog)
# ---------------------------------------------------------------------------

class _WeaponEntryDialog:
    """Small dialog for defining a single weapon on a homebrew ship."""

    def __init__(self, root: tk.Tk, on_save: Callable):
        dlg = tk.Toplevel(root)
        dlg.title("Add Weapon")
        dlg.geometry("420x310")
        dlg.configure(bg=_BG)
        dlg.transient(root)
        dlg.grab_set()

        tk.Label(dlg, text="ADD WEAPON", font=_FONT_BOLD, bg=_BG, fg=_ACCENT).pack(pady=8)

        def _field(label, var, width=20):
            f = tk.Frame(dlg, bg=_BG)
            f.pack(fill=tk.X, padx=15, pady=2)
            tk.Label(f, text=label, font=_FONT_BODY, bg=_BG, fg=_FG,
                     width=14, anchor="w").pack(side=tk.LEFT)
            tk.Entry(f, textvariable=var, font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                     insertbackground=_FG, width=width).pack(side=tk.LEFT, padx=4)

        name_var  = tk.StringVar(value="Weapons Battery")
        type_var  = tk.StringVar(value="battery")
        range_var = tk.StringVar(value="30")
        str_var   = tk.StringVar(value="6")

        _field("Name:", name_var, 22)

        tf = tk.Frame(dlg, bg=_BG)
        tf.pack(fill=tk.X, padx=15, pady=2)
        tk.Label(tf, text="Type:", font=_FONT_BODY, bg=_BG, fg=_FG,
                 width=14, anchor="w").pack(side=tk.LEFT)
        ttk.Combobox(tf, textvariable=type_var,
                     values=["battery", "lance", "torpedo", "nova_cannon",
                             "launch_bay"],
                     state="readonly", width=18).pack(side=tk.LEFT, padx=4)

        _field("Range (cm):", range_var, 8)
        _field("Strength:", str_var, 8)

        tk.Label(dlg, text="Fire Arcs:", font=_FONT_BODY, bg=_BG, fg=_FG).pack(
            anchor="w", padx=15, pady=(6, 2))
        arc_frame = tk.Frame(dlg, bg=_BG)
        arc_frame.pack(fill=tk.X, padx=15)
        arc_vars: Dict[str, tk.BooleanVar] = {}
        for arc in ["front", "left", "right", "rear"]:
            v = tk.BooleanVar(value=(arc != "rear"))
            arc_vars[arc] = v
            tk.Checkbutton(arc_frame, text=arc.capitalize(), variable=v,
                           font=_FONT_BODY, bg=_BG, fg=_FG,
                           selectcolor=_SEL_BG,
                           activebackground=_BG).pack(side=tk.LEFT, padx=4)

        def _add():
            try:
                w = {
                    "name":        name_var.get().strip() or "Weapon",
                    "weapon_type": type_var.get(),
                    "range_cm":    int(range_var.get() or 30),
                    "strength":    int(str_var.get() or 1),
                    "arcs":        [arc for arc, v in arc_vars.items() if v.get()],
                }
                on_save(w)
                dlg.destroy()
            except ValueError as exc:
                messagebox.showerror("Invalid", str(exc), parent=dlg)

        bf = tk.Frame(dlg, bg=_BG)
        bf.pack(pady=10)
        tk.Button(bf, text="Add", font=_FONT_BOLD,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=12,
                  command=_add).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Cancel", font=_FONT_BODY,
                  bg="#221111", fg=_FG, relief=tk.FLAT, padx=12,
                  command=dlg.destroy).pack(side=tk.LEFT, padx=4)

        root.wait_window(dlg)


# ---------------------------------------------------------------------------
# Ship builder dialog (creates homebrew ship classes)
# ---------------------------------------------------------------------------

class _ShipBuilderDialog:
    """Dialog for designing and saving a new homebrew ship class."""

    def __init__(self, root: tk.Tk, on_save: Callable):
        self._on_save = on_save
        self._weapons: List[Dict] = []

        self.dialog = tk.Toplevel(root)
        self.dialog.title("New Homebrew Ship")
        self.dialog.geometry("580x660")
        self.dialog.configure(bg=_BG)
        self.dialog.transient(root)
        self.dialog.grab_set()

        self._build_ui()
        root.wait_window(self.dialog)

    def _build_ui(self):
        tk.Label(self.dialog, text="NEW HOMEBREW SHIP", font=_FONT_TITLE,
                 bg=_BG, fg=_ACCENT).pack(pady=(10, 4))

        # Scrollable body
        canvas = tk.Canvas(self.dialog, bg=_BG, highlightthickness=0)
        scroll = tk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True, padx=10)

        inner = tk.Frame(canvas, bg=_BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=e.width))

        self._class_var   = tk.StringVar(value="Custom Prototype")
        self._type_var    = tk.StringVar(value="cruiser")
        self._size_var    = tk.StringVar(value="small")
        self._speed_var   = tk.StringVar(value="20")
        self._turn_var    = tk.StringVar(value="45")
        self._shields_var = tk.StringVar(value="2")
        self._ap_var      = tk.StringVar(value="6+")
        self._as_var      = tk.StringVar(value="5+")
        self._turrets_var = tk.StringVar(value="2")
        self._hits_var    = tk.StringVar(value="8")
        self._ld_var      = tk.StringVar(value="7")
        self._pts_var_sb  = tk.StringVar(value="0")
        self._rules_var   = tk.StringVar(value="")

        def _field(label, var, width=12):
            f = tk.Frame(inner, bg=_BG)
            f.pack(fill=tk.X, pady=1, padx=5)
            tk.Label(f, text=label, font=_FONT_BODY, bg=_BG, fg=_FG,
                     width=18, anchor="w").pack(side=tk.LEFT)
            tk.Entry(f, textvariable=var, font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                     insertbackground=_FG, width=width).pack(side=tk.LEFT, padx=4)

        def _combo_field(label, var, values):
            f = tk.Frame(inner, bg=_BG)
            f.pack(fill=tk.X, pady=1, padx=5)
            tk.Label(f, text=label, font=_FONT_BODY, bg=_BG, fg=_FG,
                     width=18, anchor="w").pack(side=tk.LEFT)
            ttk.Combobox(f, textvariable=var, values=values,
                         state="readonly", width=14).pack(side=tk.LEFT, padx=4)

        _field("Ship Class Name:", self._class_var, 24)
        _combo_field("Ship Type:", self._type_var,
                     ["battleship", "cruiser", "escort", "defense"])
        _combo_field("Base Size:", self._size_var, ["small", "large"])
        _field("Speed (cm):",     self._speed_var)
        _field("Turn Angle (°):", self._turn_var)
        _field("Shields Max:",    self._shields_var)
        _field("Armour Prow:",    self._ap_var)
        _field("Armour Side:",    self._as_var)
        _field("Turrets:",        self._turrets_var)
        _field("Hits Max:",       self._hits_var)
        _field("Leadership:",     self._ld_var)
        _field("Points Cost:",    self._pts_var_sb)
        _field("Special Rules:",  self._rules_var, 28)
        tk.Label(inner, text="(comma-separated, e.g. ponderous,deflector)",
                 font=("Consolas", 7), bg=_BG, fg="#888888").pack(
            anchor="w", padx=23, pady=(0, 4))

        tk.Label(inner, text="Weapons", font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(anchor="w", padx=5, pady=(6, 2))

        self._weapon_list = tk.Listbox(inner, font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                                       selectbackground="#334466", height=5)
        self._weapon_list.pack(fill=tk.X, padx=5)

        wb = tk.Frame(inner, bg=_BG)
        wb.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(wb, text="Add Weapon", font=_FONT_BODY, bg=_SEL_BG, fg=_FG,
                  relief=tk.FLAT, padx=6,
                  command=self._add_weapon).pack(side=tk.LEFT, padx=2)
        tk.Button(wb, text="Remove", font=_FONT_BODY, bg="#221111", fg=_FG,
                  relief=tk.FLAT, padx=6,
                  command=self._remove_weapon).pack(side=tk.LEFT, padx=2)

        bf = tk.Frame(inner, bg=_BG)
        bf.pack(pady=10, padx=5, fill=tk.X)
        tk.Button(bf, text="Save Homebrew Ship", font=_FONT_BOLD,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=12,
                  command=self._save).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="Cancel", font=_FONT_BODY,
                  bg="#221111", fg=_FG, relief=tk.FLAT, padx=12,
                  command=self.dialog.destroy).pack(side=tk.LEFT, padx=6)

    def _add_weapon(self):
        _WeaponEntryDialog(self.dialog, on_save=self._on_weapon_added)

    def _on_weapon_added(self, w: dict):
        self._weapons.append(w)
        arcs_str = ",".join(w.get("arcs", [])) or "all"
        self._weapon_list.insert(
            tk.END,
            f"{w['name']}  [{w['weapon_type']}]  {w['range_cm']}cm  "
            f"Str{w.get('strength_dice') or w['strength']}  {arcs_str}")

    def _remove_weapon(self):
        sel = self._weapon_list.curselection()
        if sel:
            self._weapon_list.delete(sel[0])
            self._weapons.pop(sel[0])

    def _save(self):
        try:
            rules = [r.strip() for r in self._rules_var.get().split(",") if r.strip()]
            entry = ShipClassEntry(
                ship_class=self._class_var.get().strip() or "Custom Ship",
                faction="homebrew",
                ship_type=self._type_var.get(),
                base_size=self._size_var.get(),
                speed=int(self._speed_var.get() or 20),
                turn_angle=int(self._turn_var.get() or 45),
                shields_max=int(self._shields_var.get() or 2),
                armor_prow=self._ap_var.get().strip() or "6+",
                armor_side=self._as_var.get().strip() or "5+",
                turrets=int(self._turrets_var.get() or 2),
                hits_max=int(self._hits_var.get() or 8),
                leadership=int(self._ld_var.get() or 7),
                weapons=list(self._weapons),
                special_rules=rules,
                upgrades_available=[],
                points_cost=int(self._pts_var_sb.get() or 0),
            )
        except ValueError as exc:
            messagebox.showerror("Invalid Values",
                                 f"Please check numeric fields:\n{exc}",
                                 parent=self.dialog)
            return
        self._on_save(entry)
        self.dialog.destroy()


# ---------------------------------------------------------------------------
# Fleet entry (in-memory row)
# ---------------------------------------------------------------------------

def _lists():
    from .fleet_lists import LISTS
    return LISTS


# The fleet's rows, totals, checks and saved contents live in fleet_model
# (no window needed; the AI list builder uses them too)
from .fleet_model import make_fleet_row as _make_fleet_row  # noqa: E402


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
        self._list_key: str = ""           # "" = playing without fleet lists (s.4)
        self._detachment_key: str = ""
        self._points_limit = 1000
        self._fleet_name = "My Fleet"

        self.win = tk.Toplevel(root)
        self.win.title("BFG:XR Fleet Builder")
        from .tk_scroll import fit_height
        self.win.geometry(f"1100x{fit_height(self.win, 720)}")
        self.win.minsize(900, 480)
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
        # Packed first so they always get their room (To do 32: packed last on
        # the faction row, they were never drawn in a 1000-pixel window)
        for text, cmd in [
            ("Validate",   self._validate_and_report),
            ("Save Fleet", self._save_fleet),
            ("Load Fleet", self._load_fleet),
        ]:
            tk.Button(top, text=text, font=_FONT_BOLD if text == "Save Fleet" else _FONT_BODY,
                      bg="#223322" if text == "Save Fleet" else _SEL_BG, fg=_FG,
                      relief=tk.FLAT, padx=8, command=cmd).pack(side=tk.RIGHT, padx=3)

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
        # Append homebrew option
        factions = factions + ["homebrew"]
        faction_names = faction_names + ["Homebrew (Custom Ships)"]
        self._faction_ids = factions
        self._faction_combo = ttk.Combobox(bar, textvariable=self._faction_var,
                                           values=faction_names, state="readonly",
                                           font=_FONT_BODY, width=20)
        self._faction_combo.pack(side=tk.LEFT, padx=5)
        self._faction_combo.bind("<<ComboboxSelected>>", self._on_faction_selected)

        tk.Label(bar, text="Fleet list:", font=_FONT_BODY, bg=_BG, fg=_FG).pack(
            side=tk.LEFT, padx=(10, 0))
        self._list_combo = ttk.Combobox(bar, values=[], state="readonly",
                                        font=_FONT_BODY, width=30)
        self._list_combo.pack(side=tk.LEFT, padx=5)
        self._list_combo.bind("<<ComboboxSelected>>", self._on_list_selected)
        self._list_options: List[str] = [""]
        tk.Label(bar, text="Detachment:", font=_FONT_BODY, bg=_BG, fg=_FG).pack(
            side=tk.LEFT, padx=(6, 0))
        self._det_combo = ttk.Combobox(bar, values=[], state="readonly",
                                       font=_FONT_BODY, width=22)
        self._det_combo.pack(side=tk.LEFT, padx=5)
        self._det_combo.bind("<<ComboboxSelected>>", self._on_detachment_selected)
        self._det_options: List[str] = [""]


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
        self._catalog_list.bind("<<ListboxSelect>>", lambda e: self._show_catalog_entry())
        self._catalog_entries: List[ShipClassEntry] = []
        self._catalog_info = tk.Label(left, text="", font=_FONT_BODY, bg=_BG, fg=_FG,
                                      justify=tk.LEFT, anchor="w", wraplength=300)
        self._catalog_info.pack(fill=tk.X, pady=(2, 0))
        # Ship card (owner: the armament and stats were hard to see): the
        # selected catalog or fleet ship's stats, every weapon and its rules
        self._card_text = tk.Text(left, height=11, font=_FONT_BODY, bg=_BG, fg=_FG,
                                  wrap=tk.WORD, relief=tk.SUNKEN, borderwidth=1)
        self._card_text.pack(fill=tk.X, pady=(2, 0))
        self._card_text.insert(tk.END, "Select a ship to see its stats and armament.")
        self._card_text.config(state=tk.DISABLED)

        add_row = tk.Frame(left, bg=_BG)
        add_row.pack(pady=4)
        tk.Button(add_row, text="Add to Fleet ▶", font=_FONT_BODY,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=8,
                  command=self._add_selected).pack(side=tk.LEFT, padx=3)
        tk.Button(add_row, text="Add with options... ▶", font=_FONT_BODY,
                  bg="#223322", fg=_FG, relief=tk.FLAT, padx=8,
                  command=lambda: self._add_selected(with_options=True)).pack(side=tk.LEFT, padx=3)
        tk.Button(left, text="+ New Homebrew Ship", font=_FONT_BODY,
                  bg="#332211", fg=_FG, relief=tk.FLAT, padx=8,
                  command=self._new_homebrew_ship).pack(pady=2)

        # Right: fleet list
        right = tk.Frame(pane, bg=_BG)
        pane.add(right, minsize=340)
        tk.Label(right, text="Fleet List", font=_FONT_BOLD,
                 bg=_BG, fg=_ACCENT).pack(anchor="w", pady=(4, 2))
        self._fleet_list = tk.Listbox(right, font=_FONT_BODY,
                                      bg=_SEL_BG, fg=_FG,
                                      selectbackground="#334466",
                                      activestyle="none", height=22,
                                      selectmode=tk.EXTENDED)
        self._fleet_list.pack(fill=tk.BOTH, expand=True)
        self._fleet_scroll = tk.Scrollbar(right, command=self._fleet_list.yview)
        self._fleet_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._fleet_list.config(yscrollcommand=self._fleet_scroll.set)
        self._fleet_list.bind("<Double-Button-1>", lambda _: self._edit_selected())
        self._fleet_list.bind("<<ListboxSelect>>", lambda _: self._show_fleet_entry())

        btn_row = tk.Frame(right, bg=_BG)
        btn_row.pack(fill=tk.X, pady=4)
        for text, cmd in [
            ("Options / Edit...", self._edit_selected),
            ("Flagship", self._toggle_flagship),
            ("Remove",   self._remove_selected),
        ]:
            tk.Button(btn_row, text=text, font=_FONT_BODY,
                      bg=_SEL_BG, fg=_FG, relief=tk.FLAT, padx=8,
                      command=cmd).pack(side=tk.LEFT, padx=3)
        # Squadrons (core s.8): select several ships (Ctrl / Shift-click)
        sq_row = tk.Frame(right, bg=_BG)
        sq_row.pack(fill=tk.X, pady=(0, 4))
        for text, cmd in [
            ("Squadron selected", self._squadron_selected),
            ("Leave squadron", self._unsquadron_selected),
            ("Auto escort squadrons", self._auto_squadrons),
        ]:
            tk.Button(sq_row, text=text, font=_FONT_BODY,
                      bg=_SEL_BG, fg=_FG, relief=tk.FLAT, padx=6,
                      command=cmd).pack(side=tk.LEFT, padx=3)
        tk.Label(right, text="Refits, weapon options (e.g. a nova cannon), torpedo types, "
                 "the fleet commander and re-rolls: select a ship and press "
                 "Options / Edit, or double-click it.",
                 font=("Consolas", 8), bg=_BG, fg="#AAAAAA", wraplength=420,
                 justify=tk.LEFT).pack(anchor="w")
        # The fleet list's rules, checked as the fleet changes (To do 32)
        self._check_var = tk.StringVar(value="")
        self._check_label = tk.Label(right, textvariable=self._check_var,
                                     font=("Consolas", 8), bg=_BG, fg="#FF8866",
                                     wraplength=420, justify=tk.LEFT)
        self._check_label.pack(anchor="w", pady=(2, 0))

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
        self._set_list_choices(faction_id)
        self._populate_catalog(faction_id)
        label = "Homebrew" if faction_id == "homebrew" else faction_display_name(faction_id)
        self._status_var.set(f"Faction: {label}")

    # ── Fleet lists (s.4) ────────────────────────────────────────────────────

    def _set_list_choices(self, faction_id: str, list_key: Optional[str] = None,
                          detachment_key: str = ""):
        """list_key None: the faction's first list (a new fleet); "" : no list."""
        from .fleet_lists import lists_for_faction
        lists = [] if faction_id == "homebrew" else lists_for_faction(faction_id)
        self._list_options = [""] + [fl["key"] for fl in lists]
        self._list_combo.config(values=["No fleet list (no restrictions)"]
                                + [fl["name"] for fl in lists])
        if list_key is None:
            list_key = lists[0]["key"] if lists else ""
        self._list_key = list_key if list_key in self._list_options else ""
        self._list_combo.current(self._list_options.index(self._list_key))
        self._set_detachment_choices(detachment_key)

    def _set_detachment_choices(self, detachment_key: str = ""):
        from .fleet_lists import detachments_for
        dets = detachments_for(self._list_key) if self._list_key else []
        self._det_options = [""] + [d["key"] for d in dets]
        self._det_combo.config(values=["None"] + [d["name"] for d in dets])
        self._detachment_key = detachment_key if detachment_key in self._det_options else ""
        self._det_combo.current(self._det_options.index(self._detachment_key))

    def _on_list_selected(self, _event=None):
        idx = self._list_combo.current()
        if idx < 0:
            return
        self._list_key = self._list_options[idx]
        self._set_detachment_choices(self._detachment_key)
        self._reprice_fleet()
        if self._faction:
            self._populate_catalog(self._faction)

    def _on_detachment_selected(self, _event=None):
        idx = self._det_combo.current()
        if idx < 0:
            return
        self._detachment_key = self._det_options[idx]
        if self._faction:
            self._populate_catalog(self._faction)

    def _list_keys(self) -> List[str]:
        return [k for k in (self._list_key, self._detachment_key) if k]

    def _reprice_fleet(self):
        """Ships already in the fleet take the chosen list's costs."""
        from .fleet_lists import LISTS, list_cost
        for r in self._fleet:
            key = r.get("list") or self._list_key
            src = key.split(":", 1)[1] if key.startswith("reserve:") else key
            fl = LISTS.get(src) if src else None
            if not r.get("list"):
                r["list"] = self._list_key
            r["base_cost"] = list_cost(fl, r["entry"].ship_class, r["entry"].points_cost)
            upgrade_map = {u.name: u for u in get_upgrades_for_ship(r["entry"])}
            r["points"] = r["base_cost"] + sum(upgrade_map[u].points_cost
                                               for u in r["upgrades"] if u in upgrade_map)
        self._refresh_fleet_list()

    def _populate_catalog(self, faction: str):
        """The catalog: every ship of the faction, or with a fleet list chosen,
        the list's ships by section at the list's costs, then the detachment's
        and the reserve lists' ships."""
        self._catalog_list.delete(0, tk.END)
        self._catalog_entries = []
        self._catalog_meta: List[tuple] = []          # (list key, cost) per entry
        if faction == "homebrew":
            entries = [(e, "", e.points_cost, "HB") for e in _hb.load_homebrew_catalog()]
        elif not self._list_key:
            entries = [(e, "", e.points_cost, e.ship_type[:3].upper())
                       for e in get_faction_ships(faction, include_unsupported=True)]
        else:
            entries = self._list_catalog()
        for e, key, cost, tag in entries:
            if e is None:                               # section header
                self._catalog_entries.append(None)
                self._catalog_meta.append(("", 0))
                self._catalog_list.insert(tk.END, f"— {tag} —")
                self._catalog_list.itemconfig(tk.END, fg=_ACCENT, selectforeground=_ACCENT)
                continue
            self._catalog_entries.append(e)
            self._catalog_meta.append((key, cost))
            suffix = "" if e.playable else "  (not playable yet)"
            self._catalog_list.insert(tk.END, f"[{tag}] {e.ship_class}  {cost}pts{suffix}")
            if not e.playable:
                self._catalog_list.itemconfig(tk.END, fg="#777777",
                                              selectforeground="#AAAAAA")
        self._catalog_info.config(text="")

    def _list_catalog(self) -> List[tuple]:
        from .fleet_model import list_catalog
        return [(e, key, cost, "RES" if key.startswith("reserve:") else
                 (name if e is None else name.split(": ")[-1][:3].upper()))
                for e, key, cost, name in list_catalog(self._list_key, self._detachment_key)]

    def _show_catalog_entry(self):
        sel = self._catalog_list.curselection()
        if not sel or self._catalog_entries[sel[0]] is None:
            return
        entry = self._catalog_entries[sel[0]]
        self._catalog_info.config(text=catalog_entry_summary(entry))
        self._show_card(entry.to_ship_dict(entry.ship_class, 1), entry.ship_class)

    def _show_fleet_entry(self):
        """The selected fleet ship's card, with its options applied."""
        sel = self._fleet_list.curselection()
        if not sel or sel[0] >= len(self._fleet):
            return
        row = self._fleet[sel[0]]
        entry = row.get("entry")
        if entry is None:
            return
        d = entry.to_ship_dict(row.get("custom_name") or entry.ship_class, 1,
                               upgrades=row.get("upgrades") or [])
        d["upgrades"] = list(row.get("upgrades") or [])
        self._show_card(d, f"{row.get('custom_name') or entry.ship_class} (in the fleet)")

    def _show_card(self, d: dict, title: str):
        card = getattr(self, "_card_text", None)
        if card is None:
            return
        card.config(state=tk.NORMAL)
        card.delete("1.0", tk.END)
        card.insert(tk.END, ship_card(d, title))
        card.config(state=tk.DISABLED)

    # ── Homebrew ship creation ────────────────────────────────────────────────

    def _new_homebrew_ship(self):
        def on_entry_saved(entry: ShipClassEntry):
            _hb.save_homebrew_ship(entry)
            if self._faction == "homebrew":
                self._populate_catalog("homebrew")
            self._status_var.set(f"Saved homebrew: {entry.ship_class}")

        _ShipBuilderDialog(self.win, on_save=on_entry_saved)

    # ── Fleet manipulation ────────────────────────────────────────────────────

    def _add_selected(self, with_options: bool = False):
        sel = self._catalog_list.curselection()
        if not sel:
            self._status_var.set("Select a ship class first.")
            return
        entry = self._catalog_entries[sel[0]]
        if entry is None:
            return
        if not entry.playable:
            self._status_var.set(f"{entry.ship_class} can't be played yet: "
                                 + "; ".join(entry.unsupported))
            return
        meta = getattr(self, "_catalog_meta", None)
        key, cost = meta[sel[0]] if meta else ("", entry.points_cost)
        row = _make_fleet_row(entry, list_key=key, base_cost=cost)
        self._fleet.append(row)
        self._refresh_fleet_list()
        self._status_var.set(f"Added {entry.ship_class}.")
        if with_options:
            self._fleet_list.selection_clear(0, tk.END)
            self._fleet_list.selection_set(len(self._fleet) - 1)
            self._edit_selected()

    def _edit_selected(self):
        sel = self._fleet_list.curselection()
        if not sel:
            return
        idx = sel[0]
        row = self._fleet[idx]

        def _save(name, upgrades, damage):
            row["custom_name"] = name
            row["upgrades"] = upgrades
            row["damage"] = damage
            upgrade_map = {u.name: u for u in get_upgrades_for_ship(row["entry"])}
            upgrade_cost = sum(upgrade_map[u].points_cost
                               for u in upgrades if u in upgrade_map)
            row["points"] = row.get("base_cost", row["entry"].points_cost) + upgrade_cost
            self._refresh_fleet_list()

        _ShipEditDialog(self.win, row["entry"], row["custom_name"],
                        row["upgrades"], on_save=_save,
                        current_damage=row.get("damage", {}),
                        base_cost=row.get("base_cost", row["entry"].points_cost),
                        list_keys=self._list_keys())

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

    def _squadron_selected(self):
        """Put the selected ships in one new squadron, if the squadron rules
        allow it (squadrons.squadron_errors)."""
        from .squadrons import squadron_errors
        sel = list(self._fleet_list.curselection())
        if len(sel) < 2:
            self._status_var.set("Select two or more ships (Ctrl / Shift-click) to squadron.")
            return
        used = {r.get("squadron_id") for r in self._fleet}
        n = 1
        while f"sq{n}" in used:
            n += 1
        sid = f"sq{n}"
        members = [self._fleet[i] for i in sel]
        errors = squadron_errors(members, sid, self._list_key or "")
        if errors:
            messagebox.showwarning("Squadron", "\n".join(errors), parent=self.win)
            return
        for r in members:
            r["squadron_id"] = sid
        self._status_var.set(f"Squadron {sid}: {len(members)} ships.")
        self._refresh_fleet_list()

    def _unsquadron_selected(self):
        for i in self._fleet_list.curselection():
            self._fleet[i]["squadron_id"] = ""
        self._refresh_fleet_list()

    def _auto_squadrons(self):
        """Re-form the escort squadrons by the rules (squadrons.organize_escorts:
        one class and set-up to a squadron, 2D3 a squadron within the list's
        sizes). Capital ship squadrons are formed at the start of the game."""
        from .squadrons import organize_escorts
        lines = []
        problems = organize_escorts(self._fleet, self._list_key or "", log=lines.append)
        self._status_var.set("; ".join(lines[-3:]) or "No escorts to squadron.")
        if problems:
            messagebox.showwarning("Squadrons", "\n".join(problems), parent=self.win)
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
            key = row.get("list", "")
            tag = (" (reserve)" if key.startswith("reserve:")
                   else " (detachment)" if key and key == self._detachment_key else "")
            sq = f" [{row['squadron_id']}]" if row.get("squadron_id") else ""
            self._fleet_list.insert(
                tk.END,
                f"{row['custom_name']}{tag}{flagship}{sq}  {row['points']}pts{upgrades}")
        self._refresh_totals()

    def _fleet_total(self) -> int:
        """Ship points plus fleet-wide adjustments (fleet_model.fleet_total)."""
        from .fleet_model import fleet_total
        return fleet_total(self._fleet)

    def _refresh_totals(self):
        total = self._fleet_total()
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
        self._live_check()

    def _live_check(self):
        """Show the fleet list's problems as the fleet changes (To do 32)."""
        if not hasattr(self, "_check_var"):
            return
        if not self._fleet:
            self._check_var.set("")
            return
        try:
            ok, errors = self._validate_fleet()
        except Exception as exc:          # noqa: BLE001 (a check never stops building)
            ok, errors = False, [f"(fleet check failed: {exc})"]
        if ok:
            self._check_label.config(fg="#88CC88")
            what = "the fleet list's rules" if self._list_key else "the points limit"
            self._check_var.set(f"Fleet valid ({what}).")
        else:
            self._check_label.config(fg="#FF8866")
            more = f"\n... and {len(errors) - 6} more (Validate)" if len(errors) > 6 else ""
            self._check_var.set("Fleet problems:\n- " + "\n- ".join(errors[:6]) + more)

    def _pts_label_color(self, color, total, limit):
        self._pts_var.set(f"Total: {total} / {limit} pts")

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_fleet(self) -> tuple:
        from .fleet_model import validate_fleet
        try:
            limit = int(self._pts_limit_var.get())
        except ValueError:
            limit = None
        errors = validate_fleet(self._fleet, self._list_key or "", self._detachment_key or "",
                                limit)
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

        from .fleet_model import fleet_data
        data = fleet_data(self._fleet, self._faction or "", self._list_key or "",
                          self._detachment_key or "",
                          self._fleet_name_var.get().strip() or "My Fleet", limit)

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self._status_var.set(f"Saved to {os.path.basename(path)}")
        if self._on_save:
            self._on_save(data, path)

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
            # Older fleet files have no fleet list: no restrictions
            dets = data.get("detachments") or [""]
            self._set_list_choices(faction, data.get("fleet_list", ""), dets[0])
            self._populate_catalog(faction)
        else:
            self._status_var.set(f"Warning: unknown faction '{faction}'.")

        self._fleet_name_var.set(data.get("fleet_name", "My Fleet"))
        self._pts_limit_var.set(str(data.get("points_limit", 1000)))
        self._fleet.clear()

        official_classes: List[str] = []
        unofficial_classes: List[str] = []
        skipped_classes: List[str] = []

        for s in data.get("ships", []):
            sc = s.get("ship_class", "")
            official_entry = get_ship_class(faction, sc)
            if official_entry is None and s.get("fleet_list"):
                from .ship_catalog import find_ship_class
                official_entry = find_ship_class(sc)      # e.g. a reserve from another faction

            if official_entry:
                official_classes.append(sc)
                entry = official_entry
            else:
                unofficial_classes.append(sc)
                entry = _hb.get_homebrew_ship(sc)
                if not entry:
                    skipped_classes.append(sc)
                    continue

            dmg: dict = {}
            if "hits_remaining" in s:
                dmg["hits_remaining"] = s["hits_remaining"]
            if "ordnance_loaded_torps" in s and not s["ordnance_loaded_torps"]:
                dmg["ordnance_loaded_torps"] = False
            if "ordnance_loaded_craft" in s and not s["ordnance_loaded_craft"]:
                dmg["ordnance_loaded_craft"] = False
            if s.get("critical_damage"):
                dmg["critical_damage"] = s["critical_damage"]
            row = _make_fleet_row(
                entry,
                custom_name=s.get("name", sc),
                upgrades=s.get("upgrades", []),
                is_flagship=s.get("is_flagship", False),
                squadron_id=s.get("squadron_id", ""),
                damage=dmg if dmg else None,
                list_key=s.get("fleet_list", ""),
            )
            self._fleet.append(row)

        self._reprice_fleet()

        n_off = len(official_classes)
        n_unoff = len(unofficial_classes)
        summary = f"{n_off} official"
        if n_unoff:
            summary += f", {n_unoff} unofficial"
        self._status_var.set(f"Loaded {os.path.basename(path)} — {summary}")

        if unofficial_classes:
            messagebox.showwarning(
                "Unofficial Ships Detected",
                "These ship classes are not in the official BFG catalog:\n" +
                "\n".join(f"• {sc}" for sc in unofficial_classes) +
                "\n\nVerify with your opponent before playing.",
            )
        if skipped_classes:
            messagebox.showwarning(
                "Unknown Ships Skipped",
                "These ships could not be loaded (not in catalog or local homebrew):\n" +
                "\n".join(f"• {sc}" for sc in skipped_classes),
            )

    # ── Public factory ────────────────────────────────────────────────────────

    @classmethod
    def open(cls, root: tk.Tk, on_save: Optional[Callable] = None,
             load_path: Optional[str] = None) -> "FleetBuilderWindow":
        return cls(root, on_save=on_save, load_path=load_path)


# ---------------------------------------------------------------------------
# fleet_list_to_ships: convert saved fleet data → list of Ship dicts for game
# ---------------------------------------------------------------------------

_ARC_SHORT = {"front": "F", "left": "L", "right": "R", "rear": "Rear", "all": "All round"}


def weapon_line(w: dict) -> str:
    """One weapon for the fleet builder's ship card: name, type, range,
    firepower / strength, arcs, and what makes it special."""
    wt = w.get("weapon_type", "")
    kind = {"battery": "FP", "lance": "FP", "torpedo": "S", "launch_bay": "S",
            "mine_launcher": "S", "nova_cannon": ""}.get(wt, "")
    val = w.get("strength_dice") or w.get("strength", "")
    rng = w.get("range_cm")
    rng_txt = (f"{w['range_min_cm']}-{rng}cm" if w.get("range_min_cm") else
               f"{rng}cm" if rng else "")
    arcs = "/".join(_ARC_SHORT.get(a, a) for a in (w.get("arcs") or []))
    extra = []
    if w.get("craft_types"):
        extra.append("craft: " + ", ".join(w["craft_types"]))
    if w.get("strength_close"):
        extra.append(f"FP{w['strength_close']} within 15cm")
    for flag, txt in (("de_phantom", "phantom lance: 1 hit on 4, 2 on 5+"),
                      ("phantom", "phantom lance"), ("pulsar", "pulsar"),
                      ("de_battery", "left shift"), ("eldar_battery", "left shift"),
                      ("plasma_torpedoes", "plasma: re-roll misses"),
                      ("boarding_torpedoes", "boarding torpedoes"),
                      ("impaler_bay", "Impalers"), ("particle_whip", "particle whip"),
                      ("lightning_arc", "lightning arc")):
        if w.get(flag):
            extra.append(txt)
    parts = [w.get("name", wt), f"{rng_txt}" if rng_txt else "",
             f"{kind}{val}" if kind else (str(val) if val else ""),
             f"({arcs})" if arcs else ""]
    line = "  " + " ".join(p for p in parts if p)
    return line + (f" - {'; '.join(extra)}" if extra else "")


def ship_card(d: dict, title: str = "") -> str:
    """Stats, armament and special rules of a ship (a ship dict as the game
    builds it, options applied) for the fleet builder (owner: the armament
    and stats were hard to see)."""
    arm = f"{d.get('armor_prow')}/{d.get('armor_side')}" + (
        f"/{d['armor_rear']}" if d.get("armor_rear") else "")
    lines = [title or d.get("ship_class", ""),
             f"Points {d.get('points_value')}   Hits {d.get('hits_max')}   "
             f"Speed {d.get('speed')}cm   Turns {d.get('turn_angle')}\u00b0",
             f"Shields {d.get('shields_max')}   Armour {arm}   Turrets {d.get('turrets')}"
             f"   Ld {d.get('leadership') or ('rolled (' + str(d.get('leadership_table')) + ')')}",
             "Armament:"]
    lines += [weapon_line(w) for w in d.get("weapons") or []] or ["  none"]
    rules = [r for r in d.get("special_rules") or [] if ":" not in r or r.startswith("torpedo_type")]
    if rules:
        lines.append("Rules: " + ", ".join(rules))
    if d.get("upgrades"):
        lines.append("Options: " + "; ".join(d["upgrades"]))
    return "\n".join(lines)


def catalog_entry_summary(entry: ShipClassEntry) -> str:
    """One-glance description of a catalog ship for the fleet builder."""
    ld = (f"Ld rolled at game start ({entry.leadership_table} table)"
          if entry.leadership_table else f"Ld {entry.leadership}")
    lines = [f"{entry.ship_class} — {entry.points_cost}pts, {entry.hits_max} hits, "
             f"{entry.speed}cm, {entry.turn_angle}°, shields {entry.shields_max}, "
             f"armour {entry.armor_prow}/{entry.armor_side}"
             f"{'/' + entry.armor_rear + ' (front/abeam/rear)' if entry.armor_rear else ''}, "
             f"turrets {entry.turrets}. {ld}."]
    if "towed" in entry.special_rules:
        lines.append("Towed ship: no warp engines of its own; needs gravitic hooks "
                     "in the fleet (fleet building only, no effect in battle).")
    if not entry.playable:
        lines.append("Not playable yet: " + "; ".join(entry.unsupported) + ".")
    return "\n".join(lines)


def fleet_list_to_ships(fleet_data: dict, player: int) -> List[dict]:
    """
    Convert a saved fleet dict into Ship-compatible dicts ready for game state.

    Lookup order per ship:
      1. Official catalog (ship_catalog.py)
      2. Local homebrew catalog (data/homebrew/)
      3. Raw fall-through (hand-crafted fleet files; stats taken as-is)
    """

    faction = fleet_data.get("faction", "")
    result: List[dict] = []

    for i, raw in enumerate(fleet_data.get("ships", [])):
        sc = raw.get("ship_class", "")
        entry = get_ship_class(faction, sc) if faction else None
        if entry and not entry.playable:
            entry = None          # not playable yet: keep the saved stats as-is
        if not entry:
            entry = _hb.get_homebrew_ship(sc)

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
            if raw.get("squadron_id"):
                ship_dict["squadron_id"] = raw["squadron_id"]
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
