"""Launch dialog: craft launch as their booklet type; split torpedo salvos (s.13)."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
errors = []
for n in ("showinfo", "showwarning"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.showerror = lambda t, m, **k: errors.append(m)
messagebox.askyesno = lambda *a, **k: True
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
from src.ship_catalog import find_ship_class
def build(weapons):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"; gs.rule_hit_and_run = True
    s = Ship(id="c", name="carrier", ship_class="T", faction="imperial_navy_gothic", player=1,
             ship_type="cruiser", base_size="small", x=40.0, y=60.0, heading=0.0, speed=20,
             turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2, hits_max=8,
             leadership=7, weapons=weapons, special_rules=[], upgrades=[], critical_damage=[])
    gs.add_ship(s)
    gs.add_ship(Ship(id="e", name="enemy", ship_class="T", faction="chaos", player=2,
                     ship_type="cruiser", base_size="small", x=110.0, y=110.0, heading=180.0,
                     speed=20, turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                     turrets=2, hits_max=8, leadership=7, weapons=[], special_rules=[],
                     upgrades=[], critical_damage=[]))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    gs.active_player = 1; gs.current_phase = "shooting"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("c"))
    root.update()
    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    return root, gs, dlg

print("1. Imperial Navy carrier launches Sharks and Starhawks as assault boats/bombers")
bays = [{"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 2,
         "arcs": [], "craft_types": ["shark_assault_boat", "bomber"],
         "craft_speeds": {"shark_assault_boat": 30, "bomber": 25}, "craft_speed": 30}]
print("   bays:", [(w["name"], w["craft_types"], w["craft_speeds"]) for w in bays])
root, gs, dlg = build(bays)
rows = {}
for w in walk(dlg):
    if isinstance(w, tk.Entry) and isinstance(w.master, tk.Frame):
        labels = [c.cget("text") for c in w.master.winfo_children() if isinstance(c, tk.Label)]
        if labels: rows[labels[0]] = w
print("   rows:", list(rows))
for name, val in (("Shark Assault Boats:", "1"), ("Bombers:", "1")):
    rows[name].delete(0, tk.END); rows[name].insert(0, val)
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Launch Attack Craft"][0].invoke()
root.update()
got = sorted((o["ordnance_type"], o["speed"]) for o in gs.ordnance)
print("   launched:", got, errors)
check(got == [("assault_boat", 30), ("bomber", 25)], "assault boat 30cm + bomber at its profile speed 25cm")
root.destroy()

print("2. Splitting a Str 8 salvo")
torps = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 8, "range_cm": 30,
         "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}
for first, h2, ok_expected in ((2, "20", False), (4, "0", False), (4, "20", True)):
    errors.clear()
    root, gs, dlg = build([torps])
    entries = [w for w in walk(dlg) if isinstance(w, tk.Entry)]
    # entries: heading, first-salvo Str, second heading
    entries[1].delete(0, tk.END); entries[1].insert(0, str(first))
    entries[2].delete(0, tk.END); entries[2].insert(0, h2)
    [b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text").startswith("Launch Torp")][0].invoke()
    root.update()
    got = sorted((o["strength"], round(o["heading"])) for o in gs.ordnance)
    print(f"   Str {first} + {8-first}, second heading {h2}: {got} {errors}")
    check(bool(got) == ok_expected, f"split {first}/{8-first} at {h2} {'allowed' if ok_expected else 'refused'}")
    if ok_expected:
        check(got == [(4, 0), (4, 20)], "two salvos, different headings")
    root.destroy()

print("3. Ork Torps S D6+4 rolled at launch; a roll of 9 may split 4/5")
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
otorps = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 7, "strength_dice": "D6+4",
          "range_cm": 30, "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}
for amount, h2, roll, expect in (("all", "0", 5, [(9, 0)]), ("4", "20", 5, [(4, 0), (5, 20)]),
                                 ("4", "20", 1, [(5, 0)])):
    errors.clear()
    root, gs, dlg = build([otorps])
    entries = [w for w in walk(dlg) if isinstance(w, tk.Entry)]
    labels = [w.cget("text") for w in walk(dlg) if isinstance(w, tk.Label)]
    entries[1].delete(0, tk.END); entries[1].insert(0, amount)
    entries[2].delete(0, tk.END); entries[2].insert(0, h2)
    import src.game_panel  # noqa
    d = Dice([roll])
    for obj in (dlg.master,):
        pass
    root.children  # noqa
    panel_ctx = [w for w in []]
    gs_panel_ctx = None
    # the ordnance panel's ctx.dice is the GamePanel's
    import gc
    from src.game_context import GameContext
    ctxs = [o for o in gc.get_objects() if isinstance(o, GameContext) and o.gs is gs]
    ctxs[0].dice = d
    [b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text").startswith("Launch Torp")][0].invoke()
    root.update()
    got = sorted((o["strength"], round(o["heading"])) for o in gs.ordnance)
    print(f"   roll {roll}, ask {amount}/{h2}: {got} {errors}; label shows dice:",
          any("D6+4 (rolled at launch)" in t for t in labels))
    check(got == expect and d.i == 1, f"rolled D6+4 with {roll}: {expect}")
    root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
