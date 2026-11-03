"""Drive the real Tkinter game panel to verify the end-phase and Load fixes."""
import os
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox, filedialog

sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())   # keep autosave/snapshot dirs out of the repo

from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel

# Never block on modal dialogs during the check
for name in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, name, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: True


def ship(id, player, x):
    return Ship(id=id, name=id, ship_class="Test", faction="imperial_navy_gothic",
                player=player, ship_type="cruiser", base_size="small",
                x=x, y=60.0, heading=0.0, speed=20, turn_angle=45,
                shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=7, weapons=[], special_rules=[],
                upgrades=[], critical_damage=[])


def build():
    root = tk.Tk()
    gs = GameState()
    gs.dice_mode = "auto"
    gs.ai_player = 2
    gs.add_ship(ship("p1", 1, 20.0))
    gs.add_ship(ship("p2", 2, 100.0))
    dice = DiceRoller(mode="auto")
    tc = TurnController(gs, dice)
    tc.start_game()
    board = BoardView(root, gs)
    frame = tk.Frame(board.side_panel)
    frame.pack()
    panel = GamePanel(frame, tc, board, root)
    return root, gs, tc, board, panel


def pump(root, ms):
    end = [False]
    root.after(ms, lambda: end.__setitem__(0, True))
    while not end[0]:
        root.update()


failures = []

# ── 1. AI end phase resolves exactly once ────────────────────────────────────
root, gs, tc, board, panel = build()
counts = {"auto": 0, "interactive": 0}
orig_auto = panel._resolve_end_phase_auto
orig_inter = panel._resolve_end_phase_interactive
panel._resolve_end_phase_auto = lambda ai: (counts.__setitem__("auto", counts["auto"] + 1), orig_auto(ai))
panel._resolve_end_phase_interactive = lambda: (counts.__setitem__("interactive", counts["interactive"] + 1), orig_inter())

gs.active_player = 2
gs.current_phase = "end"
panel._schedule_ai_phase(0)
pump(root, 1500)
print(f"[end phase] auto={counts['auto']} interactive={counts['interactive']} "
      f"-> now turn {gs.turn_number} {gs.current_phase} player {gs.active_player}")
if (counts["auto"], counts["interactive"]) != (1, 0):
    failures.append("AI end phase did not resolve exactly once")

# Human End Phase button still resolves the end phase interactively
counts.update(auto=0, interactive=0)
gs.active_player = 1
gs.current_phase = "end"
panel._end_phase()
print(f"[human end phase] interactive={counts['interactive']}")
if counts["interactive"] != 1:
    failures.append("Human end phase no longer resolves")
root.destroy()

# ── 2. Load Game updates the state the engine plays on ───────────────────────
for path_name in ("panel button", "board File menu"):
    root, gs, tc, board, panel = build()
    save_dir = tempfile.mkdtemp()
    gs.turn_number = 9
    gs.current_phase = "shooting"
    gs.save(save_dir)

    gs.turn_number = 2
    gs.current_phase = "movement"
    gs.ships = gs.ships[:1]        # pretend the live game diverged
    tc.ships_moved.append("p1")

    filedialog.askdirectory = lambda **k: save_dir
    (panel._load_game if path_name == "panel button" else board._load_game)()
    pump(root, 200)

    same_obj = panel.ctx.gs is gs and tc.gs is gs and board.gs is gs
    ok = (same_obj and gs.turn_number == 9 and gs.current_phase == "shooting"
          and len(gs.ships) == 2 and tc.ships_moved == [])
    print(f"[load via {path_name}] turn={gs.turn_number} phase={gs.current_phase} "
          f"ships={len(gs.ships)} shared_refs={same_obj} ships_moved={tc.ships_moved} "
          f"-> {'OK' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"Load via {path_name}")
    root.destroy()

print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
