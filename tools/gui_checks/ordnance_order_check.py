import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
def ship(id, player, x, y):
    return Ship(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=y, heading=90.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=0,
                hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[], critical_damage=[])
def run(active):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(ship("p1ship", 1, 10.0, 10.0)); gs.add_ship(ship("target", 2, 40.0, 50.0))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    gs.active_player = active; gs.current_phase = "ordnance"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    gs.add_ordnance(OrdnanceMarker(id="bomber", ordnance_type="bomber", owner_player=1,
                                   launched_by="p1ship", x=40.0, y=35.0, heading=90.0, speed=20.0,
                                   launched_turn=0, craft_target_id="target"))
    gs.add_ordnance(OrdnanceMarker(id="fighter", ordnance_type="fighter", owner_player=2,
                                   launched_by="target", x=40.0, y=10.0, heading=90.0, speed=30.0,
                                   launched_turn=0, craft_target_id="bomber"))
    dice = Dice([4, 6, 6, 6, 6] + [1] * 10); panel.ctx.dice = dice
    panel.ordnance._resolve_ordnance_movement()
    t = gs.get_ship_by_id("target")
    left = sorted(o["id"] for o in gs.ordnance)
    root.destroy()
    return t.hits_remaining, left
print("1. Player 1's turn: their bomber moves first and bombs before the fighter can reach it")
hits, left = run(1)
check(hits < 8 and "bomber" not in left, f"target damaged (hits {hits}), bomber spent; markers left {left}")
print("2. Player 2's turn: their fighter moves first and intercepts the bomber")
hits, left = run(2)
check(hits == 8 and left == [], f"target untouched (hits {hits}); both craft removed {left}")
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
