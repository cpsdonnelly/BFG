"""Unpatched AI-vs-AI game through the real GamePanel until game over."""
import os
import sys
import tempfile
import time
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src import game_panel as gp_mod
from src.game_panel import GamePanel

dialogs = []
for name in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, name,
            (lambda n: lambda title, msg="", **k: dialogs.append((n, title, msg)))(name))
messagebox.askyesno = lambda *a, **k: False
gp_mod.messagebox = messagebox

difficulty = sys.argv[1]
WEAPONS = [
    {"name": "Port Battery", "weapon_type": "battery", "strength": 6, "range": 45, "arcs": ["left"]},
    {"name": "Stbd Battery", "weapon_type": "battery", "strength": 6, "range": 45, "arcs": ["right"]},
    {"name": "Prow Lance", "weapon_type": "lance", "strength": 2, "range": 60, "arcs": ["front"]},
]


def ship(id, player, x, y):
    return Ship(id=id, name=id, ship_class="Test", faction="imperial_navy_gothic",
                player=player, ship_type="cruiser", base_size="small",
                x=x, y=y, heading=0.0 if player == 1 else 180.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                turrets=2, hits_max=8, leadership=8, weapons=[dict(w) for w in WEAPONS],
                special_rules=[], upgrades=[], critical_damage=[], points_value=180)


root = tk.Tk()
gs = GameState()
gs.dice_mode = "mixed"          # the default the bug report was about
gs.ai_spectator = True
gs.ai_difficulty = difficulty
gs.turn_limit = 6
from src.fleet_loader import load_fleet_file, fleet_to_ships, roll_starting_leadership
for p, f in ((1, "data/fleets/imperial_navy_demo.json"), (2, "/home/user/BFG/tools/gui_checks/sm_test_fleet.json")):
    for sh in fleet_to_ships(load_fleet_file(f if f.startswith('/') else '/home/user/BFG/' + f), p):
        gs.add_ship(sh)
dice = DiceRoller(mode=gs.dice_mode)
from src.chapter_tactics import apply_fleet_tactics; apply_fleet_tactics(gs)
print('Leadership:', roll_starting_leadership(gs, dice, ai_dice=DiceRoller(mode='auto'))[:3])
tc = TurnController(gs, dice)
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel)
frame.pack()
panel = GamePanel(frame, tc, board, root)

game_over = []
orig_dialog = panel._show_game_over_dialog
panel._show_game_over_dialog = lambda w, **k: (game_over.append((w, k)), orig_dialog(w, **k))

# Count dice popups: in mixed mode each would be a Toplevel window
popups = []
orig_mixed = DiceRoller._mixed_input if hasattr(DiceRoller, "_mixed_input") else None
if orig_mixed:
    DiceRoller._mixed_input = lambda self, *a, **k: (popups.append(1), orig_mixed(self, *a, **k))[1]

panel._begin_turn1()
start = time.time()
phases_seen = set()
while not panel._game_over and time.time() - start < (180 if difficulty == "expert" else 90):
    root.update()
    phases_seen.add((gs.turn_number, gs.current_phase))
    time.sleep(0.01)

hp = {s.id: s.hits_remaining for s in gs.get_ships()}
print(f"[{difficulty}] game over={panel._game_over} after {time.time()-start:.1f}s, "
      f"reached turn {gs.turn_number}, phases visited={len(phases_seen)}")
print(f"[{difficulty}] hits remaining: {hp}")
print(f"[{difficulty}] game-over dialogs: {len(game_over)} winner={game_over[0][0] if game_over else None}")
print(f"[{difficulty}] dice popups: {len(popups)}; error dialogs: "
      f"{[d for d in dialogs if d[0] == 'showerror']}")
print(f"[{difficulty}] dice mode after game: {dice.mode}")
ok = (panel._game_over and len(game_over) == 1 and not popups
      and not [d for d in dialogs if d[0] == "showerror"] and dice.mode == "mixed")
print(f"[{difficulty}] RESULT:", "OK" if ok else "FAIL")
open("/tmp/sm_gamelog.txt", "w").write("\n".join(str(x) for x in gs.log))
sys.exit(0 if ok else 1)
