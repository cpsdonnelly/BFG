"""The Planet Killer's Armageddon Gun from the real Fire dialog: it sweeps 90cm
straight ahead whatever target is picked, and needs Reload Ordnance after."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: False
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src import combat_panel
from src.combat_dialog import _FireDialog
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
combat_panel.messagebox = messagebox
GUN = {"name": "Armageddon Gun", "weapon_type": "armageddon_gun", "range_cm": 90,
       "strength": 0, "arcs": ["front"]}
def ship(id, x, y, player, **kw):
    b = dict(id=id, name=id, ship_class="T", faction="chaos", player=player, ship_type="cruiser",
             base_size="small", x=x, y=y, heading=0.0, speed=20, turn_angle=45, shields_max=0,
             armor_prow="5+", armor_side="5+", turrets=2, hits_max=8, leadership=8, weapons=[],
             special_rules=[], upgrades=[], critical_damage=[], points_value=180)
    b.update(kw); return Ship(**b)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(ship("pk", 20.0, 60.0, 1, hits_max=14, weapons=[GUN], base_size="large"))
gs.add_ship(ship("t", 60.0, 60.0, 2))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
enemies = [s for s in gs.get_ships() if s.player == 2]
dlg = _FireDialog(panel.combat, gs.get_ship_by_id("pk"), enemies, None, False, False,
                  gs.get_blast_markers(), [(0, GUN)])
dlg.run(); root.update()
opts = dlg.target_options_per_weapon[0]
dlg.weapon_assignments[0][3].set(opts[0])
dlg._fire_all(); root.update()
hit = gs.get_ship_by_id("t").hits_remaining < 8
spent = "armageddon_spent" in gs.get_ship_by_id("pk").special_rules
print("target hit:", hit, "| gun spent:", spent)
print("RESULT:", "OK" if hit and spent else "FAIL")
root.destroy()
sys.exit(0 if hit and spent else 1)
