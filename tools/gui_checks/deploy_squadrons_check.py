"""Owner: players place ships in any order (any group, any ship of a
squadron) and form capital ship squadrons before deploying, with the squadron
rules checked (the capital squadrons dialog and its Auto)."""
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, ".")
from src.board_view import BoardView                       # noqa: E402
from src.deployment_panel import DeploymentPanel            # noqa: E402
from src.fleet_loader import load_fleet_file, fleet_to_ships  # noqa: E402
from src.game_state import GameState                        # noqa: E402

warn = []
messagebox.showwarning = lambda t, m="", **k: warn.append(m)
messagebox.askyesno = lambda *a, **k: True
root = tk.Tk()
gs = GameState()
gs.game_seed = 11
for p, f in ((1, "owner_gothic_1000.json"), (2, "owner_chaos_1000.json")):
    for s in fleet_to_ships(load_fleet_file("data/fleets/" + f), p):
        gs.add_ship(s)
board = BoardView(root, gs)
panel = DeploymentPanel(parent_frame=board.side_panel, board_view=board, gs=gs, root=root,
                        on_complete=lambda: None)
root.update()
ok = True
panel._squadron_dialog()
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
lb = next(w for w in dlg.winfo_children() if isinstance(w, tk.Listbox))
buttons = {w.cget("text"): w for f in dlg.winfo_children() if isinstance(f, tk.Frame)
           for w in f.winfo_children() if isinstance(w, tk.Button)}
names = lb.get(0, tk.END)
# an illegal squadron is refused: a single ship
lb.selection_set(0)
buttons["Squadron"].invoke()
ok &= bool(warn)
print("  illegal squadron refused:", bool(warn), warn[:1])
warn.clear()
# two cruisers squadron together
idx = [i for i, n in enumerate(names) if "Cruiser" in n and "Battle" not in n][:2]
lb.selection_clear(0, tk.END)
for i in idx:
    lb.selection_set(i)
buttons["Squadron"].invoke()
grouped = [g for g in panel.state.groups[1] if len(g) > 1 and g[0].ship_type != "escort"]
ok &= bool(grouped) and not warn
print("  cruisers squadroned:", [s.ship_class for s in grouped[0]] if grouped else None)
buttons["Close"].invoke()
# place the squadron with its ships in any order
gi = panel.state.groups[1].index(grouped[0])
panel.state.select_group(gi)
first = panel.state.current_group()[0].id
panel._next_member()
ok &= panel.state.current_group()[0].id != first
print("  next ship in squadron:", panel.state.current_group()[0].name)
root.destroy()
print("RESULT:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
