"""Advanced settings: the blast marker rules combobox sets GameState and the engine mode."""
import os, sys, tempfile, tkinter as tk
from tkinter import ttk, messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.optional_rules import blast_rules
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)

def ship(id, player, x):
    return Ship(id=id, name=id, ship_class="Test", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=0.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[],
                critical_damage=[])

root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(ship("p1", 1, 20.0)); gs.add_ship(ship("p2", 2, 100.0))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel); frame.pack()
panel = GamePanel(frame, tc, board, root)
root.update()
result = {}
def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

def act():
    dlgs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    if not dlgs:
        root.after(100, act); return
    dlg = dlgs[0]
    combos = [w for w in walk(dlg) if isinstance(w, ttk.Combobox)
              and "Remastered (s.11)" in w.cget("values")]
    result["combo"] = bool(combos)
    if combos:
        combos[0].set("Remastered (s.11)")
    btn = next(w for w in walk(dlg) if isinstance(w, tk.Button) and w.cget("text") == "Apply")
    btn.invoke()

root.after(300, act)
panel._settings_dialog()
root.update()
ok = result.get("combo", False)
print(("  ok   " if ok else "  FAIL ") + "blast marker combobox present")
ok2 = gs.blast_marker_rules == "remastered" and blast_rules() == "remastered"
print(("  ok   " if ok2 else "  FAIL ") + f"applied: {gs.blast_marker_rules} / {blast_rules()}")
print("RESULT: ALL OK" if ok and ok2 else "RESULT: FAIL")
