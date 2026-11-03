import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.movement import MoveCommand
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
def build():
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(Ship(id="a", name="mover", ship_class="T", faction="imperial_navy_gothic", player=1,
                     ship_type="cruiser", base_size="small", x=20.0, y=60.0, heading=0.0, speed=20,
                     turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=1,
                     hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[],
                     critical_damage=[]))
    gs.add_ship(Ship(id="e", name="enemy", ship_class="T", faction="chaos", player=2,
                     ship_type="cruiser", base_size="small", x=110.0, y=110.0, heading=180.0,
                     speed=20, turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                     turrets=2, hits_max=8, leadership=7, weapons=[], special_rules=[],
                     upgrades=[], critical_damage=[]))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    tc.begin_phase("movement")
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    return root, gs, panel, board
print("1. Ship drags through an enemy torpedo salvo: the salvo attacks it (prow armour)")
root, gs, panel, board = build()
gs.add_ordnance(OrdnanceMarker(id="t", ordnance_type="torpedo_standard", owner_player=2,
                               launched_by="e", x=30.0, y=60.0, heading=180.0, strength=3,
                               speed=30.0, launched_turn=0))
rolls = [1,          # mover's single turret vs the salvo
         6, 6, 1]    # vs prow 6+: two hits
dice = Dice(rolls + [1] * 6); panel.ctx.dice = dice
board.commit_drag_fn(gs.get_ship_by_id("a"), [MoveCommand("forward", 20)])
a = gs.get_ship_by_id("a")
check(a.x == 40.0 and a.hits_remaining == 6, f"moved to x={a.x}, hits {a.hits_remaining}")
check(gs.ordnance and gs.ordnance[0]["strength"] == 1, "salvo goes on with 1 torpedo")
check(a.pending_ordnance_contacts == [], "contact cleared")
root.destroy()
print("2. Ship moves onto an enemy bomber: turrets fire, then the bomber attacks")
root, gs, panel, board = build()
gs.add_ordnance(OrdnanceMarker(id="b", ordnance_type="bomber", owner_player=2,
                               launched_by="e", x=40.0, y=60.0, heading=180.0,
                               speed=20.0, launched_turn=0))
rolls = [1,          # 1 turret misses
         4,          # bomber attacks D6 4 - 1 turret = 3
         5, 5, 1]    # vs 5+: two hits
dice = Dice(rolls + [1] * 6); panel.ctx.dice = dice
board.commit_drag_fn(gs.get_ship_by_id("a"), [MoveCommand("forward", 20)])
a = gs.get_ship_by_id("a")
check(a.hits_remaining == 6 and gs.ordnance == [], f"bombed for 2 (hits {a.hits_remaining}), bomber spent")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
