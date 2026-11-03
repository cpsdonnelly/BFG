import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, BlastMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.geometry import BLAST_MARKER_RADIUS_CM
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
class Dice:
    mode = "auto"
    def roll_d6(self, n, label=""): return [1] * n          # AAF bonus 4D6 = 4; shield tests 1
    def roll_2d6(self, label=""): return 2
    def roll_d3(self, label=""): return 1
def ship(id, x, y, **kw):
    b = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=1, ship_type="cruiser",
             base_size="small", x=x, y=y, heading=0.0, speed=20, turn_angle=45, shields_max=2, armor_prow="6+",
             armor_side="5+", turrets=2, hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[],
             critical_damage=[]); b.update(kw); return Ship(**b)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
a = ship("a", 20.0, 60.0, special_order="all_ahead_full")
gs.add_ship(a); gs.add_ship(ship("enemy", 110.0, 110.0, player=2))
gs.add_blast_marker(BlastMarker(id="bm", x=20.0 + 22.0 + BLAST_MARKER_RADIUS_CM + a.base_radius, y=60.0))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); tc.current = None
gs.current_phase = "movement"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(frame := f, tc, board, root) if False else GamePanel(f, tc, board, root)
panel.ctx.dice = Dice(); panel.movement.ctx.dice = panel.ctx.dice
panel._update_phase_display()
panel.movement._min_move_all_ships()
a = gs.get_ship_by_id("a")
print(f"AAF ship moved {a.distance_moved_this_turn:.1f}cm to x={a.x:.1f}; locked={'a' in tc.ships_moved}")
print("RESULT:", "OK" if abs(a.distance_moved_this_turn - 22.0) < 0.05 and "a" in tc.ships_moved else "FAIL")
