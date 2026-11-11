"""Combine Ordnance Launch (s.15): capital ships of one squadron in contiguous base
contact combine torpedoes; ships not in a squadron aren't offered as a group."""
import os, sys, tempfile, time, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
INFO = []
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: INFO.append(a))
TORP = {"name": "Prow Torps", "weapon_type": "torpedo", "range_cm": 30, "strength": 6,
        "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}

def mk(i, x, y, sq):
    return Ship(id=i, name=i, ship_class="Lunar", faction="imperial_navy_gothic", player=1,
                ship_type="cruiser", base_size="small", x=x, y=y, heading=0.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=8, weapons=[dict(TORP)], special_rules=[], upgrades=[],
                critical_damage=[], squadron_id=sq)

def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

def run(squadron):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(mk("a", 40.0, 60.0, squadron)); gs.add_ship(mk("b", 40.0, 63.0, squadron))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    gs.current_phase = "ordnance"; gs.active_player = 1
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    steps = ["Select Group", "Torpedoes", "Launch Combined"]
    def act():
        for d in [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]:
            for w in walk(d):
                if isinstance(w, tk.Button) and steps and steps[0] in w.cget("text"):
                    steps.pop(0); w.invoke(); break
        if steps:
            root.after(150, act)
    root.after(200, act)
    panel.ordnance._combine_ordnance_dialog()
    end = time.time() + 1.5
    while time.time() < end:
        root.update(); time.sleep(0.02)
    torps = [o for o in gs.ordnance if "torpedo" in o["ordnance_type"]]
    root.destroy()
    return torps

ok = True
t = run("sq1")
good = len(t) == 1 and t[0]["strength"] == 12
print(("  ok   " if good else "  FAIL ") + f"squadron of two cruisers: one salvo S12 {[o['strength'] for o in t]}")
ok &= good
INFO.clear()
t2 = run("")
good2 = not t2 and any("No Groups" in a[0] for a in INFO)
print(("  ok   " if good2 else "  FAIL ") + f"not squadroned: no combined group {INFO[:1]}")
ok &= good2
print("RESULT: ALL OK" if ok else "RESULT: FAIL")
