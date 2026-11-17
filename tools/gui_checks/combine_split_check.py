"""Combined squadron craft launch: "Best split" fills the planner's mix for
two Dictators (8 bays) against a 4-turret target, and launches one wave."""
import os, sys, tempfile, time, tkinter as tk
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

def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
for i, y in (("a", 60.0), ("b", 63.0)):
    d = find_ship_class("Dictator Class Cruiser").to_ship_dict(i, 1, ship_id=i)
    d.update(x=40.0, y=y, heading=0.0, leadership=8, squadron_id="sq")
    gs.add_ship(Ship.from_dict(d))
gs.add_ship(Ship(id="e", name="e", ship_class="T", faction="imperial_navy_gothic", player=2,
                 ship_type="cruiser", base_size="small", x=90.0, y=60.0, heading=90.0,
                 speed=20, turn_angle=45, shields_max=2, armor_prow="5+", armor_side="5+",
                 turrets=4, hits_max=8, leadership=7, weapons=[], special_rules=[],
                 upgrades=[], critical_damage=[]))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
gs.current_phase = "ordnance"; gs.active_player = 1
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
steps = ["Select Group", "Attack Craft", "Best split", "Launch Combined"]
seen = {}
def act():
    for d in [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]:
        for w in walk(d):
            if isinstance(w, tk.Button) and steps and steps[0] in w.cget("text"):
                if steps[0] == "Launch Combined":
                    for e in walk(d):
                        if isinstance(e, tk.Entry) and isinstance(e.master, tk.Frame):
                            kids = e.master.winfo_children(); k = kids.index(e)
                            if k and isinstance(kids[k - 1], tk.Label):
                                seen[kids[k - 1].cget("text")] = e.get()
                steps.pop(0); w.invoke(); break
    if steps:
        root.after(150, act)
root.after(200, act)
panel.ordnance._combine_ordnance_dialog()
end = time.time() + 2.0
while time.time() < end:
    root.update(); time.sleep(0.02)
fb, bb, _ = best_wave_split(8, 4, 4, 0, 5)
got = (int(seen.get("Fury Interceptors:", -1)), int(seen.get("Starhawk Bombers:", -1)))
craft = [o for o in gs.ordnance if o["owner_player"] == 1]
waves = {o.get("wave_id") for o in craft}
ok1 = got == (fb, bb)
ok2 = len(craft) == 8 and len(waves) == 1 and None not in waves
print(("  ok   " if ok1 else "  FAIL ") + f"planned {got}, expected {(fb, bb)}")
print(("  ok   " if ok2 else "  FAIL ") + f"launched {len(craft)} in waves {waves}")
root.destroy()
print("RESULT: ALL OK" if ok1 and ok2 else "RESULT: FAIL")
