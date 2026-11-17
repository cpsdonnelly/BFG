"""Fire at Ordnance dialog (engine combat.fire_at_ordnance): a lance shoots a mine."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)

class Dice:
    mode = "auto"
    def roll_d6(self, n, desc=""):
        return [6] * n
    def roll_2d6(self, desc=""):
        return 7

lance = {"name": "Prow Lances", "weapon_type": "lance", "range_cm": 30, "strength": 2,
         "arcs": ["front"]}
s1 = Ship(id="p1", name="p1", ship_class="T", faction="imperial_navy_gothic", player=1,
          ship_type="cruiser", base_size="small", x=20.0, y=60.0, heading=0.0, speed=20,
          turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2, hits_max=8,
          leadership=7, weapons=[lance], special_rules=[], upgrades=[], critical_damage=[])
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"; gs.add_ship(s1)
gs.add_ordnance(OrdnanceMarker(id="m", ordnance_type="mine_launcher", owner_player=2,
                               launched_by="x", x=35.0, y=60.0, heading=180.0, strength=1,
                               speed=10.0))
tc = TurnController(gs, Dice()); tc.start_game()
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel); frame.pack()
panel = GamePanel(frame, tc, board, root)
gs.current_phase = "shooting"; gs.active_player = 1
panel.ctx.pick_ship = lambda ships, title: ships[0]
panel.ctx.dice = Dice()

def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

def act():
    dlgs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    if not dlgs:
        root.after(100, act); return
    btn = next(w for w in walk(dlgs[0]) if isinstance(w, tk.Button) and "Fire" in w.cget("text"))
    btn.invoke()

root.after(200, act)
panel.combat._fire_at_ordnance_dialog()
import time
end = time.time() + 1.5
while time.time() < end:
    root.update(); time.sleep(0.02)
ok = not gs.ordnance
print(("  ok   " if ok else "  FAIL ") + f"mine destroyed: {gs.ordnance}")
print("RESULT: ALL OK" if ok else "RESULT: FAIL")
