import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
errs = []
for n in ("showinfo", "showwarning"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.showerror = lambda *a, **k: errs.append(a)
messagebox.askyesno = lambda *a, **k: False
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
BAY = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 2,
       "arcs": [], "craft_types": ["bomber"], "craft_speeds": {"bomber": 20}}
def setup(n_craft):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(Ship(id="c", name="carrier", ship_class="T", faction="chaos", player=1,
                     ship_type="cruiser", base_size="small", x=40.0, y=60.0, heading=0.0, speed=20,
                     turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                     hits_max=8, leadership=7, weapons=[BAY], special_rules=[], upgrades=[],
                     critical_damage=[]))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    gs.active_player = 1; gs.current_phase = "ordnance"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    for i in range(n_craft):
        gs.add_ordnance(OrdnanceMarker(id=f"old{i}", ordnance_type="bomber", owner_player=1,
                                       launched_by="c", x=80.0, y=60.0 + i, speed=20.0,
                                       launched_turn=1))
    return root, gs, panel
def click_recall(root, n_pick):
    def act():
        tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)
                and w.title() == "Recall Attack Craft"]
        if not tops:
            root.after(50, act); return
        d = tops[-1]
        for cb in [w for w in walk(d) if isinstance(w, tk.Checkbutton)][:n_pick]:
            cb.invoke()
        [b for b in walk(d) if isinstance(b, tk.Button) and b.cget("text") == "Recall"][0].invoke()
    root.after(50, act)
def launch_dialog(root, panel, gs):
    panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("c")); root.update()
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)
            and w.title() != "Recall Attack Craft"][-1]
def set_bombers(dlg, n):
    for w in walk(dlg):
        if isinstance(w, tk.Entry) and isinstance(w.master, tk.Frame):
            ls = [c.cget("text") for c in w.master.winfo_children() if isinstance(c, tk.Label)]
            if ls and ls[0].startswith("Bombers"):
                w.delete(0, tk.END); w.insert(0, str(n))
def press(dlg, text):
    [b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text").startswith(text)][0].invoke()

print("1. Fleet full (2 bays, 2 craft out): recall one, then launch one")
root, gs, panel = setup(2)
dlg = launch_dialog(root, panel, gs)
click_recall(root, 1)
press(dlg, "Recall Squadrons")
root.update()
check(len(gs.ordnance) == 1, f"one squadron recalled ({len(gs.ordnance)} left)")
dlg2 = launch_dialog(root, panel, gs)
set_bombers(dlg2, 2)
press(dlg2, "Launch Attack Craft"); root.update()
check(len(gs.ordnance) == 2, f"only one new squadron fits ({len(gs.ordnance)} in play)")
root.destroy()

print("2. More craft out than bays (3 out, 2 bays): one must go before launching")
root, gs, panel = setup(3)
dlg = launch_dialog(root, panel, gs)
set_bombers(dlg, 1)
click_recall(root, 1)
press(dlg, "Launch Attack Craft"); root.update()
ids = sorted(o["id"] for o in gs.ordnance)
check(len(ids) == 2 and sum(i.startswith("old") for i in ids) == 2,
      f"excess removed; the fleet is at its 2 bays, no room for a new one: {ids}")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
