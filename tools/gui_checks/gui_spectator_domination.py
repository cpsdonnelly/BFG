"""AI-vs-AI Domination (booklet p.125, To do 7), Imperial Navy against Chaos,
through the real GamePanel until game over: objective points scored at the end
of each player's turn (each AA round), the game ending at 10 points or the turn
limit. Usage: gui_spectator_domination.py [igougo|aa] [layout 1-6]."""
import os
import sys
import tempfile
import time
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
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

system = sys.argv[1] if len(sys.argv) > 1 else "igougo"
mode, phase_order = "bag_adjusted", "shoot_first"
difficulty = "normal"
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
gs.turn_system = system
gs.aa_settings = {"order_mode": mode, "phase_order": phase_order}
from src.ship_catalog import find_ship_class
from src.fleet_loader import roll_starting_leadership
def cat(name, player, i, x, y, sq=""):
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"p{player}_{i}")
    d.update(x=x, y=y, heading=0.0 if player == 1 else 180.0, squadron_id=sq)
    return Ship.from_dict(d)
gs.table_width, gs.table_height = 180.0, 120.0
gs.scenario_mode = "domination"
gs.scenario_attacker = 1
gs.turn_limit = 14
from src import scenarios as sc
layout = int(sys.argv[2]) if len(sys.argv) > 2 else 1
sc.setup_scenario(gs, layout=layout)
zones = {z.player: z for z in sc.deployment_zones(gs)}
imp = ["Lunar Class Cruiser", "Gothic Class Cruiser", "Dominator Class Cruiser",
       "Dauntless Class Light Cruiser"]
chs = ["Slaughter Class Cruiser", "Carnage Class Cruiser", "Murder Class Cruiser",
       "Infidel Class Raider"]
for p, names in ((1, imp), (2, chs)):
    z = zones[p]
    for i, n in enumerate(names):
        # spread along the zone's long side, in its middle
        if z.x_max - z.x_min >= z.y_max - z.y_min:
            x = z.x_min + (z.x_max - z.x_min) * (i + 1) / (len(names) + 1)
            y = (z.y_min + z.y_max) / 2
        else:
            x = (z.x_min + z.x_max) / 2
            y = z.y_min + (z.y_max - z.y_min) * (i + 1) / (len(names) + 1)
        s_ = cat(n, p, i, x, y)
        s_.heading = 90.0 if z.y_max < gs.table_height / 2 else 270.0
        if z.x_max - z.x_min < z.y_max - z.y_min:
            s_.heading = 0.0 if z.x_max < gs.table_width / 2 else 180.0
        gs.update_ship(s_) if gs.get_ship_by_id(s_.id) else gs.add_ship(s_)
dice = DiceRoller(mode=gs.dice_mode)
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
while not panel._game_over and time.time() - start < 240:
    root.update()
    phases_seen.add((gs.turn_number, gs.current_phase))
    time.sleep(0.01)

hp = {s.id: s.hits_remaining for s in gs.get_ships()}
print(f"[domination {system} {layout}] game over={panel._game_over} after {time.time()-start:.1f}s, "
      f"reached turn {gs.turn_number}, phases visited={len(phases_seen)}")
print(f"[domination {system} {layout}] hits remaining: {hp}")
print(f"[domination {system} {layout}] game-over dialogs: {len(game_over)} winner={game_over[0][0] if game_over else None}")
print(f"[domination {system} {layout}] dice popups: {len(popups)}; error dialogs: "
      f"{[d for d in dialogs if d[0] == 'showerror']}")
print(f"[domination {system} {layout}] dice mode after game: {dice.mode}")
aa_log = [l for l in gs.log if "[AA]" in l]
print(f"[domination {system} {layout}] objective points: {sc.points(gs)}; "
      f"result: {game_over[0][1] if game_over else None}")
scored = [l for l in gs.log if "[Domination]" in l]
print(f"[domination {system} {layout}] scoring lines: {len(scored)}")
print(f"[domination {system} {layout}] AA log lines: {len(aa_log)}; phases: "
      f"{sorted({p for _t, p in phases_seen})}")
ok = (panel._game_over and len(game_over) == 1 and len(scored) >= 2 and not popups
      and not [d for d in dialogs if d[0] == "showerror"] and dice.mode == "mixed")
print(f"[domination {system} {layout}] RESULT:", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
