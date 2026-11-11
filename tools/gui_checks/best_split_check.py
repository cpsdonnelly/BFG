"""Launch dialog's "Best split" (fighters vs bombers for one wave) matches
waves.best_wave_split for the nearest enemy's turrets and CAP."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.ship_catalog import find_ship_class
from src.waves import best_wave_split
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)
fails = []

def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

for turrets in (1, 4):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    d = find_ship_class("Dictator Class Cruiser").to_ship_dict("D", 1, ship_id="d")
    d.update(x=30.0, y=60.0, heading=0.0, leadership=8)
    gs.add_ship(Ship.from_dict(d))
    gs.add_ship(Ship(id="e", name="e", ship_class="T", faction="imperial_navy_gothic", player=2,
                     ship_type="cruiser", base_size="small", x=80.0, y=60.0, heading=90.0,
                     speed=20, turn_angle=45, shields_max=2, armor_prow="5+", armor_side="5+",
                     turrets=turrets, hits_max=8, leadership=7, weapons=[], special_rules=[],
                     upgrades=[], critical_damage=[]))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    gs.current_phase = "ordnance"; gs.active_player = 1
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("d")); root.update()
    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    btn = [b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Best split"]
    if not btn:
        fails.append("no Best split button"); print("  FAIL no button"); root.destroy(); continue
    btn[0].invoke(); root.update()
    vals = {}
    for w in walk(dlg):
        if isinstance(w, tk.Entry) and isinstance(w.master, tk.Frame):
            ls = [c.cget("text") for c in w.master.winfo_children() if isinstance(c, tk.Label)]
            if ls:
                vals[ls[0]] = w.get()
    bays = sum(int(v) for v in vals.values() if v.isdigit())
    fb, bb, _ = best_wave_split(bays, turrets, turrets, 0, 5)
    got_f = next((int(v) for k, v in vals.items() if "ight" in k), None)
    got_b = next((int(v) for k, v in vals.items() if "omb" in k), None)
    ok = (got_f, got_b) == (fb, bb)
    print(("  ok   " if ok else "  FAIL ") + f"turrets {turrets}: {vals} expected {fb}F/{bb}B")
    if not ok:
        fails.append(turrets)
    root.destroy()
print("RESULT: ALL OK" if not fails else f"RESULT: FAIL {fails}")
