import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.movement import MoveCommand
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""): out = self.r[self.i:self.i + n]; self.i += n; return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; print("   2D6:", label, "->", v); return v
def esc(i):
    return Ship(id=f"e{i}", name=f"Sword {i}", ship_class="Sword", faction="imperial_navy_gothic", player=1,
                ship_type="escort", base_size="small", x=4.0 + 5 * i, y=60.0, heading=180.0, speed=25,
                turn_angle=90, shields_max=1, armor_prow="5+", armor_side="4+", turrets=2, hits_max=1,
                leadership=7, weapons=[], special_rules=[], upgrades=[], critical_damage=[], squadron_id="sq")
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
for i in range(3): gs.add_ship(esc(i))
gs.add_ship(Ship(id="foe", name="foe", ship_class="T", faction="tau", player=2, ship_type="cruiser",
                 base_size="small", x=110.0, y=110.0, heading=0.0, speed=20, turn_angle=45, shields_max=2,
                 armor_prow="6+", armor_side="5+", turrets=2, hits_max=8, leadership=7, weapons=[],
                 special_rules=[], upgrades=[], critical_damage=[]))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); tc.begin_phase("movement")
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root); panel._update_phase_display()
panel.ctx.dice = Dice([11]); panel.movement.ctx.dice = panel.ctx.dice
board.commit_drag_fn(gs.get_ship_by_id("e0"), [MoveCommand("forward", 12.5)])
st = {s.id: (s.status, s.disengage_failed_this_turn, s.must_disengage) for s in gs.get_ships() if s.player == 1}
print("after drag off table (squadron test failed):", st)
ok = (st["e0"][0] == "disengaged" and st["e1"] == ("active", True, True) and st["e2"] == ("active", True, True))
print("RESULT:", "OK" if ok else "FAIL")
