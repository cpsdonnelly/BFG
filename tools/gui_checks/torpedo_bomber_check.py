"""Torpedo bombers (s.21) in the real GamePanel: launch them from the launch
dialog, then fire their salvo from the "Fire Torpedo Bombers" button a turn
later; the salvo runs out of fuel at the end of the ordnance phase."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
import src.choice_dialog as cd
for n in ("showinfo", "showwarning"): setattr(messagebox, n, lambda *a, **k: None)
errs = []
messagebox.showerror = lambda *a, **k: errs.append(a)
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
BAY = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 2,
       "arcs": [], "craft_types": ["fighter", "torpedo_bomber"],
       "craft_speeds": {"fighter": 30, "torpedo_bomber": 20}}
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(Ship(id="c", name="carrier", ship_class="T", faction="chaos", player=1,
                 ship_type="cruiser", base_size="small", x=40.0, y=60.0, heading=0.0, speed=20,
                 turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                 hits_max=8, leadership=7, weapons=[BAY], special_rules=[], upgrades=[],
                 critical_damage=[]))
gs.add_ship(Ship(id="e", name="target", ship_class="T", faction="chaos", player=2,
                 ship_type="cruiser", base_size="small", x=100.0, y=60.0, heading=180.0,
                 speed=20, turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                 turrets=1, hits_max=8, leadership=7, weapons=[], special_rules=[],
                 upgrades=[], critical_damage=[], points_value=180))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
gs.active_player = 1; gs.current_phase = "ordnance"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
panel.ctx.is_ai_controlled = lambda p: False

print("1. The launch dialog offers torpedo bombers")
panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("c")); root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
labels = [w.cget("text") for w in walk(dlg) if isinstance(w, tk.Label)]
check(any(t.startswith("Torpedo Bombers") for t in labels), "torpedo bomber row shown")
dlg.destroy()

print("2. A squadron launched last turn fires a salvo from the button")
gs.turn_number = 2
gs.add_ordnance(OrdnanceMarker(id="tb", ordnance_type="torpedo_bomber", owner_player=1,
                               launched_by="c", x=80.0, y=60.0, speed=20.0, launched_turn=1))
asked = []
def fake_choose(root_, title, text, options, best):
    asked.append((title, best)); return best
cd.choose = fake_choose
import src.ordnance_panel  # noqa: F401  (imports choose at call time)
panel.fire_tb_btn.invoke(); root.update()
kinds = [o["ordnance_type"] for o in gs.ordnance]
check(asked and asked[0][1] == "e", f"Auto (best) aims at the target ({asked})")
check(kinds == ["torpedo_standard"], f"the squadron became a salvo ({kinds})")
check(gs.ordnance and gs.ordnance[0]["strength"] == 2, "strength 2")

print("3. The salvo runs out of fuel at the end of the ordnance phase")
tc.end_phase()
check(not gs.ordnance, f"salvo removed ({len(gs.ordnance)} left)")
check(not errs, f"no errors ({errs})")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
