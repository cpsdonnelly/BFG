"""To do 32: the owner's builder-saved fleets (no ids, no positions) load, and
the deployment window's Auto-Place deploys both fleets, squadrons coherent,
then hands over to turn 1 (it stopped at a 4-Cobra squadron before)."""
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

ok = True
for f1, f2 in (("owner_gothic_1000.json", "owner_chaos_1000.json"),
               ("owner_bakka_1000.json", "owner_tau_merchant_1000.json"),
               ("owner_space_marines_1000.json", "owner_mechanicus_1000.json")):
    root = tk.Tk()
    gs = GameState()
    for p, f in ((1, f1), (2, f2)):
        for s in fleet_to_ships(load_fleet_file("data/fleets/" + f), p):
            gs.add_ship(s)
    board = BoardView(root, gs)
    done = []
    panel = DeploymentPanel(parent_frame=board.side_panel, board_view=board, gs=gs, root=root,
                            on_complete=lambda: done.append(True))
    root.update()
    panel._auto_place_remaining()
    complete = panel.state.is_complete()
    if complete:
        panel._finish()
    inside = all(0 < s["x"] < gs.table_width and 0 < s["y"] < gs.table_height for s in gs.ships)
    good = complete and bool(done) and inside and not errors
    ok &= good
    print(f"  {'ok  ' if good else 'FAIL'} {f1} v {f2}: {len(gs.ships)} ships placed, "
          f"errors {errors[:2]}")
    errors.clear()
    root.destroy()
print("RESULT:", "ALL OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
