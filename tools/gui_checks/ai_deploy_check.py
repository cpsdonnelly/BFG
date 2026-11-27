"""To do 28: in a game against the AI, the human places their fleet (here with
Auto-Place, which places only their own ships) and the AI then places its own,
buff ships last; deployment then hands over to turn 1."""
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, ".")
from src.board_view import BoardView                       # noqa: E402
from src.deployment_panel import DeploymentPanel            # noqa: E402
from src.fleet_loader import load_fleet_file, fleet_to_ships  # noqa: E402
from src.game_state import GameState                        # noqa: E402

errors = []
messagebox.askyesno = lambda *a, **k: True
messagebox.showerror = lambda t, m="", **k: errors.append(m)
messagebox.showwarning = lambda t, m="", **k: errors.append(m)

root = tk.Tk()
gs = GameState()
gs.ai_player = 2
for p, f in ((1, "owner_gothic_1000.json"), (2, "owner_tau_merchant_1000.json")):
    for s in fleet_to_ships(load_fleet_file("data/fleets/" + f), p):
        gs.add_ship(s)
board = BoardView(root, gs)
done = []
panel = DeploymentPanel(parent_frame=board.side_panel, board_view=board, gs=gs, root=root,
                        on_complete=lambda: done.append(True))
root.update()
panel._auto_place_remaining(ask=False)           # the human's fleet only
mine_placed = all(s["x"] or s["y"] for s in gs.ships if s["player"] == 1)
ai_left = sum(1 for s in gs.ships if s["player"] == 2 and not (s["x"] or s["y"]))
for _ in range(40):                              # the AI places its own after 300ms
    root.update()
    root.after(50)
    if done:
        break
inside = all(0 < s["x"] < gs.table_width and 0 < s["y"] < gs.table_height for s in gs.ships)
lines = [ln for ln in gs.log if "[AI]" in str(ln)]
ok = mine_placed and ai_left > 0 and bool(done) and inside and not errors
print(f"human placed: {mine_placed}; AI ships left for the AI: {ai_left}; complete: {bool(done)}; "
      f"inside: {inside}; errors: {errors}")
print("\n".join(str(x) for x in lines[:6]))
print("RESULT:", "OK" if ok else "FAIL")
root.destroy()
sys.exit(0 if ok else 1)
